import json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];cal=json.loads((ROOT/'case/calibration_initial.json').read_text());S=json.loads((ROOT/'candidates/001/scene.json').read_text())
def save(stage,files,reason):
 out=ROOT/'evidence'/stage;out.mkdir(exist_ok=True,parents=True)
 for name,data in files.items():(out/name).write_text(json.dumps(data,indent=2))
 shutil.copyfile(ROOT/'case/fit_room.py',out/'fit_room.py')
 (out/'response.json').write_text(json.dumps(dict(status='complete',artifacts=list(files)+['fit_room.py'],evidence=['source image manually annotated','least-squares fit actually executed','camera_fit_initial.log','camera_fit_refined.log'],reasoning_summary=reason,parameters={'metric_gauge':'assumed room height 2.8m'},issues=[]),indent=2))
cal['anchor_interpretation_correction']='back_right names designate window-right endpoint, NOT measured right-wall corner; room right extension separately hypothesized'
cal['uncertainty']=['single-view scale ambiguity +/-12.5% ceiling-height prior','focal/principal-point coupling, no EXIF; fitted principal point is an effective crop parameter','no independent validation','hidden dimensions and distortion remain uncertain']
save('agent_calibrate',{'calibration.json':cal,'correspondences.json':cal['fit_landmarks']},'Fit the visible window plane and column, correcting an initial ambiguity between a window edge and room boundary. All residuals are fitting residuals, not independent accuracy.')
r=S['room'];land=cal['fit_landmarks'];surfaces=[]
for name,plane,vis,evid,ids in [
 ('wall_back',{'normal':[0,1,0],'offset_m':0},'partial','window endpoints, left white pier and right white return',[0,1,2,3]),
 ('wall_left',{'normal':[1,0,0],'offset_m':0},'partial','left window / column support plane; wall hidden behind column',[4,5,6,7]),
 ('wall_right',{'normal':[1,0,0],'offset_m':r['x_max']},'unobserved','right white region ambiguously back return versus right plane; conservative complete-shell position',[]),
 ('wall_front',{'normal':[0,1,0],'offset_m':r['y_min']},'unobserved','behind camera; no metric constraint',[]),
 ('floor',{'normal':[0,0,1],'offset_m':0},'observed','floor contacts and wall/column lower anchors',[1,3,5,7]),
 ('ceiling',{'normal':[0,0,1],'offset_m':2.8},'observed','tile grid and upper window/column anchors',[0,2,4,6])]:
  entry=dict(id=name,plane=plane,visibility=vis,status='hypothesized' if vis=='unobserved' else 'fitted',evidence=[evid],uncertainty='scale globally unconstrained; unseen extent range +/-0.5m; assumptions retained')
  if ids:entry.update(image_constraints=[land[i] for i in ids],residuals={'anchor_errors_px':[land[i]['error_px'] for i in ids],'interpretation':'in-sample support anchors, not full-plane measurement'})
  surfaces.append(entry)
save('agent_calibrate_room',{'room_calibration.json':dict(surfaces=surfaces,openings_and_columns_reviewed=True,openings={'main_window':'explicit mullions, railing and three separate blinds','left_return':'window depth partially occluded','doorway':'glass leaf and near doorway margins visible; hinge axis unknown'},column=cal['room_parameters'],room=r,required_inspection='four interior camera directions after geometry build')},'Account for six surfaces; distinguish fitted support planes from unobserved room bounds. Do not equate window endpoint with room-right corner.')
