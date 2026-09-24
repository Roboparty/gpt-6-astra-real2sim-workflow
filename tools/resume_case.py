"""Resume through the executor, invalidating declared case sources when they change.
Does not invent Agent responses or mark stages successful.
"""
import json,sys,hashlib
from pathlib import Path
from r2s.core import Workflow,atomic_json
case=Path(sys.argv[1]).resolve();watch=case/'source_watch.json';w=Workflow(case);changed=[]
if watch.exists():
 data=json.loads(watch.read_text());base=(case/data['root']).resolve()
 for stage,items in data['stages'].items():
  new=[]
  for item in items:
   path=(base/item['path']).resolve()
   if not path.is_relative_to(base):raise ValueError('Watch path escapes declared case root')
   sha=hashlib.sha256(path.read_bytes()).hexdigest();new.append(dict(path=item['path'],sha256=sha))
   if sha!=item['sha256']:changed.append(dict(stage=stage,path=item['path'],old=item['sha256'],new=sha))
  if any(x['stage']==stage for x in changed):
   w.revise(stage,'Declared case source changed: '+', '.join(x['path'] for x in changed if x['stage']==stage));w.config.setdefault('stages',{}).setdefault(stage,{}).setdefault('parameters',{})['watched_sources']=new;data['stages'][stage]=new
 if changed:
  atomic_json(case/'case.json',w.config);atomic_json(watch,data);w.event({'action':'case_source_change_detected','changes':changed});w=Workflow(case)
print(json.dumps({'source_changes':changed,'run':w.run(retry_failed='--retry-failed' in sys.argv)},indent=2))
