import pathlib,json,math,copy,numpy as np
R=pathlib.Path(__file__).resolve().parents[1];L=json.loads((R/'versions/v1/layout.json').read_text());L['version']=2
O={o['id']:o for o in L['objects']}
def box(o,n,c,s,m,rot=None):
 p={'name':o['id']+'__'+n,'type':'box','center':list(c),'size':list(s),'material':m}
 if rot:p['rotation']=rot
 o['parts'].append(p)
def mesh(o,n,v,f,m):o['parts'].append({'name':o['id']+'__'+n,'type':'mesh','vertices':v,'faces':f,'material':m})
def cyl(o,n,c,r,d,m,rot=None):
 p={'name':o['id']+'__'+n,'type':'cylinder','center':list(c),'radius':r,'depth':d,'material':m}
 if rot:p['rotation']=rot
 o['parts'].append(p)
def proxy(o,c,s):
 L['colliders']=[k for k in L['colliders'] if k['object_id']!=o['id']];L['colliders'].append({'name':'COLLIDER__'+o['id'],'object_id':o['id'],'shape':'box','center':list(c),'size':list(s),'physics':'static conservative proxy; physical parameters unmeasured','exclude_from_evaluation':True})
# 1. Cut out actual sloping cab surface; rebuild surrounding frame and exterior glazing.
o=O['delivery_truck'];cab=next(p for p in o['parts'] if p['name'].endswith('__cab'));cab['faces']=[f for f in cab['faces'] if f!=[3,4,9,8]];o['parts']=[p for p in o['parts'] if not p['name'].endswith('__windshield')]
cx=-5.64
def slope(x,z,out=0):return [cx+x,8.65+(z-1.1)*(.55/.9)-out,z]
zlo=1.24;zhi=1.91;half=.84
mesh(o,'windshield',[slope(-half,zlo,.006),slope(half,zlo,.006),slope(half,zhi,.006),slope(-half,zhi,.006)],[[0,1,2,3]],'glass')
mesh(o,'windshield_bottom_frame',[slope(-.96,1.1),slope(.96,1.1),slope(.96,zlo),slope(-.96,zlo)],[[0,1,2,3]],'door_white')
mesh(o,'windshield_top_frame',[slope(-.96,zhi),slope(.96,zhi),slope(.96,2),slope(-.96,2)],[[0,1,2,3]],'door_white')
for side in [-1,1]:mesh(o,'windshield_side_frame_'+str(side),[slope(side*half,zlo),slope(side*.96,zlo),slope(side*.96,zhi),slope(side*half,zhi)],[[0,1,2,3]],'door_white')
# 2. Two separate column contact footprints, same rigid scene gauge.
def clip(poly):
 for axis,val,g in [(0,-.5,True),(0,.5,False),(1,.07,True),(1,2.18,False)]:
  out=[]
  for a,b in zip(poly,poly[1:]+poly[:1]):
   ia=a[axis]>=val if g else a[axis]<=val;ib=b[axis]>=val if g else b[axis]<=val
   if ia:out.append(a)
   if ia!=ib:
    t=(val-a[axis])/(b[axis]-a[axis]);out.append([a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])])
  poly=out
  if not poly:return []
 return poly
def column(o,x,y,sx,sy):
 o['parts']=[];box(o,'body',[x,y,2.3],[sx,sy,4.6],'white_wall');box(o,'yellow_base',[x,y,1.12],[sx+.008,sy+.008,2.12],'yellow')
 for face in range(4):
  for j in range(-5,10):
   a=j*.46;poly=clip([[-.5,a-.5],[.5,a+.5],[.5,a+.73],[-.5,a-.27]])
   if not poly:continue
   vs=[]
   for u,z in poly:
    if face<2:vs.append([x+(-1 if face==0 else 1)*(sx/2+.005),y+u*sy,z])
    else:vs.append([x+u*sx,y+(-1 if face==2 else 1)*(sy/2+.005),z])
   mesh(o,f'stripe_{face}_{j}',vs,[list(range(len(vs)))],'dark')
 proxy(o,[x,y,2.3],[sx,sy,4.6]);o['evidence_frames']=[16,17,18,19];o['provenance']='two RGB-observed distinct support members; front faces depth-verified in16/17, unseen cross-section depth inferred'
column(O['center_column'],-4.36,1.20,.60,.58)
o=copy.deepcopy(O['center_column']);o['id']='center_column_adjacent';L['objects'].append(o);O[o['id']]=o;column(o,-4.32,.63,.56,.33)
# 3. Tapered closed-thickness wall components, open interior and rim/feet.
for k,cy in enumerate([10.5,13.15]):
 o=O[f'green_skip_{k}'];o['parts']=[];cx=2.65;tx=2.3;ty=2.3;bx=2.00;by=1.40;zb=.21;zt=1.51;t=.055
 lower=[[-bx/2,-by/2],[bx/2,-by/2],[bx/2,by/2],[-bx/2,by/2]];upper=[[-tx/2,-ty/2],[tx/2,-ty/2],[tx/2,ty/2],[-tx/2,ty/2]]
 for j in range(4):
  k2=(j+1)%4;vs=[]
  for inside in [False,True]:
   for ring,z in [(lower,zb),(upper,zt)]:
    for kk in [j,k2]:
     x,y=ring[kk];x-=math.copysign(t,x) if inside else 0;y-=math.copysign(t,y) if inside else 0;vs.append([cx+x,cy+y,z])
  mesh(o,f'tapered_wall_{j}',vs,[[0,1,3,2],[4,6,7,5],[0,4,5,1],[2,3,7,6],[0,2,6,4],[1,5,7,3]],'green')
 box(o,'floor',[cx,cy,zb],[bx,by,.10],'green')
 for s in [-1,1]:
  box(o,f'long_upper_rim_{s}',[cx+s*tx/2,cy,zt],[.13,ty+.12,.11],'green');box(o,f'end_upper_rim_{s}',[cx,cy+s*ty/2,zt],[tx+.12,.13,.11],'green')
  for j in [-.45,.45]:box(o,f'foot_{s}_{j}',[cx+s*.73,cy+j,.095],[.18,.28,.19],'green')
  box(o,f'base_runner_{s}',[cx+s*.73,cy,.14],[.18,1.35,.10],'green')
 proxy(o,[cx,cy,.8],[tx+.13,ty+.13,1.6]);o['evidence_frames']=[8,9,12];o['provenance']='RGB-observed tapered open skip topology and depths at top/bottom; hidden inner walls and taper details inferred'
# 4. Lumber endpoints fitted jointly using explicit correspondence triangulation.
o=O['lumber_trolley'];o['parts']=[];cx=.40;cy=-7.14
box(o,'frame_front',[cx,cy+.36,.27],[1.95,.055,.075],'blue_steel');box(o,'frame_rear',[cx,cy-.48,.27],[1.95,.055,.075],'blue_steel')
for xx in [-.48,1.28]:
 box(o,f'frame_cross_{xx}',[xx,cy-.06,.27],[.055,.88,.075],'blue_steel');box(o,f'upright_{xx}',[xx,-7.72,1.02],[.045,.055,1.60],'blue_steel')
 for yy in [cy-.33,cy+.27]:cyl(o,f'caster_{xx}_{yy}',[xx,yy,.145],.135,.06,'rubber',[math.pi/2,0,0]);box(o,f'caster_fork_{xx}_{yy}',[xx,yy,.245],[.09,.08,.16],'steel')
for z in [.58,1.37]:box(o,f'rack_horizontal_{z}',[.40,-7.72,z],[1.80,.045,.045],'blue_steel')
for j in range(11):
 frac=j/10;left=2.59+.35*frac+([0,.05,-.04][j%3]);right=-1.40+.31*frac+([0,-.03,.02][j%3]);ya=-6.95;yb=-6.72;xc=(left+right)/2;yc=(ya+yb)/2;length=math.hypot(left-right,ya-yb);angle=math.atan2(ya-yb,left-right)
 box(o,f'lumber_{j}',[xc,yc,.46+j*.045],[length,.40,.042],'light_wood',[0,0,angle])
box(o,'restraining_strap',[.40,-6.60,.72],[.035,.015,.68],'dark');proxy(o,[.7,-7.18,.95],[4.5,1.2,1.9]);o['provenance']='frame24/28 RGB endpoint triangulation and interior depth; low-res thin-edge DA3 and rejected correspondence preserved; individual plank ends inferred'
# 5. Irregular independently editable bulk-bag meshes and observed nonuniform occupancy.
o=O['storage_shelf'];o['parts']=[p for p in o['parts'] if '__bag_' not in p['name']]
def bag(name,x,y,z,w,d,h,seed):
 rng=np.random.default_rng(seed);N=12;vs=[];rings=[(0,.68),(.05,.90),(.25,1.0),(.72,.91),(.91,.57),(1,.24)]
 for zz,rad in rings:
  for a in range(N):
   th=2*math.pi*a/N;noise=1+rng.uniform(-.09,.09);vs.append([x+math.cos(th)*w*.5*rad*noise,y+math.sin(th)*d*.5*rad*noise,z+zz*h+rng.uniform(-.012,.012)])
 fs=[list(range(N-1,-1,-1)),list(range((len(rings)-1)*N,len(rings)*N))]
 for j in range(len(rings)-1):
  for a in range(N):b=(a+1)%N;fs.append([j*N+a,j*N+b,(j+1)*N+b,(j+1)*N+a])
 mesh(o,name,vs,fs,'bag');cyl(o,name+'_tied_neck',[x,y,z+h+.018],w*.08,.065,'bag')
for lev,(z,positions) in enumerate([(.14,[6.1,6.6,7.08,7.59,8.10,8.68,9.20,9.78]),(1.05,[6.05,6.53,7.06,7.63,8.12,8.69,9.24,9.84,10.39,10.95]),(2.02,[6.11,6.74,7.38,8.07,8.65,9.43,10.13,10.8,11.51])]):
 for j,x in enumerate(positions):bag(f'filled_sack_{lev}_{j}',x,9.99+(.055 if j%2 else 0),z,.51+(j%3)*.045,.68,.59+(j%3)*.035,lev*100+j)
# Left top shelf has layered flat sacks; far-right has a separate bulk bag.
for j in range(4):
 for k in range(2):bag(f'top_flat_sack_{j}_{k}',6.35+k*.77,10.10,3.06+j*.14,.82,.67,.16,500+j*2+k)
bag('top_bulk_sack',11.84,10.18,3.07,.82,.75,.68,900)
o['provenance']='shelf beams/uprights unchanged; separately editable filled-bag silhouettes and nonuniform level occupancy observed in4/8/9; hidden sack count and folds inferred';o['evidence_frames']=[4,6,7,8,9]
# Update portable semantic component map from actual parameterized parts.
objs=[]
for o in L['objects']:
 pts=[]
 for p in o['parts']:
  if p['type']=='mesh':pts.extend(p['vertices'])
  elif p['type']=='box':
   c=np.array(p['center']);s=np.array(p['size'])/2;angle=p.get('rotation',[0,0,0])[2];rot=np.array([[math.cos(angle),-math.sin(angle),0],[math.sin(angle),math.cos(angle),0],[0,0,1]])
   pts.extend([c+rot@(s*np.array([i,j,k])) for i in [-1,1] for j in [-1,1] for k in [-1,1]])
  else:
   c=np.array(p['center']);s=np.array([p['radius'],p['radius'],p['depth']/2]);rot=p.get('rotation',[0,0,0])
   if rot[0]:s=np.array([p['radius'],p['depth']/2,p['radius']])
   if rot[1]:s=np.array([p['depth']/2,p['radius'],p['radius']])
   pts.extend([c-s,c+s])
 a=np.array(pts);objs.append({k:v for k,v in o.items() if k!='parts'}|{'components':[p['name'] for p in o['parts']],'dimensions':(a.max(0)-a.min(0)).tolist(),'bounds':[a.min(0).tolist(),a.max(0).tolist()],'measurement_source':'analysis/measurements.json,point_measurements.json,v2_measurements.json; hidden dimensions explicitly inferred'})
(R/'layout.json').write_text(json.dumps(L,indent=2));(R/'objects.json').write_text(json.dumps({'objects':objs},indent=2));(R/'colliders.json').write_text(json.dumps({'colliders':L['colliders'],'physical_parameters':'unmeasured, no physical acceptance'},indent=2))
m=json.load(open(R/'modelling_manifest.json'));m.update(revisions=2,status='v2_ready_for_checks',quality_status='LIMITED_PENDING_INDEPENDENT_REVIEW');(R/'modelling_manifest.json').write_text(json.dumps(m,indent=2))
changes=[{'issue':1,'change':'cut cab slope face, exterior windshield and separate window borders','evidence':'review triangle first-hit audit12, RGB12/13; prior glass117.7..146.1mm occluded','assumption':'same cab shape retained, glazing mount6mm exterior inference'},{'issue':2,'change':'center_column x-4.36,y1.2,sx0.60,sy0.58; adjacent x-4.32,y0.63,sx0.56,sy0.33, separate contacts/gap','evidence':'depth points16/17 fronts~-4.04, ybands0.63/1.2; v1frame16 middle signedmedian+0.216m','assumption':'unseen cross-section depth inferred; far truck column unchanged'},{'issue':3,'change':'replace vertical walls with open tapered shells top2.3x2.3,bottom2.0x1.4; rim0.13, thickness0.055, independent feet','evidence':'RGB8/9/12 silhouette, top depthz1.45..1.49 and bottomz0.125..0.183','assumption':'taper slope hidden side inferred; v1centres retained'},{'issue':4,'change':'load endpoints shorten/angle/varied, cartcenterx0.4 from0.95, rearposts y-7.72, add connected upper frame','evidence':'RGB24/28 triangulation retained residual1.3..3px for accepted points and10px rejected; internal depth samples','assumption':'per-plank interpolation inferred; no camera change'},{'issue':5,'change':'uniform boxes replaced by irregular ring-surface filled sacks; unequal level occupancy; top layered flat sacks plus separated bulkbag','evidence':'RGB4/8/9 visible shelf occupancy; beams/uprights unchanged','assumption':'hidden sacks and exact folds unobservable, approximate'}]
a=json.load(open(R/'iteration_log.json'));a.append({'version':2,'action':'five independent reviewer repairs','changes':changes,'status':'await_checks','input_reference_unchanged':True,'camera_gauge_unchanged':True});(R/'iteration_log.json').write_text(json.dumps(a,indent=2));(R/'analysis/v2_change_evidence.json').write_text(json.dumps(changes,indent=2));print('V2_LAYOUT',len(objs),sum(len(o['parts']) for o in L['objects']))
