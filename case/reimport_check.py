"""Actually reopen GLB/USD in Blender and compare semantic world-space bounds."""
import bpy,sys,json,math
import numpy as np
from pathlib import Path
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
args=sys.argv[sys.argv.index('--')+1:];path=Path(args[0]);audit_path=Path(args[1]);output=Path(args[2]);audit=json.loads(audit_path.read_text());scene=json.loads((audit_path.parent/'scene.json').read_text());bpy.ops.wm.read_factory_settings(use_empty=True)
if path.suffix=='.glb':bpy.ops.import_scene.gltf(filepath=str(path))
elif path.suffix in ['.usd','.usdc','.usda']:bpy.ops.wm.usd_import(filepath=str(path))
else:raise ValueError('Unsupported format')
expected=audit['entities'];keys=sorted(expected,key=len,reverse=True);groups={};deps=bpy.context.evaluated_depsgraph_get()
def identify(o):
 e=o.get('entity_id')
 if isinstance(e,str) and e in expected:return e
 for key in keys:
  if o.name==key or o.name.startswith(key+'__'):return key
 p=o.parent
 while p:
  if p.name in expected:return p.name
  p=p.parent
 return None
for o in bpy.data.objects:
 if o.type!='MESH':continue
 e=identify(o)
 if e is None:continue
 ev=o.evaluated_get(deps);me=ev.to_mesh();groups.setdefault(e,[]).extend([list(o.matrix_world@v.co) for v in me.vertices]);ev.to_mesh_clear()
checks=[];missing=[]
for key,ref in expected.items():
 if key not in groups:missing.append(key);continue
 v=np.array(groups[key]);bounds=np.array([v.min(axis=0),v.max(axis=0)]);err=float(abs(bounds-np.array(ref['world_aabb'])).max());checks.append(dict(entity=key,maximum_bound_error_m=err,status='pass' if err<.0002 else 'fail'))
cameras=[]
for o in bpy.data.objects:
 if o.type=='CAMERA' and o.name.startswith('source_camera'):
  error=float(np.linalg.norm(np.array(o.matrix_world.translation)-scene['camera']['position']));expected_rotation=np.array(scene['camera']['rotation_world_to_cv']).T@np.diag([1,-1,-1]);rotation_error=float(np.max(abs(np.array(o.matrix_world.to_3x3())-expected_rotation)));record=dict(name=o.name,position_error_m=error,rotation_matrix_max_error=rotation_error,lens_mm=o.data.lens,shift_x=o.data.shift_x,shift_y=o.data.shift_y,canonical_principal_point_px=scene['camera']['principal_point'],camera_extras=dict(o.items()));c=scene['camera'];sc=bpy.context.scene;sc.render.resolution_x,sc.render.resolution_y=c['image_size'];sc.render.resolution_percentage=100
  def projection_error():
   errs=[]
   for point in c['fit_landmarks']:
    xyz=np.array(point['xyz']);q=np.array(c['rotation_world_to_cv'])@(xyz-np.array(c['position']));expected=q[:2]/q[2]*c['focal_px']+c['principal_point'];uv=world_to_camera_view(sc,o,Vector(xyz));actual=np.array([uv.x*c['image_size'][0],(1-uv.y)*c['image_size'][1]]);errs.append(float(np.linalg.norm(actual-expected)))
   return max(errs)
  record['native_camera_projection_max_error_px']=projection_error()
  if path.suffix=='.glb':
   assert 'r2s_intrinsics_json' in o,'Portable off-axis intrinsics metadata missing';meta=json.loads(o['r2s_intrinsics_json']);assert meta==c;o.data.sensor_fit='HORIZONTAL';o.data.sensor_width=36;o.data.lens=c['focal_px']*36/c['image_size'][0];o.data.shift_x=(c['image_size'][0]/2-c['principal_point'][0])/c['image_size'][0];o.data.shift_y=(c['principal_point'][1]-c['image_size'][1]/2)/c['image_size'][0];bpy.context.view_layer.update();record['projection_error_after_intrinsics_metadata_px']=projection_error()
  cameras.append(record)
passed=not missing and all(x['status']=='pass' for x in checks) and bool(cameras) and all(x['position_error_m']<.0002 and x['rotation_matrix_max_error']<.0002 for x in cameras)
passed=passed and all(x.get('projection_error_after_intrinsics_metadata_px',x['native_camera_projection_max_error_px'])<.002 for x in cameras)
report=dict(format=path.suffix,status='passed' if passed else 'failed',actually_reimported=True,units='metres, checked after importer axis conversion to Blender Z up',missing_entities=missing,entity_bounds=checks,cameras=cameras,limitations=['Core glTF camera is centred; canonical off-axis intrinsics must be read from delivered scene.json / camera extras' if path.suffix=='.glb' else 'USD camera/geometry round trip checked; renderer-specific shading may differ','Blender procedural microtextures are not guaranteed identical in interchange formats'],file=path.name)
output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2,default=str));print(json.dumps(dict(status=report['status'],format=path.suffix,entities=len(checks),missing=missing,max_error=max([x['maximum_bound_error_m'] for x in checks],default=0)),indent=2))
if not passed:raise RuntimeError('Export reimport geometry/pose check failed')
