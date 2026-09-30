"""Scientific contact sheet from unchanged actual source/render images; no generative edit."""
import argparse
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve old figure')
    base=Path('/data/real2sim_capability_wqz_20260929/simfoundry_desk1');items=[('Real source / single image',base/'source/input.jpg',None),
      ('A retained ray solids / assumed geometry',base/'authoring_002/source_view.png',base/'authoring_002/virtual_inspection.png')]
    for arm,label in [('B_image_cuboids','B image-only orthogonal cuboids'),('C_web_soft_cuboids','C web dimensions / soft assumption'),('D_web_fixed_cuboids','D fixed nominal web dimensions')]:
        out=a.root/arm/'rendered_entrypoint_repair';items.append((label,out/'source_view.png',out/'virtual_inspection.png'))
    panelw,panelh=640,360;figure=Image.new('RGB',(panelw*5,30+panelh+30+panelh+65),(245,245,245));draw=ImageDraw.Draw(figure)
    try:font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14)
    except OSError:font=ImageFont.load_default()
    for i,(title,source,virtual) in enumerate(items):
        draw.text((i*panelw+8,8),title,fill=(20,20,20),font=font)
        image=Image.open(source).convert('RGB');image.thumbnail((panelw,panelh));figure.paste(image,(i*panelw,30))
        draw.text((i*panelw+8,30+panelh+8),'Virtual inspection / no real heldout view' if virtual else 'No second real observation supplied',fill=(160,40,30),font=font)
        if virtual:
            image=Image.open(virtual).convert('RGB');image.thumbnail((panelw,panelh));figure.paste(image,(i*panelw,30+panelh+30))
    y=30+panelh+30+panelh+8
    draw.text((8,y),'Single-case development diagnostics. Photo texture contains captured lighting; visual fit is not independent 3D accuracy.',fill=(20,20,20),font=font)
    draw.text((8,y+23),'B/C/D same-image heldout corner distance: 2.74 / 5.80 / 7.99 px. A used all corners. No SOTA claim.',fill=(20,20,20),font=font)
    figure.save(a.output,quality=90);print(a.output)

if __name__=='__main__':main()
