"""Recompute Desk1 diagnostics from actual geometry/renders; not a GT 3D evaluator."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import cv2
import numpy as np

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def mask_from_pixels(points):
    mask=np.zeros((720,1280),np.uint8);cv2.fillConvexPoly(mask,cv2.convexHull(np.array(points,dtype=np.float32)).astype(np.int32),1);return mask.astype(bool)
def box_angles(v):
    v=np.array(v);vectors=[v[1]-v[0],v[3]-v[0],v[4]-v[0]]
    return [abs(math.degrees(math.acos(np.clip(np.dot(vectors[i],vectors[j])/np.linalg.norm(vectors[i])/np.linalg.norm(vectors[j]),-1,1)))-90) for i,j in [(0,1),(0,2),(1,2)]]
def closed_mesh(obj):
    edges={}
    for f in obj['faces']:
        for i,j in zip(f,f[1:]+f[:1]):
            key=tuple(sorted((i,j)));edges[key]=edges.get(key,0)+1
    return bool(edges) and all(n==2 for n in edges.values())
def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--annotation',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--require-blend-audits',action='store_true');a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve previous evaluation')
    annotation=json.loads(a.annotation.read_text());source=cv2.imread(annotation['source_image']);source=cv2.resize(source,(1280,720),interpolation=cv2.INTER_AREA).astype(float)
    roi={}
    for spec in annotation['boxes']:roi[spec['id']]=mask_from_pixels(spec['top_front_order']+list(spec['bottom_pixels'].values()))
    # Marker ROI uses only original endpoints and a predeclared 12px transverse half width.
    start,end=np.array(annotation['marker']['axis_pixels']);d=end-start;normal=np.array([-d[1],d[0]])/np.linalg.norm(d)*12
    roi['expo_marker']=mask_from_pixels([start+normal,start-normal,end+normal,end-normal]);all_roi=np.logical_or.reduce(list(roi.values()))
    baseline=json.loads((a.root/'baseline_audit.json').read_text());records=[]
    for arm in ['A_retained_ray_fit','B_image_cuboids','C_web_soft_cuboids','D_web_fixed_cuboids']:
        if arm.startswith('A_'):
            objects=baseline['objects'];render=Path('/data/real2sim_capability_wqz_20260929/simfoundry_desk1/authoring_002/source_view.png');fit=None
            bindings={'model_sha256':baseline['model_sha256'],'audit_sha256':sha(a.root/'baseline_audit.json')}
        else:
            fit_path=a.root/arm/'fitting/fit.json';fit=json.loads(fit_path.read_text());out=a.root/arm/'rendered_entrypoint_repair'
            inventory=json.loads((out/'objects.json').read_text());objects=[]
            for obj in inventory:
                if obj['object_id'] in [x['id'] for x in fit['boxes']]:
                    obj['projected_vertices_1280']=next(x['projected_vertices_1280'] for x in fit['boxes'] if x['id']==obj['object_id'])
                objects.append(obj)
            render=out/'source_view.png';receipt=json.loads((out/'receipt.json').read_text());bindings={'model_sha256':receipt['model_sha256'],'fit_sha256':sha(fit_path),'receipt_sha256':sha(out/'receipt.json')}
            if a.require_blend_audits:
                audit_path=a.root/arm/'blend_audit.json';audit=json.loads(audit_path.read_text())
                if audit['model_sha256']!=receipt['model_sha256'] or sha(out/'scene.blend')!=receipt['model_sha256'] or not audit['source_model_unchanged']:raise ValueError('Actual Blender model/receipt mismatch')
                deviations=[]
                for box in fit['boxes']:
                    obj=next(o for o in audit['objects'] if o['object_id']==box['id'])
                    deviations.extend(np.linalg.norm(np.array(obj['projected_vertices_1280'])-box['projected_vertices_1280'],axis=1))
                if max(deviations)>.01:raise ValueError('Solver camera/projection differs from saved Blender model')
                bindings['blend_audit_sha256']=sha(audit_path);bindings['solver_blender_max_vertex_distance_px']=max(deviations)
                objects=audit['objects']
        generated=cv2.imread(str(render)).astype(float);per=[];angles=[];fiterrors=[];holderrors=[]
        for spec in annotation['boxes']:
            obj=next(o for o in objects if o['object_id']==spec['id']);pixels=np.array(obj['projected_vertices_1280']);predmask=mask_from_pixels(pixels);truthmask=roi[spec['id']]
            errors=np.array([pixels[i+4]-px for i,px in enumerate(spec['top_front_order'])]+[pixels[int(i)]-px for i,px in spec['bottom_pixels'].items()])
            fitrows=[pixels[i+4]-px for i,px in enumerate(spec['top_front_order'])]+[pixels[i]-spec['bottom_pixels'][str(i)] for i in [0,1]]
            holdrows=[pixels[int(i)]-px for i,px in spec['bottom_pixels'].items() if int(i) not in [0,1]]
            fiterrors.extend(fitrows);holderrors.extend(holdrows)
            deviations=box_angles(obj['vertices_world']);angles.extend(deviations)
            per.append({'object_id':spec['id'],'source_corner_mean_distance_px':float(np.mean(np.linalg.norm(errors,axis=1))),
                'projected_prebevel_footprint_iou':float(np.logical_and(predmask,truthmask).sum()/np.logical_or(predmask,truthmask).sum()),
                'rgb_mae_0_255_in_source_roi':float(np.abs(generated-source)[truthmask].mean()),
                'orthogonality_angle_deviation_deg':deviations,'closed_prebevel_mesh':closed_mesh(obj)})
        records.append({'arm':arm,'bindings':bindings,'source_render_sha256':sha(render),'foreground_rgb_mae_0_255':float(np.abs(generated-source)[all_roi].mean()),
            'box_orthogonality_max_deviation_deg':max(angles),'box_orthogonality_mean_deviation_deg':float(np.mean(angles)),
            'closed_foreground_mesh_parts':sum(closed_mesh(o) for o in objects),'foreground_mesh_parts':len(objects),'per_box':per,
            'training_corner_mean_distance_px':float(np.mean(np.linalg.norm(fiterrors,axis=1))),
            'same_image_heldout_corner_mean_distance_px':None if fit is None else float(np.mean(np.linalg.norm(holderrors,axis=1))),
            'baseline_point_scope':'All these manual corners already used to build A; A has no legitimate heldout endpoint' if fit is None else '18 fitting corners; 3 same-image heldout corners',
            'prior_relative_absolute_deviation_mean':None if fit is None else float(np.mean([abs(v) for box in fit['boxes'] for v in box['relative_web_prior_deviation']]))})
    report={'schema':'real2sim.desk1-cuboid-evaluation/1','status':'diagnostics_recomputed','source_sha256':annotation['source_sha256'],
        'annotation_sha256':sha(a.annotation),'evaluator_sha256':sha(__file__),'records':records,'independent_source_images':1,
        'geometry_readback':'Actual saved Blender files, read-only; solver projection checked <=0.01px' if a.require_blend_audits else 'Builder inventory; retained baseline actual blend readback',
        'fitted_boxes':3,'full_object_denominator':4,'marker_numeric_web_prior':'excluded due to conflicting source dimensions',
        'heldout_points':3,'sota_established':False,'independent_3d_accuracy':None,'real_novel_view_accuracy':None,
        'limits':['Same-image heldout corners are manually estimated and not independent 3D truth.',
            'The old ray-fit baseline used all source corners and cannot receive a heldout score.',
            'Nominal dimension deviation is an objective diagnostic, not instance accuracy.',
            'Visible source-photo texture contains captured illumination; MAE can reward source projection.',
            'Footprint masks and angle checks use prebevel mesh geometry, not actual render silhouette.',
            'Closed/editable/orthogonal geometry is not physics, collision or reconstruction qualification.',
            'One scene and three correlated heldout corners do not establish statistical superiority.']}
    a.output.write_text(json.dumps(report,indent=2,allow_nan=False));print(json.dumps([{k:v for k,v in r.items() if k in ['arm','foreground_rgb_mae_0_255','box_orthogonality_max_deviation_deg','same_image_heldout_corner_mean_distance_px','prior_relative_absolute_deviation_mean']} for r in records]))

if __name__=='__main__':main()
