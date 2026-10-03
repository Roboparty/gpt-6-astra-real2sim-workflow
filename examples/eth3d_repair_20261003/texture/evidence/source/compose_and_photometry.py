import pathlib,json,sys,numpy as np
from PIL import Image,ImageDraw
root=pathlib.Path(sys.argv[1]);P=json.load(open('/home/wqz/real2sim_agent_compare_20261003/OURS/inputs/packet.json'));indices=[0,4,8,12,16,20,24,28,32,35];geo=root/'geometry_previews';tex=root/'fit_previews'
for page in range(2):
 sheet=Image.new('RGB',(1200,5*290),(240,240,240));draw=ImageDraw.Draw(sheet)
 for row,i in enumerate(indices[page*5:page*5+5]):
  draw.text((5,row*290+4),f'{i} | INPUT / GEOMETRY-ONLY / TEXTURE-ONLY; same camera, lighting, exposure',fill='black')
  for col,path in enumerate([P['frames'][i]['path'],str(geo/f'view_{i:03d}.png'),str(tex/f'view_{i:03d}.png')]):
   im=Image.open(path).convert('RGB');im.thumbnail((400,266));sheet.paste(im,(col*400,row*290+24))
 sheet.save(root/f'comparison_{page}.jpg',quality=91)
def linear(x):return np.where(x<=.04045,x/12.92,((x+.055)/1.055)**2.4)
rois={8:[650,600,1160,770],12:[450,590,1100,770],20:[420,550,1140,760]};rows=[]
for i,box in rois.items():
 source=np.array(Image.open(P['frames'][i]['path']).convert('RGB'),float)/255;render=np.array(Image.open(tex/f'view_{i:03d}.png').convert('RGB'),float)/255;W,H=P['frames'][i]['image_size'];x0,y0,x1,y1=box;src=source[y0:y1,x0:x1];x0,x1=np.round(np.array([x0,x1])*render.shape[1]/W).astype(int);y0,y1=np.round(np.array([y0,y1])*render.shape[0]/H).astype(int);dst=render[y0:y1,x0:x1];sl=float(np.median(linear(src)@np.array([.2126,.7152,.0722])));dl=float(np.median(linear(dst)@np.array([.2126,.7152,.0722])));rows.append({'frame':i,'source_roi_xyxy':box,'source_median_linear_luma':sl,'render_median_linear_luma':dl,'suggested_exposure_delta_ev':float(np.log2(sl/dl))})
evs=np.array([r['suggested_exposure_delta_ev'] for r in rows]);data={'scope':'fixed three input floor regions, no GT/heldout; heuristic exposure diagnosis of photo-baked colour, not physical light/albedo recovery','rows':rows,'median_ev':float(np.median(evs)),'ev_spread':float(np.ptp(evs)),'suggested_bounded_delta_ev':float(np.clip(np.median(evs),-.5,.5)),'consistent_sign':bool(np.all(evs>0) or np.all(evs<0)),'colour_pipeline':'source RGB and PNG atlases store sRGB bytes; sampled texture is decoded by Blender sRGB node. Unsupported fallback remains original scene-linear BaseColor graph. Render comparison linearizes display sRGB for diagnostic only.'};(root/'photometry_diagnostic.json').write_text(json.dumps(data,indent=2));print(json.dumps(data,indent=2))
