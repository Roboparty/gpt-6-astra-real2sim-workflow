"""Rebuild from EMPTY Blender using only layout.json and allowed input camera packet.
Run Blender --background --factory-startup --threads 2 --python build_scene.py.
Procedural materials are inference; object/component geometry is editable and named.
"""
import bpy, json, pathlib, math
from mathutils import Matrix, Vector
R=pathlib.Path(__file__).resolve().parent
L=json.loads((R/'layout.json').read_text())
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
for d in list(bpy.data.materials):bpy.data.materials.remove(d)
materials={}
for name,c in L['materials'].items():
    m=bpy.data.materials.new(name);m.diffuse_color=(*c[:3],1);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*c[:3],1);p.inputs['Roughness'].default_value=c[3] if len(c)>3 else .65
    if name in ['steel','blue_steel','orange_steel']:p.inputs['Metallic'].default_value=.5
    if name=='lamp':p.inputs['Emission Color'].default_value=(1,.97,.87,1);p.inputs['Emission Strength'].default_value=4
    if name in ['concrete','ceiling','wood','white_wall']:
        ns=m.node_tree.nodes;ls=m.node_tree.links;noise=ns.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=3 if name!='wood' else 18;noise.inputs['Detail'].default_value=2
        ramp=ns.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(*(v*.68 for v in c[:3]),1);ramp.color_ramp.elements[1].color=(*(min(1,v*1.12) for v in c[:3]),1);ls.new(noise.outputs['Fac'],ramp.inputs['Fac']);ls.new(ramp.outputs['Color'],p.inputs['Base Color'])
    materials[name]=m
for group in L['objects']:
    coll=bpy.data.collections.new(group['id']);bpy.context.scene.collection.children.link(coll)
    for part in group['parts']:
        typ=part.get('type','box')
        if typ=='box':
            bpy.ops.mesh.primitive_cube_add(size=1,location=part['center']);o=bpy.context.object;o.dimensions=part['size'];bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        elif typ=='cylinder':
            bpy.ops.mesh.primitive_cylinder_add(vertices=part.get('vertices',16),radius=part['radius'],depth=part['depth'],location=part['center']);o=bpy.context.object
        elif typ=='mesh':
            me=bpy.data.meshes.new(part['name']);me.from_pydata(part['vertices'],[],part['faces']);me.update();o=bpy.data.objects.new(part['name'],me);bpy.context.scene.collection.objects.link(o)
        elif typ=='sphere':
            bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,location=part['center']);o=bpy.context.object;o.scale=part['size'];bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        o.name=part['name'];o['semantic_id']=group['id'];o['category']=group['category'];o['provenance']=group['provenance'];o.rotation_euler=part.get('rotation',[0,0,0]);o.data.materials.append(materials[part['material']])
        for c in list(o.users_collection):c.objects.unlink(o)
        coll.objects.link(o)
# Conservative independent collision proxies, excluded from render/evaluation.
col=bpy.data.collections.new('COLLISION_PROXIES');bpy.context.scene.collection.children.link(col)
for x in L['colliders']:
    bpy.ops.mesh.primitive_cube_add(size=1,location=x['center']);o=bpy.context.object;o.name=x['name'];o.dimensions=x['size'];bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.hide_render=True;o['exclude_from_evaluation']=True;o['collision_for']=x['object_id'];o.display_type='WIRE'
    for c in list(o.users_collection):c.objects.unlink(o)
    col.objects.link(o)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=12;scene.render.threads_mode='FIXED';scene.render.threads=2
world=bpy.data.worlds.new('IndustrialAmbient');scene.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.7,.72,.75,1);world.node_tree.nodes['Background'].inputs[1].default_value=.3
for i,light in enumerate(L['lights']):
    d=bpy.data.lights.new('FixtureLight_%03d'%i,'AREA');d.energy=light.get('power',180);d.shape='RECTANGLE';d.size=light.get('length',3);d.size_y=.2;o=bpy.data.objects.new(d.name,d);scene.collection.objects.link(o);o.location=light['center']
scene.view_settings.view_transform='AgX';scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
bpy.ops.wm.save_as_mainfile(filepath=str(R/'scene.blend'))
bpy.ops.object.select_all(action='DESELECT')
for o in scene.objects:
    if o.type=='MESH' and not o.hide_render:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(R/'scene.glb'),export_format='GLB',use_selection=True,export_cameras=False,export_lights=False)
print('REBUILD_COMPLETE',len(L['objects']),sum(len(o['parts']) for o in L['objects']))
