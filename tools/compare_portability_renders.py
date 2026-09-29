"""Compare every fixed format render to hash-bound controls and the source photo."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rgb(path):
    with Image.open(path) as im:return np.asarray(im.convert('RGB'),dtype=float)/255.

p=argparse.ArgumentParser(description=__doc__)
for key in ('protocol','candidate-dir','output'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();cfg=json.loads(a.protocol.read_text());assert not a.output.exists()
assert sha(cfg['source_photo'])==cfg['source_sha256']
receipt=json.loads((a.candidate_dir/'receipt.json').read_text())
assert receipt['protocol_sha256']==sha(a.protocol) and receipt['sources_unchanged']
size=(cfg['render']['width'],cfg['render']['height'])
with Image.open(cfg['source_photo']) as im:photo=np.asarray(im.convert('RGB').resize(size,Image.Resampling.LANCZOS),float)/255.
native=rgb(cfg['controls']['native']['render']);rows=[]
for name in cfg['formats']:
    control=cfg['controls'][name];assert sha(control['render'])==control['sha256']
    path=a.candidate_dir/name/'render.png';entry=next(r for r in receipt['groups'] if r['group']==name)
    assert entry['status'] in {'rendered','rendered_geometry_failed'} and sha(path)==entry['render_sha256']
    old,new=rgb(control['render']),rgb(path);assert old.shape==new.shape==photo.shape==native.shape
    row={'format':name,'control_sha256':sha(control['render']),'candidate_sha256':sha(path),
         'geometry_status':entry['geometry_status'],'control_to_native_full_mae':float(abs(old-native).mean()),
         'candidate_to_native_full_mae':float(abs(new-native).mean()),
         'control_to_photo_full_mae':float(abs(old-photo).mean()),'candidate_to_photo_full_mae':float(abs(new-photo).mean()),'regions':{}}
    for region,box in cfg['appearance_regions_xyxy'].items():
        x0,y0,x1,y1=[int(v/2) for v in box];sl=np.s_[y0:y1,x0:x1]
        row['regions'][region]={'control_to_native_mae':float(abs(old[sl]-native[sl]).mean()),
            'candidate_to_native_mae':float(abs(new[sl]-native[sl]).mean()),
            'control_to_photo_mae':float(abs(old[sl]-photo[sl]).mean()),'candidate_to_photo_mae':float(abs(new[sl]-photo[sl]).mean())}
    rows.append(row)
report={'schema':'real2sim.portability-render-comparison/1','protocol_sha256':sha(a.protocol),
        'render_receipt_sha256':sha(a.candidate_dir/'receipt.json'),'script_sha256':sha(__file__),
        'expected_formats':len(cfg['formats']),'groups':rows,
        'scope':'Fixed same-image RGB diagnostics only; all formats and inherited geometry failures retained. No material measurement or SOTA claim.'}
a.output.parent.mkdir(parents=True,exist_ok=True)
with a.output.open('x') as f:json.dump(report,f,indent=2,allow_nan=False)
print(json.dumps(rows,indent=2))
