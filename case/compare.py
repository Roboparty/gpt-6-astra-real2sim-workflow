"""Same-resolution source diagnostics. In-sample fit metrics, never independent accuracy."""
import sys,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parents[1];render=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
orig=Image.open(root/'inputs/utility_room_original.jpg').convert('RGB');im=Image.open(render).convert('RGB');resized=im.size!=orig.size
if resized:im=im.resize(orig.size,Image.Resampling.LANCZOS)
a=np.asarray(orig)/255;b=np.asarray(im)/255
def linear(x):return np.where(x<=.04045,x/12.92,((x+.055)/1.055)**2.4)
la=linear(a)@np.array([.2126,.7152,.0722]);lb=linear(b)@np.array([.2126,.7152,.0722])
rois={'left_wall':[70,150,270,480],'column':[390,230,485,580],'carpet':[450,850,1050,1180],'blinds':[820,220,1050,430],'cabinet':[1250,780,1410,970],'garments':[1130,480,1230,620]}
metrics={}
for name,(x0,y0,x1,y1) in rois.items():
 av=float(np.median(la[y0:y1,x0:x1]));bv=float(np.median(lb[y0:y1,x0:x1]));metrics[name]=dict(roi=[x0,y0,x1,y1],source_linear_luminance_median=av,render_linear_luminance_median=bv,absolute_error=abs(av-bv),source_rgb_median=np.median(a[y0:y1,x0:x1],axis=(0,1)).tolist(),render_rgb_median=np.median(b[y0:y1,x0:x1],axis=(0,1)).tolist())
result=dict(kind='in-sample appearance diagnostic',render=render.name,render_resized_for_comparison=resized,source_size=list(orig.size),roi_metrics=metrics,whole_image_srgb_mae=float(abs(a-b).mean()),independent_accuracy=False)
(out/'comparison_metrics.json').write_text(json.dumps(result,indent=2));pair=Image.new('RGB',(orig.width*2,orig.height+40),'white');pair.paste(orig,(0,40));pair.paste(im,(orig.width,40));d=ImageDraw.Draw(pair);d.text((8,10),'ORIGINAL / authorized source',fill='black');d.text((orig.width+8,10),'ACTUAL BLENDER RENDER / same camera',fill='black');pair.save(out/'source_comparison.jpg',quality=91)
Image.blend(orig,im,.5).save(out/'source_overlay.jpg',quality=91)
print(json.dumps(result,indent=2))
