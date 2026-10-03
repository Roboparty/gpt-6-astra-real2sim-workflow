"""Score frozen real-scene outputs, reusing the pinned AWSM optical-Z metric code."""
import argparse
import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image,ImageDraw
from scipy.spatial import cKDTree

from prepare_eth3d_camera_benchmark import sha,save


def ssim(a,b):
    a=a.astype(float)/255;b=b.astype(float)/255
    mu_a=cv2.GaussianBlur(a,(11,11),1.5);mu_b=cv2.GaussianBlur(b,(11,11),1.5)
    va=cv2.GaussianBlur(a*a,(11,11),1.5)-mu_a*mu_a;vb=cv2.GaussianBlur(b*b,(11,11),1.5)-mu_b*mu_b;cov=cv2.GaussianBlur(a*b,(11,11),1.5)-mu_a*mu_b
    values=((2*mu_a*mu_b+.01**2)*(2*cov+.03**2))/((mu_a**2+mu_b**2+.01**2)*(va+vb+.03**2))
    return float(values[5:-5,5:-5].mean())


def main():
    p=argparse.ArgumentParser();p.add_argument('--benchmark',type=Path,required=True);p.add_argument('--awsm-depth-code',type=Path,required=True);a=p.parse_args()
    spec=importlib.util.spec_from_file_location('frozen_awsm_depth',a.awsm_depth_code);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    root=a.benchmark;ev=root/'evaluation';truth=np.load(ev/'truth_grid.npz')['depth'];views=json.loads((ev/'views.json').read_text())
    points=np.load(ev/'laser_points.npy',mmap_mode='r');tree=cKDTree(points)
    report=dict(status='complete',scene='ETH3D delivery_area',photographs=44,mapping=36,heldout=8,
        awsm_depth_code_sha256=sha(a.awsm_depth_code),awsm_revision='4dc2f5c515b77fd5f5f8dbedbdad76663882267e',
        scope='Real-scene Pi3X reference and static editable-mesh adapter ablation. Not full semantic Agent reconstruction or an AWSM authoring rerun.',
        geometry_domain='Published ETH3D eval scan points. Model100000 area-weighted samples to all24.9M laser points;100000 uniform laser samples to exact candidate triangle BVH.',
        depth_domain='Official sparse laser-derived optical-Z truth in[0.1,30]m; missing candidate pixels count30m penalty; missing GT is excluded and coverage reported.',
        variants=[],lpips_status='pending separate pinned AlexNet v0.1 evaluation')
    for variant in json.loads((ev/'variants.json').read_text()):
        directory=ev/(variant['id']+('_colorfix' if variant['id'] in ['RGB_SE3','RGB_K_T'] else ''))
        receipt=json.loads((directory/'receipt.json').read_text())
        if receipt['status']!='complete' or not receipt['model_unchanged']:raise ValueError('Incomplete or changed candidate')
        pred=np.load(directory/'rendered_z.npy');per_view=[dict(frame=v['frame_id'],split=v['role'],**module.metrics(pred[i],truth[i])) for i,v in enumerate(views)]
        depth={}
        for role in ['reconstruction','heldout']:
            rows=[x for x in per_view if x['split']==role]
            depth[role]=dict(views=len(rows),GT_valid_pixels=sum(x['pixels_domain'] for x in rows),GT_total_grid_pixels=len(rows)*19200,
                **{key:float(np.mean([x[key] for x in rows if x[key] is not None])) if any(x[key] is not None for x in rows) else None for key in
                   ['absrel','rmse_m','valid_coverage','invalid_rate','missing_penalty_mae_m','delta1']})
        sample=np.load(directory/'model_surface_samples.npy');accuracy=tree.query(sample,k=1,workers=2)[0];completeness=np.load(directory/'gt_to_model_m.npy')
        if not np.isfinite(accuracy).all() or not np.isfinite(completeness).all():raise ValueError('Invalid geometry distances')
        geom=dict(model_to_laser_mean_m=float(accuracy.mean()),laser_to_model_mean_m=float(completeness.mean()),symmetric_mean_m=float((accuracy.mean()+completeness.mean())/2),
            model_to_laser_p95_m=float(np.percentile(accuracy,95)),laser_to_model_p95_m=float(np.percentile(completeness,95)))
        for threshold in [.01,.05,.1]:
            precision=float(np.mean(accuracy<=threshold));recall=float(np.mean(completeness<=threshold));geom[f'fscore_{round(threshold*100)}cm']=2*precision*recall/(precision+recall) if precision+recall else 0.
            geom[f'precision_{round(threshold*100)}cm']=precision;geom[f'recall_{round(threshold*100)}cm']=recall
        appearance=[]
        for render in json.loads((directory/'render_manifest.json').read_text()):
            target=Image.open(render['source']).convert('RGB').resize(tuple(render['size']),Image.Resampling.LANCZOS);candidate=Image.open(render['render']).convert('RGB')
            x=np.asarray(target);y=np.asarray(candidate);mse=float(np.mean((x.astype(float)-y.astype(float))**2))
            appearance.append(dict(**render,psnr_db=float(10*np.log10(255**2/max(mse,1e-12))),ssim=ssim(x,y)))
        row=dict(**variant,directory=str(directory),depth=depth,geometry=geom,appearance=appearance)
        report['variants'].append(row);save(directory/'scores.json',row);save(directory/'depth_per_view.json',per_view)
        print(json.dumps(dict(id=variant['id'],surface_m=geom['symmetric_mean_m'],heldout_absrel=depth['heldout']['absrel'])),flush=True)
    save(ev/'comparison.json',report)
    # Same fixed first heldout source across every column; no best-view selection.
    rows=[r for r in report['variants'] if r['id'] in ['RGB_Sim3','RGB_K_Sim3','RGB_K_T']]
    chosen=[next(x for x in row['appearance'] if x['split']=='heldout') for row in rows]
    canvas=Image.new('RGB',(1600,340),'#eeeeee');draw=ImageDraw.Draw(canvas)
    paths=[chosen[0]['source']]+[x['render'] for x in chosen];labels=['Real heldout photograph','RGB + diagnostic Sim3','RGB+K + diagnostic Sim3','RGB+K+T (reference poses)']
    for i,(path,label) in enumerate(zip(paths,labels)):
        im=Image.open(path).convert('RGB');im.thumbnail((400,300));canvas.paste(im,(i*400,32));draw.text((i*400+5,7),label,fill='black')
    canvas.save(ev/'comparison_preview.jpg',quality=90)


if __name__=='__main__':main()
