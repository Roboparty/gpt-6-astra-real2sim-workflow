import sys,os,json,hashlib
from pathlib import Path
root=Path('/home/wqz/real2sim_awsm_20261003');base=root/'eth3d_lpips'
sys.path.insert(0,str(root/'evaldeps'));os.environ['TORCH_HOME']=str(root/'torch_eval_cache')
import torch,numpy as np
sys.path.append('/home/wqz/real2sim_fresh_20260921/runtime/venv/lib/python3.10/site-packages')
import lpips
from PIL import Image
torch.set_num_threads(2);model=lpips.LPIPS(net='alex',version='0.1',verbose=False).eval();rows=[]
for item in json.loads((base/'pairs.json').read_text()):
 tensors=[]
 for key in ('source','render'):
  path=base/item[key];assert hashlib.sha256(path.read_bytes()).hexdigest()==item[key+'_sha256']
  arr=np.asarray(Image.open(path).convert('RGB'),np.float32).transpose(2,0,1)/127.5-1
  tensors.append(torch.from_numpy(arr)[None])
 with torch.inference_mode():value=float(model(*tensors).item())
 rows.append(dict(**item,lpips_alex_v01=value))
weights=json.loads((root/'lpips_weights.json').read_text())
(base/'lpips_results.json').write_text(json.dumps(dict(status='complete',pairs=rows,weights=weights),indent=2))
print('LPIPS_COMPLETE',len(rows))