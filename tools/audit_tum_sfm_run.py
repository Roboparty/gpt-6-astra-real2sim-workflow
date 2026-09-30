"""Read-only match-graph and persisted model audit for the frozen TUM SfM run."""
import argparse
import itertools
import json
from pathlib import Path
import sqlite3
import numpy as np
import pycolmap
from evaluate_tum_trajectory import file_sha


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve previous audit')
    receipt=json.loads((a.run/'receipt.json').read_text());frames=json.loads((a.run/'frames.json').read_text());rows=[]
    for source,freeze in zip(receipt['sources'],frames['sources']):
        root=Path(source['directory']);database=root/'database.db';before=file_sha(database)
        for n,frame in enumerate(freeze['selected_frames']):
            assert file_sha(frame['path'])==file_sha(root/'images'/f'frame_{n:04d}.png')==frame['sha256']
        with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as connection:
            ids=dict(connection.execute('select image_id,name from images'))
            raw=dict(connection.execute('select pair_id,rows from matches'))
            verified={p:(n,c) for p,n,c in connection.execute('select pair_id,rows,config from two_view_geometries')}
            pairs=[]
            for first,second in itertools.combinations(sorted(ids),2):
                pair_id=first*2147483647+second
                count,config=verified.get(pair_id,(0,None))
                pairs.append(dict(first=ids[first],second=ids[second],raw_matches=raw.get(pair_id,0),verified_matches=count,configuration=config))
        assert file_sha(database)==before and len(ids)==6 and len(pairs)==15
        pose_error=0.;model_hashes={}
        if source['result']['registered_frames']:
            model=pycolmap.Reconstruction(str(root/'models'))
            by_name={model.images[i].name:model.images[i] for i in model.reg_image_ids()}
            assert len(by_name)==source['result']['registered_frames']
            for camera in source['result']['cameras']:
                im=by_name[camera['frame_name']];inverse=im.cam_from_world().inverse()
                pose_error=max(pose_error,float(np.max(abs(np.asarray(inverse.translation)-camera['position_in_sfm_gauge']))))
                assert np.allclose(inverse.rotation.matrix(),np.asarray(camera['rotation_world_to_cv']).T,atol=1e-12)
            assert pose_error<1e-12
            model_hashes={p.name:file_sha(p) for p in (root/'models').glob('*.txt')}
        log=(root/'process.log').read_text()
        rows.append(dict(id=source['id'],keypoint_counts=[x['count'] for x in source['result']['keypoints']],pairs=pairs,
                         verified_nonzero_edges=sum(x['verified_matches']>0 for x in pairs),
                         persisted_model_center_max_error=pose_error if source['result']['registered_frames'] else None,
                         model_sha256=model_hashes,database_sha256=before,
                         effective_options_sha256=file_sha(root/'effective_options.json'),
                         log_sha256=file_sha(root/'process.log'),
                         initialization_log=[line for line in log.splitlines() if any(term in line for term in ['No good initial','bad initial pair','No images with matches'])]))
    a.output.write_text(json.dumps(dict(schema='real2sim.tum-sfm-model-audit/1',initializer_receipt_sha256=file_sha(a.run/'receipt.json'),script_sha256=file_sha(__file__),
                                       sources=rows,scope='Read-only persisted poses, original RGB hashes and all 15 pair counts per scene; no new fit or threshold changes.'),indent=2))
    print(json.dumps([{k:r[k] for k in ['id','keypoint_counts','verified_nonzero_edges','persisted_model_center_max_error']} for r in rows]))


if __name__=='__main__':main()
