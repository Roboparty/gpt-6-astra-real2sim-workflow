"""Independent raw-mesh readback for all four generated assets; no GT scale/alignment."""
import argparse
import hashlib
import json
from pathlib import Path
import trimesh

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve previous audit')
    rows=[]
    for key in ['domino_sugar_box','chocolate_jello_box','red_jello_box','expo_marker']:
        path=a.root/'objects'/key/'shape.ply'
        if not path.is_file():rows.append({'object_id':key,'status':'missing','expected_path':str(path)});continue
        before=sha(path)
        try:
            mesh=trimesh.load(path,force='mesh',process=False)
            row={'object_id':key,'status':'loaded','path':str(path),'sha256':before,'bytes':path.stat().st_size,
                'vertices':len(mesh.vertices),'faces':len(mesh.faces),'watertight':bool(mesh.is_watertight),
                'winding_consistent':bool(mesh.is_winding_consistent),'extents_raw_model_units':mesh.extents.tolist(),
                'bounds_raw_model_units':mesh.bounds.tolist(),'finite_vertices':bool(__import__('numpy').isfinite(mesh.vertices).all()),
                'unit_status':'canonical model units; metric dimension not recovered','source_unchanged':sha(path)==before}
        except Exception as exc:row={'object_id':key,'status':'load_failed','sha256':before,'error':str(exc)}
        rows.append(row)
    report={'schema':'real2sim.desk1-shape-independent-audit/1','objects':rows,'expected_objects':4,
        'loaded_objects':sum(r['status']=='loaded' for r in rows),'watertight_objects':sum(r.get('watertight',False) for r in rows),
        'audit_script_sha256':sha(__file__),'independent_geometry_accuracy':None,'sota_established':False,
        'limits':['Topology readback only; no GT metric scale, pose, camera, appearance or full-scene evaluation.',
                  'Raw generative shape stays unchanged; watertight does not establish correct anatomy, physical scale or collision quality.']}
    a.output.write_text(json.dumps(report,indent=2));print(json.dumps({'loaded':report['loaded_objects'],'watertight':report['watertight_objects'],'expected':4}))

if __name__=='__main__':main()
