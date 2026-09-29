"""Fixed five-group endpoint comparison; no candidate selection or source mutation."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
import numpy as np
from PIL import Image

repo=Path(__file__).resolve().parents[1]
root=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();out.mkdir(parents=True,exist_ok=False)
blender=sys.argv[3];protocol=json.loads((repo/'docs/research/COMBINED_PROTOCOL_20260929.json').read_text())
groups={
 'unchanged_baseline':(Path('/home/wqz/real2sim_whole_scene_20260926/delivery_candidate/export/scene.blend'),root/'combined_comparison_001/baseline/render.png',root/'room_geometry_baseline_001/report.json'),
 'render_only_round2':(root/'pilot_ab_001/control/round2/model.blend',root/'combined_comparison_001/control/render.png',root/'pilot_ab_001/control/round2/evaluation/report.json'),
 'numeric_feedback_round2':(root/'pilot_ab_001/feedback/round2/model.blend',root/'combined_comparison_001/feedback/render.png',root/'pilot_ab_001/feedback/round2/evaluation/report.json'),
 'appearance_only':(root/'appearance_001/model.blend',root/'appearance_001/ordinary_render.png',root/'appearance_001/evaluation/report.json'),
 'combined':(root/'combined_001/model.blend',root/'combined_001/ordinary_render.png',root/'combined_001/evaluation/report.json')}
assert list(groups)==protocol['expected_candidate_groups']
source=Image.open('/home/wqz/real2sim_whole_scene_20260926/input/01_bedroom.jpg').convert('RGB').resize((851,638),Image.Resampling.LANCZOS)
source=np.asarray(source,float)/255
room=json.loads((repo/'examples/independent_whole_scene_20260926/authoring/room.json').read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def linear(x):return np.where(x<=.04045,x/12.92,((x+.055)/1.055)**2.4)
rows=[]
reference_render=json.loads((root/'combined_comparison_001/baseline/receipt.json').read_text())
for name,(model,image,geometry) in groups.items():
    row={'group':name,'status':'failed'};rows.append(row);t=time.monotonic()
    directory=out/name;directory.mkdir()
    try:
        row['model_sha256']=sha(model);row['image_sha256']=sha(image)
        if name in {'appearance_only','combined'}:
            action=json.loads(model.with_name('actions.json').read_text());settings=action['render_settings'];camera=np.array(action['camera']['matrix_world']).reshape(4,4)
        else:
            settings=json.loads(image.with_name('receipt.json').read_text());camera=np.array(settings['camera_matrix'])
        assert settings['samples']==8 and settings['seed']==0 and settings['adaptive_sampling'] is False
        assert settings['view_transform']==reference_render['view_transform'] and settings['exposure']==reference_render['exposure']
        assert np.allclose(camera,reference_render['camera_matrix'],atol=1e-6,rtol=0)
        row['matched_camera_and_render_settings']=True
        image_data=np.asarray(Image.open(image).convert('RGB'),float)/255;assert image_data.shape==source.shape
        metrics={}
        for region,bounds in protocol['appearance_regions_xyxy'].items():
            x0,y0,x1,y1=[int(v/2) for v in bounds];a=source[y0:y1,x0:x1];b=image_data[y0:y1,x0:x1]
            ya=linear(a)@np.array([.2126,.7152,.0722]);yb=linear(b)@np.array([.2126,.7152,.0722])
            metrics[region]={'rgb_mae':float(np.mean(abs(a-b))), 'mean_absolute_log_luminance_ratio':float(np.mean(abs(np.log((yb+1e-4)/(ya+1e-4)))))}
        row['appearance']=metrics;row['geometry']=json.loads(geometry.read_text())['summary']
        scene=json.loads(model.with_name('scene.json').read_text());w=room['window']
        scene['room']['openings']=[{'wall':'wall_left','bounds':[w['y0'],w['y1'],w['bottom'],w['top']]}]
        (directory/'scene.json').write_text(json.dumps(scene,indent=2))
        env=dict(os.environ,R2S_CPU='1',CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
        # Apply the same metadata measurement to every group. Historical JSON may
        # predate serializer/mesh-cleanup effects; never count its repair as an arm gain.
        with (directory/'metadata.log').open('w') as log:
            result=subprocess.run([blender,'-b',str(model),'-t','2','--python-exit-code','12','-P',str(repo/'workflow/r2s/blender_metadata.py'),'--',str(directory/'scene.json'),'update',str(directory/'metadata_sync.json')],stdout=log,stderr=log,env=env,timeout=300)
        row['metadata_returncode']=result.returncode
        if result.returncode:raise RuntimeError('Derived metadata sync failed')
        row['metadata_sync']=json.loads((directory/'metadata_sync.json').read_text())
        with (directory/'export.log').open('w') as log:
            result=subprocess.run([blender,'-b',str(model),'-t','2','--python-exit-code','12','-P',str(repo/'workflow/r2s/blender_export.py'),'--',str(directory/'scene.json'),str(directory),'--geometry-only'],stdout=log,stderr=log,env=env,timeout=300)
        row['geometry_export_returncode']=result.returncode
        if result.returncode:raise RuntimeError('Geometry export failed; see retained log')
        with (directory/'simulation.log').open('w') as log:
            result=subprocess.run([sys.executable,str(repo/'workflow/r2s/simulation.py'),str(directory/'scene.json'),str(directory)],stdout=log,stderr=log,env=env,timeout=300)
        row['static_returncode']=result.returncode
        if result.returncode:raise RuntimeError('Static simulation check failed; see retained log')
        row['static_audit']=json.loads((directory/'simulation_audit.json').read_text())
        assert sha(model)==row['model_sha256'];row['input_unchanged']=True;row['status']='evaluated'
    except Exception as error:row['error']=repr(error)
    row['wall_seconds']=time.monotonic()-t
report={'schema':'real2sim.combined-comparison/1','expected_groups':5,'groups':rows,
        'metadata_policy':'Same evaluated-geometry metadata synchronization for all five groups; source model and JSON unchanged',
        'protocol_sha256':sha(repo/'docs/research/COMBINED_PROTOCOL_20260929.json'),'script_sha256':sha(__file__),
        'scope':'One in-sample room, component and combination diagnostics; not independent visual accuracy or SOTA'}
(out/'comparison.json').write_text(json.dumps(report,indent=2,allow_nan=False))
print(json.dumps([{k:r.get(k) for k in ['group','status','error','appearance','geometry']} for r in rows],indent=2))
