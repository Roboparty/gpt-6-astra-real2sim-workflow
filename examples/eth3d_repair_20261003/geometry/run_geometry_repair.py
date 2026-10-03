"""Relocate and replay the frozen repair recipe without weakening its baseline pin.

blender -b BASE/models/v3/model.blend --threads 2 --python run_geometry_repair.py -- \
  --baseline-root BASE --repair-root NEW_ROOT --output-name replay_v4
"""
import argparse,sys,json,hashlib,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--baseline-root',type=Path,required=True);p.add_argument('--repair-root',type=Path,required=True);p.add_argument('--output-name',default='replay_v4');a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
here=Path(__file__).resolve().parent;root=a.repair_root.resolve();base=a.baseline_root.resolve();out=(root/a.output_name).resolve()
if not out.is_relative_to(root) or out.exists():raise ValueError('Use a new output directory inside repair-root')
root.mkdir(parents=True,exist_ok=True)
for name in ['topology_plan.json','repair_measurements.json','bin_multiview_tracks.json','bin_foot_seeded_tracks.json']:
 src=here/'evidence'/name;dst=root/name
 if dst.exists() and src.read_bytes()!=dst.read_bytes():raise ValueError('Existing parameter differs: '+name)
 if not dst.exists():shutil.copyfile(src,dst)
if not (root/'code').exists():shutil.copytree(base/'code',root/'code')
for name in ['shell_collision.py','simulation.py']:
 src=here/'runtime_changes'/name
 if src.exists():shutil.copyfile(src,root/'code/workflow/r2s'/name)
recipe=here/'repair_geometry.py';source=recipe.read_text()
for original,replacement in [("Path('/home/wqz/real2sim_agent_repair_20261003/geometry')",'Path('+repr(str(root))+')'),("Path('/home/wqz/real2sim_agent_compare_20261003/OURS')",'Path('+repr(str(base))+')'),("R/'candidate_v4'",'R/'+repr(a.output_name))]:
 if source.count(original)!=1:raise ValueError('Unexpected recipe version/ROOT count')
 source=source.replace(original,replacement)
exec(compile(source,str(recipe),'exec'),{'__name__':'__main__','__file__':str(recipe)})
(out/'replay_receipt.json').write_text(json.dumps(dict(recipe_sha256=hashlib.sha256(recipe.read_bytes()).hexdigest(),baseline_root=str(base),repair_root=str(root),adaptation='Filesystem paths/output name only; original frozen baseline SHA check retained',caveat='The output blend binary hash can differ because save metadata and paths differ. Compare evaluated geometry/camera/material hashes separately. This does not grant native acceptance.'),indent=2))
