from PIL import Image,ImageDraw
from pathlib import Path
import json
root=Path(__file__).resolve().parents[1];src=Image.open(root/'inputs/utility_room_original.jpg');out=Image.new('RGB',src.size,(180,193,190));mask=Image.new('L',src.size,0);draw=ImageDraw.Draw(mask)
polys=[[(557,521),(635,514),(635,636),(565,647)],[(788,488),(1096,511),(1059,707),(787,662)],[(1138,307),(1284,284),(1252,429),(1110,428)],[(1048,654),(1187,683),(1181,728),(1044,712)]]
for p in polys:draw.polygon(p,fill=255)
out.paste(src,mask=mask);out.save(root/'evidence/exterior_only.png')
(root/'evidence/exterior_texture_provenance.json').write_text(json.dumps(dict(source='inputs/utility_room_original.jpg',transform='Copy only manually segmented visible outdoor regions into neutral-color canvas; no generative processing',polygons=polys,restriction='applied solely to remote exterior backdrop, never to interior reconstruction',limitations='single-view photographic background, no independent outdoor geometry or novel-view accuracy'),indent=2))
