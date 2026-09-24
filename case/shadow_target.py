from PIL import Image,ImageDraw
from pathlib import Path
import numpy as np,json
r=Path(__file__).resolve().parents[1];out=r/'evidence/shadow_fit';out.mkdir(parents=True,exist_ok=True);src=Image.open(r/'inputs/utility_room_original.jpg').convert('RGB');roi=Image.new('L',src.size,0);d=ImageDraw.Draw(roi)
d.polygon([(540,680),(650,645),(786,661),(1100,717),(1215,785),(1160,1010),(495,930)],fill=255)
for poly in [[(760,591),(869,588),(875,706),(830,745),(758,719)],[(614,546),(853,546),(853,599),(716,609),(615,589)],[(634,672),(696,672),(699,746),(640,750)]]:d.polygon(poly,fill=0)
v=np.array(src)/255;mask=(v.mean(axis=2)>.59)&(np.array(roi)>0);target=Image.fromarray(np.uint8(mask)*255);target.resize((425,319),Image.Resampling.NEAREST).save(out/'target.png');roi.resize((425,319),Image.Resampling.NEAREST).save(out/'roi.png');preview=np.array(src);preview[mask]=(.4*preview[mask]+.6*np.array([255,30,30])).astype('uint8');Image.fromarray(preview).save(out/'target_overlay.jpg',quality=90)
(out/'protocol.json').write_text(json.dumps(dict(purpose='fit sun direction to source observed bright floor pixels; not independent validation',roi_definition='manual floor polygon with furniture regions excluded',threshold_srgb_mean=.59,render_size=[425,319]),indent=2))
