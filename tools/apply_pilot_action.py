"""Apply bounded cumulative cabinet poses to a fresh copy of the frozen input blend."""
import hashlib,json,math,sys,time
from pathlib import Path
import bpy
from mathutils import Matrix,Vector

repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'workflow'))
from r2s.blender_metadata import synchronize

args=sys.argv[sys.argv.index('--')+1:]
protocol_path,actions_path,out=map(Path,args);protocol=json.loads(protocol_path.read_text());actions=json.loads(actions_path.read_text())['actions']
out.mkdir(parents=True,exist_ok=False);start=time.monotonic()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(bpy.data.filepath)==protocol['shared_model_sha256']
scene=json.loads(Path(protocol['shared_scene']).read_text());assert sha(protocol['shared_scene'])==protocol['shared_scene_sha256']
assert len(actions)==2 and {a['entity'] for a in actions}=={'wardrobe','shoe_cabinet'}
before={o.name:o.matrix_world.copy() for o in bpy.context.scene.objects}
def owner(o):return o.get('entity_id',o.get('furniture_id',o.name))
changed=set()
for action in actions:
    dx,dy=action['xy_m'];angle=action['yaw_deg']
    assert all(type(v) in [int,float] and math.isfinite(v) for v in [dx,dy,angle])
    assert abs(dx)<=.03 and abs(dy)<=.03 and abs(angle)<=2
    assert action.get('reason')
    entity=action['entity'];center=Vector(next(o['position'] for o in scene['objects'] if o['id']==entity))
    transform=Matrix.Translation(Vector((dx,dy,0)))@Matrix.Translation(center)@Matrix.Rotation(math.radians(angle),4,'Z')@Matrix.Translation(-center)
    objects=[o for o in bpy.context.scene.objects if owner(o)==entity and o.type in {'MESH','CURVE','SURFACE','FONT','META'}]
    assert objects
    def depth(o):return 0 if o.parent is None else 1+depth(o.parent)
    for obj in sorted(objects,key=depth):obj.matrix_world=transform@before[obj.name];changed.add(obj.name)
bpy.context.view_layer.update()
for obj in bpy.context.scene.objects:
    if obj.name not in changed:assert max(abs(obj.matrix_world[i][j]-before[obj.name][i][j]) for i in range(4) for j in range(4))<1e-6
metadata=synchronize(scene,update=True);(out/'scene.json').write_text(json.dumps(scene,indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
sc=bpy.context.scene;camera=scene['camera'];sc.camera=bpy.data.objects.get('source_camera') or sc.camera
sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=8;sc.cycles.use_denoising=True
sc.render.resolution_x=camera['image_size'][0];sc.render.resolution_y=camera['image_size'][1];sc.render.resolution_percentage=50
sc.render.filepath=str(out/'ordinary_render.png');bpy.ops.render.render(write_still=True)
report={'status':'passed','input_blend_sha256':protocol['shared_model_sha256'],'output_blend_sha256':sha(out/'model.blend'),
        'actions':actions,'action_sha256':sha(actions_path),'changed_geometry_objects':len(changed),
        'other_object_transforms_unchanged':True,'metadata':metadata,'wall_seconds':time.monotonic()-start,
        'script_sha256':sha(__file__),'scope':'Bounded pose edit and ordinary render; not scene acceptance'}
(out/'action_receipt.json').write_text(json.dumps(report,indent=2))
