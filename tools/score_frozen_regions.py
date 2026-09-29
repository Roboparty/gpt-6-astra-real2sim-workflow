"""Measure fixed source-image regions; neither alignment nor thresholds are fitted."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def linear(rgb):return np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--protocol',type=Path,required=True);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--image',action='append',required=True,help='name=path, every declared comparison group')
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    if args.output.exists():raise ValueError('Preserve existing result; use new output')
    protocol=json.loads(args.protocol.read_text(encoding='utf-8-sig'))
    regions=protocol.get('evaluation_regions_source_xyxy',protocol.get('appearance_regions_xyxy'))
    if not regions:raise ValueError('No frozen source-coordinate regions')
    source_sha=sha(args.source)
    if protocol.get('source_sha256',source_sha)!=source_sha:raise ValueError('Source hash changed')
    rows=[];names=set()
    with Image.open(args.source) as im:source=im.convert('RGB');width,height=source.size
    for image in args.image:
        name,path=image.split('=',1);path=Path(path)
        if not name or name in names:raise ValueError('Duplicate/empty group')
        names.add(name);pred=Image.open(path).convert('RGB');w,h=pred.size
        if abs(w/width-h/height)>1e-9:raise ValueError('Aspect ratio differs from source')
        a=np.asarray(source.resize((w,h),Image.Resampling.LANCZOS),float)/255.;b=np.asarray(pred,float)/255.;metrics={}
        for key,xyxy in regions.items():
            x0,y0,x1,y1=[int(v*(w/width if i%2==0 else h/height)) for i,v in enumerate(xyxy)]
            if not 0<=x0<x1<=w or not 0<=y0<y1<=h:raise ValueError('Invalid frozen ROI')
            s,t=a[y0:y1,x0:x1],b[y0:y1,x0:x1]
            ys=linear(s)@np.array([.2126,.7152,.0722]);yt=linear(t)@np.array([.2126,.7152,.0722])
            metrics[key]={'rgb_mae':float(np.mean(abs(s-t))),'mean_absolute_log_luminance_ratio':float(np.mean(abs(np.log((yt+1e-4)/(ys+1e-4))))),'pixels':int(ys.size)}
        rows.append({'group':name,'image_sha256':sha(path),'image_size':[w,h],'metrics':metrics})
    report={'expected_groups':len(args.image),'groups':rows,'source_sha256':source_sha,
            'protocol_sha256':sha(args.protocol),'script_sha256':sha(__file__),
            'scope':'Fixed same-image appearance diagnostics; no physical reflectance or held-out accuracy claim'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
