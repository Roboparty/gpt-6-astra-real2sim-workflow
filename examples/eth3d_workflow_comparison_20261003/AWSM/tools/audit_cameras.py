import bpy,json,pathlib,numpy as np,hashlib
from mathutils import Matrix,Vector
from bpy_extras.object_utils import world_to_camera_view
R=pathlib.Path(__file__).resolve().parents[1];P=json.loads((R/'inputs/packet.json').read_text());C=json.loads((R/'cameras.json').read_text());X=np.array(json.loads((R/'model_from_input.json').read_text())['model_from_input']);scene=bpy.context.scene
cam=bpy.data.objects.new('audit_camera',bpy.data.cameras.new('audit_camera'));scene.collection.objects.link(cam);scene.camera=cam
rows=[]
for f,c in zip(P['frames'],C['frames']):
 T=np.array(c['camera_to_world']);pose_error=float(np.max(abs(T-X@np.array(f['T_world_camera']))));K=np.array(f['K']);W,H=f['image_size'];w=640;h=round(H*w/W);sx=w/W;sy=h/H;fx=K[0,0]*sx;fy=K[1,1]*sy;cx=(K[0,2]+.5)*sx;cy=(K[1,2]+.5)*sy;ratio=fx/fy
 cam.matrix_world=Matrix((T@np.diag([1,-1,-1,1])).tolist());cam.data.type='PERSP';cam.data.sensor_fit='HORIZONTAL';cam.data.sensor_width=36;cam.data.lens=fx*36/w;cam.data.shift_x=(w/2-cx)/w;cam.data.shift_y=(cy-h/2)*ratio/w;scene.render.resolution_x=w;scene.render.resolution_y=h;scene.render.resolution_percentage=100;scene.render.pixel_aspect_x=max(1,1/ratio);scene.render.pixel_aspect_y=max(1,ratio);bpy.context.view_layer.update()
 errors=[]
 for u,v in [(50.5,50.5),(320.5,213.5),(590.5,375.5)]:
  pc=np.array([(u-cx)/fx,(v-cy)/fy,1])*3;pw=T[:3,:3]@pc+T[:3,3];ndc=world_to_camera_view(scene,cam,Vector(pw));errors.append(float(max(abs(ndc.x*w-u),abs((1-ndc.y)*h-v))))
 rows.append({'index':f['input_index'],'pose_XT_max_error':pose_error,'source_K_exact':np.array_equal(c['intrinsics'],f['K']),'render_roundtrip_pixel_errors':errors})
print('MAX_XT_ERROR',max(r['pose_XT_max_error'] for r in rows),flush=True)
assert max(r['pose_XT_max_error'] for r in rows)<1e-12
print('MAX_PIXEL_ERROR',max(max(r['render_roundtrip_pixel_errors']) for r in rows),rows[0],flush=True)
assert max(max(r['render_roundtrip_pixel_errors']) for r in rows)<.01
(R/'analysis/camera_checks.json').write_text(json.dumps({'frames':rows,'all36_exact_XT':True,'single_rigid_rotation_det':float(np.linalg.det(X[:3,:3])),'geometry_scale':1,'projection_test':'independent world_to_camera_view numerical roundtrip,3rays per camera, no renders','maximum_pixel_error':max(max(r['render_roundtrip_pixel_errors']) for r in rows),'intrinsics_convention':'integer-centre source, image-corner render K','camera_convention':'OpenCV RDF c2w, Blender c2w=T@diag(1,-1,-1,1)'},indent=2));print('CAMERA_AUDIT_PASSED36',max(max(r['render_roundtrip_pixel_errors']) for r in rows))
