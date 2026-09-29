"""Small RGB previews for manual source annotation; original frozen frames stay remote."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from PIL import Image, ImageDraw


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--frames',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();start=time.monotonic()
    frozen=json.loads(a.frames.read_text());a.output.mkdir(parents=True,exist_ok=False)
    result={'schema':'real2sim.annotation-previews/1','frames_manifest_sha256':sha(a.frames),
            'script_sha256':sha(__file__),'sources':[],
            'scope':'Lossy RGB display copies only; geometry labels must bind original frame hashes, not these previews'}
    for source in frozen['sources']:
        directory=a.output/source['id'];directory.mkdir()
        sheet=Image.new('RGB',(960,870),'white');draw=ImageDraw.Draw(sheet);rows=[]
        for index,frame in enumerate(source['selected_frames']):
            assert sha(frame['path'])==frame['sha256']
            with Image.open(frame['path']) as image:
                assert list(image.size)==frame['image_size']==[960,540]
                rgb=image.convert('RGB');dest=directory/f'frame_{index:02d}.jpg'
                rgb.save(dest,quality=88)
                x=(index%2)*480;y=(index//2)*290
                sheet.paste(rgb.resize((480,270),Image.Resampling.LANCZOS),(x,y+20))
                draw.text((x+5,y+3),f"frame {index}: decoded {frame['decoded_frame_index']}",fill='black')
            rows.append({'ordinal':index,'decoded_frame_index':frame['decoded_frame_index'],
                         'original_sha256':frame['sha256'],'preview':str(dest),
                         'preview_sha256':sha(dest),'preview_bytes':dest.stat().st_size})
        overview=directory/'overview.jpg';sheet.save(overview,quality=88)
        result['sources'].append({'id':source['id'],'frames':rows,'overview':str(overview),
                                  'overview_sha256':sha(overview)})
    result['wall_seconds']=time.monotonic()-start
    (a.output/'receipt.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'sources':len(result['sources']),'frames':sum(len(s['frames']) for s in result['sources']),
                      'wall_seconds':result['wall_seconds']}))


if __name__=='__main__':main()
