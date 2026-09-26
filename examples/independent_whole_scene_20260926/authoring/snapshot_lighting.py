import bpy,sys,json,re
from pathlib import Path
from mathutils import Vector
R=Path('/home/wqz/real2sim_whole_scene_20260926');state=json.loads((R/'case/runs/state.json').read_text());out=Path(state['stages']['agent_calibrate_lighting']['directory']);trial=sys.argv[sys.argv.index('--')+1];assert re.fullmatch(r'lighting_rect_\d+',trial);bpy.ops.wm.open_mainfile(filepath=str(out/(trial+'.blend')));sc=bpy.context.scene
lights=[]
for o in sc.objects:
 if o.type=='LIGHT':
  row=dict(name=o.name,type=o.data.type,position_m=list(o.location),direction_world=list(o.matrix_world.to_3x3()@Vector((0,0,-1))),energy=float(o.data.energy),color_rgb=list(o.data.color),camera_visible=o.visible_camera,glossy_visible=o.visible_glossy,transmission_visible=o.visible_transmission)
  for key in ['shape','size','size_y','angle']:
   if hasattr(o.data,key):row[key]=getattr(o.data,key)
  lights.append(row)
fixtures=[]
for o in sc.objects:
 if o.type=='MESH' and o.get('entity_id')=='ceiling_fixtures':
  fixtures.append(dict(object=o.name,interpretation=o.get('interpretation','Source fixture or explicitly inferred housing'),materials=[dict(name=m.name,emission_strength=float(m.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value)) for m in o.data.materials if m]))
record=dict(selected_trial=trial,lights=lights,world=dict(color=list(sc.world.node_tree.nodes['Background'].inputs['Color'].default_value),strength=float(sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value)),color_management={k:getattr(sc.view_settings,k) for k in ['view_transform','look','exposure','gamma','use_white_balance','temperature','tint'] if hasattr(sc.view_settings,k)},fixtures=fixtures,scope='Actual saved candidate settings; fixture electrical state is not measured by the single source photo.')
(out/'lighting_rig_snapshot.json').write_text(json.dumps(record,indent=2));print('ACTUAL_LIGHT_RIG_SNAPSHOT',trial)
