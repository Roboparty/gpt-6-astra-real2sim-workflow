"""Same-mask image/footprint diagnostics, not full-project or true3D ranking."""
import argparse
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageDraw,ImageFont

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def footprint(points):
    mask=np.zeros((720,1280),np.uint8);cv2.fillConvexPoly(mask,cv2.convexHull(np.asarray(points,np.float32)).astype(np.int32),1);return mask.astype(bool)
def closed(obj):
    edges={}
    for face in obj['faces']:
        for a,b in zip(face,face[1:]+face[:1]):
            key=tuple(sorted((a,b)));edges[key]=edges.get(key,0)+1
    return bool(edges) and all(v==2 for v in edges.values())
def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    previous=Path('/data/real2sim_capability_wqz_20260929/desk1_web_phase_20260930');original=Path('/data/real2sim_capability_wqz_20260929/simfoundry_desk1/source/input.jpg');source=cv2.resize(cv2.imread(str(original)),(1280,720),interpolation=cv2.INTER_AREA).astype(float);masks={}
    for key in ['domino_sugar_box','chocolate_jello_box','red_jello_box','expo_marker']:masks[key]=cv2.resize(cv2.imread(str(previous/'hunyuan2/inputs'/(key+'_mask.png')),0),(1280,720),interpolation=cv2.INTER_NEAREST)>0
    allmask=np.logical_or.reduce(list(masks.values()));definitions=[('A_retained_ray_fit',Path('/data/real2sim_capability_wqz_20260929/simfoundry_desk1/authoring_002'),previous/'baseline_audit.json'),
        ('B_image_and_height_assumption',previous/'B_image_cuboids/rendered_entrypoint_repair',previous/'B_image_cuboids/blend_audit.json'),
        ('C_web_soft_priors',previous/'C_web_soft_cuboids/rendered_entrypoint_repair',previous/'C_web_soft_cuboids/blend_audit.json'),
        ('AHa_Pi3X_single_image_adaptation',a.root/'aha_pi3x_adapted_scene',a.root/'aha_pi3x_adapted_scene/blend_audit.json'),
        ('Real2Gym_MoGe3_static_adaptation',a.root/'real2gym_moge3_adapted_scene',a.root/'real2gym_moge3_adapted_scene/blend_audit.json'),
        ('AHa_Pi3X_adaptation_RGB_background_revision',a.root/'aha_pi3x_adapted_scene_rgb_repaired',a.root/'aha_pi3x_adapted_scene_rgb_repaired/blend_audit.json'),
        ('Real2Gym_MoGe3_adaptation_RGB_background_revision',a.root/'real2gym_moge3_adapted_scene_rgb_repaired',a.root/'real2gym_moge3_adapted_scene_rgb_repaired/blend_audit.json')]
    rows=[]
    for method,directory,audit_path in definitions:
        if not audit_path.is_file() or not (directory/'source_view.png').is_file():rows.append({'method':method,'status':'missing','expected_objects':4});continue
        audit=json.loads(audit_path.read_text());render=cv2.imread(str(directory/'source_view.png')).astype(float);objects=audit['objects'];parts={key:[obj for obj in objects if obj['object_id']==key] for key in masks};individual=[]
        for key,mask in masks.items():
            if not parts[key]:individual.append({'object_id':key,'status':'missing','iou':0});continue
            pixelpoints=[point for obj in parts[key] for point in obj['projected_vertices_1280']];pred=footprint(pixelpoints);individual.append({'object_id':key,'status':'present','projected_prebevel_footprint_iou':float(np.logical_and(pred,mask).sum()/np.logical_or(pred,mask).sum()),
                'rgb_mae_source_roi_0_255':float(np.abs(render-source)[mask].mean()),'closed_parts':sum(closed(obj) for obj in parts[key]),'parts':len(parts[key])})
        rows.append({'method':method,'status':'rendered_and_blend_readback','expected_objects':4,'present_objects':sum(bool(v) for v in parts.values()),
            'foreground_rgb_mae_0_255':float(np.abs(render-source)[allmask].mean()),'full_frame_rgb_mae_0_255':float(np.abs(render-source).mean()),
            'mean_instance_prebevel_footprint_iou':float(np.mean([x.get('projected_prebevel_footprint_iou',0) for x in individual])),
            'closed_foreground_parts':sum(closed(obj) for obj in objects),'total_foreground_parts':len(objects),'model_sha256':audit['model_sha256'],
            'audit_sha256':sha(audit_path),'source_render_sha256':sha(directory/'source_view.png'),'objects':individual})
    report={'schema':'real2sim.desk1-peer-adaptation-diagnostics/1','source_sha256':sha(original),'records':rows,'source_images':1,'mask_policy':'All four frozen manual source instance masks reused; not SAM or independent GT segmentation',
        'heldout_corner_metric':None,'heldout_reason':'Mask contours consumed prior manual corner observations; do not call these independent heldout points',
        'framework_ranking_valid':False,'gpt6_astra_independent_sessions':False,'sota_established':False,
        'limits':['One common hand-authored editable carton/cylinder adapter; differences primarily measure reference initializers and scale assumptions.',
            'Original AHa video/SAM3/TSDF/agent iterations and full Real2Gym Astra workflow not reproduced.',
            'Baseline B/C use explicit2D corner fitting, adaptations use point-reference primitives; optimization and supervision are not matched.',
            'Photo-projected visible materials contain captured light; image error is not independent material or geometry accuracy.',
            'Footprints use convex prebevel projected vertices, not an actual render instance mask.',
            'Novel views are virtual with no real reference; true metric3D/physics quality unmeasured.']}
    (a.output/'comparison.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    panelw,panelh=640,360;canvas=Image.new('RGB',(panelw*3,(panelh+38)*2+74),(244,246,249));draw=ImageDraw.Draw(canvas)
    try:font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17)
    except OSError:font=ImageFont.load_default()
    items=[('Real Desk1 / sole RGB',original),('Ours A / retained ray solids',definitions[0][1]/'source_view.png'),('Ours C / soft web dimensions',definitions[2][1]/'source_view.png'),
           ('AHa-inspired / Pi3X + RGB background ADAPTATION',definitions[5][1]/'source_view.png'),('Real2Gym-inspired / MoGe3 + RGB background ADAPTATION',definitions[6][1]/'source_view.png')]
    for i,(title,path) in enumerate(items):
        x=(i%3)*panelw;y=(i//3)*(panelh+38);draw.text((x+8,y+10),title,fill=(20,25,35),font=font)
        if path.is_file():canvas.paste(Image.open(path).convert('RGB').resize((panelw,panelh)),(x,y+38))
        else:draw.text((x+10,y+120),'Missing result retained',fill=(180,30,30),font=font)
    draw.multiline_text((2*panelw+15,panelh+80),'Same original photo; 4 objects retained.\n\nAdaptations use common instance authoring.\nThey are not official project Desk1 outputs.\n\nRGB projection includes captured lighting.\nNo true3D or full-framework ranking.',fill=(20,25,35),font=font,spacing=10)
    draw.text((10,(panelh+38)*2+10),'Single-case development comparison. See comparison.json for different supervision, camera/scale assumptions and retained failures.',fill=(20,25,35),font=font)
    canvas.save(a.output/'comparison.jpg',quality=92);print(json.dumps([{k:r.get(k) for k in ['method','status','foreground_rgb_mae_0_255','full_frame_rgb_mae_0_255','mean_instance_prebevel_footprint_iou']} for r in rows]))

if __name__=='__main__':main()
