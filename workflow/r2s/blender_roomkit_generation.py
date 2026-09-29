"""RoomKit parts -> canonical Real2Sim model. Existing audits remain downstream."""
import importlib.util
import json
from pathlib import Path
import sys
import bpy
from mathutils import Matrix

parts_path, scene_path, out, skills = map(Path, sys.argv[sys.argv.index('--')+1:])
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from r2s.shell_collision import shell_boxes, SURFACES
from r2s.contracts import scene_check
from r2s.structure import file_sha as file_hash
scene = json.loads(scene_path.read_text()); scene_check(scene)
spec = importlib.util.spec_from_file_location('roomkit', skills/'blender-roomkit/scripts/roomkit.py')
roomkit = importlib.util.module_from_spec(spec); spec.loader.exec_module(roomkit)
parts = json.loads(parts_path.read_text())
if any(p['id'] in SURFACES for p in parts['parts']):
    raise ValueError('Canonical shell is generated separately; do not supply shell parts')
entities = {o['id']:o for o in scene['objects']}
if {p['assembly'] for p in parts['parts']} != set(entities)-set(SURFACES):
    raise ValueError('RoomKit ownership must cover canonical non-shell entities exactly')
declared = {p['object']:(a['entity'], p['id']) for a in scene['structure']['assemblies'] for p in a['parts']}
for p in parts['parts']:
    if p['assembly'] in {a['entity'] for a in scene['structure']['assemblies']} and declared.get(p['id']) != (p['assembly'],p['id']):
        raise ValueError('RoomKit part id/object/assembly must match structural declaration')
roomkit.build(parts, out/'roomkit_build')
for part in parts['parts']:
    obj = bpy.data.objects[part['id']]
    obj['entity_id'] = obj['furniture_id'] = part['assembly']
    obj['part_id'] = part['id']
for surface in SURFACES:
    objects = []
    for box in shell_boxes(scene['room'], surface):
        bpy.ops.mesh.primitive_cube_add(size=1, location=box['position'])
        obj = bpy.context.object; obj.dimensions = box['dimensions']
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        objects.append(obj)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects: obj.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    bpy.ops.object.join(); obj=bpy.context.object;obj.name=surface
    obj['entity_id']=surface;obj['geometry_role']='room_shell'
    obj['prior_status']='assumed';obj['collision_source']='canonical_room_surface'
sc=bpy.context.scene;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=8
sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.render.image_settings.color_mode='RGB'
sc.world=bpy.data.worlds.new('roomkit_initial_world');sc.world.use_nodes=True
sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.3
for entity in entities.values():
    if 'lamp' in entity['kind'] or 'pendant' in entity['kind'] or entity.get('semantic_class')=='luminaire':
        bpy.ops.object.light_add(type='AREA',location=entity['position'])
        light=bpy.context.object;light.name=entity['id']+'_initial_light';light.data.energy=100;light.data.size=.5
        light['prior_status']='assumed';light['stage']='initial_gray_geometry_only'
c=scene['camera'];bpy.ops.object.camera_add();camera=bpy.context.object;camera.name='source_camera'
camera.location=c['position'];camera.rotation_euler=(Matrix(c['rotation_world_to_cv']).transposed()@Matrix(((1,0,0),(0,-1,0),(0,0,-1)))).to_euler()
W,H=c['image_size'];camera.data.sensor_fit='HORIZONTAL';camera.data.sensor_width=36;camera.data.lens=c['focal_px']*36/W
camera.data.shift_x=(W/2-c['principal_point'][0])/W;camera.data.shift_y=(c['principal_point'][1]-H/2)/W
sc.camera=camera;sc.render.resolution_x=W;sc.render.resolution_y=H
bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
(out/'roomkit_generation.json').write_text(json.dumps({'schema':'real2sim-roomkit-generation/1',
    'manifest_sha256':file_hash(parts_path),'canonical_scene_sha256':file_hash(scene_path),
    'model_sha256':file_hash(out/'model.blend'),'skill_script_sha256':file_hash(skills/'blender-roomkit/scripts/roomkit.py'),
    'blender':bpy.app.version_string,'shell_surfaces':list(SURFACES),'parts':len(parts['parts']),
    'light_parameters':'assumed_initialization','geometry_accuracy':'unverified','physics':'not_run'},indent=2))
