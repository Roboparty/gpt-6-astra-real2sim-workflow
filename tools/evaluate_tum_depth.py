"""Read-only registered-pixel depth diagnostics with fixed frame/pixel denominators."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from PIL import Image


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(8*1024**2),b''):h.update(chunk)
    return h.hexdigest()


def depth_metrics(predicted, truth):
    predicted=np.asarray(predicted,dtype=np.float64);truth=np.asarray(truth,dtype=np.float64)
    if predicted.shape!=truth.shape or predicted.ndim!=2:
        raise ValueError('Equal two-dimensional depth rasters required')
    if not np.isfinite(truth).all() or np.any(truth<0):raise ValueError('Reference depth invalid')
    valid=truth>0;count=int(valid.sum());good=np.isfinite(predicted)&(predicted>0)
    invalid=int((valid&~good).sum())
    result=dict(reference_valid_pixels=count,total_pixels=int(truth.size),invalid_prediction_pixels=invalid,
                status='unavailable',abs_rel=None,rmse_m=None,mae_m=None,delta_1=None)
    if not count:return result
    result['prediction_coverage']=1-invalid/count
    if invalid:
        result['status']='incomplete_prediction';return result
    gt=truth[valid];pr=predicted[valid];error=pr-gt
    result.update(status='evaluated',abs_rel=float(np.mean(abs(error)/gt)),rmse_m=float(np.sqrt(np.mean(error**2))),
                  mae_m=float(np.mean(abs(error))),delta_1=float(np.mean(np.maximum(pr/gt,gt/pr)<1.25)))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    cfg=json.loads(args.protocol.read_text())
    assert sha(__file__)==cfg['evaluator_sha256']
    for key in ('rgb_index','prediction_receipt','trajectory_evaluation'):
        assert sha(cfg[key])==cfg[key+'_sha256']
    index=json.loads(Path(cfg['rgb_index']).read_text());predictions=json.loads(Path(cfg['prediction_receipt']).read_text())
    scales=json.loads(Path(cfg['trajectory_evaluation']).read_text())
    assert [x['id'] for x in index['sources']]==[x['id'] for x in predictions['sources']]==[x['id'] for x in scales['sources']]==cfg['source_ids']
    report=dict(schema='real2sim.tum-depth-evaluation/1',protocol_sha256=sha(args.protocol),evaluator_sha256=sha(__file__),
                expected_sources=3,expected_frames=18,sources=[],scope=cfg['scope'])
    for source,prediction,scale_row in zip(index['sources'],predictions['sources'],scales['sources']):
        row=dict(id=source['id'],expected_frames=6,status='failed',frames=[]);report['sources'].append(row)
        try:
            assert sha(source['input_manifest_path'])==source['input_manifest_sha256']
            ep=Path(source['evaluator_manifest_path']);assert sha(ep)==source['evaluator_manifest_sha256']
            em=json.loads(ep.read_text());frames=source['input_manifest']['frames'];assert len(frames)==len(em['depth_matches'])==6
            npz=Path(cfg['prediction_root'])/source['id']/'predictions.npz';assert sha(npz)==prediction['predictions_sha256']
            assert prediction['status']=='predicted'
            with np.load(npz,allow_pickle=False) as data:local=data['local_points'][0]
            assert local.shape==(6,434,574,3)
            scale=scale_row['fitted_scale'];assert np.isfinite(scale) and scale>0
            row.update(npz_sha256=prediction['predictions_sha256'],fixed_trajectory_scale=scale)
            for f,d in zip(frames,em['depth_matches']):
                fr=dict(ordinal=f['ordinal'],rgb_timestamp=f['timestamp'],status='missing_reference',depth_gap_seconds=d['gap_seconds'],raw=None,trajectory_scaled=None);row['frames'].append(fr)
                assert d['rgb_ordinal']==f['ordinal'] and d['rgb_timestamp']==f['timestamp']
                assert sha(f['path'])==f['sha256']
                if not d['matched']:
                    assert d['gap_seconds']>.02
                    continue
                assert d['gap_seconds']<=.02
                depth=Path(d['path']);assert sha(depth)==d['sha256']
                with Image.open(depth) as im:gt=np.asarray(im)
                assert gt.shape==(480,640) and gt.dtype.kind in 'iu' and np.all(gt<=65535)
                gt=gt.astype(np.float64)/5000.
                # The upstream local_points already include its learned metric factor.
                # Use optical-axis Z, never Euclidean range or a second metric multiply.
                z=local[f['ordinal'],:,:,2]
                upsampled=np.asarray(Image.fromarray(z.astype(np.float32)).resize((640,480),Image.Resampling.BILINEAR),dtype=np.float64)
                raw=depth_metrics(upsampled,gt);scaled=depth_metrics(upsampled*scale,gt)
                fr.update(status='evaluated' if raw['status']==scaled['status']=='evaluated' else 'incomplete_prediction',
                          depth_sha256=d['sha256'],raw=raw,trajectory_scaled=scaled)
            row['matched_reference_frames']=sum(f['status']!='missing_reference' for f in row['frames'])
            row['evaluated_frames']=sum(f['status']=='evaluated' for f in row['frames'])
            row['full_six_frame_metrics']=None
            row['available_frame_diagnostic']=None
            available=[f for f in row['frames'] if f['status']=='evaluated']
            if available:
                # Descriptive frame-macro average, not a success-filtered full score.
                diagnostic={arm:{metric:float(np.mean([f[arm][metric] for f in available])) for metric in ('abs_rel','rmse_m','mae_m','delta_1')} for arm in ('raw','trajectory_scaled')}
                row['available_frame_diagnostic']=dict(frame_count=len(available),metrics=diagnostic)
                if len(available)==6:row['full_six_frame_metrics']=diagnostic
            row['status']='complete' if row['evaluated_frames']==6 else 'incomplete'
        except Exception as error:row['error']=repr(error)
    report['evaluated_frames']=sum(r.get('evaluated_frames',0) for r in report['sources'])
    report['complete_sources']=sum(r['status']=='complete' for r in report['sources'])
    report['full_18_frame_metrics']=None
    if report['evaluated_frames']==18:
        report['full_18_frame_metrics']={arm:{metric:float(np.mean([f[arm][metric] for r in report['sources'] for f in r['frames']])) for metric in ('abs_rel','rmse_m','mae_m','delta_1')} for arm in ('raw','trajectory_scaled')}
    for key in ('rgb_index','prediction_receipt','trajectory_evaluation'):assert sha(cfg[key])==cfg[key+'_sha256']
    report['wall_seconds']=time.monotonic()-start
    (args.output/'receipt.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps({k:report[k] for k in ('complete_sources','evaluated_frames','expected_frames','wall_seconds')}))


if __name__=='__main__':main()
