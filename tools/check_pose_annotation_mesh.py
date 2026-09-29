"""Compare old and corrected annotations against the same retained posed mesh."""
import argparse,copy,hashlib,json,os,subprocess,sys,time
from pathlib import Path

repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'workflow'))
from r2s.pose_annotations import update_xy_yaw_annotations
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

p=argparse.ArgumentParser(description=__doc__)
for name in ['initial-scene','candidate-scene','model','actions','blender','output']:p.add_argument('--'+name,type=Path,required=True)
args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
initial=json.loads(args.initial_scene.read_text());candidate=json.loads(args.candidate_scene.read_text())
updated,update_receipt=update_xy_yaw_annotations(initial,json.loads(args.actions.read_text())['actions'])
corrected=copy.deepcopy(candidate);corrected['structure']=updated['structure']
model_sha=sha(args.model);rows=[]
for label,scene in [('retained_annotations',candidate),('corrected_annotations',corrected)]:
    directory=out/label;directory.mkdir();spec=directory/'scene.json';spec.write_text(json.dumps(scene,indent=2))
    started=time.monotonic()
    with (directory/'process.log').open('w') as log:
        proc=subprocess.run([str(args.blender),'-b',str(args.model),'-t','2','--python-exit-code','12','-P',str(repo/'workflow/r2s/blender_structure.py'),'--',str(spec),str(directory)],
            stdout=log,stderr=log,env=dict(os.environ,R2S_STRUCTURE_NO_RENDER='1',R2S_CPU='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2'),timeout=600)
    row={'label':label,'returncode':proc.returncode,'wall_seconds':time.monotonic()-started}
    audit=directory/'structural_audit.json'
    if audit.exists():
        data=json.loads(audit.read_text());row.update(audit_status=data['status'],failures=data['failures'],
            joint_count=sum(len(a['joints_checked']) for a in data['assemblies']),
            joint_failures=sum(j['status']!='pass' for a in data['assemblies'] for j in a['joints_checked']),audit_sha256=sha(audit))
    rows.append(row)
report={'scope':'Annotation binding validation on the same retained mesh; no new pose candidate or full-scene acceptance',
        'expected_conditions':2,'conditions':rows,'annotation_update':update_receipt,'input_model_unchanged':sha(args.model)==model_sha,
        'input_model_sha256':model_sha,'script_sha256':sha(__file__)}
(out/'comparison.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
