"""Generic metric-prior camera fitting; observations and object identities are external data."""
import math
import numpy as np
import cv2
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

def fit_camera(observations,initial,options=None):
    options=options or {};W,H=initial['image_size'];land=observations['landmarks'];xyz=np.array([p['xyz'] for p in land]);uv=np.array([p['uv'] for p in land]);planes=observations.get('plane_outlines',[]);lines=observations.get('parallel_lines',[])
    if len(land)<6:raise ValueError('At least six metric correspondences are required; Agent must document planar ambiguity')
    def unpack(v):return Rotation.from_rotvec(v[:3]).as_matrix(),v[3:6],v[6],v[7:9]
    def plane_points(v,p):
        R,C,f,cp=unpack(v);rays=np.c_[(np.array(p['uv'])-cp)/f,np.ones(len(p['uv']))]@R;n=np.array(p.get('normal',[0,0,1.]));den=rays@n
        if np.any(abs(den)<1e-9):den=np.where(abs(den)<1e-9,1e-9,den)
        world=C+rays*((p['offset']-C@n)/den)[:,None];basis=np.array(p.get('basis',[[1,0,0],[0,1,0]]));return world@basis.T
    def extent(points,theta):
        rot=np.array([[math.cos(theta),-math.sin(theta)],[math.sin(theta),math.cos(theta)]]);return np.ptp(points@rot,axis=0)
    v=np.r_[Rotation.from_matrix(initial['rotation_world_to_cv']).as_rotvec(),initial['position'],initial['focal_px'],initial['principal_point']]
    theta=[]
    for p in planes:
        points=plane_points(v,p);target=np.array(p['dimensions']);grid=np.linspace(-math.pi,math.pi,1001);theta.append(min(grid,key=lambda t:sum(((extent(points,t)-target)/target)**2)))
    def objective(v):
        R,C,f,cp=unpack(v);q=(xyz-C)@R.T;pred=q[:,:2]/q[:,2,None]*f+cp;res=list(((pred-uv)/options.get('pixel_sigma',1.5)).ravel())
        for line in lines:
            axis=R@np.array(line['axis']);vp=axis[:2]/axis[2]*f+cp;a,b=np.array(line['uv']);d=vp-(a+b)/2;normal=np.array([-d[1],d[0]])/np.linalg.norm(d);res.append(np.dot(b-a,normal)/options.get('line_sigma',2))
        for i,p in enumerate(planes):res.extend((extent(plane_points(v,p),v[9+i])-p['dimensions'])/p.get('dimension_sigma_m',.0125))
        res.extend((cp-options.get('principal_prior',[W/2,H/2]))/options.get('principal_sigma_px',400));res.append((f-options.get('focal_prior',initial['focal_px']))/options.get('focal_sigma_px',1000))
        return res
    pos_bounds=options.get('position_bounds',[[-np.inf]*3,[np.inf]*3]);pp_bounds=options.get('principal_bounds',[[-W,-H],[2*W,2*H]]);fb=options.get('focal_bounds',[W*.2,W*4])
    lo=np.r_[[-np.inf]*3,pos_bounds[0],fb[0],pp_bounds[0],[-20]*len(planes)];hi=np.r_[[np.inf]*3,pos_bounds[1],fb[1],pp_bounds[1],[20]*len(planes)]
    result=least_squares(objective,np.r_[v,theta],loss='soft_l1',max_nfev=options.get('max_nfev',3000),bounds=(lo,hi));R,C,f,cp=unpack(result.x);q=(xyz-C)@R.T
    if not result.success or np.any(q[:,2]<=0):raise ValueError('Camera fit failed or places observed anchors behind the camera')
    errors=np.linalg.norm(q[:,:2]/q[:,2,None]*f+cp-uv,axis=1);singular=np.linalg.svd(result.jac,compute_uv=False);condition=float(singular[0]/max(singular[-1],1e-15))
    prior_results=[]
    for i,p in enumerate(planes):
        bounds=extent(plane_points(result.x,p),result.x[9+i]);target=np.array(p['dimensions']);prior_results.append({'id':p['id'],'axis_angle':float(result.x[9+i]),'estimated_bounds_m':bounds.tolist(),'prior_m':target.tolist(),'relative_prior_residual':((bounds-target)/target).tolist(),'role':'reconstruction_prior_fit_not_validation'})
    return {'position':C.tolist(),'rotation_world_to_cv':R.tolist(),'focal_px':float(f),'principal_point':cp.tolist(),'image_size':[W,H],'fit_landmarks':land,'median_fit_error_px':float(np.median(errors)),'max_fit_error_px':float(max(errors)),'prior_fits':prior_results,'jacobian_condition_number':condition,'conditioning':'weak' if condition>1e7 else 'locally_constrained','status':'estimated_from_reconstruction_inputs','limitations':['reprojection and catalogue residuals are in-sample','local conditioning does not resolve wrong object identities or single-view hidden geometry','uncertainty intervals require an explicit noise model; no calibrated accuracy claimed']}

def fit_multiview_poses(shared_points,views):
    """Estimate per-frame poses in a shared metric gauge defined by approved anchors."""
    cameras=[]
    for view in views:
        ids=view['point_ids'];xyz=np.array([shared_points[i] for i in ids],np.float64);uv=np.array(view['uv'],np.float64)
        if len(ids)<6:raise ValueError('At least six reviewed correspondences per view are required')
        f=view['focal_px'];cx,cy=view['principal_point'];K=np.array([[f,0,cx],[0,f,cy],[0,0,1.]],float)
        ok,rvec,tvec,inliers=cv2.solvePnPRansac(xyz,uv,K,None,reprojectionError=3.,iterationsCount=200,flags=cv2.SOLVEPNP_EPNP)
        if not ok or inliers is None or len(inliers)<6:raise ValueError('Insufficient consistent multiview correspondences')
        rvec,tvec=cv2.solvePnPRefineLM(xyz[inliers[:,0]],uv[inliers[:,0]],K,None,rvec,tvec);R,_=cv2.Rodrigues(rvec);C=(-R.T@tvec).ravel();q=(xyz-C)@R.T
        if np.any(q[:,2]<=0):raise ValueError('Negative-depth multiview pose')
        predicted=q[:,:2]/q[:,2,None]*f+[cx,cy];errors=np.linalg.norm(predicted-uv,axis=1)
        cameras.append({'frame_id':view['frame_id'],'role':'reconstruction','position':C.tolist(),'rotation_world_to_cv':R.tolist(),'focal_px':f,'principal_point':[cx,cy],'image_size':view['image_size'],'inlier_count':len(inliers),'median_fit_error_px':float(np.median(errors)),'scale_source':'shared reviewed metric anchors; not recovered from essential matrix alone'})
    return cameras
