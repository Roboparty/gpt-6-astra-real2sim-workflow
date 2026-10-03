import json,hashlib,struct
from pathlib import Path
import cv2,numpy as np
from .contracts import ContractError,digest
from .media import file_hash

def evaluate_sealed_dimensions(scene,truth,freeze,used_evidence):
    if freeze.get('scene_sha256')!=digest(scene):raise ContractError('Scene must be frozen before validation truth is loaded')
    objects={o['id']:o for o in scene['objects']};results=[]
    for m in truth.get('measurements',[]):
        if m.get('role')!='validation' or m.get('source_id') in used_evidence:raise ContractError('Validation/reconstruction evidence leakage')
        if m.get('method') not in {'independent_physical_measurement','held_out_calibrated_scan'}:raise ContractError('Product priors are not independent validation dimensions')
        est=np.array(objects[m['entity']]['dimensions']);actual=np.array(m['dimensions_m']);err=est-actual
        results.append({'entity':m['entity'],'signed_error_m':err.tolist(),'absolute_error_m':abs(err).tolist(),'relative_error':(abs(err)/actual).tolist(),'source_id':m['source_id']})
    return {'status':'available' if results else 'unavailable','measurements':results,'reason':None if results else 'No independent measured dimensions supplied; error is not zero'}

def segmentation_scores(id_image,palette,annotations):
    image=cv2.imread(str(id_image));image=cv2.cvtColor(image,cv2.COLOR_BGR2RGB).astype(np.int16);h,w=image.shape[:2];scores={};ignore=np.zeros((h,w),np.uint8)
    for p in annotations.get('ignore_polygons',[]):cv2.fillPoly(ignore,[np.int32(p)],1)
    target={}
    for e in annotations['objects']:
        mask=np.zeros((h,w),np.uint8)
        for p in e['polygons']:cv2.fillPoly(mask,[np.int32(p)],1)
        target[e['id']]=mask
    # Subtract nearer object annotations in a documented painter's order.
    order=annotations.get('occlusion_order',[])
    for i,key in enumerate(order):
        for near in order[i+1:]:target[key][target[near].astype(bool)]=0
    for e in annotations['objects']:
        key=e['id'];color=np.array(palette[key]);pred=np.max(abs(image-color),axis=-1)<=3;gt=target[key].astype(bool);valid=ignore==0
        if 'roi' in e:
            x0,y0,x1,y1=e['roi'];roi=np.zeros((h,w),bool);roi[y0:y1,x0:x1]=True;valid&=roi
        pred&=valid;gt&=valid;inter=(pred&gt).sum();union=(pred|gt).sum();scores[key]={'iou':float(inter/union) if union else None,'reference_pixels':int(gt.sum()),'predicted_pixels':int(pred.sum()),'intersection_pixels':int(inter),'protocol':'manual source-view diagnostic mask; in-sample, not independent 3-D accuracy'}
    return scores

def glb_check(path,required_entities):
    data=Path(path).read_bytes();magic,version,length=struct.unpack_from('<4sII',data,0)
    if magic!=b'glTF' or version!=2 or length!=len(data):raise ContractError('Invalid GLB header')
    size,typ=struct.unpack_from('<II',data,12)
    if typ!=0x4e4f534a:raise ContractError('Missing GLB JSON chunk')
    doc=json.loads(data[20:20+size]);names={n.get('name') for n in doc.get('nodes',[])};missing=set(required_entities)-names
    if missing:raise ContractError('Required entities missing from GLB: '+str(missing))
    # Validate all accessor counts/ranges against actual bufferViews, not just file existence.
    sizes={5120:1,5121:1,5122:2,5123:2,5125:4,5126:4};widths={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT2':4,'MAT3':9,'MAT4':16}
    for a in doc.get('accessors',[]):
        if a.get('count',0)<=0:raise ContractError('Empty GLB accessor')
        if 'bufferView' not in a:continue
        v=doc['bufferViews'][a['bufferView']];component=sizes[a['componentType']]*widths[a['type']];stride=v.get('byteStride',component);need=a.get('byteOffset',0)+(a['count']-1)*stride+component
        if need>v['byteLength']:raise ContractError('GLB accessor exceeds bufferView')
    return {'status':'passed','bytes':len(data),'nodes':len(doc.get('nodes',[])),'meshes':len(doc.get('meshes',[])),'materials':len(doc.get('materials',[])),'images':len(doc.get('images',[])),'required_entities_present':list(required_entities),'glTF_convention':'metres, Y up; canonical scene is metres, Z up'}
