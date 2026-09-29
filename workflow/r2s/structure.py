"""Executable evidence contracts for coherent multi-part assemblies.
These checks reject missing/invalid evidence; they do not replace visual judgement.
Geometry measurements must be produced by the Blender evaluator on the bound file.
"""
import hashlib,json,math
from itertools import combinations
from pathlib import Path
from .contracts import ContractError

def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def empty_room_inventory(scene):
    structure=scene['structure'];roles={n:'room_shell' for n in structure['shell_objects']}
    lamps=structure.get('fixed_luminaire_objects',[])
    if not isinstance(lamps,list) or any(not isinstance(n,str) or not n for n in lamps) or len(set(lamps))!=len(lamps) or set(lamps)&set(roles):raise ContractError('Invalid empty-room luminaire inventory')
    roles.update({n:'fixed_luminaire' for n in lamps})
    objects=scene.get('objects',[])
    if len(objects)!=len(roles) or {o['id'] for o in objects}!=set(roles) or any(o.get('structural_role')!=roles[o['id']] for o in objects):raise ContractError('Empty-room semantic objects must exactly match shell and fixed luminaire inventory')
    return roles
def structure_contract(data):
    if not isinstance(data,dict) or data.get('schema')!='real2sim.assembly/1':raise ContractError('Missing assembly structure contract')
    if data.get('scope')=='empty_room':
        shell=data.get('shell_objects')
        if data.get('assemblies')!=[] or not isinstance(shell,list) or not shell or any(not isinstance(n,str) or not n for n in shell) or len(set(shell))!=len(shell):raise ContractError('Empty-room scope requires explicit zero assemblies and unique nonempty shell object names')
    owners=set();entities=set()
    for a in data.get('assemblies',[]):
        if a['entity'] in entities:raise ContractError('Duplicate assembly owner')
        entities.add(a['entity']);parts={p['id']:p for p in a.get('parts',[])}
        if not parts or len(parts)!=len(a['parts']):raise ContractError('Empty or duplicate assembly parts')
        for p in parts.values():
            if p['object'] in owners:raise ContractError('Part assigned to multiple furniture owners')
            owners.add(p['object'])
        graph={p:set() for p in parts}
        for j in a.get('joints',[]):
            pair=j.get('parts',[])
            if len(pair)!=2 or pair[0]==pair[1] or any(p not in parts for p in pair):raise ContractError('Unknown or self-connected part')
            if len(j.get('anchor_world',[]))!=3 or not all(math.isfinite(x) for x in j['anchor_world']):raise ContractError('Joint lacks finite shared anchor')
            if not 0<j.get('tolerance_m',0)<=.01:raise ContractError('Joint tolerance missing or excessive')
            graph[pair[0]].add(pair[1]);graph[pair[1]].add(pair[0])
        visited=set();todo=[next(iter(parts))]
        while todo:
            p=todo.pop()
            if p not in visited:visited.add(p);todo.extend(graph[p]-visited)
        if visited!=set(parts):raise ContractError('Disconnected assembly graph: '+a['entity'])
        if not a.get('source_observation_ids') or not a.get('floor_supports'):raise ContractError('Assembly lacks observation binding or support constraints')
        if any(f['part'] not in parts for f in a['floor_supports']):raise ContractError('Floor constraint references missing part')
    return entities

def evidence_file(attempt,ref,artifacts):
    if not isinstance(ref,str) or ref not in artifacts:raise ContractError('Evidence reference is not a delivered artifact: '+str(ref))
    p=(Path(attempt)/ref).resolve()
    if not p.is_relative_to(Path(attempt).resolve()) or not p.is_file():raise ContractError('Evidence file missing or escapes attempt')
    return p

def review_contract(attempt,review,artifacts,scene,binding):
    structure=scene.get('structure');required=structure_contract(structure)
    empty_room=structure.get('scope')=='empty_room'
    if not required and not empty_room:raise ContractError('Zero assemblies require explicit empty_room scope')
    if empty_room:empty_room_inventory(scene)
    if review.get('geometry_freeze_sha256')!=binding['model_sha256']:raise ContractError('Geometry review is not bound to current model bytes')
    if review.get('model_version')!=scene.get('model_version'):raise ContractError('Geometry model version mismatch')
    expected={o['id'] for o in scene['objects']};rows=review.get('per_object',[])
    if len(rows)!=len(expected) or {r.get('entity') for r in rows}!=expected:raise ContractError('Per-object review must cover the current scene exactly once')
    for row in rows:
        if row.get('status') not in ['pass','hypothesized'] or not row.get('findings'):raise ContractError('Object review lacks explicit status/findings')
        if row['status']=='hypothesized' and not row.get('uncertainty'):raise ContractError('Hypothesized object needs uncertainty')
        if not row.get('evidence'):raise ContractError('Object review needs file evidence')
        for ref in row['evidence']:evidence_file(attempt,ref,artifacts)
    for check in review.get('checks',{}).values():
        for ref in check.get('evidence',[]):evidence_file(attempt,ref,artifacts)
    audit_path=evidence_file(attempt,'structural_audit.json',artifacts)
    if file_sha(audit_path)!=binding.get('structural_audit_sha256'):raise ContractError('Reviewer modified or replaced executable structural audit')
    audit=json.loads(audit_path.read_text())
    if audit.get('source_model_sha256')!=binding['model_sha256'] or audit.get('source_scene_sha256')!=binding['scene_sha256']:raise ContractError('Structural measurements use stale model/scene')
    if audit.get('status')!='passed' or audit.get('failures'):raise ContractError('Unresolved physical furniture structure issue')
    audited_assemblies=audit.get('assemblies',[])
    if len(audited_assemblies)!=len(required) or {x['entity'] for x in audited_assemblies}!=required:raise ContractError('Structural evidence must cover each furniture assembly exactly once')
    declared={a['entity']:a for a in structure['assemblies']}
    for a in audit['assemblies']:
        if not all(a.get(k) for k in ['ownership_checked','floor_checked','source_landmarks','isolated_views']):raise ContractError('Incomplete furniture structure evidence')
        assembly=declared[a['entity']];part_ids={p['id'] for p in assembly['parts']}
        joints=assembly.get('joints');checked=a.get('joints_checked')
        if not isinstance(joints,list) or not isinstance(checked,list):raise ContractError('Declared joints and joint checks must be explicit lists')
        def joint_key(joint):
            pair=joint.get('parts') if isinstance(joint,dict) else None
            if not isinstance(pair,list) or len(pair)!=2 or pair[0]==pair[1] or any(not isinstance(p,str) or p not in part_ids for p in pair):raise ContractError('Invalid audited joint parts')
            anchor=joint.get('anchor_world');tolerance=joint.get('tolerance_m')
            if not isinstance(anchor,list) or len(anchor)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in anchor):raise ContractError('Invalid audited joint anchor')
            if type(tolerance) not in (int,float) or not math.isfinite(tolerance) or not 0<tolerance<=.01:raise ContractError('Invalid audited joint tolerance')
            return (tuple(sorted(pair)),tuple(anchor),tolerance)
        expected_joints={joint_key(joint) for joint in joints};seen_joints=set()
        if len(expected_joints)!=len(joints):raise ContractError('Duplicate declared joint constraint')
        # A single part has no internal connection to measure. Multi-part graphs
        # remain connected by structure_contract, and every declared anchor must
        # have its own bound executable measurement (not just a truthy list).
        if len(part_ids)==1 and (joints or checked):raise ContractError('Single-part assembly cannot claim an internal joint')
        for joint in checked:
            key=joint_key(joint)
            if key not in expected_joints or key in seen_joints:raise ContractError('Unexpected or duplicate audited joint constraint')
            distances=joint.get('measured_anchor_outside_distances_m')
            if joint.get('status')!='pass' or not isinstance(distances,list) or len(distances)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 or v>key[2] for v in distances):raise ContractError('Missing or failing executable joint measurement')
            seen_joints.add(key)
        if seen_joints!=expected_joints:raise ContractError('Joint evidence does not cover all declared constraints')
        for ref in a['isolated_views']:evidence_file(attempt,ref,artifacts)
    for ref,sha in audit.get('evidence_hashes',{}).items():
        if file_sha(evidence_file(attempt,ref,artifacts))!=sha:raise ContractError('Structure evidence bytes changed')
    checks=audit.get('interassembly_checks')
    if not isinstance(checks,list) or not audit.get('evaluated_visible_meshes'):raise ContractError('Visible furniture intersections were not tested')
    owners={p['object']:a['entity'] for a in structure['assemblies'] for p in a['parts']}
    expected_pairs={pair for pair in combinations(sorted(owners),2) if owners[pair[0]]!=owners[pair[1]]}
    checked_pairs=set()
    for check in checks:
        parts=check.get('parts') if isinstance(check,dict) else None
        if not isinstance(parts,list) or len(parts)!=2 or any(not isinstance(p,str) or p not in owners for p in parts):raise ContractError('Invalid interassembly component pair')
        pair=tuple(sorted(parts))
        if pair not in expected_pairs or pair in checked_pairs:raise ContractError('Unexpected or duplicate interassembly component pair')
        if check.get('owners')!=[owners[p] for p in parts]:raise ContractError('Interassembly pair owner mismatch')
        checked_pairs.add(pair)
    if checked_pairs!=expected_pairs:raise ContractError('Interassembly evidence does not cover all cross-assembly component pairs')
    if empty_room:
        inventory=audit.get('empty_room_inventory',{})
        if inventory.get('all_geometry_checked') is not True or inventory.get('object_roles')!=empty_room_inventory(scene) or audit.get('component_pair_checks')!=[]:raise ContractError('Empty-room inventory must cover every declared shell and exclude other geometry')
        ref='furniture_source_view.png'
        if ref not in audit.get('evidence_hashes',{}):raise ContractError('Empty-room review requires hash-bound full source-camera evidence')
        check=review.get('checks',{}).get('empty_room',{})
        if check.get('status')!='pass' or not check.get('findings') or ref not in check.get('evidence',[]):raise ContractError('Empty-room review requires explicit source-view inspection')
    return audit
