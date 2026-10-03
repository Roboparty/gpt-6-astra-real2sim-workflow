import json,pathlib,sys,numpy as np,hashlib
from PIL import Image
R=pathlib.Path(__file__).resolve().parents[1]
if sys.argv[1]=='prepare':
 out=R/'cache_rgb';out.mkdir(exist_ok=True);p=json.load(open('/home/wqz/real2sim_agent_compare_20261003/OURS/inputs/packet.json'))
 for f in p['frames']:
  assert hashlib.sha256(pathlib.Path(f['path']).read_bytes()).hexdigest()==f['sha256'];np.save(out/f"{f['input_index']:03d}.npy",np.array(Image.open(f['path']).convert('RGB')))
 print('PREPARED36_SRGB')
else:
 arr=np.load(sys.argv[2]);Image.fromarray(arr,'RGBA').save(sys.argv[3])
