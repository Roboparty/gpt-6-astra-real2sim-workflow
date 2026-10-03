"""Make source/render/depth-error review sheets from common fit-only checker outputs."""
import argparse,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw


def main():
    p=argparse.ArgumentParser();p.add_argument('checks',type=Path);a=p.parse_args();report=json.loads((a.checks/'report.json').read_text());data=np.load(a.checks/'depth_checks.npz')
    for group in range((len(report['rows'])+4)//5):
        sheet=Image.new('RGB',(1200,5*290),'#eeeeee');draw=ImageDraw.Draw(sheet)
        for j,row in enumerate(report['rows'][group*5:group*5+5]):
            i=group*5+j;model=data['model_depth_z_m'][i];reference=data['reference_depth_z_m'][i];domain=np.isfinite(reference)&(reference>=.1)&(reference<=30);valid=domain&np.isfinite(model)
            error=np.clip(np.nan_to_num(model-reference),-1,1);rgb=np.full((*error.shape,3),100,np.uint8);rgb[valid]=np.stack([255*np.maximum(error,0),255*(1-np.abs(error)),255*np.maximum(-error,0)],axis=-1)[valid];rgb[domain&~valid]=[255,0,255]
            images=[Image.open(row['source']).convert('RGB'),Image.open(a.checks/row['render']).convert('RGB'),Image.fromarray(rgb)]
            for col,image in enumerate(images):image.thumbnail((400,260));sheet.paste(image,(col*400,j*290+25))
            draw.text((5,j*290+4),f"{row['index']} {row['frame_id']} | SOURCE / MODEL / predicted-depth residual(+red,-blue,missing magenta)",fill='black')
        sheet.save(a.checks/f'comparison_{group}.jpg',quality=90)
    print('SHEETS_READY',a.checks)


if __name__=='__main__':main()
