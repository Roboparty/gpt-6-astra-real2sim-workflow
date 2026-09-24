import bpy,json,hashlib,sys
from pathlib import Path
def geometry_hash():
 data=[]
 for o in sorted(bpy.context.scene.objects,key=lambda o:o.name):
  if o.type not in ['MESH','CURVE','CAMERA']:continue
  item=[o.name,o.type,list(sum((list(row) for row in o.matrix_world),[]))]
  if o.type=='MESH':item.extend([[list(v.co) for v in o.data.vertices],[list(p.vertices) for p in o.data.polygons]])
  if o.type=='CURVE':item.append([[list(p.co) for p in sp.bezier_points] for sp in o.data.splines])
  if o.type=='CAMERA':item.extend([o.data.lens,o.data.shift_x,o.data.shift_y])
  data.append(item)
 return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
if __name__=='__main__':
 out=Path(sys.argv[sys.argv.index('--')+1]);shell=['wall_front','wall_back','wall_left','wall_right','floor','ceiling'];report=dict(geometry_camera_sha256=geometry_hash(),shell={n:dict(present=bpy.data.objects.get(n) is not None,visible=not bpy.data.objects[n].hide_render) for n in shell},lamp_present=bpy.data.objects.get('ceiling_luminaire') is not None)
 mats=[]
 for m in sorted(bpy.data.materials,key=lambda m:m.name):
  if not m.use_nodes:continue
  p=m.node_tree.nodes.get('Principled BSDF')
  if p:mats.append([m.name,list(p.inputs['Base Color'].default_value),float(p.inputs['Roughness'].default_value),float(p.inputs['Metallic'].default_value),float(p.inputs['Transmission Weight'].default_value)])
 report['material_pbr_sha256']=hashlib.sha256(json.dumps(mats).encode()).hexdigest();report['lights']=[dict(name=o.name,type=o.data.type,position=list(o.location),rotation_euler=list(o.rotation_euler),energy=o.data.energy,color=list(o.data.color),size=getattr(o.data,'size',None),size_y=getattr(o.data,'size_y',None),angle=getattr(o.data,'angle',None)) for o in bpy.data.objects if o.type=='LIGHT'];sc=bpy.context.scene;report['render']=dict(resolution=[sc.render.resolution_x,sc.render.resolution_y],percentage=sc.render.resolution_percentage,exposure=sc.view_settings.exposure,view_transform=sc.view_settings.view_transform,look=sc.view_settings.look)
 assert all(v['present'] and v['visible'] for v in report['shell'].values()) and report['lamp_present'];out.write_text(json.dumps(report,indent=2));print(json.dumps(report))
