"""Actual single-assembly audit plus review contract; run inside Blender."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import bpy
from mathutils import Vector

repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(repo/'workflow'))
from r2s.structure import file_sha,review_contract

out=Path(sys.argv[sys.argv.index('--')+1]).resolve()
out.mkdir(parents=True,exist_ok=False)
start=time.monotonic()
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
parts=[]
single_part='--single-part' in sys.argv
part_definitions=[('base',(0,0,.2),(.4,.4,.4))]+([] if single_part else [('top',(0,0,.5),(.3,.3,.2))])
for name,position,dimensions in part_definitions:
    bpy.ops.mesh.primitive_cube_add(size=1,location=position)
    obj=bpy.context.object;obj.name=name;obj.dimensions=dimensions
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    obj['entity_id']='cabinet';obj['furniture_id']='cabinet';obj['part_id']=name
    parts.append({'id':name,'object':name})
bpy.ops.object.camera_add(location=(2,-3,2));cam=bpy.context.object
cam.rotation_euler=(Vector((0,0,.3))-cam.location).to_track_quat('-Z','Y').to_euler()
bpy.context.scene.camera=cam;bpy.context.view_layer.update()
cam.data.sensor_width=36;cam.data.sensor_fit='HORIZONTAL';cam.data.lens=200*36/320
rot=cam.matrix_world.to_3x3().transposed();R=[list(rot[0]),list(-rot[1]),list(-rot[2])]
point=Vector((-.2,-.2,0));q=Vector([sum(R[i][j]*(point[j]-cam.location[j]) for j in range(3)) for i in range(3)])
uv=[q.x/q.z*200+160,q.y/q.z*200+120]
assembly={'entity':'cabinet','parts':parts,'source_observation_ids':['synthetic_corner'],
          'frame':{'yaw_rad':0},'joints':[{'parts':['base','top'],'anchor_world':[0,0,.4],'tolerance_m':.002}],
          'floor_supports':[{'part':'base','plane_z':0,'tolerance_m':.002}],
          'fit':{'landmarks':[{'id':'corner','world':list(point),'uv':uv,'part':'base'}]}}
if single_part:assembly['joints']=[]
scene={'model_version':'single_assembly_engine_fixture','objects':[{'id':'cabinet'}],
       'camera':{'position':list(cam.location),'rotation_world_to_cv':R,'focal_px':200,
                 'principal_point':[160,120],'image_size':[320,240]},
       'structure':{'schema':'real2sim.assembly/1','assemblies':[assembly],
                    'acceptance':{'landmark_median_px':1,'landmark_max_px':1},
                    'unexpected_interpenetration_tolerance_m':.002}}
spec=out/'scene.json';spec.write_text(json.dumps(scene));model=out/'model.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(model))
env=dict(os.environ,R2S_CPU='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
env.pop('R2S_STRUCTURE_NO_RENDER',None)
command=[bpy.app.binary_path,'-b',str(model),'-t','2','--python-exit-code','12','--python',
         str(repo/'workflow/r2s/blender_structure.py'),'--',str(spec),str(out)]
with (out/'audit.log').open('w') as log:
    result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
if result.returncode:raise RuntimeError('Actual audit failed; inspect retained audit.log')
audit=json.loads((out/'structural_audit.json').read_text())
binding={'model_sha256':file_sha(model),'scene_sha256':file_sha(spec),
         'structural_audit_sha256':file_sha(out/'structural_audit.json')}
review={'geometry_freeze_sha256':binding['model_sha256'],'model_version':scene['model_version'],
        'per_object':[{'entity':'cabinet','status':'pass','findings':'Synthetic supported assembly',
                       'evidence':['furniture_source_view.png']}],
        'checks':{'support':{'status':'pass','evidence':['structure_cabinet_front.png']}}}
artifacts=[p.name for p in out.iterdir() if p.is_file()]
review_contract(out,review,artifacts,scene,binding)
assert audit['assemblies'][0]['ownership_checked'] and not audit['interassembly_checks']
report={'status':'passed','scope':'Actual synthetic single-assembly Blender audit and review; not empty-room or source reconstruction acceptance',
        'blender_version':bpy.app.version_string,'assembly_count':len(audit['assemblies']),
        'cross_assembly_pair_count':len(audit['interassembly_checks']),
        'within_assembly_pair_count':len(audit['component_pair_checks']),
        'isolated_views':len(audit['assemblies'][0]['isolated_views']),
        'wall_seconds':time.monotonic()-start,'input_hashes':binding,
        'implementation_sha256':file_sha(repo/'workflow/r2s/structure.py')}
report['test_script_sha256']=file_sha(__file__)
report['single_part']=single_part
report['declared_joint_count']=len(assembly['joints'])
report['audited_joint_count']=len(audit['assemblies'][0]['joints_checked'])
(out/'summary.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
