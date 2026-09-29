"""Read-only audit of acquired RGB/evaluator separation and sensor timestamp coverage."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from PIL import Image


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise ValueError('Retain previous audit; new output required')
    start=time.monotonic();receipt=json.loads((a.input/'receipt.json').read_text());rows=[]
    for acquired in receipt['sources']:
        row={'source_id':acquired['id'],'status':'not_ready','expected_frames':6};rows.append(row)
        if acquired['status']!='prepared':row['reason']='Acquisition incomplete';continue
        try:
            root=a.input/acquired['id'];inputs=root/'inputs';evaldir=root/'evaluator'
            assert sha(inputs/'manifest.json')==acquired['input_manifest_sha256']
            assert sha(evaldir/'manifest.json')==acquired['evaluator_manifest_sha256']
            data=json.loads((inputs/'manifest.json').read_text());evaluation=json.loads((evaldir/'manifest.json').read_text())
            assert sha(evaldir/'groundtruth.txt')==evaluation['groundtruth_sha256']
            gt=np.loadtxt(evaldir/'groundtruth.txt',comments='#',ndmin=2)
            if gt.shape[1]!=8 or not np.isfinite(gt).all() or not np.all(np.diff(gt[:,0])>0):raise ValueError('Invalid mocap trajectory rows')
            norms=np.linalg.norm(gt[:,4:8],axis=1)
            if np.any(abs(norms-1)>1e-3):raise ValueError('Invalid mocap quaternions')
            expected=set(['manifest.json']+[f'rgb_{i:02d}.png' for i in range(6)])
            if {p.name for p in inputs.iterdir()}!=expected:raise ValueError('Proposer directory contains unexpected files')
            checks=[];used=set()
            for frame in data['frames']:
                fp=Path(frame['path']);assert fp.resolve().parent==inputs.resolve() and sha(fp)==frame['sha256']
                with Image.open(fp) as im:assert im.size==(640,480) and im.mode=='RGB';im.verify()
                idx=int(np.argmin(abs(gt[:,0]-frame['timestamp'])));gap=float(abs(gt[idx,0]-frame['timestamp']))
                matched=gap<=.02 and idx not in used
                if matched:used.add(idx)
                checks.append({'ordinal':frame['ordinal'],'timestamp':frame['timestamp'],'rgb_sha256':frame['sha256'],
                               'gt_match':matched,'gt_timestamp':float(gt[idx,0]) if matched else None,'gt_gap_seconds':gap})
            for d in evaluation['depth_matches']:
                entry=checks[d['rgb_ordinal']];entry['depth_match']=d['matched'];entry['depth_gap_seconds']=d['gap_seconds']
                if not d['matched']:continue
                dp=Path(d['path']);assert dp.resolve().parent==evaldir.resolve() and sha(dp)==d['sha256']
                with Image.open(dp) as im:depth=np.asarray(im)
                if depth.shape!=(480,640) or depth.dtype.kind not in 'iu' or np.any((depth<0)|(depth>65535)):raise ValueError('Invalid uint16 depth encoding')
                valid=depth>0;entry['valid_depth_pixels']=int(valid.sum());entry['total_depth_pixels']=int(depth.size)
                entry['depth_metres_range']=[float(depth[valid].min()/5000),float(depth[valid].max()/5000)] if valid.any() else None
            row.update(observations=checks,groundtruth_rows=len(gt),groundtruth_sha256=evaluation['groundtruth_sha256'],
                       matched_gt=sum(x['gt_match'] for x in checks),matched_depth=sum(x.get('depth_match',False) for x in checks),
                       max_quaternion_norm_error=float(abs(norms-1).max()),input_directory_rgb_only=True,
                       status='ready' if len(checks)==6 and all(x['gt_match'] and x.get('depth_match') for x in checks) else 'not_ready')
        except Exception as exc:row.update(status='failed',reason=repr(exc))
    report={'schema':'real2sim.tum-input-audit/1','acquisition_receipt_sha256':sha(a.input/'receipt.json'),
            'script_sha256':sha(__file__),'expected_sequences':3,'ready_sequences':sum(r['status']=='ready' for r in rows),
            'sources':rows,'wall_seconds':time.monotonic()-start,
            'scope':'Data decoding and sensor-reference association only; no predicted geometry, calibration accuracy or SOTA',
            'truth_separation':'Logical directory separation only; not a filesystem sandbox'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2))
    print(json.dumps({'ready_sequences':report['ready_sequences'],'expected_sequences':3,'wall_seconds':report['wall_seconds']}))


if __name__=='__main__':main()
