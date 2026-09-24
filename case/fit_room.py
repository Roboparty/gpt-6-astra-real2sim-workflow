"""Case-specific single-view Manhattan room fit from manually inspected source corners.
No prior scene parameters. Metric gauge: height prior 2.80 m, uncertain +/- 0.35 m.
"""
import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.optimize import least_squares
ROOT=Path(__file__).resolve().parents[1]
W,H=1702,1276
# Main window wall: left ceiling/floor, right ceiling/floor; projecting column and left window.
uv=np.array([[622,195],[648,649],[1362,40],[1258,751], [515,154],[574,693],[360,48],[465,718]],float)
labels=['back_left_top','back_left_floor','back_right_top','back_right_floor','column_far_top','column_far_floor','column_near_top','column_near_floor']
def points(p):
    width,leftdist,coldepth,colwidth=p[7:11]
    return np.array([[0,0,2.8],[0,0,0],[width,0,2.8],[width,0,0],[colwidth,-leftdist,2.8],[colwidth,-leftdist,0],[colwidth,-coldepth,2.8],[colwidth,-coldepth,0]])
def unpack(p):return Rotation.from_rotvec(p[:3]).as_matrix(),p[3:6],p[6]
def project(p,xyz):
    R,C,f=unpack(p);q=(xyz-C)@R.T;return q[:,:2]/q[:,2,None]*f+p[11:13]
def fun(p):
    res=((project(p,points(p))-uv)/3).ravel().tolist()
    res.extend([(p[6]-850)/250,(p[7]-3.1)/.8,(p[8]-.55)/.3,(p[9]-1.5)/.6,(p[10]-.5)/.2,(p[5]-1.6)/.25,(p[11]-W/2)/60,(p[12]-H/2)/60])
    return res
# camera looking predominantly +Y, pitched down, roll weak.
C=np.array([1.2,-3.7,1.6]);target=np.array([1.4,0,1.3]);fwd=(target-C);fwd/=np.linalg.norm(fwd);right=np.cross(fwd,[0,0,1]);right/=np.linalg.norm(right);down=np.cross(fwd,right);R=np.array([right,down,fwd])
p=np.r_[Rotation.from_matrix(R).as_rotvec(),C,850,3.1,.5,1.5,.5,W/2,H/2]
lo=[-6]*3+[-3,-8,1.1,500,2,.15,.5,.15,W/2-120,H/2-120];hi=[6]*3+[6,-1.5,2.1,1500,5,1.5,3,1,W/2+120,H/2+120]
result=least_squares(fun,p,bounds=(lo,hi),max_nfev=5000,loss='linear')
R,C,f=unpack(result.x);xyz=points(result.x);pred=project(result.x,xyz);err=np.linalg.norm(pred-uv,axis=1)
out=dict(position=C.tolist(),rotation_world_to_cv=R.tolist(),focal_px=float(f),principal_point=[W/2,H/2],image_size=[W,H],role='reconstruction',fit_landmarks=[dict(id=l,xyz=x.tolist(),uv=u.tolist(),predicted=v.tolist(),error_px=float(e)) for l,x,u,v,e in zip(labels,xyz,uv,pred,err)],median_fit_error_px=float(np.median(err)),max_fit_error_px=float(max(err)),metric_gauge='assumed ceiling height 2.8m, plausible 2.45-3.15m; no measured or exact catalogue anchor',status='estimated_from_reconstruction_inputs',distortion='zero; no EXIF or lens calibration',room_parameters=dict(width=float(result.x[7]),left_window_depth=float(result.x[8]),column_front_y=-float(result.x[9]),column_width=float(result.x[10]),height=2.8))
out['principal_point']=result.x[11:13].tolist()
(ROOT/'case/calibration_initial.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
