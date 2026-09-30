"""One frozen RGB-only Pi3X configuration across the complete TUM cohort."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024**2),b''):h.update(chunk)
    return h.hexdigest()


def write(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False))


def gpu_guard(uuid,allow_self=False):
    apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_gpu_memory','--format=csv,noheader'],text=True)
    for line in apps.splitlines():
        fields=[x.strip() for x in line.split(',')]
        if fields[0]==uuid and (not allow_self or int(fields[1])!=os.getpid()):
            raise RuntimeError('Selected GPU has external work; refuse inference')
    info=subprocess.check_output(['nvidia-smi','--query-gpu=uuid,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True)
    selected=next([x.strip() for x in line.split(',')] for line in info.splitlines() if line.split(',')[0].strip()==uuid)
    if not allow_self and (int(selected[1])>100 or int(selected[2])!=0):raise RuntimeError('Selected GPU not idle')
    return dict(apps=apps.splitlines(),selected=selected)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('protocol','frames','output'):parser.add_argument('--'+key,type=Path,required=True)
    a=parser.parse_args();cfg=json.loads(a.protocol.read_text());frames=json.loads(a.frames.read_text())
    assert sha(a.frames)==cfg['frames_sha256'] and frames['cohort_id']==cfg['cohort']
    assert [s['id'] for s in frames['sources']]==cfg['source_ids'] and len(frames['sources'])==3
    assert sha(__file__)==cfg['runner_sha256']
    a.output.mkdir(parents=True,exist_ok=False);start=time.monotonic();session_start=None
    report=dict(schema='real2sim.tum-pi3x-prediction/1',status='started',protocol_sha256=sha(a.protocol),frames_sha256=sha(a.frames),
                runner_sha256=sha(__file__),expected_sources=3,expected_frames=18,sources=[dict(id=s['id'],status='not_run') for s in frames['sources']])
    write(a.output/'receipt.json',report)
    try:
        assert os.environ.get('CUDA_VISIBLE_DEVICES')==cfg['gpu_uuid']
        report['gpu_preflight']=gpu_guard(cfg['gpu_uuid'])
        if shutil.disk_usage(a.output).free<4*1024**3:raise RuntimeError('Insufficient disk reserve')
        base=Path(cfg['runtime_root'])
        for rel,value in cfg['source_sha256'].items():
            if sha(base/rel)!=value:raise ValueError('Pinned source changed: '+rel)
        if sha(base/'model.safetensors')!=cfg['weight_sha256']:raise ValueError('Weights changed')
        sys.path.insert(0,str(base/'source'))
        import numpy as np
        import torch
        from safetensors.torch import load_file
        from pi3.models.pi3x import Pi3X
        from pi3.utils.basic import load_multimodal_data
        torch.set_num_threads(2);torch.manual_seed(cfg['seed'])
        report['runtime']=dict(torch=torch.__version__,numpy=np.__version__,cuda=torch.version.cuda)
        session_start=time.monotonic()
        model=Pi3X(use_multimodal=True).eval();weights=load_file(str(base/'model.safetensors'),device='cpu')
        loaded=model.load_state_dict(weights,strict=True);del weights
        assert not loaded.missing_keys and not loaded.unexpected_keys
        model.disable_multimodal(free_cuda_cache=False);model=model.to('cuda')
        report['checkpoint_loaded_strictly']=True
        for source,row in zip(frames['sources'],report['sources']):
            t=time.monotonic();out=a.output/source['id'];out.mkdir();inputs=out/'inputs';inputs.mkdir()
            try:
                if time.monotonic()-start>cfg['max_wall_seconds']:raise TimeoutError('Shared run deadline reached')
                row['gpu_preflight']=gpu_guard(cfg['gpu_uuid'],allow_self=True)
                assert len(source['selected_frames'])==6
                for i,frame in enumerate(source['selected_frames']):
                    assert sha(frame['path'])==frame['sha256']
                    shutil.copyfile(frame['path'],inputs/f'{i:02d}.png')
                    assert sha(inputs/f'{i:02d}.png')==frame['sha256']
                torch.manual_seed(cfg['seed'])
                imgs,conditions=load_multimodal_data(str(inputs),dict(intrinsics=None,poses=None,depths=None),interval=1,PIXEL_LIMIT=cfg['pixel_limit'],device='cuda')
                assert list(imgs.shape)==[1,6,3,*cfg['output_hw']]
                torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();forward_start=time.monotonic()
                with torch.inference_mode(),torch.amp.autocast('cuda',dtype=torch.bfloat16):pred=model(imgs=imgs,**conditions)
                torch.cuda.synchronize();row['forward_seconds']=time.monotonic()-forward_start
                row['peak_reserved_bytes']=torch.cuda.max_memory_reserved()
                arrays={k:v.detach().float().cpu().numpy() for k,v in pred.items() if torch.is_tensor(v)}
                np.savez(out/'predictions.npz',**arrays)
                row['predictions_sha256']=sha(out/'predictions.npz')
                assert all(np.isfinite(v).all() for v in arrays.values())
                poses=arrays['camera_poses'];assert poses.shape==(1,6,4,4)
                assert np.allclose(poses[0,:,3,:],np.array([0,0,0,1]),atol=1e-5)
                rot=poses[0,:,:3,:3]
                assert np.max(abs(rot.transpose(0,2,1)@rot-np.eye(3)))<1e-4
                assert np.max(abs(np.linalg.det(rot)-1))<1e-4
                error=max(float(np.max(abs(arrays['local_points'][0,i]@rot[i].T+poses[0,i,:3,3]-arrays['points'][0,i]))) for i in range(6))
                assert error<1e-3
                row.update(status='predicted',camera_count=6,poses_camera_to_world=poses[0].tolist(),point_transform_max_error=error,
                           outputs={k:dict(shape=list(v.shape),dtype=str(v.dtype)) for k,v in arrays.items()})
                del pred,arrays,imgs,conditions
                torch.cuda.empty_cache()
            except Exception as exc:row.update(status='failed',error=repr(exc))
            row['wall_seconds']=time.monotonic()-t;write(a.output/'receipt.json',report)
            print(json.dumps({k:row.get(k) for k in ('id','status','error','forward_seconds')}),flush=True)
        report['status']='predicted' if all(r['status']=='predicted' for r in report['sources']) else 'incomplete'
        report['source_inputs_unchanged']=all(sha(f['path'])==f['sha256'] for s in frames['sources'] for f in s['selected_frames'])
        assert sha(a.protocol)==report['protocol_sha256'] and sha(a.frames)==report['frames_sha256']
    except Exception as exc:report.update(status='failed',error=repr(exc))
    finally:
        report['wall_seconds']=time.monotonic()-start
        report['gpu_session_wall_seconds']=0 if session_start is None else time.monotonic()-session_start
        report['forward_seconds']=sum(r.get('forward_seconds',0) for r in report['sources'])
        report['scope']='Three-source RGB-only learned reference; prediction/numerical validity, not real geometry or SOTA. No GT opened by this runner.'
        write(a.output/'receipt.json',report)
    if report['status']!='predicted':raise RuntimeError('Full prediction cohort incomplete; retain all source rows')


if __name__=='__main__':main()
