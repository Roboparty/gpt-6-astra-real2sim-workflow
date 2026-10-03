import bpy,bmesh,json,sys,hashlib,math
import numpy as np
from pathlib import Path
from mathutils import Vector,Matrix
R=Path('/home/wqz/real2sim_agent_repair_20261003/geometry');B=Path('/home/wqz/real2sim_agent_compare_20261003/OURS');O=R/'candidate_v4';O.mkdir(exist_ok=False)
assert Path(bpy.data.filepath).resolve()==(B/'models/v3/model.blend').resolve()
assert hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest()=='4d53b2a7fa076a6892592e555f33b55b07476dc2f6dab58651ab146fc1acdf85'
S=json.loads((B/'models/v3/scene.json').read_text());plan=json.loads((R/'topology_plan.json').read_text());M=json.loads((R/'repair_measurements.json').read_text());sc=bpy.context.scene
basehash=hashlib.sha256((B/'models/v3/model.blend').read_bytes()).hexdigest();changes=[];landmark_updates={}
shell_materials={name:list(bpy.data.objects[name].data.materials) for name in ['floor','ceiling','wall_front','wall_back','wall_left','wall_right']}
mat=bpy.data.materials.new('geometry_only_neutral');mat.use_nodes=True;mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.55,.55,.55,1);mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.8
rects=[r['bounds'] for r in plan['regions']];xs=sorted(set(v for r in rects for v in r[:2]));ys=sorted(set([v for r in rects for v in r[2:]]+[-7.2]));cells=set()
for i in range(len(xs)-1):
 for j in range(len(ys)-1):
  x=(xs[i]+xs[i+1])/2;y=(ys[j]+ys[j+1])/2
  if any(a<=x<=b and c<=y<=d for a,b,c,d in rects):cells.add((i,j))
def mesh_obj(name,verts,faces,owner=None):
 me=bpy.data.meshes.new(name+'_repaired');me.from_pydata(verts,[],faces);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();o=bpy.data.objects.new(name,me);sc.collection.objects.link(o);o['entity_id']=owner or name;o['geometry_role']='source_constrained_shell';o['boundary_status']='observed/partial/assumed; see topology_plan.json'
 for material in shell_materials.get(name,[mat]):o.data.materials.append(material)
 return o
def box_part(verts,faces,lo,hi):
 p=len(verts);x,y,z=lo;X,Y,Z=hi;verts.extend([(x,y,z),(X,y,z),(X,Y,z),(x,Y,z),(x,y,Z),(X,y,Z),(X,Y,Z),(x,Y,Z)]);faces.extend(tuple(p+k for k in f) for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
remove=['floor','ceiling','wall_front','wall_back','wall_left','wall_right','main_side_wall','corridor_north_wall','corridor_south_wall','rack_back_wall','lumber_back_wall']
for name in remove:
 o=bpy.data.objects.get(name)
 if o:changes.append(dict(object=name,action='replace_geometry' if name in remove[:6] else 'remove_duplicate_old_partition',reason='Rebuilt actual orthogonal-union exterior, not visibility masking'));bpy.data.objects.remove(o,do_unlink=True)
for name,z0,z1 in [('floor',-.2,0),('ceiling',4.68,4.88)]:
 verts=[];faces=[];idx={}
 def vi(v):
  if v not in idx:idx[v]=len(verts);verts.append(v)
  return idx[v]
 for i,j in sorted(cells):
  corners=[(xs[i],ys[j]),(xs[i+1],ys[j]),(xs[i+1],ys[j+1]),(xs[i],ys[j+1])];lo=[vi((*p,z0)) for p in corners];hi=[vi((*p,z1)) for p in corners];faces += [tuple(reversed(lo)),tuple(hi)]
  for edge,other in [(0,(i,j-1)),(1,(i+1,j)),(2,(i,j+1)),(3,(i-1,j))]:
   if other not in cells:k=(edge+1)%4;faces.append((lo[edge],lo[k],hi[k],hi[edge]))
 mesh_obj(name,verts,faces)
walls={n:([],[]) for n in ['wall_front','wall_back','wall_left','wall_right']};boundary=[]
for i,j in sorted(cells):
 for direction,other,name in [(0,(i,j-1),'wall_front'),(1,(i+1,j),'wall_right'),(2,(i,j+1),'wall_back'),(3,(i-1,j),'wall_left')]:
  if other in cells:continue
  x0,x1,y0,y1=xs[i],xs[i+1],ys[j],ys[j+1];v,f=walls[name];z0=0.
  # Real garage aperture is occupied by existing sliding leaves, not an extra solid wall.
  if direction==1 and abs(x1-5.25)<.01 and y0>=-7.2 and y1<=.55:z0=4.04
  if direction==0:lo=[x0,y0-.2,z0];hi=[x1,y0,4.68];a=[x0,y0];b=[x1,y0]
  elif direction==2:lo=[x0,y1,z0];hi=[x1,y1+.2,4.68];a=[x0,y1];b=[x1,y1]
  elif direction==1:lo=[x1,y0,z0];hi=[x1+.2,y1,4.68];a=[x1,y0];b=[x1,y1]
  else:lo=[x0-.2,y0,z0];hi=[x0,y1,4.68];a=[x0,y0];b=[x0,y1]
  box_part(v,f,lo,hi);boundary.append(dict(shell=name,a=a,b=b,z_min=z0,z_max=4.68,door_closure='garage_door' if z0 else None))
for name in walls:
 vv=[];ff=[];groups={}
 for seg in boundary:
  if seg['shell']!=name:continue
  along_x=name in ['wall_front','wall_back'];axis=1 if along_x else 0;uaxis=0 if along_x else 1;n=seg['a'][axis]
  groups.setdefault(n,[]).append([seg['a'][uaxis],seg['b'][uaxis],seg['z_min'],seg['z_max']])
 for normal,rectangles in groups.items():
  us=sorted(set(x for r in rectangles for x in r[:2]));zs=sorted(set(x for r in rectangles for x in r[2:]));occ=set()
  for i in range(len(us)-1):
   for j in range(len(zs)-1):
    u=(us[i]+us[i+1])/2;z=(zs[j]+zs[j+1])/2
    if any(a<=u<=b and c<=z<=d for a,b,c,d in rectangles):occ.add((i,j))
  sign=-1 if name in ['wall_front','wall_left'] else 1;idx={}
  def idxv(u,z,n):
   p=(u,n,z) if name in ['wall_front','wall_back'] else (n,u,z)
   if p not in idx:idx[p]=len(vv);vv.append(p)
   return idx[p]
  for i,j in sorted(occ):
   corners=[(us[i],zs[j]),(us[i+1],zs[j]),(us[i+1],zs[j+1]),(us[i],zs[j+1])];lo=[idxv(u,z,normal) for u,z in corners];hi=[idxv(u,z,normal+sign*.2) for u,z in corners];ff.extend([tuple(reversed(lo)),tuple(hi)])
   for edge,other in [(0,(i,j-1)),(1,(i+1,j)),(2,(i,j+1)),(3,(i-1,j))]:
    if other not in occ:k=(edge+1)%4;ff.append((lo[edge],lo[k],hi[k],hi[edge]))
 mesh_obj(name,vv,ff)
# Remove unsupported old fixture completions outside all newly evidenced zones.
def inside(x,y):return any(a-.05<=x<=b+.05 and c-.05<=y<=d+.05 for a,b,c,d in rects)
# Existing luminaires and their source shading are preserved for geometry-only ablation.
for k in range(3):
 o=bpy.data.objects.get('ceiling_pipe'+str(k))
 if o:
  old=o.matrix_world.copy();ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=bpy.data.meshes.new_from_object(ev,preserve_all_data_layers=True,depsgraph=bpy.context.evaluated_depsgraph_get());before=np.array([old@v.co for v in me.vertices]);lo=before.min(0);hi=before.max(0);xmin=float(lo[0]);xmax=5.20;assert abs((hi-lo)[1]-.11)<1e-4 and abs((hi-lo)[2]-.11)<1e-4
  inverse=old.inverted()
  for vertex in me.vertices:
   q=old@vertex.co;q.x=xmin+(q.x-xmin)*(xmax-xmin)/(hi[0]-lo[0]);vertex.co=inverse@q
  o.modifiers.clear();o.data=me;o.matrix_world=old;me.update();after=np.array([old@v.co for v in me.vertices]);changes.append(dict(object=o.name,action='world_axial_pipe_clip_baked',baseline_bounds=[lo.tolist(),hi.tolist()],candidate_bounds=[after.min(0).tolist(),after.max(0).tolist()],axis='world_X',radial_yz_preserved=True,reason='Clip unsupported run behind closed garage atX5.20; preserve originalXmin-15 in the actual corridor, radius55mm and centerZ4.24. No object.dimensions assignment.'))
o=bpy.data.objects.get('far_corridor_door');o.location.x=M['terminal_x']+.03
o=bpy.data.objects.get('entrance_recess_door');o.location.y=-12.39
o=bpy.data.objects.get('entrance_soffit');o.location.y=(-12.44-8)/2;o.dimensions.y=4.44
# Continuous object-frame changes; the original source pixels and cameras remain frozen.
for owner,fit in M['fit_proposals'].items():
 if owner=='lime_skip_0':continue
 t=fit['parameters'];center=Vector(fit['center']);rot=Matrix.Rotation(t[5],4,'Z');affine=Matrix.Translation(center+Vector([t[0],t[1],0]))@rot@Matrix.Diagonal([*t[2:5],1])@Matrix.Translation(-center)
 for o in sc.objects:
  if o.get('entity_id')!=owner:continue
  old=o.matrix_world.copy();new=affine@old
  if any(k in o.name for k in ['tyre','hub','wheel']):new=Matrix.Translation(new.translation)@rot@old.to_3x3().to_4x4()@Matrix.Diagonal([t[4],t[4],t[4],1])
  for assembly in S['structure']['assemblies']:
   for lm in assembly['fit']['landmarks']:
    if lm['part']==o.name:landmark_updates[lm['id']]=list(new@old.inverted()@Vector(lm['world']))
  ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=bpy.data.meshes.new_from_object(ev,preserve_all_data_layers=True,depsgraph=bpy.context.evaluated_depsgraph_get());before_vertices=np.array([old@v.co for v in mesh.vertices]);transport=old.inverted()@new
  for vertex in mesh.vertices:vertex.co=transport@vertex.co
  o.modifiers.clear();o.data=mesh;o.matrix_world=old;mesh.update();after_vertices=np.array([old@v.co for v in mesh.vertices])
  changes.append(dict(object=o.name,action='continuous_local_frame_fit_baked_evaluated_vertices',owner=owner,parameters=t,world_transport=[list(r) for r in new@old.inverted()],baseline_evaluated_vertices_sha256=hashlib.sha256(before_vertices.tobytes()).hexdigest(),candidate_evaluated_vertices_sha256=hashlib.sha256(after_vertices.tobytes()).hexdigest(),vertex_count=len(mesh.vertices),modifiers_baked=True,vertex_correspondence_preserved=True,wheel_uniform_exception=any(k in o.name for k in ['tyre','hub','wheel']),reason='Frozen source endpoint fit; preserve affine shear exactly in evaluated mesh, no TRS decomposition'))
# Existing materials, lights, exposure, render settings and visibility stay unchanged.
bpy.context.view_layer.update();ids={o.get('entity_id',o.name) for o in sc.objects if o.type=='MESH'};S['objects']=[o for o in S['objects'] if o['id'] in ids]
S['model_version']='geometry_repair_v1';S['room'].update(x_min=min(xs),x_max=max(xs),y_min=min(ys),y_max=max(ys),bounds_only=True,topology='orthogonal_union',nonrectangular_topology=True,collision_policy='mesh_only',openings=[],collision_proxies=[])
S['room']['topology_regions']=plan['regions'];S['room']['boundary_segments']=boundary;S['room']['unknown_completions']=plan['unknown_completions'];S['collision_policy']={'canonical_rectangle_fallback':'forbidden','native_simulation':'unsupported/refused','actual_static_collision':'evaluated shell and object triangle meshes; see collision_mesh_coverage.json'}
sys.path.insert(0,str(R/'code/workflow'));from r2s.blender_metadata import synchronize
synchronize(S,update=True)
# Preserve original UV/frame labels and semantic part associations; transform their actual mesh vertices with objects.
baseS=json.loads((B/'models/v3/scene.json').read_text());base_world={}
for a in baseS['structure']['assemblies']:
 for lm in a['fit']['landmarks']:base_world[lm['id']]=lm['world']
for a in S['structure']['assemblies']:
 if a['entity'] not in M['fit_proposals'] or a['entity']=='lime_skip_0':continue
 fit=M['fit_proposals'][a['entity']];t=fit['parameters'];center=Vector(fit['center']);rot=Matrix.Rotation(t[5],4,'Z');aff=Matrix.Translation(center+Vector([t[0],t[1],0]))@rot@Matrix.Diagonal([*t[2:5],1])@Matrix.Translation(-center)
 for j in a['joints']:j['anchor_world']=list(aff@Vector(j['anchor_world']))
 for lm in a['fit']['landmarks']:lm['world']=landmark_updates.get(lm['id'],list(aff@Vector(lm['world'])))
flat=next(a for a in S['structure']['assemblies'] if a['entity']=='flatbed_trailer')
flat['joints'].append(dict(parts=['flatbed_frame','flatbed_towA'],anchor_world=[6.55,7.1,.39],tolerance_m=.01,construction_basis='Previously verified intended connection: endpoint inside frame; not a tolerance waiver'))
# Reconstruct the front skip from source8->9 rim triangulation, not a global stretch.
tracks=json.loads((R/'bin_multiview_tracks.json').read_text());rim=[r for r in tracks if r['input_index']==9 and r['reliable'] and r['source_uv'] in [[119.0,357.0],[390.0,350.0]]];assert len(rim)==2
p0,p1=[np.array(r['model_world']) for r in rim];depth=np.load(B/'inputs/depth_reference/frames/008.npz');F=json.loads((B/'inputs/packet.json').read_text())['frames'][8];u,v=145.,552.;h,w=depth['depth_z_m'].shape;W,H=F['image_size'];xx=int(round((u+.5)*w/W-.5));yy=int(round((v+.5)*h/H-.5));zdepth=float(np.median(depth['depth_z_m'][yy-1:yy+2,xx-1:xx+2]));T=np.array(S['model_from_input'])@np.array(F['T_world_camera']);foot=T[:3,:3]@(np.linalg.inv(np.array(F['K']))@np.array([u,v,1])*zdepth)+T[:3,3];assert .04<foot[2]<.2
cx=(p0[0]+p1[0])/2;cy=(p0[1]+p1[1])/2;rim_z=(p0[2]+p1[2])/2;thick=p1[2]-p0[2];assert .01<thick<.05
lx=p0[0]-.026;rx=p1[0]+.026;fy=p1[1]+.025;by=p0[1]-.025;base_l=cx-.675;base_r=cx+.675;base_front=foot[1];base_back=11.65;base_z=foot[2]
def replace_world_mesh(name,verts,faces):
 o=bpy.data.objects[name];materials=list(o.data.materials);me=bpy.data.meshes.new(name+'_source_repair');me.from_pydata(verts,[],faces);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();o.data=me;o.modifiers.clear();o.matrix_world=Matrix.Identity(4)
 for ma in materials:me.materials.append(ma)
 changes.append(dict(object=name,action='source_evidence_parametric_rebuild',reason='Two rim endpoints triangulated from8/9; support bound from visible8 learned depth and floor contact; frame9support tracking rejected',vertex_correspondence_preserved=False))
def replace_box(name,lo,hi):
 verts=[];faces=[];box_part(verts,faces,lo,hi);replace_world_mesh(name,verts,faces)
verts=[(base_l,base_front,base_z),(base_r,base_front,base_z),(base_r,base_back,base_z),(base_l,base_back,base_z),(lx,fy,rim_z),(rx,fy,rim_z),(rx,by,rim_z),(lx,by,rim_z)]
replace_world_mesh('skip0_shell',verts,[(0,3,2,1),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]);bpy.data.objects['skip0_shell'].modifiers.new('actual_plate_thickness','SOLIDIFY').thickness=.025
replace_box('skip0_side_rim0',[lx-.026,p1[1],p0[2]],[lx+.026,p0[1],p1[2]])
replace_box('skip0_side_rim1',[rx-.026,p1[1],p0[2]],[rx+.026,p0[1],p1[2]])
replace_box('skip0_rim0',[lx-.026,fy-.026,p0[2]],[rx+.026,fy+.026,p1[2]])
replace_box('skip0_rim1',[lx-.026,by-.026,p0[2]],[rx+.026,by+.026,p1[2]])
replace_box('skip0_foot0',[foot[0],base_front,0],[foot[0]+.20,base_back,base_z]);right=2*cx-foot[0]-.20;replace_box('skip0_foot1',[right,base_front,0],[right+.20,base_back,base_z])
a=next(a for a in S['structure']['assemblies'] if a['entity']=='lime_skip_0')
for lm,point in zip(a['fit']['landmarks'],[p0,p1,foot]):
 lm['previous_world']=lm['world'];lm['world']=list(point);lm['association_evidence']='Original UV/frame unchanged; rim vertex identity supported by8-9 triangulation; foot visible in8+DA3 only, other-view tracking failed and retained'
bpy.context.view_layer.update()
from mathutils.bvhtree import BVHTree
def tree(name):
 o=bpy.data.objects[name];ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();me.calc_loop_triangles();vv=[o.matrix_world@v.co for v in me.vertices];tt=[tuple(t.vertices) for t in me.loop_triangles];b=BVHTree.FromPolygons(vv,tt,all_triangles=True);ev.to_mesh_clear();return b,vv
# Actual common contact anchors for the rebuilt skip, retaining pair scope/tolerance.
anchors={'skip0_foot0':[base_l,(base_front+base_back)/2,base_z],'skip0_foot1':[base_r,(base_front+base_back)/2,base_z],'skip0_rim0':[cx,fy,rim_z],'skip0_rim1':[cx,by,rim_z],'skip0_side_rim0':[lx,cy,rim_z],'skip0_side_rim1':[rx,cy,rim_z]}
for j in a['joints']:
 if 'skip0_shell' in j['parts']:j['anchor_world']=anchors[next(x for x in j['parts'] if x!='skip0_shell')]
 else:
  A,Bb=[bpy.data.objects[n] for n in j['parts']];aa=np.array([A.matrix_world@Vector(v) for v in A.bound_box]);bb=np.array([Bb.matrix_world@Vector(v) for v in Bb.bound_box]);j['anchor_world']=((np.maximum(aa.min(0),bb.min(0))+np.minimum(aa.max(0),bb.max(0)))/2).tolist()
van=next(a for a in S['structure']['assemblies'] if a['entity']=='white_van');ta,va=tree('van_cab_body');tb,vb=tree('van_windshield');shared=[v for v in vb if ta.find_nearest(v)[3]<1e-5];assert shared
for j in van['joints']:
 if set(j['parts'])=={'van_cab_body','van_windshield'}:j['previous_anchor_world']=j['anchor_world'];j['anchor_world']=list(shared[0]);j['construction_basis']='Actual shared cut-opening edge vertex; old anchor was inside the open window, not at physical attachment'
synchronize(S,update=True)
(O/'source_rebuild_evidence.json').write_text(json.dumps(dict(rim_tracks=rim,foot_world=foot.tolist(),foot_source='frame8DA3+floor contact only;9tracking failed, not declared multi-view verified',van_shared_edge_anchor=list(shared[0])),indent=2))
(O/'scene.json').write_text(json.dumps(S,indent=2));(O/'topology.json').write_text(json.dumps(plan,indent=2));(O/'geometry_changes.json').write_text(json.dumps(changes,indent=2))
area=sum((xs[i+1]-xs[i])*(ys[j+1]-ys[j]) for i,j in cells)
coverage=dict(status='static_mesh_geometry_prepared',floor_area_m2=area,old_rectangular_area_m2=2008.5,regions=plan['regions'],cell_count=len(cells),shells={name:dict(vertices=len(bpy.data.objects[name].data.vertices),faces=len(bpy.data.objects[name].data.polygons),visible=True,opaque=True) for name in ['floor','ceiling',*walls]},boundary=boundary,actual_collision_source='same evaluated triangle surfaces as visible shell; no canonical box fallback',native_simulation_status='unsupported/refused',pending='independent surface coverage and object intersection review')
(O/'collision_mesh_coverage.json').write_text(json.dumps(coverage,indent=2));bpy.ops.wm.save_as_mainfile(filepath=str(O/'model.blend'));print('CANDIDATE',str(O/'model.blend'),'area',area,'parts',sum(o.type=='MESH' for o in sc.objects))
