"""Freeze explicitly annotated source polygons; never infer labels from a render."""
import argparse
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.contracts import digest
from r2s.geometry_feedback import file_sha256

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['source','scene','annotations','output']:
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    scene=json.loads(args.scene.read_text(encoding='utf-8-sig'))
    annotations=json.loads(args.annotations.read_text(encoding='utf-8-sig'))
    source=args.source.resolve()
    if file_sha256(source)!=annotations['source_sha256']:raise ValueError('Annotations refer to another source')
    size=Image.open(source).size
    if list(size)!=scene['camera']['image_size']:raise ValueError('Image size differs from fixed camera')
    objects=[]
    for index,obj in enumerate(annotations['objects']):
        mask=Image.new('L',size,0);draw=ImageDraw.Draw(mask)
        for polygon in obj['polygons']:draw.polygon([tuple(p) for p in polygon],fill=255)
        for polygon in obj.get('holes',[]):draw.polygon([tuple(p) for p in polygon],fill=0)
        path=out/f'mask_{index:04d}.png';mask.save(path)
        objects.append({'id':obj['id'],'mask':{'path':str(path),'sha256':file_sha256(path)}})
    protocol={'schema':'real2sim.geometry-feedback-protocol/1.0',
              'thresholds':annotations['thresholds'],
              'annotation_basis':annotations['annotation_basis'],
              'annotation_sha256':file_sha256(args.annotations),
              'views':[{'id':'source','role':'fit','camera':scene['camera'],
                        'source':{'path':str(source),'sha256':file_sha256(source)},'objects':objects}]}
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2))
    (out/'protocol.sha256').write_text(digest(protocol)+'\n')
    print(json.dumps({'protocol':str(out/'protocol.json'),'sha256':digest(protocol)}))
