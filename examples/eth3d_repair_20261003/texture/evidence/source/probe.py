import bpy,sys,json,pathlib
bpy.ops.wm.open_mainfile(filepath='/home/wqz/real2sim_agent_compare_20261003/OURS/models/v3/model.blend',load_ui=False,use_scripts=False)
obs=[o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_render and not o.get('exclude_from_evaluation')]
print('PY',sys.version,'OBJECTS',len(obs),'POLYS',sum(len(o.data.polygons) for o in obs),'LOOPS',sum(len(o.data.loops) for o in obs))
print('SAMPLE',[(o.name,len(o.data.polygons),len(o.modifiers),o.get('entity_id'),[m.name for m in o.data.materials]) for o in obs[:15]])
try:import PIL; print('PIL',PIL.__version__)
except Exception as e:print('NO_PIL',str(e))
print('MATERIALS',[(m.name,[n.bl_idname for n in m.node_tree.nodes] if m.use_nodes else []) for m in bpy.data.materials][:25])
