"""Read-only explanation of a retained native contract failure, not a waiver."""
import bpy,json,hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path('/home/wqz/real2sim_agent_compare_20261003/OURS');V=R/'models/v3';S=json.loads((V/'scene.json').read_text());anchor=Vector((6.55,7.1,.39));deps=bpy.context.evaluated_depsgraph_get();rows=[]
for name in ['flatbed_frame','flatbed_towA']:
 o=bpy.data.objects[name];ev=o.evaluated_get(deps);m=ev.to_mesh();m.calc_loop_triangles();verts=[o.matrix_world@v.co for v in m.vertices];faces=[tuple(t.vertices) for t in m.loop_triangles];tree=BVHTree.FromPolygons(verts,faces,all_triangles=True);near,n,idx,dist=tree.find_nearest(anchor)
 signed=(anchor-near).dot(n);rows.append(dict(part=name,owner=o.get('furniture_id'),nearest_surface_distance_m=dist,outside_distance_m=max(0,dist if signed>0 else -dist),anchor=tuple(anchor)))
 ev.to_mesh_clear()
assembly=next(a for a in S['structure']['assemblies'] if a['entity']=='flatbed_trailer');declared=any(set(j['parts'])=={'flatbed_frame','flatbed_towA'} for j in assembly['joints'])
out=dict(status='diagnostic_only_unresolved_contract_failure',selected_model_sha256=hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),pair=['flatbed_frame','flatbed_towA'],declared_in_accepted_structure=declared,construction_evidence="build_scene_v3.py explicitly starts flatbed_towA at (6.55,7.1,.39), inside the observed flatbed frame; this is an intended tow-frame attachment",source_builder_sha256=hashlib.sha256((V/'build_scene_v3.py').read_bytes()).hexdigest(),measurements=rows,proposed_repair='Add the missing measured intended-joint declaration in a future revision and rerun native review; no active artifact or accepted state has been edited.',limitation='This note does not erase native failure, grant visual acceptance, or interpret the sampled depth as calibrated penetration.')
(V/'intended_joint_diagnostic.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
