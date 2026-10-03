import json, os, pathlib, numpy as np, hashlib
R=pathlib.Path(__file__).resolve().parents[1]
def fit(P):
    q=np.ones(len(P),bool)
    for k in range(5):
        c=np.median(P[q],axis=0); _,_,v=np.linalg.svd(P[q]-c,full_matrices=False);n=v[-1];d=(P-c)@n
        lim=max(.015, np.quantile(np.abs(d[q]),.8)*1.5);q=np.abs(d)<lim
    if n[2]<0:n=-n
    d=(P-c)@n
    return dict(normal=n.tolist(),offset=float(-c@n),count=len(P),inliers=int(q.sum()),median_abs_residual_m=float(np.median(abs(d))),p90_abs_residual_m=float(np.quantile(abs(d),.9)),signed_residual_quantiles_m=np.quantile(d,[.05,.5,.95]).tolist())
def main():
    packet=json.loads((R/'inputs/packet.json').read_text()); regions=json.loads((R/'analysis/regions.json').read_text())
    frames={f['input_index']:f for f in packet['frames']}; clouds={}; records={}
    for name, rr in regions.items():
        points=[];supports=[]
        for idx,box in rr:
            f=frames[idx]; dep=R/'inputs/depth_reference/frames'/f'{idx:03d}.npz'
            n=np.load(dep);depth=n['depth_z_m'];K=n['K_depth'];h,w=depth.shape
            # Source RGB integer-centre coordinates mapped by exact depth K.
            Krgb=np.array(f['K']); raymap=K@np.linalg.inv(Krgb)
            a=raymap@np.array([box[0],box[1],1]);b=raymap@np.array([box[2],box[3],1]);x0,y0=np.maximum(np.floor(a[:2]).astype(int),0);x1,y1=np.minimum(np.ceil(b[:2]).astype(int),[w-1,h-1])
            u,v=np.meshgrid(np.arange(x0,x1+1,2),np.arange(y0,y1+1,2)); z=depth[v,u];valid=np.isfinite(z)&(z>.1)&(z<60)
            if 'valid_mask' in n:valid &= n['valid_mask'][v,u].astype(bool)
            uv=np.stack([u[valid],v[valid],np.ones(valid.sum())],1);pc=(uv@np.linalg.inv(K).T)*z[valid,None];T=np.array(f['T_world_camera']);pw=pc@T[:3,:3].T+T[:3,3]
            points.extend(pw);supports.append({'frame':idx,'source_pixel_region_xyxy':box,'depth_pixel_xy':uv[:,:2].astype(int).tolist(),'depth_shape':[h,w],'depth_K':K.tolist(),'sample_count':len(pw),'world_bounds_05_95':np.quantile(pw,[.05,.95],axis=0).tolist(),'plane':fit(pw)})
        P=np.array(points);clouds[name]=P;records[name]={'supports':supports,'plane':fit(P)}
    nf=np.array(records['floor']['plane']['normal']);nd=np.array(records['sliding_door']['plane']['normal']);nd-=nf*(nf@nd);nd/=np.linalg.norm(nd)
    if nd[0]<0:nd=-nd
    y=np.cross(nf,nd);X=np.eye(4);X[:3,:3]=np.array([nd,y,nf]);X[2,3]=records['floor']['plane']['offset']
    for name,P in clouds.items():
        P=P@X[:3,:3].T+X[:3,3];records[name]['model_bounds_02_98']=np.quantile(P,[.02,.98],axis=0).tolist();records[name]['model_median']=np.median(P,axis=0).tolist();records[name]['model_plane']=fit(P)
    out={'source':'same pose-conditioned DA3 predicted optical-Z + registered reference cameras, not GT depth','method':'semantic RGB ROIs backprojected using NPZ exact K, iterative robust SVD planes; one floor/door-derived rigid basis, scale1','model_from_input':X.tolist(),'regions':records}
    (R/'analysis/measurements.json').write_text(json.dumps(out,indent=2));(R/'analysis/measurement_summary.json').write_text(json.dumps({n:{k:v for k,v in r.items() if k!='supports'} for n,r in records.items()},indent=2)); print(json.dumps({n:r['model_bounds_02_98'] for n,r in records.items()},indent=1))
if __name__=='__main__': main()
