"""Actual authored scene export comparison; all sources remain untouched."""
import argparse,hashlib,json,os,subprocess,time
from pathlib import Path

sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser(description=__doc__)
for key in ['protocol','old-exporter','new-exporter','blender','output']:p.add_argument('--'+key,type=Path,required=True)
args=p.parse_args();protocol=json.loads(args.protocol.read_text());root=args.output.resolve();root.mkdir(parents=True,exist_ok=False)
model=Path(protocol['source_model']);spec=Path(protocol['source_scene']);scene=json.loads(spec.read_text())
assert sha(model)==protocol['source_model_sha256']
inputs={'model':sha(model),'scene':sha(spec)};rows=[]
for label,worker in zip(protocol['registered_conditions'],[args.old_exporter,args.new_exporter]):
    out=root/label;out.mkdir();t=time.monotonic()
    env=dict(os.environ,R2S_CPU='1',CUDA_VISIBLE_DEVICES='',PYTHONPATH=str(args.new_exporter.parent),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
    with (out/'run.log').open('w') as log:
        run=subprocess.run([str(args.blender),'-b',str(model),'-t','2','--python-exit-code','12','-P',str(worker),'--',str(spec),str(out),'--geometry-only'],stdout=log,stderr=log,env=env,timeout=300)
    row={'condition':label,'returncode':run.returncode,'worker_sha256':sha(worker),'wall_seconds':time.monotonic()-t}
    if (out/'geometry_audit.json').exists():
        audit=json.loads((out/'geometry_audit.json').read_text());errors={}
        for obj in scene['objects']:
            expected=[[obj['position'][i]-obj['dimensions'][i]/2 for i in range(3)],[obj['position'][i]+obj['dimensions'][i]/2 for i in range(3)]]
            actual=audit['entities'][obj['id']]['world_aabb']
            errors[obj['id']]=max(abs(expected[j][i]-actual[j][i]) for j in range(2) for i in range(3))
        row.update(per_entity_bound_error_m=errors,maximum_bound_error_m=max(errors.values()))
        row['preservation_gate_pass']=run.returncode==0 and row['maximum_bound_error_m']<=protocol['gate_m']
    rows.append(row)
report={'conditions':rows,'expected_conditions':2,'input_hashes':inputs,'inputs_unchanged':inputs=={'model':sha(model),'scene':sha(spec)},'protocol_sha256':sha(args.protocol)}
(root/'comparison.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
