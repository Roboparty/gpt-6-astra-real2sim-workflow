"""Single-image, multi-image and video ingestion. No model-generated imagery as formal input."""
import json,hashlib,shutil
from pathlib import Path
import cv2,numpy as np

def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def ingest(config,out):
    out=Path(out);out.mkdir(exist_ok=True,parents=True);mode=config['mode']
    if mode not in {'single','multi','video'}:raise ValueError('mode must be single/multi/video')
    sources=config['inputs']
    if not sources or (mode in {'single','video'} and len(sources)!=1):raise ValueError('Invalid input cardinality')
    provenance=config.get('provenance',{})
    if config.get('formal_test',True) and (provenance.get('kind') not in {'real_photograph','real_video'} or provenance.get('status')!='verified' or not provenance.get('evidence')):raise ValueError('Formal cases require verified real photography/video; CGI and unknown origins are blocked')
    records=[]
    for i,entry in enumerate(sources):
        if entry.get('role','reconstruction')!='reconstruction':raise ValueError('Held-out or validation input must never enter ingestion')
        src=Path(entry['path']).resolve();sha=file_hash(src)
        if entry.get('sha256') and entry['sha256'].lower()!=sha:raise ValueError('Input hash mismatch: '+str(src))
        dest=out/f'{i:04d}{src.suffix.lower()}';shutil.copyfile(src,dest)
        if file_hash(dest)!=sha:raise ValueError('Byte-copy verification failed')
        if mode!='video':
            im=cv2.imread(str(dest))
            if im is None:raise ValueError('Image decode failed')
            shape=list(im.shape[:2][::-1])
        else:
            cap=cv2.VideoCapture(str(dest));ok,im=cap.read();shape=list(im.shape[:2][::-1]) if ok else None;cap.release()
            if not ok:raise ValueError('Video decode failed')
        records.append({'path':str(dest),'source_path':str(src),'sha256':sha,'bytes':dest.stat().st_size,'image_size':shape,'role':'reconstruction'})
    result={'mode':mode,'files':records,'provenance':provenance,'formal_test':config.get('formal_test',True)};(out/'ingest.json').write_text(json.dumps(result,indent=2));return result

def preprocess(ingested,out,params=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);params=params or {};candidates=[]
    max_frames=int(params.get('max_frames',80));interval=float(params.get('interval_seconds',.7));max_edge=int(params.get('max_edge',1600))
    if ingested['mode']=='video':
        cap=cv2.VideoCapture(ingested['files'][0]['path']);fps=cap.get(cv2.CAP_PROP_FPS)
        if not np.isfinite(fps) or fps<=0:raise ValueError('Video FPS unavailable; cannot assign reliable timestamps')
        stride=max(1,round(fps*interval));total=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total<=0:raise ValueError('Video frame count unavailable; use an explicit decoded-frame adapter')
        count=min(max_frames,(total-1)//stride+1)
        if count<1:raise ValueError('max_frames must be positive')
        indices=np.linspace(0,total-1,count,dtype=int)
        for n in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES,int(n));ok,frame=cap.read()
            if not ok:continue
            ts=cap.get(cv2.CAP_PROP_POS_MSEC)/1000
            candidates.append((frame,{'source_frame':int(n),'timestamp_seconds':float(ts if ts>0 else n/fps),'timestamp_method':'container timestamp with frame/FPS fallback','sampling':'uniform_full_clip','source_sha256':ingested['files'][0]['sha256']}))
        cap.release()
    else:
        candidates=[(cv2.imread(r['path']),{'source_sha256':r['sha256'],'source_path':r['path']}) for r in ingested['files']]
    accepted=[];rejected=[];thumbs=[]
    for i,(im,meta) in enumerate(candidates):
        if im is None:rejected.append({'index':i,'reason':'decode_failure'});continue
        h,w=im.shape[:2];scale=min(1,max_edge/max(w,h));processed=cv2.resize(im,(round(w*scale),round(h*scale))) if scale<1 else im.copy();gray=cv2.cvtColor(processed,cv2.COLOR_BGR2GRAY);blur=float(cv2.Laplacian(gray,cv2.CV_64F).var());thumb=cv2.resize(gray,(32,32)).astype(float)
        duplicate=any(float(np.mean(abs(thumb-t)))<float(params.get('duplicate_mae',.5)) for t in thumbs)
        # Single frames are preserved even when blurred; quality is metadata, never silently enhanced.
        if ingested['mode']!='single' and duplicate:rejected.append({'index':i,'reason':'near_duplicate','meta':meta});continue
        if ingested['mode']=='video' and blur<float(params.get('min_laplacian_variance',8)):rejected.append({'index':i,'reason':'blur','variance':blur,'meta':meta});continue
        name=f'frame_{i:05d}.png';cv2.imwrite(str(out/name),processed);thumbs.append(thumb)
        accepted.append({'path':str(out/name),'sha256':file_hash(out/name),'original_size':[w,h],'processed_size':list(processed.shape[:2][::-1]),'resize_scale':scale,'resize_scale_xy':[processed.shape[1]/w,processed.shape[0]/h],'blur_variance':blur,**meta})
    if not accepted:raise ValueError('No usable original frames remain')
    report={'mode':ingested['mode'],'accepted':accepted,'rejected':rejected,'parameters':params,'image_enhancement':False,'decode_orientation_policy':'OpenCV default EXIF/display orientation; original bytes preserved','quality_status':'insufficient_for_multiview' if ingested['mode']!='single' and len(accepted)<2 else 'usable','sparse_geometry':sparse_tracks(accepted) if len(accepted)>1 else {'status':'not_applicable_single_image' if ingested['mode']=='single' else 'insufficient_distinct_views'}}
    (out/'preprocess.json').write_text(json.dumps(report,indent=2));return report

def sparse_tracks(frames):
    """Conservative adjacent-view initialization; rotations/translations remain up to scale."""
    sift=cv2.SIFT_create(nfeatures=5000);features=[];pairs=[]
    for f in frames:
        im=cv2.imread(f['path'],0);kp,des=sift.detectAndCompute(im,None);features.append((kp,des,im.shape))
    for i in range(len(frames)-1):
        a,da,shape=features[i];b,db,_=features[i+1]
        if da is None or db is None:pairs.append({'i':i,'j':i+1,'status':'insufficient_features'});continue
        matches=cv2.BFMatcher().knnMatch(da,db,k=2);good=[m for pair in matches if len(pair)==2 for m,n in [pair] if m.distance<.75*n.distance]
        if len(good)<24:pairs.append({'i':i,'j':i+1,'status':'insufficient_matches','matches':len(good)});continue
        p=np.float32([a[m.queryIdx].pt for m in good]);q=np.float32([b[m.trainIdx].pt for m in good]);F,mask=cv2.findFundamentalMat(p,q,cv2.FM_RANSAC,1.5,.999)
        if F is None or mask is None:pairs.append({'i':i,'j':i+1,'status':'fundamental_fit_failed'});continue
        sel=mask.ravel().astype(bool);h,w=shape;focal=.9*max(w,h);K=np.array([[focal,0,w/2],[0,focal,h/2],[0,0,1.]],float);E,em=cv2.findEssentialMat(p[sel],q[sel],K,method=cv2.RANSAC,prob=.999,threshold=1.5)
        item={'i':i,'j':i+1,'matches':len(good),'fundamental_inliers':int(sel.sum()),'F':F.tolist(),'K_prior':K.tolist(),'intrinsics_source':'uncalibrated focal prior; requires Agent review','status':'correspondences_only'}
        if E is not None and E.shape==(3,3):
            count,R,t,mask=cv2.recoverPose(E,p[sel],q[sel],K)
            if count>=24:
                item.update(status='relative_pose_candidate',R=R.tolist(),translation_direction=t.ravel().tolist(),cheirality_inliers=int(count))
        pairs.append(item)
    return {'status':'needs_agent_review','pairs':pairs,'limitations':['relative poses have no metric scale','pairwise estimates are not a globally optimized reconstruction','planar scenes and low parallax may be degenerate','Agent may request calibrated SfM/COLMAP through a configured stage command']}
