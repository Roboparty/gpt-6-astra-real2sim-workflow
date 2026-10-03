"""Read-only selected-model measurements for export and a provisional appearance record."""
import bpy,json,sys,hashlib
from pathlib import Path
R=Path('/home/wqz/real2sim_agent_compare_20261003/OURS');V=R/'models/v3';O=R/'technical_export';O.mkdir(exist_ok=True)
before=hashlib.sha256((V/'model.blend').read_bytes()).hexdigest();S=json.loads((V/'scene.json').read_text())
sys.path.insert(0,str(R/'code/workflow'));from r2s.blender_metadata import synchronize
audit=synchronize(S,update=True);(O/'scene.json').write_text(json.dumps(S,indent=2));(O/'authoritative_metadata_check.json').write_text(json.dumps(audit,indent=2))
materials=[]
for m in bpy.data.materials:
 row=dict(name=m.name,uses_nodes=m.use_nodes,bindings=[o.name for o in bpy.context.scene.objects if o.type=='MESH' and m.name in [slot.material.name for slot in o.material_slots if slot.material]])
 if m.use_nodes:
  row['nodes']=[dict(name=n.name,type=n.bl_idname) for n in m.node_tree.nodes];row['links']=[dict(from_node=l.from_node.name,from_socket=l.from_socket.name,to_node=l.to_node.name,to_socket=l.to_socket.name) for l in m.node_tree.links]
  p=next((n for n in m.node_tree.nodes if n.bl_idname=='ShaderNodeBsdfPrincipled'),None)
  if p:
   row['pbr_defaults']={k:(list(p.inputs[k].default_value) if hasattr(p.inputs[k].default_value,'__len__') else p.inputs[k].default_value) for k in ['Base Color','Roughness','Metallic','Emission Color','Emission Strength']}
 materials.append(row)
lights=[dict(name=o.name,type=o.data.type,power=o.data.energy,color=list(o.data.color),position=list(o.location),rotation_euler=list(o.rotation_euler),size=getattr(o.data,'size',None),size_y=getattr(o.data,'size_y',None)) for o in bpy.context.scene.objects if o.type=='LIGHT']
result=dict(source_model_sha256=before,stage_status='provisional candidate appearance; native material/light calibration not accepted because geometry fails',materials=materials,lights=lights,color_management=dict(view_transform=bpy.context.scene.view_settings.view_transform,look=bpy.context.scene.view_settings.look,exposure=bpy.context.scene.view_settings.exposure,gamma=bpy.context.scene.view_settings.gamma),provenance='Observed RGB palette/strip directions and generic PBR priors; not manufacturer specifications or measured reflectance/power',uncertainties=['RGB patches are illuminated colours, not direct albedo','Procedural wear and grain are conservative synthetic textures','GLB may flatten procedural Blender shaders','World/environment lighting and fixture powers are nonunique estimates'])
(O/'appearance_and_lighting_candidate.json').write_text(json.dumps(result,indent=2))
receipt=dict(selected_model_sha256=before,selected_scene_sha256=hashlib.sha256((V/'scene.json').read_bytes()).hexdigest(),derived_scene_sha256=hashlib.sha256((O/'scene.json').read_bytes()).hexdigest(),source_model_unchanged=hashlib.sha256((V/'model.blend').read_bytes()).hexdigest()==before,scope='Only evaluated AABB metadata synchronized in derived copy; selected model and scene unchanged; no acceptance waiver')
(O/'source_binding.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
