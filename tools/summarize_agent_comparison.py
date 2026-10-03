"""Same frozen truth and scoring for two independently authored semantic scenes."""
import argparse,importlib.util,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from scipy.spatial import cKDTree
from prepare_eth3d_camera_benchmark import sha,save
from summarize_eth3d_evaluation import ssim


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--truth',type=Path,required=True);p.add_argument('--awsm-depth-code',type=Path,required=True);a=p.parse_args()
    spec=importlib.util.spec_from_file_location('pinned_depth_metrics',a.awsm_depth_code);metrics=importlib.util.module_from_spec(spec);spec.loader.exec_module(metrics)
    truth=np.load(a.truth/'truth_grid.npz')['depth'];views=json.loads((a.truth/'views.json').read_text());tree=cKDTree(np.load(a.truth/'laser_points.npy',mmap_mode='r'))
    result=dict(status='complete',denominator=2,scene='ETH3D delivery_area',mapping_views=36,heldout_views=8,
        scope='Independent native quality_v2 authoring vs ported AWSM semantic authoring protocol; common RGB/K/referenceT/DA3 input, no GT depth used in modelling',
        awsm_depth_code_sha256=sha(a.awsm_depth_code),truth_grid_sha256=sha(a.truth/'truth_grid.npz'),methods=[],lpips_status='pending')
    for method in ['OURS','AWSM']:
        directory=a.root/'evaluation'/method;receipt=json.loads((directory/'receipt.json').read_text());freeze=json.loads((a.root/'freeze'/(method+'.json')).read_text())
        if receipt['status']!='complete' or not receipt['model_unchanged'] or receipt['model_sha256']!=freeze['model_sha256']:raise ValueError('Incomplete or changed frozen model')
        pred=np.load(directory/'rendered_z.npy');per_view=[dict(frame_id=v['frame_id'],split=v['role'],**metrics.metrics(pred[i],truth[i])) for i,v in enumerate(views)]
        depth={}
        for split in ['reconstruction','heldout']:
            rows=[r for r in per_view if r['split']==split]
            depth[split]=dict(views=len(rows),GT_valid_pixels=sum(r['pixels_domain'] for r in rows),GT_grid_pixels=len(rows)*19200,
                **{key:float(np.mean([r[key] for r in rows if r[key] is not None])) if any(r[key] is not None for r in rows) else None
                   for key in ['absrel','rmse_m','valid_coverage','invalid_rate','missing_penalty_mae_m','delta1']})
        accuracy=tree.query(np.load(directory/'model_surface_samples.npy'),k=1,workers=2)[0];completeness=np.load(directory/'gt_to_model_m.npy')
        if not np.isfinite(accuracy).all() or not np.isfinite(completeness).all():raise ValueError('Nonfinite geometry result')
        geometry=dict(model_to_laser_mean_m=float(accuracy.mean()),laser_to_model_mean_m=float(completeness.mean()),symmetric_mean_m=float((accuracy.mean()+completeness.mean())/2),
                      model_to_laser_p95_m=float(np.percentile(accuracy,95)),laser_to_model_p95_m=float(np.percentile(completeness,95)))
        for threshold in [.01,.05,.1]:
            precision=float(np.mean(accuracy<=threshold));recall=float(np.mean(completeness<=threshold));tag=str(round(threshold*100))+'cm'
            geometry['precision_'+tag]=precision;geometry['recall_'+tag]=recall;geometry['fscore_'+tag]=2*precision*recall/(precision+recall) if precision+recall else 0.
        appearance=[]
        for render in json.loads((directory/'render_manifest.json').read_text()):
            x=np.asarray(Image.open(render['source']).convert('RGB').resize(tuple(render['size']),Image.Resampling.LANCZOS));y=np.asarray(Image.open(render['render']).convert('RGB'))
            mse=float(np.mean((x.astype(float)-y.astype(float))**2));appearance.append(dict(**render,psnr_db=float(10*np.log10(255**2/max(mse,1e-12))),ssim=ssim(x,y)))
        row=dict(id=method,freeze=freeze,depth=depth,geometry=geometry,appearance=appearance,
            appearance_means={split:{key:float(np.mean([r[key] for r in appearance if r['split']==split])) for key in ['psnr_db','ssim']} for split in ['reconstruction','heldout']})
        save(directory/'scores.json',row);save(directory/'depth_per_view.json',per_view);result['methods'].append(row)
        print(json.dumps(dict(method=method,surface_m=geometry['symmetric_mean_m'],heldout_absrel=depth['heldout']['absrel'])),flush=True)
    save(a.root/'evaluation/comparison.json',result)
    held=[[r for r in method['appearance'] if r['split']=='heldout'] for method in result['methods']]
    # Every heldout view is shown in the complete sheet; first, fourth and eighth
    # are a fixed compact preview, chosen before any result scores are examined.
    for filename,indices in [('all_heldout.jpg',range(8)),('comparison_preview.jpg',[0,3,7])]:
        sheet=Image.new('RGB',(1200,305*len(indices)),'#eeeeee');draw=ImageDraw.Draw(sheet)
        for row,index in enumerate(indices):
            paths=[held[0][index]['source'],held[0][index]['render'],held[1][index]['render']]
            labels=['REAL '+held[0][index]['frame_id'],'OURS native quality_v2','AWSM protocol port']
            for col,(path,label) in enumerate(zip(paths,labels)):
                image=Image.open(path).convert('RGB');image.thumbnail((400,275));sheet.paste(image,(col*400,row*305+25));draw.text((col*400+5,row*305+5),label,fill='black')
        sheet.save(a.root/'evaluation'/filename,quality=91)


if __name__=='__main__':main()
