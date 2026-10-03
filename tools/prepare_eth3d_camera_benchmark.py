"""Freeze real ETH3D photographs and calibration; keep8 withheld images outside input."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image,ImageDraw
from scipy.spatial.transform import Rotation

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.camera import load_observations


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(8<<20),b''):h.update(chunk)
    return h.hexdigest()


def save(path,data):path.write_text(json.dumps(data,indent=2,allow_nan=False))


def read_cameras(path):
    cameras={}
    for line in path.read_text().splitlines():
        if not line or line.startswith('#'):continue
        parts=line.split();ident=int(parts[0]);model=parts[1];W,H=map(int,parts[2:4]);params=list(map(float,parts[4:]));cameras[ident]=dict(model=model,image_size=[W,H],parameters=params)
    return cameras


def read_images(path):
    lines=[line for line in path.read_text().splitlines() if not line.startswith('#')];rows=[]
    for line in lines[::2]:
        p=line.split()
        if not p:continue
        q=np.array(list(map(float,p[1:5])));R=Rotation.from_quat(q[[1,2,3,0]]).as_matrix();t=np.array(list(map(float,p[5:8])))
        T=np.eye(4);T[:3,:3]=R.T;T[:3,3]=-R.T@t
        rows.append(dict(image_id=int(p[0]),camera_id=int(p[8]),name=p[9],T=T))
    return sorted(rows,key=lambda x:x['name'])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    camera_path=next(args.source.rglob('cameras.txt'));image_path=camera_path.with_name('images.txt')
    cameras=read_cameras(camera_path);images=read_images(image_path)
    if len(images)!=44:raise ValueError('Expected official44-photo delivery_area sequence')
    holdout=set(range(4,44,5));mapping=[row for i,row in enumerate(images) if i not in holdout]
    # Canonical Z-up is estimated only from allowed mapping-camera up axes.
    # This is a coordinate gauge, not a claim of gravity/inclinometer accuracy.
    up=-np.mean([r['T'][:3,1] for r in mapping],axis=0);up/=np.linalg.norm(up)
    rotation=Rotation.align_vectors([[0,0,1]],[up])[0].as_matrix();origin=np.mean([r['T'][:3,3] for r in mapping],axis=0)
    G=np.eye(4);G[:3,:3]=rotation;G[:3,3]=-rotation@origin
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);obs=out/'observations';obs.mkdir();(obs/'rgb').mkdir();gt=out/'evaluator';gt.mkdir();(gt/'withheld_rgb').mkdir()
    frames=[];withheld=[];all_rows=[]
    for i,row in enumerate(images):
        c=cameras[row['camera_id']]
        if c['model']!='PINHOLE':raise ValueError('Use the official pre-undistorted PINHOLE archive')
        # COLMAP image names are relative to scene/images, not calibration folder.
        matches=list(args.source.rglob(Path(row['name']).name))
        if len(matches)!=1:raise ValueError('Ambiguous or absent image '+row['name'])
        source=matches[0]
        with Image.open(source) as image:
            if list(image.size)!=c['image_size']:raise ValueError('Decoded size/calibration mismatch')
            W,H=image.size;scale=min(1.,1200/max(W,H));size=(round(W*scale),round(H*scale))
            image=image.convert('RGB').resize(size,Image.Resampling.LANCZOS)
            fit=i not in holdout;index=len(frames) if fit else len(withheld)
            path=(obs/'rgb' if fit else gt/'withheld_rgb')/f'{index:03d}.png';image.save(path)
        fx,fy,cx,cy=c['parameters'];K=np.array([[fx,0,cx],[0,fy,cy],[0,0,1]],float);K[0]*=size[0]/W;K[1]*=size[1]/H
        K_integer=K.copy();K_integer[:2,2]-=.5
        record=dict(input_index=index,frame_id=Path(row['name']).stem,image_id=row['image_id'],source_name=row['name'],
            path=str(path),sha256=sha(path),source_sha256=sha(path),original_sha256=sha(source),original_size=[W,H],image_size=list(size),
            role='reconstruction' if fit else 'heldout',K=K_integer.tolist(),K_raster=K.tolist(),T_world_camera=(G@row['T']).tolist(),
            distortion_model='none',pose_source='ground_truth',evidence=['ETH3D registered reference camera, diagnostic input; no laser geometry/depth exposed'])
        (frames if fit else withheld).append(record);all_rows.append(record)
    save(obs/'frames.json',dict(scene_id='eth3d_delivery_area',kind='real_photograph',frames=frames))
    save(obs/'cameras.json',dict(schema='real2sim.camera-observations/1',units='m',up_axis='Z',camera_frame='opencv',pixel_coordinates='integer_centers',frames=frames))
    config=dict(id='eth3d-delivery-area-camera',mode='multi',workflow_profile='quality_v2',formal_test=True,
        provenance=dict(kind='real_photograph',status='verified',evidence=['Official ETH3D DSLR archive; https://www.eth3d.net/datasets']),
        inputs=[dict(path=f['path'],sha256=f['sha256'],role='reconstruction') for f in frames],
        camera_observations=dict(path=str(obs/'cameras.json'),sha256=sha(obs/'cameras.json'),allow_ground_truth_pose=True),
        stages=dict(preprocess=dict(parameters=dict(max_edge=1200))))
    load_observations(config,[dict(sha256=f['sha256'],image_size=f['image_size']) for f in frames])
    save(obs/'case.json',config);save(gt/'frames.json',dict(frames=all_rows));save(gt/'withheld.json',dict(frames=withheld))
    save(gt/'canonical_from_eth3d.json',dict(matrix=G.tolist(),derivation='Mean allowed camera up and centre only; no GT surface used',up_uncertainty='Camera roll/pitch bias remains, not measured gravity'))
    protocol=dict(status='frozen_before_inference',scene='ETH3D delivery_area high-res training',source='https://www.eth3d.net/datasets',
        photographs=44,mapping_images=36,withheld_images=8,split='sorted filenames; indices4,9,14,19,24,29,34,39 withheld before inference',
        conditions=['RGB','RGB_K','RGB_K_T'],reference_input='Registered reference camera poses only in RGB_K_T; never scored as estimated zero-error poses',
        truth='Independent laser scan evaluation points and official scan-derived depth; heldout photographs hidden from modelling',
        metrics=['observed symmetric surface nearest-neighbour distance','precision/recall/Fscore@1cm/5cm/10cm','rendered optical-Z AbsRel/RMSE/coverage/missing30m penalty','withheld view depth'],
        comparable_to_awsm='Metric definitions and separation of inputs/truth only; different scene, frames, frontend, authoring and budget; no direct leaderboard claim',
        camera_sha256=sha(obs/'cameras.json'),frames_sha256=sha(obs/'frames.json'),calibration_source_sha256=sha(camera_path),pose_source_sha256=sha(image_path),
        model_freeze='All three raw outputs and editable meshes frozen before opening scan/depth values',
        adapter='Same static triangle-patch adapter for all conditions; not a full independent Agent/SOTA comparison')
    save(out/'protocol.json',protocol)
    contact=Image.new('RGB',(1200,800),'#eeeeee');draw=ImageDraw.Draw(contact)
    for j,index in enumerate([0,5,10,15,20,25]):
        f=frames[index];im=Image.open(f['path']);im.thumbnail((400,370));x=(j%3)*400;y=(j//3)*400;contact.paste(im,(x,y+22));draw.text((x+5,y+4),f['frame_id'],fill='black')
    contact.save(obs/'contact.jpg',quality=86)
    print(json.dumps(dict(status='frozen',mapping=len(frames),withheld=len(withheld),camera_contract='passed',output=str(out))))


if __name__=='__main__':main()
