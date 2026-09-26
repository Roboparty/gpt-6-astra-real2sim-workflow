import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageOps
R=Path('/home/wqz/real2sim_whole_scene_20260926');s=json.loads((R/'case/runs/state.json').read_text());b=s['refinement']['agent_review']['best'];src=Path(s['stages']['build_render']['directory']);canvas=Image.new('RGB',(1530,1050),(35,35,35));d=ImageDraw.Draw(canvas)
names=['comparison_source.png','comparison_wide.png','comparison_reverse.png']
for j,ref in enumerate([True,False]):
 for i,n in enumerate(names):
  p=next(Path(x['path']) for x in b['artifacts'] if Path(x['path']).name==n) if ref else src/n
  im=ImageOps.contain(Image.open(p).convert('RGB'),(510,320));canvas.paste(im,(i*510,j*350+25));d.text((i*510+5,j*350+4),('previous best ' if ref else 'current ')+n,fill='white')
p=src/'appearance_neutral.png';canvas.paste(ImageOps.contain(Image.open(p).convert('RGB'),(510,320)),(0,725));d.text((5,704),'current neutral',fill='white');canvas.save(R/'evidence/final_comparison.jpg',quality=88)
