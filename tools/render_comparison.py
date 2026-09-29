"""Fixed render settings for endpoint comparison; never saves the loaded model."""
import bpy,hashlib,json,sys,time
from pathlib import Path

out=Path(sys.argv[sys.argv.index('--')+1]);out.mkdir(parents=True,exist_ok=False)
start=time.monotonic();model=Path(bpy.data.filepath);before=hashlib.sha256(model.read_bytes()).hexdigest()
sc=bpy.context.scene;sc.camera=bpy.data.objects.get('source_camera') or sc.camera
sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=8
sc.cycles.use_denoising=True;sc.cycles.use_adaptive_sampling=False;sc.cycles.seed=0
sc.render.resolution_x=1702;sc.render.resolution_y=1276;sc.render.resolution_percentage=50
sc.render.use_border=False;sc.render.use_crop_to_border=False
sc.render.filepath=str(out/'render.png');bpy.ops.render.render(write_still=True)
after=hashlib.sha256(model.read_bytes()).hexdigest();assert before==after
(out/'receipt.json').write_text(json.dumps({'model_sha256':before,'input_unchanged':True,'engine':bpy.app.version_string,
 'resolution':[851,638],'samples':8,'seed':0,'adaptive_sampling':False,'denoising':True,
 'view_transform':sc.view_settings.view_transform,'exposure':sc.view_settings.exposure,
 'camera_matrix':[[float(v) for v in row] for row in sc.camera.matrix_world],
 'wall_seconds':time.monotonic()-start},indent=2))
