"""Recover v1 by reversing this run's recorded v2 edits; no external history/assets."""
from pathlib import Path
import hashlib,json
root=Path('/home/wqz/real2sim_agent_compare_20261003/OURS')
s=(root/'models/v2/build_scene.py').read_text()
s=s.replace('import bpy, bmesh, json, sys, math, random, hashlib','import bpy, json, sys, math, random, hashlib')
s=s.replace("mat('floor',(.19,.175,.125),.74,noise=.30);mat('ceiling',(.20,.195,.17),.9,noise=.23)","mat('floor',(.28,.265,.21),.7,noise=.28);mat('ceiling',(.17,.165,.14),.9,noise=.32)")
def span(a,b,new=''):
 global s
 i=s.index(a);j=s.index(b,i);s=s[:i]+new+s[j:]
span("materials['wood_y']=", "materials['light'].node_tree")
span(" if owner=='wood_crates':",' o.name=name;')
s=s.replace(" if ma=='wood' and dim[1]>dim[0]*2:ma='wood_y'\n",'')
s=s.replace(";bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(me);bm.free()",'')
s=s.replace('def slab_sections(name,sections,center,ma,owner,window_segment=None):','def slab_sections(name,sections,center,ma,owner):')
s=s.replace("  for j in range(4):\n   if i==window_segment and j==2:continue\n   faces.append((4*i+j,4*i+(j+1)%4,4*(i+1)+(j+1)%4,4*(i+1)+j))","  for j in range(4):faces.append((4*i+j,4*i+(j+1)%4,4*(i+1)+(j+1)%4,4*(i+1)+j))")
s=s.replace("box('cage_upper_wall',(-4.2,-8.0,3.49),(19.3,.22,2.38),'wall')","box('cage_upper_wall',(-5.95,-8.0,3.49),(15.8,.22,2.38),'wall')")
span("box('entrance_soffit'", "box('garage_reveal'")
span("box('main_dock_sidewall'", "box('loading_platform'")
span("for j,(x,y,dx,dy) in enumerate(", '\n# Seven sliding', """for j,(x,y,dx,dy) in enumerate([(-4.3,10.7,.58,.75),(-4.25,1.06,.56,.68),(-4.21,.52,.40,.37),(-4.25,-7.8,.58,.62),(5.35,.82,.48,.6),(5.45,9.5,.5,.6),(-13.5,.35,.5,.5),(-13.5,-7.55,.4,.45)]):
 owner='column_'+str(j);box(owner+'_lower',(x,y,1.08),(dx,dy,2.16),'hazard',owner);box(owner+'_upper',(x,y,3.42),(dx,dy,2.52),'wall',owner)
""")
s=s.replace("for j in range(7):box(f'door_hanger{j}',(doorx,dstart+(j+.5)*pw,4.08),(.08,.06,.20),'steel','garage_door')\n",'')
span('  for k in range(3):box(f\'rack_pallet_joist_', '\n# Two open wooden', """  for k in range(6):box(f'rack_pallet_{level}_{bay}_{k}',(cx,ry-.5+k*.20,z+.14),(2.6,.16,.09),'lumber','storage_rack')
  if level<3:
   for bag in range(5):
    x=cx+(bag-2)*.5;y=ry-.1;h=.85+random.uniform(-.08,.05)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,location=(x,y,z+.16+h*.5));o=bpy.context.object;o.scale=(.24,.44,h*.54)
    for v in o.data.vertices:
     v.co.x*=1+random.uniform(-.08,.08);v.co.y*=1+random.uniform(-.09,.09)
    finish(o,f'rack_sack_{level}_{bay}_{bag}','storage_rack','bag','irregular_bag_mesh')
""")
s=s.replace("beam('trailer_towA',(10.25,7.3,.52),(8.5,8.12,.52),.09,'steel','white_trailer');beam('trailer_towB',(10.25,8.95,.52),(8.5,8.12,.52),.09,'steel','white_trailer')", "beam('trailer_towA',(10.15,7.25,.43),(8.5,8.12,.43),.09,'steel','white_trailer');beam('trailer_towB',(10.15,9,.43),(8.5,8.12,.43),.09,'steel','white_trailer')")
s=s.replace(",'white_van',window_segment=2)",",'white_van')")
span('windshield=[', 'for s in [-1,1]:', "mesh('van_windshield',[(vx-.84,vy-1.03,1.55),(vx+.84,vy-1.03,1.55),(vx+.81,vy-.30,2.12),(vx-.81,vy-.30,2.12)],[(0,1,2,3)],'glass','white_van')\n")
s=s.replace(" beam('van_mirror_stem'+str(s),(vx+s*.96,vy-.65,1.5),(vx+s*1.16,vy-.65,1.57),.045,'rubber','white_van')\n",'')
s=s.replace(",'black_car',window_segment=0)",",'black_car')")
span('rear=[','for s in [-1,1]:',"mesh('car_rear_glass',[(cx-.7,cy-1.62,1.04),(cx+.7,cy-1.62,1.04),(cx+.61,cy-.96,1.43),(cx-.61,cy-.96,1.43)],[(0,1,2,3)],'glass','black_car')\n")
s=s.replace('z=.32+layer*.046','z=.35+layer*.055')
span("box('compactor_body'", "box('fire_cabinet'", """box('compactor_body',(-20.5,-1.55,1.36),(2.5,2.3,2.72),'steel',bevel=.06)
box('compactor_hopper',(-20.5,-1.55,3.0),(2.7,2.5,1.0),'steel')
box('compactor_yellow_front',(-19.21,-1.55,1.2),(.1,1.8,1.6),'yellow')
""")
s=s.replace("box(owner,(x,y,4.52),(.095,3.4,.075),'light')", "box(owner,(x,y,4.52),(3.4,.095,.075),'light')")
s=s.replace('ld.size=.16;ld.size_y=3.4','ld.size=3.4;ld.size_y=.16')
if "for ob in list(sc.objects):\n if ob.type=='FONT':" in s:span("for ob in list(sc.objects):\n if ob.type=='FONT':",'cameras=[]')
out=root/'models/v1/build_scene_recovered.py';out.write_text(s)
compile(s,str(out),'exec')
receipt=dict(status='executed_source_recovered_from_this_run_edits',source=str(out),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),pre_run_source_hash_recorded=False,geometry_reproduction_check='pending; no new fitting trial',note='Original v1 build command was reviewed; this reverses only the subsequent recorded v2 source edits. Original model and checks were never overwritten.')
(root/'models/v1/source_recovery.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
