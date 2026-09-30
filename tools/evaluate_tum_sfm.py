"""Evaluate already-frozen RGB SfM outputs, retaining every expected timestamp."""
import argparse
import json
from pathlib import Path
import time
import numpy as np
import pycolmap
from evaluate_tum_trajectory import evaluate, read_tum, file_sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('run','rgb-index','output'):
        parser.add_argument('--'+key,type=Path,required=True)
    a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    receipt=json.loads((a.run/'receipt.json').read_text())
    frames=json.loads((a.run/'frames.json').read_text())
    protocol=json.loads((a.run/'protocol.json').read_text())
    index=json.loads(a.rgb_index.read_text())
    assert file_sha(a.run/'frames.json')==receipt['frames_receipt_sha256']
    assert file_sha(a.run/'protocol.json')==receipt['protocol_sha256']
    assert file_sha(a.run/'initializer_snapshot.py')==receipt['script_sha256']
    assert receipt['original_inputs_unchanged'] and len(receipt['sources'])==len(index['sources'])==3
    report=dict(schema='real2sim.tum-sfm-evaluation/1',initializer_receipt_sha256=file_sha(a.run/'receipt.json'),
                rgb_index_sha256=file_sha(a.rgb_index),script_sha256=file_sha(__file__),
                evaluator_sha256=file_sha(Path(__file__).with_name('evaluate_tum_trajectory.py')),
                expected_sources=3,expected_frames=18,sources=[],
                scope='Unknown-intrinsics RGB-only classical reference, one seed. Sim3 scale uses GT alignment; no recovered metric scale or SOTA. SE3 values are unscaled-gauge diagnostics, not physical metre errors.')
    assert report['evaluator_sha256']==protocol['implementation_sha256']['tools/evaluate_tum_trajectory.py']
    for source,freeze,rgb in zip(receipt['sources'],frames['sources'],index['sources']):
        assert source['id']==freeze['id']==rgb['id']
        assert file_sha(rgb['input_manifest_path'])==rgb['input_manifest_sha256']
        out=a.output/source['id'];out.mkdir()
        selected=freeze['selected_frames'];expected=[f['timestamp'] for f in selected]
        predictions=[]
        for camera in source.get('result',{}).get('cameras',[]):
            n=int(camera['frame_name'].removeprefix('frame_').removesuffix('.png'))
            assert camera['frame_name']==f'frame_{n:04d}.png' and 0<=n<len(selected)
            rotation=np.asarray(camera['rotation_world_to_cv'],float).T
            assert np.allclose(rotation.T@rotation,np.eye(3),atol=1e-6) and abs(np.linalg.det(rotation)-1)<1e-6
            quaternion=pycolmap.Rotation3d(rotation).quat
            predictions.append([expected[n],*camera['position_in_sfm_gauge'],*quaternion])
        predictions.sort(key=lambda row:row[0])
        prediction=out/'prediction.txt'
        prediction.write_text('# Camera-to-world poses in arbitrary SfM gauge; not metres\n'+''.join(' '.join(format(float(x),'.17g') for x in row)+'\n' for row in predictions))
        truth=Path(rgb['evaluator_manifest_path']).parent/'groundtruth.txt'
        eval_manifest=json.loads(Path(rgb['evaluator_manifest_path']).read_text())
        assert file_sha(Path(rgb['evaluator_manifest_path']))==rgb['evaluator_manifest_sha256']
        truth_sha=file_sha(truth);assert truth_sha==eval_manifest['groundtruth_sha256']
        result=evaluate(expected,read_tum(prediction),read_tum(truth))
        assert file_sha(truth)==truth_sha
        result['inputs']={'prediction_sha256':file_sha(prediction),'ground_truth_sha256':truth_sha}
        (out/'evaluation.json').write_text(json.dumps(result,indent=2,allow_nan=False))
        # Independent residual check using the returned Sim3 transformation.
        residual_check=None
        if result['sim3_ate'] is not None:
            transform=result['sim3_ate']['alignment'];errors=[]
            for observation in result['observations']:
                x=observation['prediction']['translation'];y=observation['ground_truth']['translation']
                z=[transform['scale']*sum(transform['rotation'][i][j]*x[j] for j in range(3))+transform['translation_m'][i] for i in range(3)]
                errors.append(sum((z[i]-y[i])**2 for i in range(3))**.5)
            rmse=(sum(e*e for e in errors)/len(errors))**.5
            assert abs(rmse-result['sim3_ate']['rmse_m'])<1e-10
            residual_check=rmse
        report['sources'].append(dict(id=source['id'],initialization_status=source['status'],expected_frames=6,
            registered_frames=len(predictions),evaluation_status=result['status'],missing_prediction_ordinals=result['missing_prediction_ordinals'],
            sim3_ate_rmse_m=None if result['sim3_ate'] is None else result['sim3_ate']['rmse_m'],
            residual_recomputed_rmse_m=residual_check,point_count=source.get('result',{}).get('point_count'),
            prediction_sha256=file_sha(prediction),evaluation_sha256=file_sha(out/'evaluation.json')))
    report['fully_evaluated_sources']=sum(s['evaluation_status']=='evaluated' for s in report['sources'])
    report['registered_frames']=sum(s['registered_frames'] for s in report['sources'])
    report['wall_seconds']=time.monotonic()-started
    (a.output/'receipt.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
