"""CPU-only connected SfM initializer on an immutable frame set."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def worker(scene_file,protocol_file,out):
    import pycolmap
    import numpy as np
    scene=json.loads(scene_file.read_text());protocol=json.loads(protocol_file.read_text())
    if pycolmap.__version__!='4.2.0':raise ValueError('Requires frozen pycolmap 4.2.0')
    images=out/'images';images.mkdir()
    for i,frame in enumerate(scene['frames']):
        path=Path(frame['path'])
        if sha(path)!=frame['sha256']:raise ValueError('Frozen frame changed')
        shutil.copyfile(path,images/f'frame_{i:04d}.png')
        if sha(images/f'frame_{i:04d}.png')!=frame['sha256']:raise ValueError('Frame changed while copying')
    reader=pycolmap.ImageReaderOptions(camera_model=protocol['camera_model'],default_focal_length_factor=protocol['default_focal_length_factor'])
    extraction=pycolmap.FeatureExtractionOptions(num_threads=2,use_gpu=False)
    extraction.sift.max_num_features=protocol['max_num_features']
    extraction.sift.peak_threshold=protocol.get('sift_peak_threshold',extraction.sift.peak_threshold)
    matching=pycolmap.FeatureMatchingOptions(num_threads=2,use_gpu=False)
    verification=pycolmap.TwoViewGeometryOptions()
    verification.ransac.random_seed=protocol.get('verification_random_seed',-1)
    pipeline=pycolmap.IncrementalPipelineOptions(num_threads=2,random_seed=protocol['random_seed'],
        multiple_models=False,min_model_size=3,max_runtime_seconds=protocol['max_runtime_seconds_per_scene'])
    pipeline.mapper.num_threads=2;pipeline.mapper.random_seed=protocol['random_seed']
    pipeline.structure_less_registration_fallback=False
    pipeline.triangulation.random_seed=protocol['random_seed'];pipeline.ba_use_gpu=False
    effective={'reader':reader.todict(),'extraction':extraction.todict(),'matching':matching.todict(),'verification':verification.todict(),'pipeline':pipeline.todict()}
    (out/'effective_options.json').write_text(json.dumps(effective,indent=2,default=str))
    database=out/'database.db'
    pycolmap.extract_features(database,images,camera_mode=pycolmap.CameraMode.SINGLE,reader_options=reader,
                              extraction_options=extraction,device=pycolmap.Device.cpu)
    pycolmap.match_exhaustive(database,matching_options=matching,verification_options=verification,device=pycolmap.Device.cpu)
    models=out/'models';models.mkdir()
    maps=pycolmap.incremental_mapping(database,images,models,options=pipeline)
    report={'expected_frames':len(scene['frames']),'registered_frames':0,'cameras':[],
            'coordinate_system':protocol['coordinate_policy'],'pycolmap_version':pycolmap.__version__,
            'physical_scale_m_per_unit':None,'gravity_alignment':None}
    if len(maps)>1:raise ValueError('Unexpected multiple models; no best-model selection allowed')
    if maps:
        rec=next(iter(maps.values()));rec.write_text(out/'models')
        for image_id in sorted(rec.reg_image_ids()):
            image=rec.images[image_id];camera=rec.cameras[image.camera_id];pose=image.cam_from_world()
            rotation=pose.rotation.matrix();center=-rotation.T@pose.translation
            report['cameras'].append({'frame_name':image.name,'position_in_sfm_gauge':center.tolist(),
                'rotation_world_to_cv':rotation.tolist(),'focal_px':float(camera.params[0]),
                'principal_point':camera.params[1:3].tolist(),'image_size':[camera.width,camera.height]})
        report.update(registered_frames=len(report['cameras']),point_count=rec.num_points3D(),
                      mean_fit_reprojection_error_px=rec.compute_mean_reprojection_error())
    registered={camera['frame_name'] for camera in report['cameras']}
    report['missing_frames']=[f'frame_{i:04d}.png' for i in range(len(scene['frames'])) if f'frame_{i:04d}.png' not in registered]
    report['status']='initialized' if not report['missing_frames'] and report.get('point_count',0)>=protocol['minimum_points3d'] else 'incomplete'
    with sqlite3.connect(database) as connection:
        report['keypoints']=[{'image_id':i,'count':count,'data_sha256':hashlib.sha256(data).hexdigest()}
            for i,count,data in connection.execute('select image_id,rows,data from keypoints order by image_id')]
    (out/'cameras.json').write_text(json.dumps(report,indent=2,allow_nan=False))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frames',type=Path)
    parser.add_argument('--protocol',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--worker-scene',type=Path)
    args=parser.parse_args()
    if args.worker_scene:return worker(args.worker_scene,args.protocol,args.output)
    frames=json.loads(args.frames.read_text());protocol=json.loads(args.protocol.read_text())
    scenes=frames['sources']
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);rows=[];start=time.monotonic()
    snapshots={}
    for name,original in [('protocol.json',args.protocol),('frames.json',args.frames),('initializer_snapshot.py',Path(__file__))]:
        target=out/name;shutil.copyfile(original,target);snapshots[name]=sha(target)
    protocol_file=out/'protocol.json';protocol=json.loads(protocol_file.read_text())
    frames=json.loads((out/'frames.json').read_text());scenes=frames['sources']
    ids=[scene.get('id') for scene in scenes]
    identity_ok=(frames.get('status')=='frozen' and frames.get('cohort_id')==protocol['cohort']
                 and len(ids)==protocol['expected_scene_count'] and all(isinstance(i,str) and i for i in ids)
                 and len(set(ids))==len(ids))
    for index in range(protocol['expected_scene_count']):
        scene=scenes[index] if index<len(scenes) else {'id':None,'status':'failed'}
        directory=out/f'source_{index:03d}';row={'id':scene.get('id'),'status':'failed','directory':str(directory)};rows.append(row)
        t=time.monotonic()
        try:
            directory.mkdir()
            if not identity_ok:raise ValueError('Cohort, global frame status or unique scene identity invalid')
            if scene['status']!='frozen' or len(scene['selected_frames'])!=protocol['expected_frames_per_scene']:raise ValueError('Frame preparation incomplete')
            scene=dict(scene,frames=scene['selected_frames'])
            scene_file=directory/'input.json';scene_file.write_text(json.dumps(scene,indent=2))
            command=[sys.executable,str(out/'initializer_snapshot.py'),'--worker-scene',str(scene_file),
                     '--protocol',str(protocol_file),'--output',str(directory)]
            with (directory/'process.log').open('w') as log:
                proc=subprocess.run(command,stdout=log,stderr=log,timeout=protocol['max_runtime_seconds_per_scene'],
                                    env=dict(os.environ,OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',CUDA_VISIBLE_DEVICES=''))
            row['returncode']=proc.returncode
            if proc.returncode:raise RuntimeError('Initializer failed; see retained process.log')
            row['result']=json.loads((directory/'cameras.json').read_text());row['status']=row['result']['status']
        except Exception as error:row['error']=type(error).__name__+': '+str(error)
        row['wall_seconds']=time.monotonic()-t
    original_inputs_unchanged=(args.protocol.is_file() and args.frames.is_file()
        and sha(args.protocol)==snapshots['protocol.json'] and sha(args.frames)==snapshots['frames.json'])
    if not original_inputs_unchanged:
        for row in rows:
            row['initialization_status_before_source_drift']=row['status'];row['status']='failed';row['error']='Source protocol or frame receipt changed during execution'
    report={'schema':'real2sim.sfm-initialization/1','expected_scene_count':protocol['expected_scene_count'],
            'initialized_scene_count':sum(row['status']=='initialized' for row in rows),'sources':rows,
            'protocol_sha256':snapshots['protocol.json'],'frames_receipt_sha256':snapshots['frames.json'],
            'script_sha256':snapshots['initializer_snapshot.py'],'snapshots':snapshots,
            'original_inputs_unchanged':original_inputs_unchanged,'wall_seconds':time.monotonic()-start,'gpu_hours':0,
            'scope':'Shared estimated cameras, not an agent A/B, measured geometry or SOTA'}
    (out/'receipt.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2))
    return 0 if report['initialized_scene_count']==report['expected_scene_count'] else 1

if __name__=='__main__':sys.exit(main())
