"""Coherent case-specific assemblies driven by the recorded observation/fit files.
Executed by build_scene.py in its construction namespace. Each part has one owner;
every intended joint has a shared world anchor, never a screen-space connection.
"""
import hashlib
fitpath=ROOT/'case/furniture_parameters.json';obspath=ROOT/'case/furniture_observation.json'
fit=json.loads(fitpath.read_text());observation=json.loads(obspath.read_text())
assert fit['source_observation_sha256']==hashlib.sha256(obspath.read_bytes()).hexdigest()
assert fit['calibration_sha256']==hashlib.sha256((ROOT/'case/calibration_initial.json').read_bytes()).hexdigest()
assert observation['source_sha256']==hashlib.sha256((ROOT/observation['source_image']).read_bytes()).hexdigest()
assert fit['model_version']==version
assemblies=[]
def assembly(e,pars):
 x,y,yaw=pars[:3];c,s=math.cos(yaw),math.sin(yaw)
 def transform(p):
  a,b,z=p;return np.array([x+c*a-s*b,y+s*a+c*b,z])
 spec=dict(entity=e,frame=dict(position=[x,y,0],yaw_rad=yaw),parts=[],joints=[],floor_supports=[],source_observation_ids=fit['targets'][e]['observation_ids'],fit=fit['targets'][e],assumptions=fit['targets'][e]['uncertainty'])
 assemblies.append(spec)
 def register(o,role,entity=None):
  o.name=e+'__'+role;o['furniture_id']=e;o['part_id']=role
  spec['parts'].append(dict(id=role,object=o.name,entity=entity or e));return o
 def slab(role,p,dim,m,bevel=.002):
  o=box(e,transform(p),dim,m,bevel);o.rotation_euler.z=yaw;register(o,role);proxy.setdefault(e,[]).append(dict(shape='box',position=transform(p).tolist(),dimensions=list(dim),yaw=yaw));return o
 def beam(role,a,b,width,depth,m):
  a,b=transform(a),transform(b);v=Vector(b-a);o=box(e,(a+b)/2,(width,depth,v.length),m,.0015);o.rotation_euler=v.to_track_quat('Z','Y').to_euler();register(o,role);radius=min(width,depth)*.46;axis=(b-a)/np.linalg.norm(b-a);proxy.setdefault(e,[]).append(dict(shape='capsule',**{'from':(a+radius*axis).tolist(),'to':(b-radius*axis).tolist(),'radius':radius}));return o
 def joint(a,b,p,kind='join'):
  spec['joints'].append(dict(parts=[a,b],anchor_world=transform(p).tolist(),kind=kind,tolerance_m=.008))
 def floor(role,p):spec['floor_supports'].append(dict(part=role,point_world=transform(p).tolist(),plane_z=0,tolerance_m=.004))
 return spec,transform,register,slab,beam,joint,floor

p=fit['targets']['table']['parameters'];tx,ty,ta,tw,tl,th=p
sp,T,reg,slab,beam,joint,floor=assembly('table',p)
for lm in sp['fit']['landmarks']:
 lm['part']='top' if lm['landmark'].startswith('top_') else ['leg_near_left','leg_far_left','leg_far_right','leg_near_right'][int(lm['landmark'].split('_')[-1])]
slab('top',(0,0,th-.011),(tw,tl,.022),topmat,.004)
cross_z=.40
for sy,end in [(-1,'near'),(1,'far')]:
 ytop=sy*tl*.46;yfoot=sy*tl*.43
 frac=(cross_z-.002)/(th-.021-.002);cy=yfoot*(1-frac)+ytop*frac;wx=tw*.43*(1-frac)+tw*.40*frac
 for sx,side in [(-1,'left'),(1,'right')]:
  role='leg_'+end+'_'+side;bottom=(sx*tw*.43,yfoot,.002);top=(sx*tw*.40,ytop,th-.017)
  beam(role,bottom,top,.029,.028,wood);floor(role,bottom);joint(role,'top',top)
  joint(role,'cross_'+end,(sx*wx,cy,cross_z))
 beam('cross_'+end,(-wx,cy,cross_z),(wx,cy,cross_z),.032,.028,wood)
 sp.setdefault('cross_centers',[]).append([0,cy,cross_z]);joint('cross_'+end,'long_stretcher',(0,cy,cross_z))
beam('long_stretcher',sp['cross_centers'][0],sp['cross_centers'][1],.032,.034,wood)
for sy,end in [(-1,'near'),(1,'far')]:
 a=(0,sy*tl*.29,th-.017);b=(0,sy*tl*.12,cross_z);beam('brace_'+end,a,b,.025,.025,wood);joint('brace_'+end,'top',a);joint('brace_'+end,'long_stretcher',b)
# Crossbars are separate parts, not the union AABB of the table.
for part in sp['parts']:
 if 'cross_' in part['id'] or part['id']=='long_stretcher':
  o=bpy.data.objects[part['object']];a,b=[o.matrix_world@Vector((0,0,z)) for z in [-o.dimensions.z/2,o.dimensions.z/2]]
  # Visual structure audit is mesh based; capsule collision is only a dynamics surrogate.

for e in ['chair_near','chair_far']:
 p=fit['targets'][e]['parameters'];x,y,yaw,w,d,h,bh=p;sp,T,reg,slab,beam,joint,floor=assembly(e,p)
 signs=[(-1,1),(1,1),(1,-1),(-1,-1)] if e=='chair_far' else [(1,-1),(-1,-1),(-1,1),(1,1)]
 for lm in sp['fit']['landmarks']:
  sx,sy=signs[int(lm['landmark'].split('_')[-1])];side='left' if sx<0 else 'right';end='front' if sy<0 else 'rear'
  lm['part']='pad' if lm['landmark'].startswith('seat_') else ('back_'+side+'_post' if lm['landmark'].startswith('back_post_') else end+'_'+side+'_leg')
 board_top=h-.030;seatq=[[-w/2,-d/2,board_top],[w/2,-d/2,board_top],[w/2,d/2,board_top],[-w/2,d/2,board_top]]
 board=mesh(e,[T(q).tolist() for q in seatq],[(0,1,2,3)],wood,.019,.004);board.modifiers['physical_thickness'].offset=-1;reg(board,'seat_board')
 padq=[[-w/2+.004,-d/2+.004,h],[w/2-.004,-d/2+.004,h],[w/2-.004,d/2-.035,h],[-w/2+.004,d/2-.035,h]]
 pad=mesh(e+'_cushion',[T(q).tolist() for q in padq],[(0,1,2,3)],green,.030,.009);pad.modifiers['physical_thickness'].offset=-1;reg(pad,'pad',e+'_cushion');joint('pad','seat_board',(0,0,board_top),'support_contact')
 record(e+'_cushion','seat_cushion',.70,'Observed thin raised green pad; foam interpretation and stiffness assumed; rigid frame dimensions jointly fitted to part observations.')
 legx=w/2-.020;legy=d/2-.020;railspan=w/2+.070;rear_x=w/2-.035
 def railpoint(xx):return [xx,d/2+.008-.25*(abs(xx)/railspan)**4,bh-.014*(abs(xx)/railspan)**2]
 rear_y=railpoint(rear_x)[1]
 for sx,side in [(-1,'left'),(1,'right')]:
  for sy,end in [(-1,'front'),(1,'rear')]:
   role=end+'_'+side+'_leg';bottom=(sx*legx,sy*legy,.002);top=(sx*legx,sy*legy,board_top-.005)
   beam(role,bottom,top,.022,.023,wood);floor(role,bottom);joint(role,'seat_board',top)
   apron_z=board_top-.035
   for apr in ([('back' if end=='rear' else 'front')+'_apron',side+'_apron']):joint(role,apr,(sx*legx,sy*legy,apron_z))
  role='back_'+side+'_post';a=(sx*legx,legy,board_top-.006);b=railpoint(sx*rear_x);b[2]-=.010
  beam(role,a,b,.023,.021,wood);joint(role,'rear_'+side+'_leg',a);joint(role,'seat_board',a);joint(role,'back_rail',b)
 # Aprons meet at legs, outside the pad and below the seat.
 z=board_top-.035
 slab('front_apron',(0,-legy,z),(2*legx,.019,.034),wood)
 slab('back_apron',(0,legy,z),(2*legx,.019,.034),wood)
 slab('left_apron',(-legx,0,z),(.019,2*legy,.034),wood)
 slab('right_apron',(legx,0,z),(.019,2*legy,.034),wood)
 for apr,px,py in [('front_apron',0,-legy),('back_apron',0,legy),('left_apron',-legx,0),('right_apron',legx,0)]:joint(apr,'seat_board',(px,py,board_top-.019),'support_contact')
 # A closed, vertically oriented bowed wood strip (not a cylinder or an armrest).
 vs=[];fs=[];N=40
 for i in range(N+1):
  xx=-railspan+2*railspan*i/N;pt=np.array(railpoint(xx));der=-1.0*np.sign(xx)*abs(xx)**3/railspan**4;normal=np.array([-der,1,0]);normal/=np.linalg.norm(normal)
  for dn,dz in [(-.010,-.013),(.010,-.013),(.010,.013),(-.010,.013)]:vs.append(T(pt+normal*dn+[0,0,dz]).tolist())
 for i in range(N):
  for k in range(4):a=i*4+k;b=i*4+(k+1)%4;fs.append((a,b,b+4,a+4))
 fs.extend([(3,2,1,0),(N*4,N*4+1,N*4+2,N*4+3)]);reg(mesh(e,vs,fs,wood,0,.0015),'back_rail')
 # Intended apron corner contacts are named; all other unexpected intersections remain errors.
 for a,b,xx,yy in [('front_apron','left_apron',-legx,-legy),('front_apron','right_apron',legx,-legy),('back_apron','left_apron',-legx,legy),('back_apron','right_apron',legx,legy)]:joint(a,b,(xx,yy,z))
 # Uprights meet the rear legs/seat, not the apron below them. Do not invent
 # direct joint edges merely because parts share a similar projected position.
 # Structural seat collision supports the volume; legs remain separate.
 proxy[e].append(dict(shape='box',position=T((0,0,board_top-.010)).tolist(),dimensions=[w,d,.018],yaw=yaw))
 entities[e]['kind']='wooden_chair';entities[e]['evidence']=['furniture_observation.json: '+', '.join(sp['source_observation_ids']),'Single local rigid frame, shared chair family shape; rear posts connect to the rear edge. Hidden joinery is assumed.']
entities['table']['kind']='trestle_table';entities['table']['evidence']=['furniture_observation.json: '+', '.join(fit['targets']['table']['observation_ids']),'Rectangular top, paired end trestles with connected crossbars and longitudinal brace; hidden joinery assumed.']
furniture_structure=dict(schema='real2sim.assembly/1',model_version=version,observation_sha256=hashlib.sha256(obspath.read_bytes()).hexdigest(),parameter_sha256=hashlib.sha256(fitpath.read_bytes()).hexdigest(),assemblies=assemblies,unexpected_interpenetration_tolerance_m=.002,acceptance=observation['acceptance_before_fit'])
(OUT/'furniture_structure.json').write_text(json.dumps(furniture_structure,indent=2));(OUT/'furniture_observation.json').write_bytes(obspath.read_bytes());(OUT/'furniture_parameters.json').write_bytes(fitpath.read_bytes())
