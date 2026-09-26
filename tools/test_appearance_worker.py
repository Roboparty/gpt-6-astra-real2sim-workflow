"""Run the real executable build_render path on a tiny synthetic room.

Usage: R2S_BLENDER=/path/to/blender python tools/test_appearance_worker.py
This verifies integration and rejection, not reconstruction quality.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workflow'))
from r2s.media import file_hash
from r2s.core import atomic_json

blender=os.environ['R2S_BLENDER']
env={**os.environ,'PYTHONPATH':str(ROOT/'workflow'),'R2S_CPU':'1','CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'}

with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp); source=p/'source';source.mkdir()
    fixture=source/'build.py'
    fixture.write_text('''import bpy,json,sys
from pathlib import Path
from mathutils import Vector
p=Path(sys.argv[sys.argv.index('--')+1]);sc=bpy.context.scene
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
mat=bpy.data.materials.new('white');mat.use_nodes=True;mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.8
objects=[]
for name,pos,size in [('floor',(0,0,-.05),(4,4,.1)),('ceiling',(0,0,3.05),(4,4,.1)),('wall_front',(0,-2,1.5),(4,.1,3)),('wall_back',(0,2,1.5),(4,.1,3)),('wall_left',(-2,0,1.5),(.1,4,3)),('wall_right',(2,0,1.5),(.1,4,3)),('lamp',(0,0,2.8),(.3,.3,.1))]:
 bpy.ops.mesh.primitive_cube_add(size=1,location=pos);o=bpy.context.object;o.name=name;o.dimensions=size;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o['entity_id']=name;o.data.materials.append(mat)
 objects.append(dict(id=name,kind='lamp' if name=='lamp' else 'room_surface',position=list(pos),dimensions=list(size),evidence=['synthetic test fixture'],confidence=1))
bpy.ops.object.light_add(type='AREA',location=(0,0,2.7));bpy.context.object.data.energy=100
bpy.ops.object.camera_add(location=(1,-1,1.5));cam=bpy.context.object;cam.rotation_euler=(Vector((0,1,1))-cam.location).to_track_quat('-Z','Y').to_euler();sc.camera=cam;bpy.context.view_layer.update()
r=cam.matrix_world.to_3x3().transposed();R=[list(r[0]),list(-r[1]),list(-r[2])]
scene=dict(schema_version='real2sim.scene/1.0',units='m',up_axis='Z',model_version=1,branch='A',objects=objects,room=dict(x_min=-2,x_max=2,y_min=-2,y_max=2,height=3,thickness=.1,preserve_full_shell=True),camera=dict(position=list(cam.location),rotation_world_to_cv=R,focal_px=100,principal_point=[80,60],image_size=[160,120]))
(p/'scene.json').write_text(json.dumps(scene));sc.render.engine='CYCLES';sc.cycles.samples=1;sc.render.resolution_percentage=10
bpy.ops.wm.save_as_mainfile(filepath=str(p/'model.blend'))
mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.2
bpy.ops.wm.save_as_mainfile(filepath=str(p/'changed.blend'))
''')
    def run(argv,cwd=p):
        result=subprocess.run(argv,cwd=cwd,env=env,capture_output=True,text=True)
        if result.returncode:
            logs='\n'.join(log.read_text()[-2500:] for log in p.rglob('*subprocess.log'))
            raise AssertionError(result.stdout[-2500:]+'\n'+result.stderr[-2500:]+'\n'+logs)
        return result
    run([blender,'-b','-t','2','--python-exit-code','12','--python',str(fixture),'--',str(source)])
    Image.new('RGB',(160,120),'white').save(source/'original.png')
    targets=[{'entity':name,'source_crop_xyxy':[0,0,160,120],'soft_surface':False} for name in ['floor','ceiling','wall_front','wall_back','wall_left','wall_right','lamp']]
    obs={'appearance_targets':targets,'appearance_source':{'path':str(source/'original.png'),'sha256':file_hash(source/'original.png')}}
    atomic_json(source/'observation.json',obs)
    rows=[{'entity':t['entity'],'objects':[t['entity']],'material_names':['white'],'soft_surface':False,'material_class':'dielectric','pbr_parameters':{'white':{'Roughness':.8,'Metallic':0}},'texture_scope':{'application':'constant','mapping':'none'}} for t in targets]
    atomic_json(source/'material_calibration.json',{'materials':rows})
    art=lambda name:{'path':str(source/name),'sha256':file_hash(source/name),'bytes':(source/name).stat().st_size}
    base={'stage':'build_render','mode':'single','workflow_profile':'quality_v2','original_input_allowlist':[str(source/'original.png')],
          'appearance_source':obs['appearance_source'],'appearance_targets':targets,'appearance_observation':art('observation.json'),
          'refinement':{'limits':{'surface_contract_version':0,'appearance_contract_version':1}},
          'parameters':{'blender':blender,'threads':2,'cuda_visible_devices':''},
          'input_artifacts':{'agent_materials':[art('model.blend'),art('scene.json'),art('material_calibration.json')], 'agent_calibrate_lighting':[art('model.blend'),art('scene.json')]}}
    protocol=None
    for name,changed in [('accepted',False),('rejected',True)]:
        out=p/name;out.mkdir();packet=json.loads(json.dumps(base));packet['output_directory']=str(out)
        if protocol:packet['comparison_protocol']=protocol
        if changed:
            bad=p/'lighting';bad.mkdir();(bad/'model.blend').write_bytes((source/'changed.blend').read_bytes())
            packet['input_artifacts']['agent_calibrate_lighting'][0]={'path':str(bad/'model.blend'),'sha256':file_hash(bad/'model.blend')}
        atomic_json(out/'packet.json',packet)
        run([sys.executable,'-m','r2s.stage_worker',str(out/'packet.json')])
        result=json.loads((out/'appearance_audit.json').read_text());binding=json.loads((out/'render_binding.json').read_text())
        assert result['model_sha256']==binding['model_sha256']
        if changed:
            assert any('Lighting changed' in x for x in result['failures']),result
            assert binding['comparison_protocol']==protocol
        else:
            assert not result['failures'],result
            protocol=binding['comparison_protocol']
        assert len(binding['comparison_images'])==3
        assert 'appearance_neutral.png' in binding['images']
        assert (out/'response.json').exists()
    print('PASS actual stage_worker build_render, accepted shader snapshot, persistent cameras and detectable lighting-stage shader tampering')
