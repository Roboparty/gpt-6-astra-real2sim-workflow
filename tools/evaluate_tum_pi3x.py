"""Score frozen Pi3X camera outputs with the same full-denominator TUM evaluator."""
import argparse
import json
from pathlib import Path
import time
import numpy as np
import pycolmap
from evaluate_tum_trajectory import evaluate,read_tum,file_sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('run','protocol','rgb-index','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    receipt=json.loads((a.run/'receipt.json').read_text());protocol=json.loads(a.protocol.read_text());idx=json.loads(a.rgb_index.read_text())
    assert receipt['protocol_sha256']==file_sha(a.protocol)
    assert file_sha(Path(__file__).with_name('evaluate_tum_trajectory.py'))==protocol['evaluation_code_sha256']
    assert [s['id'] for s in receipt['sources']]==[s['id'] for s in idx['sources']]==protocol['source_ids']
    rows=[]
    for prediction,source in zip(receipt['sources'],idx['sources']):
        frames=source['input_manifest']['frames'];expected=[f['timestamp'] for f in frames]
        assert file_sha(source['input_manifest_path'])==source['input_manifest_sha256']
        out=a.output/source['id'];out.mkdir();poses=[]
        if prediction['status']=='predicted':
            path=a.run/source['id']/'predictions.npz';assert file_sha(path)==prediction['predictions_sha256']
            with np.load(path,allow_pickle=False) as data:camera=data['camera_poses'][0]
            assert camera.shape==(6,4,4) and np.isfinite(camera).all()
            assert np.array_equal(camera,np.asarray(prediction['poses_camera_to_world'],dtype=camera.dtype))
            for timestamp,matrix in zip(expected,camera):
                q=pycolmap.Rotation3d(matrix[:3,:3].astype(float)).quat
                poses.append([timestamp,*matrix[:3,3],*q])
        pred_file=out/'prediction.txt'
        pred_file.write_text('# Predicted camera-to-world; physical scale unverified\n'+''.join(' '.join(format(float(x),'.17g') for x in pose)+'\n' for pose in poses))
        evaluator=Path(source['evaluator_manifest_path']);assert file_sha(evaluator)==source['evaluator_manifest_sha256']
        gt=evaluator.parent/'groundtruth.txt';gt_sha=file_sha(gt);assert gt_sha==json.loads(evaluator.read_text())['groundtruth_sha256']
        result=evaluate(expected,read_tum(pred_file),read_tum(gt));assert file_sha(gt)==gt_sha
        result['inputs']=dict(prediction_sha256=file_sha(pred_file),ground_truth_sha256=gt_sha)
        (out/'evaluation.json').write_text(json.dumps(result,indent=2,allow_nan=False))
        check=None
        if result['sim3_ate'] is not None:
            m=result['sim3_ate']['alignment'];errors=[]
            for o in result['observations']:
                x=o['prediction']['translation'];y=o['ground_truth']['translation']
                errors.append(sum((m['scale']*sum(m['rotation'][i][j]*x[j] for j in range(3))+m['translation_m'][i]-y[i])**2 for i in range(3)))
            check=(sum(errors)/len(errors))**.5
            assert abs(check-result['sim3_ate']['rmse_m'])<1e-10
        rows.append(dict(id=source['id'],expected_frames=6,predicted_frames=len(poses),status=result['status'],
            sim3_ate_rmse_m=None if result['sim3_ate'] is None else result['sim3_ate']['rmse_m'],residual_recomputed_rmse_m=check,
            fitted_scale=None if result['sim3_ate'] is None else result['sim3_ate']['alignment']['scale'],
            prediction_sha256=file_sha(pred_file),evaluation_sha256=file_sha(out/'evaluation.json')))
    report=dict(schema='real2sim.tum-pi3x-evaluation/1',prediction_receipt_sha256=file_sha(a.run/'receipt.json'),
        script_sha256=file_sha(__file__),evaluator_sha256=protocol['evaluation_code_sha256'],expected_sources=3,expected_frames=18,
        evaluated_sources=sum(x['status']=='evaluated' for x in rows),predicted_frames=sum(x['predicted_frames'] for x in rows),sources=rows,
        wall_seconds=time.monotonic()-start,scope='One-seed learned reference on same six RGB frames as classical comparator. Different preprocessing/device/budget, not matched-budget agent A/B. Sim3 fitted from GT, not metric scale recovery; orientation/depth/physics and SOTA not evaluated.')
    (a.output/'receipt.json').write_text(json.dumps(report,indent=2,allow_nan=False));print(json.dumps(report,indent=2))


if __name__=='__main__':main()
