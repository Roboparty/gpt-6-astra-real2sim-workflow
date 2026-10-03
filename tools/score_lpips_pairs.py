"""Evaluate frozen image pairs with an existing pinned LPIPS/AlexNet installation."""
import argparse,hashlib,json,os,sys
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--pairs',type=Path,required=True);p.add_argument('--package-root',type=Path,required=True);p.add_argument('--scipy-site',type=Path,required=True)
    p.add_argument('--torch-home',type=Path,required=True);p.add_argument('--weights-receipt',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise ValueError('Use a new output file')
    sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
    weights=json.loads(a.weights_receipt.read_text())
    for row in weights['files']:
        if sha(row['path'])!=row['sha256']:raise ValueError('LPIPS checkpoint hash drift')
    sys.path.insert(0,str(a.package_root));os.environ['TORCH_HOME']=str(a.torch_home)
    import torch,numpy as np
    sys.path.append(str(a.scipy_site))
    import lpips
    from PIL import Image
    torch.set_num_threads(2);model=lpips.LPIPS(net='alex',version='0.1',verbose=False).eval();results=[];identity=None
    for item in json.loads(a.pairs.read_text()):
        tensors=[]
        for name in ['source','render']:
            path=(a.pairs.parent/item[name]).resolve()
            if not path.is_relative_to(a.pairs.parent.resolve()) or sha(path)!=item[name+'_sha256']:raise ValueError('Image pair hash/path mismatch')
            rgb=np.asarray(Image.open(path).convert('RGB'),np.float32).transpose(2,0,1)/127.5-1;tensors.append(torch.from_numpy(rgb)[None])
        with torch.inference_mode():
            if identity is None:
                identity=float(model(tensors[0],tensors[0]).item())
                if abs(identity)>1e-7:raise ValueError('LPIPS identical-image sanity check failed')
            value=float(model(*tensors).item())
        results.append(dict(**item,lpips_alex_v01=value))
    a.out.write_text(json.dumps(dict(status='complete',pair_manifest_sha256=sha(a.pairs),runner_sha256=sha(__file__),pair_count=len(results),
        identical_image_sanity=identity,weights=weights,pairs=results),indent=2,allow_nan=False));print('LPIPS_COMPLETE',len(results))


if __name__=='__main__':main()
