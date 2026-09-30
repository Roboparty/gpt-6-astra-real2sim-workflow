"""Independent pixel-center interpolation and depth metric recalculation."""
import argparse
import json
from pathlib import Path
import time
import numpy as np
from PIL import Image
from evaluate_tum_depth import sha


def pixel_center_bilinear(z,height=480,width=640):
    y=np.clip((np.arange(height)+.5)*z.shape[0]/height-.5,0,z.shape[0]-1)
    x=np.clip((np.arange(width)+.5)*z.shape[1]/width-.5,0,z.shape[1]-1)
    y0=y.astype(int);x0=x.astype(int);y1=np.minimum(y0+1,z.shape[0]-1);x1=np.minimum(x0+1,z.shape[1]-1)
    wx=x-x0;wy=(y-y0)[:,None]
    top=z[y0[:,None],x0]*(1-wx)+z[y0[:,None],x1]*wx
    bottom=z[y1[:,None],x0]*(1-wx)+z[y1[:,None],x1]*wx
    return top*(1-wy)+bottom*wy


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','result','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();start=time.monotonic()
    if a.output.exists():raise ValueError('Preserve previous audit')
    cfg=json.loads(a.protocol.read_text());result=json.loads(a.result.read_text());idx=json.loads(Path(cfg['rgb_index']).read_text())
    assert sha(a.protocol)==result['protocol_sha256']
    rows=[];max_abs_rel_difference=0.;max_rmse_difference=0.;missing=0
    for source,scored in zip(idx['sources'],result['sources']):
        assert source['id']==scored['id']
        em=json.loads(Path(source['evaluator_manifest_path']).read_text())
        npz=Path(cfg['prediction_root'])/source['id']/'predictions.npz';assert sha(npz)==scored['npz_sha256']
        with np.load(npz,allow_pickle=False) as data:z=data['local_points'][0,...,2].astype(np.float64)
        for observed,entry in zip(em['depth_matches'],scored['frames']):
            if not observed['matched']:
                assert entry['status']=='missing_reference' and entry['raw'] is None
                missing+=1;continue
            assert sha(observed['path'])==entry['depth_sha256']
            with Image.open(observed['path']) as image:gt=np.array(image,dtype=np.float64)/5000.
            raw=pixel_center_bilinear(z[entry['ordinal']]);mask=gt>0;count=int(mask.sum())
            assert count==entry['raw']['reference_valid_pixels']
            for arm,factor in [('raw',1.),('trajectory_scaled',scored['fixed_trajectory_scale'])]:
                pred=raw[mask]*factor;truth=gt[mask]
                assert np.isfinite(pred).all() and (pred>0).all()
                absrel=float(np.sum(abs(pred/truth-1))/count)
                rmse=float(np.sqrt(np.dot(pred-truth,pred-truth)/count))
                da=abs(absrel-entry[arm]['abs_rel']);dr=abs(rmse-entry[arm]['rmse_m'])
                assert da<1e-6 and dr<1e-6
                max_abs_rel_difference=max(max_abs_rel_difference,da);max_rmse_difference=max(max_rmse_difference,dr)
            rows.append(dict(source_id=source['id'],ordinal=entry['ordinal'],reference_valid_pixels=count))
    assert len(rows)==17 and missing==1 and result['full_18_frame_metrics'] is None
    report=dict(schema='real2sim.tum-depth-independent-audit/1',status='passed',result_sha256=sha(a.result),script_sha256=sha(__file__),
        frames_recomputed=len(rows),missing_reference_frames=missing,reference_valid_pixels=sum(r['reference_valid_pixels'] for r in rows),
        expected_pixels_18_frames=18*480*640,matched_frame_pixels=17*480*640,
        max_abs_rel_difference=max_abs_rel_difference,max_rmse_difference_m=max_rmse_difference,wall_seconds=time.monotonic()-start,
        scope='Explicit pixel-center bilinear interpolation independent of PIL resizing, plus alternative summation of primary depth metrics. No confidence filtering or new model inference.')
    a.output.write_text(json.dumps(report,indent=2));print(json.dumps(report))


if __name__=='__main__':main()
