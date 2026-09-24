import copy,json,math,hashlib
from pathlib import Path

class ContractError(ValueError): pass
class LayoutConflict(ContractError): pass

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def scene_check(scene):
    if scene.get('schema_version')!='real2sim.scene/1.0':raise ContractError('Unsupported scene schema')
    if scene.get('units')!='m' or scene.get('up_axis')!='Z':raise ContractError('Canonical scene must be metres, Z up')
    r=scene['room']
    if not r.get('preserve_full_shell'):raise ContractError('Four walls, floor and ceiling must remain present')
    if not (r['x_min']<r['x_max'] and r['y_min']<r['y_max'] and r['height']>0 and r['thickness']>0):raise ContractError('Invalid enclosure')
    ids=set()
    for o in scene['objects']:
        if o['id'] in ids:raise ContractError('Duplicate entity id: '+o['id'])
        ids.add(o['id'])
        if len(o['position'])!=3 or len(o['dimensions'])!=3 or not all(math.isfinite(x) for x in o['position']+o['dimensions']):raise ContractError('Nonfinite geometry')
        if min(o['dimensions'])<=0:raise ContractError('Nonpositive dimensions')
        if not o.get('evidence') or not 0<=o.get('confidence',-1)<=1:raise ContractError('Every entity needs evidence and confidence')
        if scene.get('branch','A')=='A' and o.get('asset_resolution',{}).get('mode')=='exact':raise ContractError('External exact geometry forbidden in A')
    lamps=[o for o in scene['objects'] if 'lamp' in o['kind'] or 'pendant' in o['kind'] or o.get('semantic_class')=='luminaire']
    if not lamps:raise ContractError('Scene must include luminaires, with inferred ones marked as hypotheses')
    for c in [scene['camera']]+scene.get('cameras',[]):
        if c['focal_px']<=0 or min(c['image_size'])<=0:raise ContractError('Invalid camera')
        if c.get('role','reconstruction')!='reconstruction':raise ContractError('Held-out camera data cannot enter reconstruction scene')
    if scene.get('structure'):
        from .structure import structure_contract
        if not structure_contract(scene['structure'])<=ids:raise ContractError('Assembly owner absent from semantic scene')
    return {'status':'passed','object_count':len(ids),'enclosure_surfaces':6,'luminaire_count':len(lamps)}

def apply_layout_patch(scene,patch,authority,evidence):
    """No generative rearrangement of evidence-backed transforms, including deletion."""
    result=copy.deepcopy(scene);objects={o['id']:o for o in result['objects']};events=[]
    if authority not in {'observation_correction','user','generative'}:raise ContractError('Unknown patch authority')
    for change in patch:
        entity=change['entity'];field=change['field'];value=change.get('value')
        if entity=='room':
            if authority=='generative':raise LayoutConflict('Generative repair cannot edit reconstruction enclosure')
            if not evidence:raise ContractError('Room correction needs evidence')
            result['room'][field]=value;continue
        if entity not in objects:raise ContractError('Unknown entity '+entity)
        obj=objects[entity];protected=field not in {'material_overrides','annotations'}
        if obj.get('layout_lock') and protected and authority=='generative':raise LayoutConflict(entity+': layout is evidence locked; return a conflict proposal')
        if authority=='observation_correction' and not evidence:raise ContractError('Observation correction requires new visual evidence')
        before=copy.deepcopy(obj.get(field))
        if field=='delete':result['objects']=[o for o in result['objects'] if o['id']!=entity]
        else:obj[field]=value
        events.append({'entity':entity,'field':field,'before':before,'after':value,'authority':authority,'evidence':evidence})
    scene_check(result);result.setdefault('revision_history',[]).extend(events);return result

def branch_b(base,registry):
    """A is immutable; exact candidates must pass identity, format and hash checks."""
    scene=copy.deepcopy(base);scene['branch']='B';scene['comparison_base_A_sha256']=digest(base)
    for o in scene['objects']:
        a=registry.get(o['id'])
        ok=a and a.get('exact_identity_verified') and a.get('geometry_audit_passed') and a.get('sha256') and a.get('variant_verified') and a.get('path')
        o['asset_resolution']={'mode':'exact','asset_id':a['id'],'sha256':a['sha256'],'path':a['path']} if ok else {'mode':'fallback_A','reason':a.get('reason','identity or geometry not verified') if a else 'no verified exact asset'}
    scene_check(scene);return scene

def layout_fingerprint(scene,include_dynamics=True):
    data={'room':scene['room'],'camera':scene['camera'],'cameras':scene.get('cameras',[]),'objects':[{k:o.get(k) for k in ['id','position','rotation_z','rotation_quaternion_wxyz','rotation_euler','transform','dimensions','kind','parameters','geometry','layout_lock']} for o in scene['objects']]}
    if include_dynamics:data['dynamics']=scene.get('dynamics',{})
    return digest(data)

def robohousegen_packet(scene,asset_manifest):
    scene_check(scene)
    return {'schema':'real2sim.robohousegen/1.1','scene':copy.deepcopy(scene),'assets':copy.deepcopy(asset_manifest),'layout_fingerprint':layout_fingerprint(scene),'asset_bindings_fingerprint':digest([{k:o.get(k) for k in ['id','asset_resolution','asset_ref']} for o in scene['objects']]),'policy':{'observed_layout':'immutable_to_generative_repair','collision_repair':'return_conflicts_only','allowed_mutations':'explicit source-evidence correction or user instruction through revisioned patches','export_validation':'shared real2sim geometry, shell and simulation validators'}}

def accept_robohousegen_result(packet,returned_scene):
    include_dynamics=packet.get('schema')!='real2sim.robohousegen/1.0'
    if layout_fingerprint(returned_scene,include_dynamics)!=packet['layout_fingerprint']:raise LayoutConflict('RoboHouseGen changed protected scene layout or camera')
    if returned_scene.get('dynamics',{})!=packet['scene'].get('dynamics',{}):raise LayoutConflict('RoboHouseGen changed protected dynamics definitions')
    if digest([{k:o.get(k) for k in ['id','asset_resolution','asset_ref']} for o in returned_scene['objects']])!=packet['asset_bindings_fingerprint']:raise LayoutConflict('RoboHouseGen changed protected asset bindings')
    scene_check(returned_scene);return returned_scene
