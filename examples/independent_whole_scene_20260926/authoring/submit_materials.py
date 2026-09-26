import sys,json
from pathlib import Path
R=Path('/home/wqz/real2sim_whole_scene_20260926');sys.path.insert(0,str(R/'repo/workflow'))
from r2s.core import Workflow,atomic_json
w=Workflow(R/'case');out=Path(w.state['stages']['agent_materials']['directory']);audit=json.loads((out/'appearance_audit.json').read_text());assert not audit['failures']
data=json.loads((out/'material_calibration.json').read_text());scene=json.loads((out/'scene.json').read_text())
for row in data['materials']:
 name=row['material_names'][0]
 if name.startswith('honey_wood'):
  axis=1 if name.endswith('_Y') else 2 if name.endswith('_Z') else 0;scale=[1/195]*3;scale[axis]=1/6;row['texture_scale_m']=scale;row['grain_direction_basis']='Actual member-local Object-coordinate scaling; inferred grain, not measured.'
 if row['entity']=='floor':row['texture_scale_m']=[(scene['room']['x_max']-scene['room']['x_min'])/8,(scene['room']['y_max']-scene['room']['y_min'])/8];row['scale_basis']='Physical axes of full-floor 8x8 inferred pattern, not independently measured tile dimensions.'
 if name=='ceiling_flat_tiles':row['texture_scale_m']=.6;row['layers']['microstructure']='Matte painted finish; no fibre, bump or relief added.';row['layers']['folds']='None; retained continuous ceiling geometry.';row['scale_basis']='Inferred 0.60m planar tile grid, 0.002m tonal seams; not measured seam depth.'
 if name=='board_glass':
  row['texture_scale_m']=next(o['dimensions'][0] for o in scene['objects'] if o['id']=='reflective_board');row['layers']['microstructure']='Inferred clear-to-hazy surface finish across width, following the complete source observation; no painted reflection.';row['layers']['folds']='None; rigid flat board.';row['uncertainty']='Roughness variation is a plausible interpretation of sharp left reflection and diffuse right region, not independently measured coating data.'
atomic_json(out/'material_calibration.json',data)
atomic_json(out/'material_visual_review.json',dict(candidate=out.name,decision='accept_material_baseline',inspected=['material_neutral.png','material_source_preview.png','authorized full original and full-object source crops'],findings=['Whole duvet pattern now dense pale sage botanical after rejecting sparse first attempt; all-over arrangement explicitly inferred, no original crop extended.','Neutral full scene preserves grey-taupe floor, ivory cabinets/walls, honey wood and restrained cloth palette; current source-light image remains dark and is not accepted as final.','Actual shaders cover every visible assignment, including shell and exterior. FabricUV drives cloth microstructure and macro image with EXTEND; floor uses FloorUV.','Macro pattern, micro bump, geometry folds and light remain separate. Board is dielectric, not metallic highlight compensation.'],limitations=['Neutral illumination differs from photograph; albedo is inferred','Exact textile identity, toy characters and footwear details remain unverified','Final full-scene light and appearance gate still required']))
files=[str(p.relative_to(out)) for p in out.rglob('*') if p.is_file() and p.name not in ['packet.json','response.json','record.json']]
atomic_json(out/'response.json',dict(status='complete',artifacts=files,evidence=['material_neutral.png','appearance_audit.json','material_visual_review.json'],reasoning_summary='Inspected complete neutral scene and whole cloth/cabinet/floor appearance. Dense inferred full-surface pattern and actual UV/material audit accepted as locked material baseline; final source illumination and visual likeness remain downstream.'))
print(w.accept('agent_materials',out/'response.json'));print(w.run())
