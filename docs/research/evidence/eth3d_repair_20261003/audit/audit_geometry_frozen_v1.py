from pathlib import Path
import bpy,bmesh,json,hashlib,numpy as np
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
r=Path(__file__).resolve().parent;g=r.parent/'geometry/candidate';base=Path('/home/wqz/real2sim_agent_compare_20261003/OURS/models/v3');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();expected='67b1f48fedcb86e58e43952d630d141d26943902bf7d830b5247c55291bb766b';assert sha(g/'model.blend')==expected

def serial(v):
 if isinstance(v,(str,int,float,bool)) or v is None:return v
 try:return [serial(x) for x in v]
 except:return str(v)
def nodes(tree):
 if tree is None:return None
 return {'nodes':sorted([{'name':n.name,'type':n.bl_idname,'inputs':[(x.name,serial(x.default_value)) for x in n.inputs if hasattr(x,'default_value')],'image':n.image.filepath if hasattr(n,'image') and n.image else None,'attrs':{a:serial(getattr(n,a)) for a in ['operation','blend_type','vector_type','interpolation','extension'] if hasattr(n,a)}} for n in tree.nodes],key=lambda x:x['name']),'links':sorted((l.from_node.name,l.from_socket.name,l.to_node.name,l.to_socket.name) for l in tree.links)}
def snap(path):
 bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False);bpy.context.view_layer.update();s=bpy.context.scene
 objects={o.name:{'type':o.type,'matrix':np.array(o.matrix_world).tolist(),'materials':[m.name if m else None for m in getattr(o.data,'materials',[])],'visibility':{k:serial(getattr(o,k)) for k in ['hide_render','hide_viewport','visible_camera','visible_shadow','visible_diffuse','visible_glossy','visible_transmission'] if hasattr(o,k)},'exclude':bool(o.get('exclude_from_evaluation',False))} for o in s.objects}
 lights={o.name:{'matrix':np.array(o.matrix_world).tolist(),'energy':o.data.energy,'color':list(o.data.color),'type':o.data.type,'size':getattr(o.data,'size',None),'nodes':nodes(o.data.node_tree),'hide_render':o.hide_render} for o in s.objects if o.type=='LIGHT'}
 materials={m.name:{'diffuse_color':list(m.diffuse_color),'nodes':nodes(m.node_tree),'surface_render_method':getattr(m,'surface_render_method',None)} for m in bpy.data.materials}
 settings={'cycles':{k:getattr(s.cycles,k) for k in ['max_bounces','diffuse_bounces','glossy_bounces','transmission_bounces','transparent_max_bounces','samples','use_denoising','device']},'color':{k:getattr(s.view_settings,k) for k in ['view_transform','look','exposure','gamma']},'world':nodes(s.world.node_tree) if s.world else None,'compositor':nodes(s.node_tree),'use_compositing':s.render.use_compositing,'use_sequencer':s.render.use_sequencer}
 collections={c.name:c.hide_render for c in bpy.data.collections};return objects,lights,materials,settings,collections
bo,bl,bm,bs,bc=snap(base/'model.blend');co,cl,cm,cs,cc=snap(g/'model.blend');same=set(bo)&set(co);material_slot_changes=[n for n in same if bo[n]['materials']!=co[n]['materials']];material_data_changes=[n for n in set(bm)&set(cm) if bm[n]!=cm[n]];visibility_changes=[n for n in same if bo[n]['visibility']!=co[n]['visibility'] or bo[n]['exclude']!=co[n]['exclude']];collection_changes=[n for n in set(bc)|set(cc) if bc.get(n)!=cc.get(n)]
baseS=json.loads((base/'scene.json').read_text());newS=json.loads((g/'scene.json').read_text());lmkey=lambda s:{(a['entity'],x['id']):(x['uv'],x.get('frame_id',a['fit'].get('frame_id'))) for a in s['structure']['assemblies'] for x in a['fit']['landmarks']};orig={x['id']:(a,x) for a in baseS['structure']['assemblies'] for x in a['fit']['landmarks']};transport=[]
for a in newS['structure']['assemblies']:
 names={p['id']:p['object'] for p in a['parts']}
 for lm in a['fit']['landmarks']:
  olda,oldlm=orig[lm['id']];oldnames={p['id']:p['object'] for p in olda['parts']};n=names[lm['part']];on=oldnames[oldlm['part']]
  if n==on and n in same:
   target=np.array(co[n]['matrix'])@np.linalg.inv(np.array(bo[n]['matrix']))@np.r_[oldlm['world'],1];transport.append({'landmark':lm['id'],'part':n,'difference_m':float(np.linalg.norm(target[:3]-lm['world']))})
# Independently inspect evaluated shell topology and build isolated BVHs.
deps=bpy.context.evaluated_depsgraph_get();shells=[];trees={}
for name in ['floor','ceiling','wall_front','wall_back','wall_left','wall_right']:
 ob=bpy.data.objects[name];e=ob.evaluated_get(deps);me=e.to_mesh();v=[ob.matrix_world@p.co for p in me.vertices];polys=[tuple(p.vertices) for p in me.polygons];keys=[tuple(sorted(tuple(round(float(x),7) for x in v[j]) for j in poly)) for poly in polys];mesh=bmesh.new();mesh.from_mesh(me);shells.append(dict(name=name,nonmanifold_edges=sum(not x.is_manifold for x in mesh.edges),inconsistent_edges=sum(not x.is_contiguous for x in mesh.edges),duplicate_faces=len(keys)-len(set(keys)),signed_volume=mesh.calc_volume(signed=True)));mesh.free();me.calc_loop_triangles();trees[name]=BVHTree.FromPolygons(v,[tuple(t.vertices) for t in me.loop_triangles],all_triangles=True);e.to_mesh_clear()
rects=[x['bounds'] for x in newS['room']['topology_regions']];xs=sorted({z for q in rects for z in q[:2]});ys=sorted({z for q in rects for z in q[2:]});floor_checks=[]
for x in [(a+b)/2 for a,b in zip(xs,xs[1:])]:
 for y in [(a+b)/2 for a,b in zip(ys,ys[1:])]:
  wanted=any(a<x<b and c<y<d for a,b,c,d in rects);hit=trees['floor'].ray_cast(Vector([x,y,.5]),Vector([0,0,-1]),1)[0];floor_checks.append(wanted==(hit is not None))
aperture=[]
for y in np.linspace(-7.19,.54,19):
 for z in [.1,.8,2.,3.9,4.10,4.5,4.65]:
  hit=trees['wall_right'].ray_cast(Vector([5.,y,z]),Vector([1,0,0]),.5)[0];wanted=z>=4.04;aperture.append(dict(y=float(y),z=z,correct=(hit is not None)==wanted))
result=dict(model_sha256=expected,model_unchanged=sha(g/'model.blend')==expected,camera_metadata_exact=baseS['cameras']==newS['cameras'],rigid_gauge_exact=baseS['model_from_input']==newS['model_from_input'],source_labels_exact=lmkey(baseS)==lmkey(newS),source_label_count=len(lmkey(newS)),acceptance_exact=baseS['structure']['acceptance']==newS['structure']['acceptance'],room_guard={k:newS['room'].get(k) for k in ['bounds_only','nonrectangular_topology','topology','collision_policy']},shell_checks=shells,floor_union_cells_checked=len(floor_checks),floor_union_failures=sum(not x for x in floor_checks),garage_rays_checked=len(aperture),garage_failures=[x for x in aperture if not x['correct']],lights_exact=bl==cl,changed_light_names=[n for n in set(bl)|set(cl) if bl.get(n)!=cl.get(n)],material_slot_changes=material_slot_changes,material_data_changes=material_data_changes,settings_exact=bs==cs,settings_differences={k:{'before':bs[k],'after':cs[k]} for k in bs if bs[k]!=cs[k]},visibility_changes=visibility_changes,collection_changes=collection_changes,removed_objects=sorted(set(bo)-set(co)),new_objects=sorted(set(co)-set(bo)),landmark_transport_max_error=max(x['difference_m'] for x in transport),landmark_transport_errors=[x for x in transport if x['difference_m']>1e-4],unknown_completions=newS['room']['unknown_completions'],not_claimed='Per-shell topology/planned coverage is not physical scene accuracy, global collision clearance or support of unobserved completion. Native object audit and fixed-view visual check are separate.')
(r/'geometry_frozen_review.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
