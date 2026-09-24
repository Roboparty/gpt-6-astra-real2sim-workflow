import argparse,json
from .core import Workflow
from .contracts import scene_check,apply_layout_patch,robohousegen_packet
from pathlib import Path
p=argparse.ArgumentParser(prog='r2s');sub=p.add_subparsers(dest='action',required=True)
for name in ['run','status','freeze']:
 q=sub.add_parser(name);q.add_argument('case')
 if name=='run':q.add_argument('--until');q.add_argument('--retry-failed',action='store_true')
q=sub.add_parser('accept');q.add_argument('case');q.add_argument('stage');q.add_argument('response')
q=sub.add_parser('revise');q.add_argument('case');q.add_argument('stage');q.add_argument('--reason',required=True)
q=sub.add_parser('check-scene');q.add_argument('scene')
q=sub.add_parser('patch');q.add_argument('scene');q.add_argument('patch');q.add_argument('output');q.add_argument('--authority',required=True);q.add_argument('--evidence',action='append',default=[])
a=p.parse_args()
if a.action=='check-scene':result=scene_check(json.loads(Path(a.scene).read_text()))
elif a.action=='patch':result=apply_layout_patch(json.loads(Path(a.scene).read_text()),json.loads(Path(a.patch).read_text()),a.authority,a.evidence);Path(a.output).write_text(json.dumps(result,indent=2))
else:
 w=Workflow(a.case)
 if a.action=='run':result=w.run(a.until,a.retry_failed)
 elif a.action=='status':result={k:{'status':v['status'],'valid':w.valid(k),'attempt':v['attempt'],'directory':v['directory']} for k,v in w.state['stages'].items()}
 elif a.action=='accept':result={'accepted':w.accept(a.stage,a.response)}
 elif a.action=='revise':result={'invalidated':w.revise(a.stage,a.reason)}
 else:result=w.freeze()
print(json.dumps(result,ensure_ascii=False,indent=2))
