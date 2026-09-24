"""Actual additional MuJoCo loading tests and offscreen demonstration. No keyframes."""
import os
os.environ.setdefault('MUJOCO_GL','egl')
import sys,json,math,subprocess,shutil
from pathlib import Path
from xml.etree import ElementTree as ET
import numpy as np
import mujoco
import cv2
from itertools import combinations
from PIL import Image,ImageDraw
out=Path(sys.argv[1]).resolve();source=out/'scene_dynamic.xml';root=ET.parse(source).getroot();model0=mujoco.MjModel.from_xml_path(str(source));d0=mujoco.MjData(model0);mujoco.mj_forward(model0,d0)
fmt=lambda a:' '.join(f'{float(x):.9g}' for x in np.asarray(a).ravel())
def flexinfo(model,name):
 i=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_FLEX,name);return i,int(model.flex_vertadr[i]),int(model.flex_vertnum[i])
_,cs,cn=flexinfo(model0,'red_garment_cloth');_,ss,sn=flexinfo(model0,'chair_pad_volume');clothcenter=d0.flexvert_xpos[cs:cs+cn].mean(axis=0);seatcenter=d0.flexvert_xpos[ss:ss+sn].mean(axis=0);world=root.find('worldbody')
targets=[('hinge_close',np.array([4.06,-2.25,1.10]),np.array([2.05,-3.70,1.40])),('cloth_close',clothcenter,clothcenter+[.1,-1.0,.16]),('pad_close',seatcenter,seatcenter+[.25,-.35,.25])]
for name,target,eye in targets:
 f=(target-eye);f/=np.linalg.norm(f);right=np.cross(f,[0,0,1]);right/=np.linalg.norm(right);up=np.cross(right,f);ET.SubElement(world,'camera',name=name,pos=fmt(eye),xyaxes=fmt(np.r_[right,up]),fovy='46')
vis=root.find('visual')
if vis is None:vis=ET.SubElement(root,'visual')
ET.SubElement(vis,'global',offwidth='640',offheight='480')
ET.ElementTree(root).write(out/'demo.xml',encoding='unicode',xml_declaration=True)
m=mujoco.MjModel.from_xml_path(str(out/'demo.xml'));d=mujoco.MjData(m);mujoco.mj_forward(m,d);initial=d.flexvert_xpos.copy();_,cs,cn=flexinfo(m,'red_garment_cloth');_,ss,sn=flexinfo(m,'chair_pad_volume');jid=mujoco.mj_name2id(m,mujoco.mjtObj.mjOBJ_JOINT,'right_door_hinge');dof=m.jnt_dofadr[jid]
# Simple simulation visuals are explicitly distinct from the textured Blender reference.
for i in range(m.ngeom):
 name=mujoco.mj_id2name(m,mujoco.mjtObj.mjOBJ_GEOM,i) or ''
 if 'cabinet' in name:m.geom_rgba[i]=[.12,.13,.12,1]
 elif 'table' in name or 'chair_near' in name or 'chair_far' in name or 'rack' in name:m.geom_rgba[i]=[.55,.40,.22,1]
 elif 'floor' in name:m.geom_rgba[i]=[.35,.36,.34,1]
 elif 'coat_' in name:m.geom_rgba[i]=[.06,.08,.075,1]
opt=mujoco.MjvOption();opt.geomgroup[2]=0
if hasattr(mujoco.mjtVisFlag,'mjVIS_FLEXFACE'):opt.flags[mujoco.mjtVisFlag.mjVIS_FLEXFACE]=1
renderer=mujoco.Renderer(m,height=320,width=426);frames=[];trajectory=[];min_contact=0;min_contact_record=None;warnings0=d.warning.number.copy();max_cloth=0;max_pad=0;angle_extrema=[0.,0.];flex_checks=[]
definitions=json.loads((out/'scene.json').read_text())['dynamics']['deformables']
for definition in definitions:
 _,start,count=flexinfo(m,definition['id']);elems=np.array(definition['elements'],int);edges=np.array(sorted({tuple(sorted(pair)) for elem in elems for pair in combinations(elem,2)}));v=initial[start:start+count];lengths=np.linalg.norm(v[edges[:,0]]-v[edges[:,1]],axis=1);check=dict(id=definition['id'],kind=definition['kind'],start=start,count=count,elements=elems,edges=edges,rest_lengths=lengths,max_strain=0.,min_volume_ratio=1.,allowed_strain=definition['maximum_allowed_edge_strain'])
 if definition['kind']=='soft_body':
  t=v[elems];check['rest_volume']=np.linalg.det(np.stack([t[:,1]-t[:,0],t[:,2]-t[:,0],t[:,3]-t[:,0]],axis=2))/6
 flex_checks.append(check)
soft_top=initial[ss:ss+sn,2]>initial[ss:ss+sn,2].max()-.001;top_ids=np.flatnonzero(soft_top)+ss
cloth_ids=[i for i in range(cs,cs+cn) if m.body_dofnum[m.flex_vertbodyid[i]]>0]
for step in range(4000):
 t=float(d.time);d.qfrc_applied[:]=0;d.xfrc_applied[:]=0;d.qfrc_applied[dof]=8 if t<1.3 else 0
 wind=.12*math.sin(math.pi*min(t/.7,1)) if t<.7 else 0
 for vi in cloth_ids:d.xfrc_applied[m.flex_vertbodyid[vi],1]-=wind/max(1,len(cloth_ids))
 load=300*min(t/.35,1) if t<.8 else 300*max(0,1-(t-.8)/.35)
 for vi in top_ids:d.xfrc_applied[m.flex_vertbodyid[vi],2]-=load/len(top_ids)
 mujoco.mj_step(m,d)
 if not np.isfinite(d.qpos).all():raise RuntimeError('Nonfinite numerical state')
 q_now=float(d.qpos[m.jnt_qposadr[jid]]);angle_extrema=[min(angle_extrema[0],q_now),max(angle_extrema[1],q_now)]
 if q_now<float(m.jnt_range[jid,0])-.04 or q_now>float(m.jnt_range[jid,1])+.04:raise RuntimeError('Hinge escaped its numerical limit tolerance')
 for i in range(d.ncon):
  c=d.contact[i]
  if c.dist<min_contact:
   min_contact=float(c.dist);min_contact_record=dict(time=float(d.time),distance_m=min_contact,geoms=[mujoco.mj_id2name(m,mujoco.mjtObj.mjOBJ_GEOM,int(g)) if int(g)>=0 else 'flex' for g in c.geom],flex_ids=list(map(int,c.flex)) if hasattr(c,'flex') else [])
 if step%1000==0:print('loading test step',step,'time',d.time,flush=True)
 if step%50==0:
  for check in flex_checks:
   v=d.flexvert_xpos[check['start']:check['start']+check['count']];e=check['edges'];strain=float(np.max(abs(np.linalg.norm(v[e[:,0]]-v[e[:,1]],axis=1)/check['rest_lengths']-1)));check['max_strain']=max(check['max_strain'],strain)
   if strain>check['allowed_strain']:raise RuntimeError('Loading test exceeded declared strain bound: '+check['id'])
   if 'rest_volume' in check:
    t=v[check['elements']];volume=np.linalg.det(np.stack([t[:,1]-t[:,0],t[:,2]-t[:,0],t[:,3]-t[:,0]],axis=2))/6;ratio=float(np.min(volume/check['rest_volume']));check['min_volume_ratio']=min(check['min_volume_ratio'],ratio)
    if ratio<=.05:raise RuntimeError('Loaded tetrahedra collapsed or inverted')
  cd=float(np.max(np.linalg.norm(d.flexvert_xpos[cs:cs+cn]-initial[cs:cs+cn],axis=1)));pd=float(np.max(np.linalg.norm(d.flexvert_xpos[ss:ss+sn]-initial[ss:ss+sn],axis=1)));max_cloth=max(max_cloth,cd);max_pad=max(max_pad,pd);q=float(d.qpos[m.jnt_qposadr[jid]]);trajectory.append(dict(time=float(d.time),hinge_rad=q,cloth_displacement_m=cd,pad_displacement_m=pd,pad_load_N=load,qpos=d.qpos.copy().tolist(),flexvert=d.flexvert_xpos.copy().tolist()))
  canvas=Image.new('RGB',(1278,372),(245,245,240));draw=ImageDraw.Draw(canvas)
  for k,(camera,_,_) in enumerate(targets):
   renderer.update_scene(d,camera=camera,scene_option=opt);rgb=renderer.render();canvas.paste(Image.fromarray(rgb),(426*k,34))
  for k,title in enumerate(['HINGE / actual torque response','CLOTH / shoulder pins + gentle wind','VOLUME / tetrahedral chair pad']):draw.text((426*k+8,9),title,fill=(10,10,10))
  draw.text((8,355),f'Numerical time {d.time:.3f}s | door {q*180/math.pi:.1f} deg | cloth max {cd*1000:.1f} mm | pad max {pd*1000:.2f} mm | pad load {load:.0f} N | assumed parameters',fill=(10,10,10));frames.append(np.asarray(canvas))
warnings=(d.warning.number-warnings0).tolist();renderer.close()
(out/'loading_observations.json').write_text(json.dumps(dict(status='observations_before_acceptance_gate',hinge_range=angle_extrema,contact=min_contact_record,warnings=warnings,maximum_sampled_cloth_displacement_m=max_cloth,maximum_sampled_pad_displacement_m=max_pad,deformation=[dict(id=c['id'],max_strain=c['max_strain'],min_volume_ratio=c['min_volume_ratio']) for c in flex_checks]),indent=2))
if any(warnings):raise RuntimeError('Solver warnings in loading test: '+str(warnings))
if min_contact<-.005:raise RuntimeError('Excessive penetration in loading test: '+str(min_contact))
angles=angle_extrema;limit_reached=max(angles)>=float(m.jnt_range[jid,1])-.015
if not limit_reached:raise RuntimeError('Hinge loading test did not exercise its upper limit')
if max(angles)>float(m.jnt_range[jid,1])+.04 or min(angles)<float(m.jnt_range[jid,0])-.04:raise RuntimeError('Hinge violated the declared numerical limit tolerance')
report=dict(status='passed',engine='MuJoCo',version=mujoco.__version__,steps=4000,timestep_s=float(m.opt.timestep),actual_duration_s=float(d.time),hinge_observed_range_rad=[min(angles),max(angles)],upper_limit_exercised=limit_reached,max_cloth_displacement_m=max_cloth,max_pad_displacement_m=max_pad,minimum_contact_distance_m=min_contact,allowed_penetration_m=.005,solver_warnings=warnings,physical_parameters='assumed, not measured',load_description='0-300N distributed on cushion top then released; <=0.12N total gentle wind on unpinned garment vertices; 8Nm hinge torque for 1.3s',geometry_exaggeration=False,video='dynamics_demo.mp4',reference_pose_preserved_in_separate_static_files=True)
report['deformation_checks']=[dict(id=c['id'],maximum_sampled_edge_strain=c['max_strain'],minimum_sampled_volume_ratio=c['min_volume_ratio'] if c['kind']=='soft_body' else None) for c in flex_checks];report['deformation_sample_interval_s']=50*float(m.opt.timestep);report['contacts_limits_warnings_checked_every_step']=True;report['video_playback_speed_vs_physical_time']=.75
(out/'loading_test_audit.json').write_text(json.dumps(report,indent=2));(out/'loading_trajectory.json').write_text(json.dumps(trajectory));Image.fromarray(frames[0]).save(out/'dynamics_start.png');Image.fromarray(frames[len(frames)//2]).save(out/'dynamics_mid.png');Image.fromarray(frames[-1]).save(out/'dynamics_end.png')
raw=out/'dynamics_demo_raw.mp4';writer=cv2.VideoWriter(str(raw),cv2.VideoWriter_fourcc(*'mp4v'),30,(1278,372))
for frame in frames:writer.write(cv2.cvtColor(frame,cv2.COLOR_RGB2BGR))
writer.release();ffmpeg=shutil.which('ffmpeg')
if ffmpeg:subprocess.run([ffmpeg,'-y','-i',str(raw),'-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(out/'dynamics_demo.mp4')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
else:shutil.copyfile(raw,out/'dynamics_demo.mp4')
print(json.dumps(report,indent=2))
