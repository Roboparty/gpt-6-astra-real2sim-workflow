"""Executable evidence contracts for coherent multi-part assemblies.
These checks reject missing/invalid evidence; they do not replace visual judgement.
Geometry measurements must be produced by the Blender evaluator on the bound file.
"""
import hashlib,json,math
from pathlib import Path
from .contracts import ContractError

def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def structure_contract(data):
    if not isinstance(data,dict) or data.get('schema')!='real2sim.assembly/1':raise ContractError('Missing assembly structure contract')
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
    if {x['entity'] for x in audit.get('assemblies',[])}!=required:raise ContractError('Structural evidence omits furniture')
    for a in audit['assemblies']:
        if not all(a.get(k) for k in ['ownership_checked','joints_checked','floor_checked','source_landmarks','isolated_views']):raise ContractError('Incomplete furniture structure evidence')
        for ref in a['isolated_views']:evidence_file(attempt,ref,artifacts)
    for ref,sha in audit.get('evidence_hashes',{}).items():
        if file_sha(evidence_file(attempt,ref,artifacts))!=sha:raise ContractError('Structure evidence bytes changed')
    if not audit.get('interassembly_checks') or not audit.get('evaluated_visible_meshes'):raise ContractError('Visible furniture intersections were not tested')
    return audit
