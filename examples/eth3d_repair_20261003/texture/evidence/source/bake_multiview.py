import bpy,numpy as np,sys,pathlib,json,hashlib,math,time,argparse
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.append('/home/wqz/real2sim_fresh_20260921/runtime/venv/lib/python3.11/site-packages')
import subprocess
R=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--out',required=True);p.add_argument('--density',type=float,default=40);p.add_argument('--objects',default='');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True);(out/'textures').mkdir(exist_ok=True);start=time.time()
IN=pathlib.Path('/home/wqz/real2sim_agent_compare_20261003/OURS/inputs');P=json.load(open(IN/'packet.json'));G=np.array(json.load(open(IN.parent/'model_from_input.json'))['model_from_input']);sha=lambda f:hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest();basehash=sha(a.model)
bpy.ops.wm.open_mainfile(filepath=a.model,load_ui=False,use_scripts=False);sc=bpy.context.scene
# Preserve full-scene object geometry and visibility; only material slots/UV may differ.
def fingerprint():
 h=hashlib.sha256()
 for o in sorted(sc.objects,key=lambda x:x.name):
  h.update(o.name.encode());h.update(np.array(o.matrix_world,dtype='<f8').tobytes());h.update(str((o.hide_render,o.hide_viewport,o.get('exclude_from_evaluation'),[(c.name,c.hide_render,c.hide_viewport) for c in o.users_collection],[(m.name,m.type) for m in o.modifiers])).encode())
  if o.type=='MESH':
   v=np.array([v.co[:] for v in o.data.vertices],dtype='<f8');h.update(v.tobytes());h.update(str([list(p.vertices) for p in o.data.polygons]).encode())
 return h.hexdigest()
before=fingerprint();lighting={'world':sc.world.name if sc.world else None,'world_tree':str([(n.name,[(i.name,str(i.default_value)) for i in n.inputs if hasattr(i,'default_value')]) for n in sc.world.node_tree.nodes]) if sc.world and sc.world.use_nodes else '', 'lights':[(o.name,o.data.energy,list(o.data.color)) for o in sc.objects if o.type=='LIGHT'],'view_transform':sc.view_settings.view_transform,'exposure':sc.view_settings.exposure,'gamma':sc.view_settings.gamma,'look':sc.view_settings.look,'cycles_bounces':{k:getattr(sc.cycles,k) for k in ['max_bounces','diffuse_bounces','glossy_bounces','transparent_max_bounces']}}
visible=[o for o in sc.objects if o.type=='MESH' and not o.hide_render and not o.get('exclude_from_evaluation') and not any(c.hide_render for c in o.users_collection)]
vertices=[];triangles=[];owners=[];graph=bpy.context.evaluated_depsgraph_get()
for oi,o in enumerate(visible):
 ev=o.evaluated_get(graph);m=ev.to_mesh();m.calc_loop_triangles();off=len(vertices);vertices.extend(o.matrix_world@v.co for v in m.vertices)
 for t in m.loop_triangles:triangles.append(tuple(off+k for k in t.vertices));owners.append(oi)
 ev.to_mesh_clear()
bvh=BVHTree.FromPolygons(vertices,triangles,all_triangles=True);owners=np.array(owners);del vertices,triangles
frames=[]
for f in P['frames']:
 i=f['input_index'];im=np.load(R/'cache_rgb'/f'{i:03d}.npy').astype(np.float32)/255.;n=np.load(IN/f'depth_reference/frames/{i:03d}.npz');T=G@np.array(f['T_world_camera']);frames.append({'index':i,'sha256':f['sha256'],'im':im,'K':np.array(f['K']),'T':T,'Ti':np.linalg.inv(T),'dep':n['depth_z_m'],'valid':n['valid_mask'],'Kd':n['K_depth']})
Cs=np.array([f['T'][:3,3] for f in frames]);plans=[]
for oi,o in enumerate(visible):
 if a.objects and o.name not in a.objects.split(','):continue
 if len(o.data.polygons)>600:continue
 W=np.array(o.matrix_world);world=np.array([v.co[:] for v in o.data.vertices])@W[:3,:3].T+W[:3,3]
 for poly in o.data.polygons:
  mat=o.data.materials[poly.material_index] if len(o.data.materials)>poly.material_index else None
  if not mat or not mat.use_nodes:continue
  ps=next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
  if ps is None:continue
  if (ps.inputs['Emission Strength'].default_value>0.01 and max(ps.inputs['Emission Color'].default_value[:3])>.01) or mat.name.lower() in ['glass','bright_metal','rubber']:continue
  pts=world[list(poly.vertices)];normal=np.linalg.inv(W[:3,:3]).T@np.array(poly.normal);normal/=max(np.linalg.norm(normal),1e-9);center=pts.mean(0);vc=Cs-center;cos=(vc@normal)/np.linalg.norm(vc,axis=1)
  if max(vc@normal)<=0:continue
  edges=np.roll(pts,-1,axis=0)-pts;u=edges[np.argmax(np.linalg.norm(edges,axis=1))];u/=np.linalg.norm(u);v=np.cross(normal,u);uv=(pts-pts[0])@np.array([u,v]).T;lo=uv.min(0);hi=uv.max(0);extent=hi-lo
  if min(extent)<.025 or np.prod(extent)<.025:continue
  w=int(np.clip(math.ceil(extent[0]*a.density),6,768));h=int(np.clip(math.ceil(extent[1]*a.density),6,768));plans.append({'oi':oi,'pi':poly.index,'mat':mat.name,'u':u,'v':v,'normal':normal,'origin':pts[0],'uv':uv,'lo':lo,'extent':extent,'w':w,'h':h})
# Shelf pack padded islands into fixed image atlases.
SIZE=2048;pages=[];cx=cy=rowh=0;page=-1
for q in sorted(plans,key=lambda q:-q['h']):
 w=q['w']+4;h=q['h']+4
 if page<0 or cy+h>SIZE:pages.append(np.zeros((SIZE,SIZE,4),np.uint8));page+=1;cx=cy=rowh=0
 if cx+w>SIZE:cx=0;cy+=rowh;rowh=0
 if cy+h>SIZE:pages.append(np.zeros((SIZE,SIZE,4),np.uint8));page+=1;cx=cy=rowh=0
 q.update(page=page,x=cx+2,y=cy+2);cx+=w;rowh=max(rowh,h)
print('PLAN',len(plans),'faces',len(pages),'atlases',sum(q['w']*q['h'] for q in plans),'texels',flush=True)
summary=[];support_counts=np.zeros(36,np.int64);source_boxes={};exact_rays=0;rejects={'source_view_texel_pairs':0,'outside_fov_or_depth_grid':0,'depth_or_edge_inconsistent':0,'grazing_or_backface':0,'exact_visibility_rejected':0,'cross_view_colour_rejected':0}
for qi,q in enumerate(plans):
 h,w=q['h'],q['w'];yy,xx=np.mgrid[:h,:w];uv=q['lo']+np.column_stack([(xx.ravel()+.5)/w,(yy.ravel()+.5)/h])*q['extent'];px,py=uv.T;inside=np.zeros(len(uv),bool);poly=q['uv']
 for va,vb in zip(poly,np.roll(poly,-1,axis=0)):
  inside ^= ((va[1]>py)!=(vb[1]>py)) & (px<(vb[0]-va[0])*(py-va[1])/(vb[1]-va[1]+1e-30)+va[0])
 ids=np.flatnonzero(inside);uv=uv[ids];world=q['origin']+uv[:,0,None]*q['u']+uv[:,1,None]*q['v'];N=len(world);rejects['source_view_texel_pairs']+=36*N
 if not N:continue
 scores=np.full((36,N),-1.,np.float32);coords={}
 for j,f in enumerate(frames):
  pc=world@f['Ti'][:3,:3].T+f['Ti'][:3,3];z=pc[:,2];proj=pc@f['K'].T;xy=proj[:,:2]/np.maximum(z[:,None],1e-6);pd=pc@f['Kd'].T;duv=np.rint(pd[:,:2]/np.maximum(z[:,None],1e-6)).astype(int);dh,dw=f['dep'].shape;du,dv=duv.T;valid=(z>.1)&(du>1)&(du<dw-2)&(dv>1)&(dv<dh-2)&(xy[:,0]>3)&(xy[:,0]<f['im'].shape[1]-4)&(xy[:,1]>3)&(xy[:,1]<f['im'].shape[0]-4)
  ix=np.flatnonzero(valid);rejects['outside_fov_or_depth_grid']+=N-len(ix)
  if not len(ix):continue
  u=du[ix];v=dv[ix];ref=f['dep'][v,u];tol=.10+.045*z[ix];ok=f['valid'][v,u] & (abs(z[ix]-ref)<tol)
  # All four depth neighbours must support the same local surface: no foreground/background edge borrowing.
  for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:ok &= f['valid'][v+dy,u+dx] & (abs(f['dep'][v+dy,u+dx]-ref)<(.10+.045*ref))
  rejects['depth_or_edge_inconsistent']+=int((~ok).sum());ix=ix[ok]
  if not len(ix):continue
  vec=f['T'][:3,3]-world[ix];cos=(vec@q['normal'])/np.linalg.norm(vec,axis=1);s=cos*cos/(1+z[ix]*z[ix]*.06);rejects['grazing_or_backface']+=int((cos<.18).sum());s[cos<.18]=-1;scores[j,ix]=s;coords[j]=xy
 chosen=np.argsort(scores,axis=0)[-3:][::-1];color=np.zeros((N,3),np.float32);weight=np.zeros(N,np.float32);count=np.zeros(N,np.uint8);sources=set();face_source_counts={}
 for rank in range(3):
  for j in np.unique(chosen[rank]):
   ix=np.flatnonzero((chosen[rank]==j)&(scores[j]>=0)&(count<2))
   if not len(ix):continue
   f=frames[j];origin=Vector(f['T'][:3,3]);good=[]
   for k in ix:
    vec=Vector(world[k])-origin;dist=vec.length;hit=bvh.ray_cast(origin,vec.normalized(),dist+.03);exact_rays+=1
    if hit[2] is not None and owners[hit[2]]==q['oi'] and abs(hit[3]-dist)<.018:good.append(k)
   rejects['exact_visibility_rejected']+=len(ix)-len(good)
   if not good:continue
   ix=np.array(good);xy=coords[j][ix];xx=xy[:,0];yy=xy[:,1];x0=xx.astype(int);y0=yy.astype(int);dx=(xx-x0)[:,None];dy=(yy-y0)[:,None];im=f['im'];rgb=im[y0,x0]*(1-dx)*(1-dy)+im[y0,x0+1]*dx*(1-dy)+im[y0+1,x0]*(1-dx)*dy+im[y0+1,x0+1]*dx*dy
   # Do not average strongly different observed colours: retain better-scored source at disocclusions/specular changes.
   ok=(count[ix]==0)|(np.max(abs(rgb-color[ix]/np.maximum(weight[ix,None],1e-8)),axis=1)<.18);rejects['cross_view_colour_rejected']+=int((~ok).sum());ix=ix[ok];rgb=rgb[ok];xy=xy[ok]
   if not len(ix):continue
   wt=scores[j,ix];color[ix]+=rgb*wt[:,None];weight[ix]+=wt;count[ix]+=1;support_counts[j]+=len(ix);sources.add(int(j));face_source_counts[str(j)]=face_source_counts.get(str(j),0)+len(ix);key=str(j);box=[int(xy[:,0].min()),int(xy[:,1].min()),int(xy[:,0].max())+1,int(xy[:,1].max())+1]
   if key in source_boxes:old=source_boxes[key];source_boxes[key]=[min(old[0],box[0]),min(old[1],box[1]),max(old[2],box[2]),max(old[3],box[3])]
   else:source_boxes[key]=box
 good=weight>0;rgba=np.zeros((h*w,4),np.uint8);rgba[ids[good],:3]=np.uint8(np.clip(color[good]/weight[good,None]*255,0,255));rgba[ids[good],3]=255;tile=rgba.reshape(h,w,4);# Colour-only 2px gutter: fill RGB neighbours without promoting unknown alpha to supported.
 known=tile[:,:,3]>0
 for iteration in range(2):
  old_known=known.copy();old_rgb=tile[:,:,:3].copy()
  for dy,dx in [(-1,0),(1,0),(0,-1),(0,1)]:
   shifted=np.roll(old_known,(dy,dx),(0,1));rgbshift=np.roll(old_rgb,(dy,dx),(0,1))
   if dy<0:shifted[-1,:]=False
   if dy>0:shifted[0,:]=False
   if dx<0:shifted[:,-1]=False
   if dx>0:shifted[:,0]=False
   fill=(~known)&shifted;tile[:,:,:3][fill]=rgbshift[fill];known[fill]=True
 padded=np.pad(tile,((2,2),(2,2),(0,0)),mode='edge');pages[q['page']][q['y']-2:q['y']+h+2,q['x']-2:q['x']+w+2]=padded
 q['supported']=int(good.sum());q['valid_texels']=int(N);q['sources']=sorted(sources)
 summary.append({'object':visible[q['oi']].name,'polygon':q['pi'],'atlas':q['page'],'tile_xywh':[q['x'],q['y'],w,h],'surface_texels':N,'supported_texels':int(good.sum()),'unknown_texels':int(N-good.sum()),'source_frames':sorted(sources),'per_source_supported_assignments':face_source_counts})
 if qi%100==0:print('BAKE',qi,'/',len(plans),'seconds',round(time.time()-start,1),flush=True)
lighting_after={'world':sc.world.name if sc.world else None,'world_tree':str([(n.name,[(i.name,str(i.default_value)) for i in n.inputs if hasattr(i,'default_value')]) for n in sc.world.node_tree.nodes]) if sc.world and sc.world.use_nodes else '', 'lights':[(o.name,o.data.energy,list(o.data.color)) for o in sc.objects if o.type=='LIGHT'],'view_transform':sc.view_settings.view_transform,'exposure':sc.view_settings.exposure,'gamma':sc.view_settings.gamma,'look':sc.view_settings.look,'cycles_bounces':{k:getattr(sc.cycles,k) for k in ['max_bounces','diffuse_bounces','glossy_bounces','transparent_max_bounces']}}
assert lighting_after==lighting
textures=[]
for i,arr in enumerate(pages):
 path=out/'textures'/f'photo_atlas_{i:02d}.png';np.save(out/'textures'/f'photo_atlas_{i:02d}.npy',arr);subprocess.run(['/home/wqz/real2sim_fresh_20260921/runtime/venv/bin/python',str(R/'tools/image_io.py'),'encode',str(out/'textures'/f'photo_atlas_{i:02d}.npy'),str(path)],check=True);textures.append({'path':str(path),'sha256':sha(path),'width':SIZE,'height':SIZE,'supported_surface_texels':sum(q.get('supported',0) for q in plans if q['page']==i),'nonzero_alpha_including_filter_gutter':int((arr[:,:,3]>0).sum()),'note':'RGB source-photo appearance; alpha is support mask mixed into opaque BaseColor, never visibility/transparency'})
images=[bpy.data.images.load(t['path'],check_existing=False) for t in textures]
for im in images:im.colorspace_settings.name='sRGB';im.alpha_mode='CHANNEL_PACKED';im.pack()

def state_value(v):
 if isinstance(v,(str,bool,int,float)) or v is None:return v
 try:return list(v)
 except:return str(v)
def socket_graph(sock,seen=()):
 value={'default':state_value(sock.default_value) if hasattr(sock,'default_value') else None,'links':[]}
 for link in sock.links:
  node=link.from_node
  if node.name in seen:value['links'].append({'repeat':node.name});continue
  row={'node':node.name,'type':node.bl_idname,'output':link.from_socket.identifier,'inputs':{s.identifier:socket_graph(s,seen+(node.name,)) for s in node.inputs}}
  for attr in ['operation','blend_type','noise_dimensions','normalize','uv_map','projection','extension']:
   if hasattr(node,attr):row[attr]=state_value(getattr(node,attr))
  if getattr(node,'color_ramp',None):row['color_ramp']=[(float(x.position),list(x.color)) for x in node.color_ramp.elements]
  value['links'].append(row)
 return value
def nonbase_state(ps):return hashlib.sha256(json.dumps({s.identifier:socket_graph(s) for s in ps.inputs if s.name!='Base Color'},sort_keys=True).encode()).hexdigest()

materials={};byobj={};preservation=[]
for q in plans:
 if not q.get('supported'):continue
 o=visible[q['oi']];key=(q['mat'],q['page'])
 if key not in materials:
  orig=bpy.data.materials[q['mat']];mat=orig.copy();mat.name='PhotoBaked__'+q['mat']+'__atlas'+str(q['page']);ns=mat.node_tree.nodes;ps=next(n for n in ns if n.type=='BSDF_PRINCIPLED');output=next(n for n in ns if n.type=='OUTPUT_MATERIAL');base=tuple(ps.inputs['Base Color'].default_value)
  # Strict texture-only: preserve every original non-BaseColor graph and use original BaseColor as unsupported fallback.
  orig_base_links=[(l.from_node,l.from_socket) for l in ps.inputs['Base Color'].links]
  nonbase_before=nonbase_state(ps)
  uvn=ns.new('ShaderNodeUVMap');uvn.name='PhotoAtlasUV';uvn.uv_map='PhotoAtlas';tex=ns.new('ShaderNodeTexImage');tex.name='PhotoAtlasImage';tex.image=images[q['page']];tex.extension='EXTEND';tex.interpolation='Linear';mix=ns.new('ShaderNodeMixRGB');mix.name='PhotoSupportMix';mix.blend_type='MIX';mix.inputs[1].default_value=base;links=mat.node_tree.links
  if orig_base_links:links.new(orig_base_links[0][1],mix.inputs[1])
  links.new(uvn.outputs['UV'],tex.inputs['Vector']);links.new(tex.outputs['Alpha'],mix.inputs[0]);links.new(tex.outputs['Color'],mix.inputs[2]);links.new(mix.outputs[0],ps.inputs['Base Color']);mat['source_material_name']=orig.name
  nonbase_after=nonbase_state(ps);assert nonbase_before==nonbase_after
  preservation.append({'original_material':orig.name,'candidate_material':mat.name,'nonbase_graph_sha256_before':nonbase_before,'nonbase_graph_sha256_after':nonbase_after,'normal_bump_roughness_metallic_alpha_emission_preserved':True,'original_basecolor_fallback_link_preserved':bool(orig_base_links),'fallback_source_node':orig_base_links[0][0].name if orig_base_links else 'original_scene_linear_constant'})
  materials[key]=mat
 uv=o.data.uv_layers.get('PhotoAtlas') or o.data.uv_layers.new(name='PhotoAtlas');o.data.uv_layers.active=uv
 po=o.data.polygons[q['pi']]
 for loopindex,coord in zip(po.loop_indices,q['uv']):
  f=(coord-q['lo'])/q['extent'];U=(q['x']+f[0]*q['w'])/SIZE;V=1-(q['y']+f[1]*q['h'])/SIZE;uv.data[loopindex].uv=(float(U),float(V))
 mat=materials[key];slot=next((j for j,m in enumerate(o.data.materials) if m==mat),None)
 if slot is None:o.data.materials.append(mat);slot=len(o.data.materials)-1
 po.material_index=slot;byobj.setdefault(o.name,[]).append(q)
assert fingerprint()==before,'Geometry/transforms/visibility changed'
sc.render.threads_mode='FIXED';sc.render.threads=2;dest=out/'model.blend';bpy.ops.wm.save_as_mainfile(filepath=str(dest))
# Canonical actual material-scope declarations for read-only framework binding audit.
cal=[]
for o in visible:
 for mat in o.data.materials:
  if not mat:continue
  ps=next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None) if mat.use_nodes else None
  if ps is None:continue
  photo=mat.name.startswith('PhotoBaked__');texs=[n for n in mat.node_tree.nodes if n.type.startswith('TEX_') and n.type!='TEX_COORD'];proc=bool(texs) and not photo;basis='uv' if photo else 'world' if proc else 'none';kind='original' if photo else 'procedural' if proc else 'constant';entity=o.get('entity_id',o.get('furniture_id',o.name));metal=float(ps.inputs['Metallic'].default_value)
  cal.append({'entity':entity,'objects':[o.name],'material_names':[mat.name],'soft_surface':any(tag in o.name.lower() for tag in ['bag','sack','cloth','fabric']),'layers':{'macro_pattern':'multi-view photo colour' if photo else 'preserved original material','microstructure':'observed image detail; not measured BRDF','folds':'existing geometry unchanged','illumination':'source-photo illumination is baked; not intrinsic albedo'},'material_class':'metal' if metal>.5 else 'mixed' if metal>.05 else 'dielectric','parameter_basis':'original PBR roughness/metallic retained; texture source constrained by exact scene first-hit and shared DA3','texture_scope':{'source_kind':kind,'application':'local' if photo else 'whole_object' if proc else 'constant','mapping':basis,'uv_map':'PhotoAtlas' if photo else None,'sample_boxes':list(source_boxes.values()) if photo else [],'preserved_auxiliary_mapping':'original procedural world graph may remain for fallback and normal; this is not a claim that all inherited texture nodes use UV','target_surface_support_file':'surface_support.json','source_samples':[{'frame':i,'sha256':frames[i]['sha256'],'box':source_boxes[str(i)]} for i in range(36) if str(i) in source_boxes] if photo else [],'uncertain_completion':'Unsupported texels retain the exact original BaseColor graph; completely unsupported faces retain original material. No unknown region counted as observed.'},'pbr_parameters':{mat.name:{'Roughness':float(ps.inputs['Roughness'].default_value),'Metallic':metal}},'whole_object_evidence':[]})
(out/'material_calibration.json').write_text(json.dumps({'status':'binding declaration; visual appearance review pending','materials':cal,'source_condition':'same36 mapping RGB/K/T + shared predictedDA3; no heldout/GT','photo_baked_color_not_albedo':True},indent=2))
receipt={'base_model':a.model,'base_sha256':basehash,'candidate_model':str(dest),'candidate_sha256':sha(dest),'geometry_transform_visibility_fingerprint_before':before,'geometry_transform_visibility_fingerprint_after':fingerprint(),'geometry_unchanged':True,'nonbase_material_preservation':preservation,'lighting_before':lighting,'lighting_after':lighting_after,'lighting_unchanged':lighting_after==lighting,'model_from_input':G.tolist(),'source_packet_sha256':sha(IN/'packet.json'),'reference_manifest_sha256':sha(IN/'depth_reference/manifest.json'),'source_frames':[{'index':f['index'],'sha256':f['sha256'],'supported_assignments':int(support_counts[i])} for i,f in enumerate(frames)],'textures':textures,'mapped_objects':len(byobj),'mapped_surface_polygons':sum(bool(q.get('supported')) for q in plans),'surface_texels':sum(s['surface_texels'] for s in summary),'supported_texels':sum(s['supported_texels'] for s in summary),'unknown_texels':sum(s['unknown_texels'] for s in summary),'reject_counts':rejects,'exact_full_scene_visibility_rays':exact_rays,'recipe':{'normal_cos_min':.18,'source_boundary_pixels':4,'DA3_absolute_plus_relative_tolerance':'.10+.045*z metres','DA3_four_neighbour_edge_gate':True,'exact_BVH_same_object_distance_tolerance_m':.018,'top_candidate_views':3,'max_blended_views':2,'colour_disagreement_gate_sRGB':.18,'mask_encoding':'PNG alpha 0/255, CHANNEL_PACKED data channel independent of sRGB RGB; mask controls BaseColor Mix only','uv_sampling':'polygon-local planar UV, atlas V=1-image_y; surface samples at texel centres','padding':'2px colour-only dilation into unknown RGB without changing support alpha, plus2px edge-extruded non-surface filtering gutter; no cross-island borrowing','world_surface_UV_atlas':True,'photo_signal_target':'opaque Principled BaseColor','strict_texture_only':True,'original_nonbase_graphs':'all preserved exactly, including bump/normal/roughness/metallic/alpha/emission','unsupported_fallback':'original BaseColor graph remains connected as fallback; no new unobserved appearance invented','opacity_visibility_unchanged':True,'no_billboards_or_background_substitution':True},'limitations':['Photo-baked observed radiance contains source light/shadow/reflections; not de-lit physical reflectance','UV seams and calibration/geometry/DA3 discrepancies may limit texture support','Unknown texels use the preserved original BaseColor graph, not observed surface recovery','Original normal/bump/roughness/metallic/alpha/emission graphs preserved; inherited world-coordinate procedural fallback may not follow object deformation; photo layer itself uses named UV.'],'seconds':time.time()-start};(out/'review_receipt.json').write_text(json.dumps(receipt,indent=2));(out/'surface_support.json').write_text(json.dumps(summary,indent=2));assert sha(a.model)==basehash;sys.path.insert(0,str(R));import blender_appearance;aud=blender_appearance.audit(out);print('DONE',dest,'support',receipt['supported_texels'],'/',receipt['surface_texels'],'audit',aud['status'],'seconds',receipt['seconds'],flush=True)
