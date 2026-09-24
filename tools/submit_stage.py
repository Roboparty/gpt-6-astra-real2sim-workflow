"""Submit an authored response to an actual pending executor packet; never edits state."""
import sys,json,shutil
from pathlib import Path
from r2s.core import Workflow
root=Path(__file__).resolve().parents[1]
branch,stage,source=sys.argv[1:4];source=Path(source)
w=Workflow(root/'case'/branch)
entry=w.state['stages'][stage]
if entry['status'] not in ['awaiting_agent','changes_requested','needs_input']:raise RuntimeError('Stage is not pending')
out=Path(entry['directory']);response=json.loads((source/'response.json').read_text())
for rel in response['artifacts']:
    dest=out/rel;dest.parent.mkdir(parents=True,exist_ok=True)
    if (source/rel).resolve()!=dest.resolve():shutil.copyfile(source/rel,dest)
(out/'response.json').write_text(json.dumps(response,indent=2,ensure_ascii=False))
print(json.dumps({'accepted':w.accept(stage,out/'response.json'),'stage':stage,'attempt':entry['attempt']}))
