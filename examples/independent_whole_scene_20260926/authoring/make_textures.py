"""Restrained full-surface inferred textures; no source crop is tiled or extended."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFilter
import random,math,json
import numpy as np
from scipy.ndimage import gaussian_filter
R=Path('/home/wqz/real2sim_whole_scene_20260926/authoring/textures');R.mkdir(exist_ok=True)
r=random.Random(1609);N=2048
im=Image.new('RGB',(N,N),(204,215,212));d=ImageDraw.Draw(im)
# Original has dense low contrast botanical linework. Entire arrangement inferred.
for k in range(4200):
 x=r.uniform(-30,N+30);y=r.uniform(-30,N+30);length=r.uniform(20,92);a=r.uniform(0,math.tau)
 col=r.choice([(139,161,156),(158,178,170),(181,196,187),(220,224,215),(133,156,149)])
 pts=[(x+math.cos(a+t*.28)*length*t,y+math.sin(a+t*.28)*length*t) for t in np.linspace(0,1,10)]
 d.line(pts,fill=col,width=1)
 for t in [.22,.4,.59,.77]:
  cx=x+math.cos(a+t*.28)*length*t;cy=y+math.sin(a+t*.28)*length*t
  for side in [-1,1]:
   aa=a+side*.72;ll=length*r.uniform(.13,.29);tip=(cx+math.cos(aa)*ll,cy+math.sin(aa)*ll);cross=(-math.sin(aa)*ll*.19,math.cos(aa)*ll*.19)
   d.polygon([(cx,cy),((cx+tip[0])/2+cross[0],(cy+tip[1])/2+cross[1]),tip,((cx+tip[0])/2-cross[0],(cy+tip[1])/2-cross[1])],fill=col)
im.filter(ImageFilter.GaussianBlur(.25)).save(R/'duvet_inferred_botanical.png')
# Full-room carpet texture, 0.5m orientation changes rather than unverified photo tiling.
size=2048;rg=np.random.default_rng(290926);a=np.zeros((size,size,3),np.uint8);tile=256
for j in range(8):
 for i in range(8):
  noise=rg.normal(0,3,(tile,tile));grad=gaussian_filter(rg.normal(0,1,(tile,tile)),sigma=(.35,5))
  grad=grad/(grad.std()+1e-9)*9
  if (i+j)%2:grad=grad.T
  v=noise+grad+rg.uniform(-3,3)
  base=np.array([82,81,82]);a[j*tile:(j+1)*tile,i*tile:(i+1)*tile]=np.clip(base+v[...,None],0,255)
Image.fromarray(a).save(R/'carpet_whole_inferred.png')
(R/'provenance.json').write_text(json.dumps(dict(source_kind='procedural',application='whole_object',source_pixels_used=False,duvet='Whole-object low contrast botanical palette/distribution inferred from complete original. Not an exact recovered print.',carpet='Alternating tile fibre orientation inferred from full floor, no original crop sampled.',microstructure='Independent actual UV-driven procedural weave in Blender',folds='Geometry only',illumination='No original shadows baked into either albedo'),indent=2))
