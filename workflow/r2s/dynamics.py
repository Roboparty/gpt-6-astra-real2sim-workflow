"""Optional real MuJoCo hinges and flex models. Static reference XML stays immutable."""
import copy,json,math
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial.transform import Rotation
from .contracts import ContractError

def fmt(values):return ' '.join(f'{float(v):.10g}' for v in np.asarray(values).ravel())
def _vec(v,n,name):
    a=np.asarray(v,dtype=float)
    if a.shape!=(n,) or not np.isfinite(a).all():raise ContractError('Invalid '+name)
    return a
def _transform(body):
    if any(k in body.attrib for k in ['euler','axisangle','xyaxes','zaxis']):raise ContractError('Dynamic body transforms must be normalized to pos/quat first')
    pos=np.fromstring(body.get('pos','0 0 0'),sep=' ');q=np.fromstring(body.get('quat','1 0 0 0'),sep=' ');T=np.eye(4);T[:3,:3]=Rotation.from_quat(q[[1,2,3,0]]).as_matrix();T[:3,3]=pos;return T
def _world_transform(body,parents):
    T=_transform(body);parent=parents.get(body)
    while parent is not None and parent.tag=='body':T=_transform(parent)@T;parent=parents.get(parent)
    return T

def apply_features(root,definitions):
    """Apply explicit, reviewed moving-part recipes, never infer a whole cabinet joint."""
    root=copy.deepcopy(root);world=root.find('worldbody');parents={c:p for p in root.iter() for c in p};bodies={b.get('name'):b for b in world.iter('body')};created=[];seen=set()
    for h in definitions.get('hinges',[]):
        name=h['id'];child_id=h['moving_body'];parent_id=h.get('parent_body','world')
        if child_id in seen:raise ContractError('Multiple dynamic recipes target the same rigid body')
        seen.add(child_id)
        if not h.get('moving_part_segmented') or not h.get('evidence'):raise ContractError('Hinge needs a separately segmented moving part and evidence')
        if child_id==parent_id or child_id not in bodies or (parent_id!='world' and parent_id not in bodies):raise ContractError('Invalid hinge body binding')
        body=bodies[child_id];parent=world if parent_id=='world' else bodies[parent_id]
        if parent in list(body.iter()):raise ContractError('Articulation cycle')
        if body.find('joint') is not None or body.find('freejoint') is not None:raise ContractError('Moving body already has joints')
        if h.get('parameter_provenance') not in {'measured','manufacturer','assumed'}:raise ContractError('Physics parameter provenance is mandatory')
        axis=_vec(h['axis_local'],3,'hinge axis');axis_norm=np.linalg.norm(axis)
        if not math.isfinite(axis_norm) or axis_norm<1e-12:raise ContractError('Zero or invalid hinge axis')
        axis/=axis_norm
        anchor=_vec(h['anchor_local'],3,'hinge anchor');limits=_vec(h['range_rad'],2,'hinge limits')
        if not limits[0]<=0<=limits[1] or limits[0]>=limits[1]:raise ContractError('Reference pose must lie within hinge limits')
        mass=float(h['mass_kg']);inertia=_vec(h['inertia_diag_kgm2'],3,'inertia')
        if not math.isfinite(mass) or mass<=0 or min(inertia)<=0 or 2*max(inertia)>sum(inertia)+1e-9:raise ContractError('Nonphysical mass/inertia')
        center=_vec(h.get('center_of_mass_local',[0,0,0]),3,'center of mass')
        damping=float(h.get('damping',.2));friction=float(h.get('frictionloss',.05));torque=float(h.get('test_torque_nm',.2))
        if not all(math.isfinite(v) for v in (damping,friction,torque)) or min(damping,friction)<0:raise ContractError('Invalid hinge damping/friction/torque')
        child_world=_world_transform(body,parents);parent_world=np.eye(4) if parent is world else _world_transform(parent,parents);relative=np.linalg.inv(parent_world)@child_world
        parents[body].remove(body);parent.append(body);parents[body]=parent
        q=Rotation.from_matrix(relative[:3,:3]).as_quat();body.set('pos',fmt(relative[:3,3]));body.set('quat',fmt(q[[3,0,1,2]]))
        old=body.find('inertial')
        if old is not None:body.remove(old)
        ET.SubElement(body,'inertial',pos=fmt(center),mass=str(mass),diaginertia=fmt(inertia))
        ET.SubElement(body,'joint',name=name,type='hinge',axis=fmt(axis),pos=fmt(anchor),limited='true',range=fmt(limits),ref='0',damping=str(damping),frictionloss=str(friction))
        created.append({'kind':'hinge','id':name,'moving_body':child_id,'reference_world_transform':child_world.tolist(),'parameter_provenance':h['parameter_provenance']})
    for d in definitions.get('deformables',[]):
        name=d['id'];entity=d['entity'];kind=d['kind'];dim=2 if kind=='cloth' else 3 if kind=='soft_body' else 0
        if not dim or entity not in bodies or entity in seen:raise ContractError('Invalid deformable target/type or conflicting dynamic recipe')
        seen.add(entity)
        if not d.get('rest_shape_matched') or not d.get('evidence'):raise ContractError('Deformable rest shape must be reviewed against the reference object')
        if d.get('parameter_provenance') not in {'measured','manufacturer','assumed'}:raise ContractError('Deformable parameter provenance is mandatory')
        body=bodies[entity]
        if body.findall('body') or body.find('joint') is not None or body.find('freejoint') is not None:raise ContractError('Deformable target must be an isolated component root')
        points=np.asarray(d['points_local'],float);raw_elements=np.asarray(d['elements'])
        if points.ndim!=2 or points.shape[1]!=3 or not len(points) or not np.isfinite(points).all():raise ContractError('Invalid rest vertices')
        if raw_elements.ndim!=2 or raw_elements.shape[1]!=dim+1 or not raw_elements.size or not np.issubdtype(raw_elements.dtype,np.integer):raise ContractError('Invalid flex topology')
        elements=raw_elements.astype(int)
        if elements.min()<0 or elements.max()>=len(points):raise ContractError('Invalid flex topology')
        if not d.get('replace_static_geometry'):raise ContractError('Explicitly replace the static component to avoid duplicate geometry/collisions')
        for geom in list(body.findall('geom')):body.remove(geom)
        mass=float(d['mass_kg']);radius=float(d.get('contact_radius_m',.002))
        if not all(math.isfinite(v) for v in (mass,radius)) or mass<=0 or radius<=0:raise ContractError('Invalid deformable mass/contact thickness')
        elastic_damping=float(d.get('elastic_damping',.001));strain_bound=float(d.get('maximum_allowed_edge_strain',.75))
        if not all(math.isfinite(v) for v in (elastic_damping,strain_bound)) or elastic_damping<0 or strain_bound<=0:raise ContractError('Invalid elastic damping/strain bound')
        rgba=_vec(d.get('rgba',[.7,.5,.3,1]),4,'deformable color')
        flex=ET.SubElement(body,'flexcomp',name=name,type='direct',dim=str(dim),point=fmt(points),element=' '.join(map(str,elements.ravel())),mass=str(mass),radius=str(radius),rgba=fmt(rgba))
        pins=d.get('pinned_vertices',[])
        if pins:
            if any(type(p) is not int for p in pins) or min(pins)<0 or max(pins)>=len(points):raise ContractError('Pinned vertex outside mesh')
            ET.SubElement(flex,'pin',id=' '.join(map(str,pins)))
        if dim==2:
            E=float(d['young_pa']);nu=float(d.get('poisson',.3));thickness=float(d['thickness_m'])
            if not all(math.isfinite(v) for v in (E,nu,thickness)) or E<=0 or not 0<=nu<.5 or thickness<=0:raise ContractError('Invalid cloth shell material')
            ET.SubElement(flex,'elasticity',young=str(E),poisson=str(nu),thickness=str(thickness),elastic2d='both',damping=str(elastic_damping))
        else:
            E=float(d['young_pa']);nu=float(d.get('poisson',.3))
            if not all(math.isfinite(v) for v in (E,nu)) or E<=0 or not 0<=nu<.5:raise ContractError('Invalid elastic material')
            ET.SubElement(flex,'elasticity',young=str(E),poisson=str(nu),damping=str(elastic_damping))
        created.append({'kind':kind,'id':name,'entity':entity,'vertices':len(points),'elements':len(elements),'parameter_provenance':d['parameter_provenance']})
    return root,created

def validate_requested_features(definitions,requested):
    if any(k not in {'hinges','cloth','soft_bodies'} or type(v) is not bool for k,v in requested.items()):raise ContractError('Physics switches must be named booleans')
    actual={'hinges':bool(definitions.get('hinges')),'cloth':any(d['kind']=='cloth' for d in definitions.get('deformables',[])),'soft_bodies':any(d['kind']=='soft_body' for d in definitions.get('deformables',[]))}
    for key,enabled in actual.items():
        if enabled and not requested.get(key,False):raise ContractError('Unrequested physics feature: '+key)
        if requested.get(key,False) and not enabled:
            reason=definitions.get('not_applicable',{}).get(key,{})
            if not reason.get('reason') or not reason.get('evidence'):raise ContractError('Enabled physics needs a recipe or an explicit not-applicable decision: '+key)

def export_and_test(reference_xml,scene,out_dir,requested=None):
    import mujoco
    out_dir=Path(out_dir);definitions=scene.get('dynamics',{})
    requested={} if requested is None else requested
    validate_requested_features(definitions,requested)
    if not definitions.get('hinges') and not definitions.get('deformables'):
        return {'status':'not_applicable' if requested and any(requested.values()) else 'disabled','reason':'No reviewed dynamic recipes; static reference preserved','not_applicable':definitions.get('not_applicable',{})}
    steps=definitions.get('test_steps',600);timestep=float(definitions.get('timestep_s',.0005))
    if type(steps) is not int or steps<=0:raise ContractError('Dynamics test_steps must be a positive integer')
    if not math.isfinite(timestep) or timestep<=0:raise ContractError('Dynamics timestep must be positive and finite')
    source=ET.parse(reference_xml).getroot();root,created=apply_features(source,definitions)
    option=root.find('option')
    if option is None:option=ET.SubElement(root,'option')
    option.set('timestep',str(timestep))
    xml=out_dir/'scene_dynamic.xml';ET.ElementTree(root).write(xml,encoding='unicode',xml_declaration=True)
    model=mujoco.MjModel.from_xml_path(str(xml));data=mujoco.MjData(model);mujoco.mj_forward(model,data)
    initial=data.flexvert_xpos.copy();samples=[];ranges={};flex_checks=[]
    from itertools import combinations
    for d in definitions.get('deformables',[]):
        fid=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_FLEX,d['id']);start=int(model.flex_vertadr[fid]);count=int(model.flex_vertnum[fid]);elements=np.array(d['elements'],int);edges=np.array(sorted({tuple(sorted(pair)) for element in elements for pair in combinations(element,2)}));v=initial[start:start+count];lengths=np.linalg.norm(v[edges[:,0]]-v[edges[:,1]],axis=1)
        if min(lengths)<1e-8:raise ContractError('Degenerate deformable rest edges')
        check={'definition':d,'start':start,'count':count,'edges':edges,'lengths':lengths,'maximum_edge_strain':0.,'minimum_volume_ratio':1.}
        if d['kind']=='soft_body':
            t=v[elements];vol=np.linalg.det(np.stack([t[:,1]-t[:,0],t[:,2]-t[:,0],t[:,3]-t[:,0]],axis=2))/6
            if min(abs(vol))<1e-12:raise ContractError('Degenerate tetrahedra')
            check.update(elements=elements,rest_volumes=vol)
        flex_checks.append(check)
    for h in definitions.get('hinges',[]):
        jid=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_JOINT,h['id']);bid=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY,h['moving_body']);expected=next(c['reference_world_transform'] for c in created if c['id']==h['id']);assert np.linalg.norm(data.xpos[bid]-np.array(expected)[:3,3])<1e-6
        ranges[h['id']]=[0.,0.]
    warning_before=data.warning.number.copy()
    for step in range(steps):
        data.qfrc_applied[:]=0
        for h in definitions.get('hinges',[]):
            jid=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_JOINT,h['id']);dof=model.jnt_dofadr[jid];data.qfrc_applied[dof]=float(h.get('test_torque_nm',.2))
        mujoco.mj_step(model,data)
        if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():raise ContractError('Unstable dynamics')
        for h in definitions.get('hinges',[]):
            jid=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_JOINT,h['id']);q=float(data.qpos[model.jnt_qposadr[jid]]);ranges[h['id']]=[min(ranges[h['id']][0],q),max(ranges[h['id']][1],q)]
            if q<h['range_rad'][0]-.04 or q>h['range_rad'][1]+.04:raise ContractError('Hinge escaped limits')
        if step%max(1,steps//60)==0:
            for check in flex_checks:
                v=data.flexvert_xpos[check['start']:check['start']+check['count']];e=check['edges'];strain=float(max(abs(np.linalg.norm(v[e[:,0]]-v[e[:,1]],axis=1)/check['lengths']-1)));check['maximum_edge_strain']=max(check['maximum_edge_strain'],strain)
                if strain>check['definition'].get('maximum_allowed_edge_strain',.75):raise ContractError('Deformable exceeded declared strain bound')
                if 'elements' in check:
                    t=v[check['elements']];vol=np.linalg.det(np.stack([t[:,1]-t[:,0],t[:,2]-t[:,0],t[:,3]-t[:,0]],axis=2))/6;ratio=float(min(vol/check['rest_volumes']));check['minimum_volume_ratio']=min(check['minimum_volume_ratio'],ratio)
                    if ratio<=.05:raise ContractError('Tetrahedron inverted or collapsed')
            samples.append({'time':float(data.time),'qpos':data.qpos.copy().tolist(),'flexvert':data.flexvert_xpos.copy().tolist()})
    motion=float(np.max(np.linalg.norm(data.flexvert_xpos-initial,axis=1))) if len(initial) else 0.
    warnings=(data.warning.number-warning_before).tolist()
    if any(warnings):raise ContractError('Simulator warning during dynamics validation: '+str(warnings))
    result={'status':'passed','engine':'MuJoCo','engine_version':mujoco.__version__,'generated':created,'steps':steps,'joint_ranges_observed_rad':ranges,'maximum_flex_displacement_m':motion,'solver_warnings':warnings,'animation_kind':'numerical_simulation_not_keyframes','static_reference_modified':False,'limitations':['Parameters labelled assumed are not physical calibration','Cloth uses triangular shell bending/stretching; volumetric soft body uses tetrahedral elasticity','Physics motion is separate from the frozen reconstruction pose']}
    result['deformation_checks']=[{'id':c['definition']['id'],'maximum_edge_strain':c['maximum_edge_strain'],'minimum_volume_ratio':c['minimum_volume_ratio'] if 'rest_volumes' in c else None} for c in flex_checks]
    (out_dir/'dynamics_trajectory.json').write_text(json.dumps(samples));(out_dir/'dynamics_audit.json').write_text(json.dumps(result,indent=2));return result
