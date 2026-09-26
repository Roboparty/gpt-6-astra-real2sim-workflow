import sys,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageOps
R=Path('/home/wqz/real2sim_whole_scene_20260926');state=json.loads((R/'case/runs/state.json').read_text());stage=sys.argv[1] if len(sys.argv)>1 else 'build_geometry';out=Path(state['stages'][stage]['directory']);dest=R/'evidence';dest.mkdir(exist_ok=True)
if not (out/'render_binding.json').is_file():raise SystemExit('BUILD_INCOMPLETE: wait for current render binding before preparing review sheets')
def sheet(name,rows,size=(340,220)):
 w,h=size;canvas=Image.new('RGB',(w*max(len(row) for row in rows),len(rows)*(h+25)),(40,40,40));draw=ImageDraw.Draw(canvas)
 for j,row in enumerate(rows):
  for i,ref in enumerate(row):
   p=out/ref
   if not p.exists():continue
   im=Image.open(p).convert('RGB');im.thumbnail((w,h));canvas.paste(im,(i*w+(w-im.width)//2,j*(h+25)+25));draw.text((i*w+5,j*(h+25)+4),ref,fill='white')
 canvas.save(dest/(stage+'_'+name+'.jpg'),quality=86)
sheet('global_'+out.name,[[n for n in ['source_reference.png','source_view.png','source_clay.png']],[n for n in ['comparison_source.png','comparison_wide.png','comparison_reverse.png']],[n for n in ['inspect_wall_left.png','inspect_wall_back.png','diagnostic_reverse.png']]],(510,350))
if (out/'surface_audit.json').exists():
 a=json.loads((out/'surface_audit.json').read_text());sheet('surface_'+out.name,[[r['source_crop'],r['front_view'],r['raking_view']] for r in a['regions']]);print('SURFACE',a['status'],a['failures'])
if (out/'structural_audit.json').exists():
 a=json.loads((out/'structural_audit.json').read_text());sheet('structure_'+out.name,[r['isolated_views'] for r in a['assemblies']]);print('STRUCTURE',a['status'],a['failures'])
if (out/'render_binding.json').exists():
 a=json.loads((out/'render_binding.json').read_text());sheet('objects_'+out.name,[[r['source'],r['render']] for r in a['object_crops'].values()],(420,280))
print(out)
