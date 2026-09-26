"""Self-contained actual Blender shader/UV and fixed-camera regression; no old room assets."""
import copy
import json
import sys
import tempfile
from pathlib import Path
import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow/r2s'))
from blender_appearance import audit, snapshot, comparison_views

bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_plane_add(size=1);obj=bpy.context.object;obj.name='quilt';obj['entity_id']='bed';obj.data.uv_layers.active.name='FabricUV'
mat=bpy.data.materials.new('cotton');mat.use_nodes=True;obj.data.materials.append(mat)
bs=mat.node_tree.nodes['Principled BSDF'];bs.inputs['Roughness'].default_value=.9
tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.new('fixture',width=8,height=8);tex.image.generated_color=(.4,.6,.5,1);tex.image.pack();tex.extension='EXTEND'
uv=mat.node_tree.nodes.new('ShaderNodeUVMap');uv.uv_map='FabricUV';mat.node_tree.links.new(uv.outputs[0],tex.inputs['Vector']);mat.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
record={'entity':'bed','objects':['quilt'],'material_names':['cotton'],'soft_surface':True,'material_class':'dielectric','pbr_parameters':{'cotton':{'Roughness':.9,'Metallic':0}},'texture_scope':{'application':'whole_object','mapping':'uv','uv_map':'FabricUV'}}
sc=bpy.context.scene;sc.render.engine='CYCLES';sc.cycles.samples=1;sc.cycles.device='CPU';sc.render.resolution_percentage=5;sc.render.resolution_x=160;sc.render.resolution_y=120
bpy.ops.object.camera_add(location=(0,-2,2));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,0))-cam.location).to_track_quat('-Z','Y').to_euler();sc.camera=cam
with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp);bpy.ops.wm.save_as_mainfile(filepath=str(p/'fixture.blend'))
    def run(row=record, baseline=None):
        (p/'material_calibration.json').write_text(json.dumps({'materials':[row]}));(p/'appearance_observation.json').write_text(json.dumps({'appearance_targets':[{'entity':'bed','soft_surface':True}]}))
        return audit(p,baseline)['failures']
    assert not run(),run()
    accepted=snapshot();bs.inputs['Roughness'].default_value=.3
    assert run(baseline=accepted);bs.inputs['Roughness'].default_value=.9
    geo=mat.node_tree.nodes.new('ShaderNodeNewGeometry');mat.node_tree.links.new(geo.outputs['Position'],tex.inputs['Vector'])
    assert any('coordinates' in f for f in run())
    mat.node_tree.links.new(uv.outputs[0],tex.inputs['Vector']);mat.node_tree.nodes.remove(geo)
    tex.extension='REPEAT';assert any('tiling' in f for f in run());tex.extension='EXTEND'
    local=copy.deepcopy(record);local['texture_scope']['application']='local';tex.extension='REPEAT';assert any('Local' in f for f in run(local));tex.extension='EXTEND'
    bs.inputs['Metallic'].default_value=.65;assert any('Dielectric' in f for f in run());bs.inputs['Metallic'].default_value=0
    saved=[list(d.uv) for d in obj.data.uv_layers.active.data]
    for d in obj.data.uv_layers.active.data:d.uv=(0,0)
    assert any('Collapsed' in f for f in run())
    for d,value in zip(obj.data.uv_layers.active.data,saved):d.uv=value
    bpy.ops.mesh.primitive_cube_add(location=(3,3,0));extra=bpy.context.object;extra.data.materials.append(mat)
    assert any('Unreviewed' in f for f in run());bpy.data.objects.remove(extra,do_unlink=True)
    assert not run(),run()
    scene={'room':{'x_min':-4,'x_max':4,'y_min':-4,'y_max':4,'height':3},'objects':[]}
    comparison_views(p,scene,{})
    def pixels(name):
        im=bpy.data.images.load(str(p/name),check_existing=False);values=list(im.pixels);bpy.data.images.remove(im);return values
    first=json.loads((p/'comparison_protocol.json').read_text());before={n:pixels(n) for n in ['comparison_source.png','comparison_wide.png','comparison_reverse.png']}
    cam.location.x+=1.2;sc.view_settings.exposure=2;scene['room']['x_max']=5
    comparison_views(p,scene,{'comparison_protocol':first})
    assert json.loads((p/'comparison_protocol.json').read_text())==first
    assert sc.view_settings.exposure==2 and abs(cam.location.x-1.2)<1e-5
    assert all(pixels(n)==content for n,content in before.items()),'Fixed rendered pixels changed after source-camera/exposure/room-metadata edit'
    print('PASS actual shaders, world mapping, repetition, metallic glass, collapsed UV, omitted assignments, material lock and real fixed-camera renders')
