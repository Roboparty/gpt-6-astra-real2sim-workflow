"""Acquire a fixed source cohort on the remote execution host; preserve failures."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import urllib.request

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    cohort=json.loads(args.cohort.read_text())
    assert len(cohort['sources'])==cohort['expected_scene_count']
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();rows=[]
    for source in cohort['sources']:
        row=dict(source,status='pending');rows.append(row)
        directory=out/source['id'];directory.mkdir()
        media=directory/'source.mp4';part=directory/'source.partial';t=time.monotonic()
        try:
            request=urllib.request.Request(source['url'],headers={'User-Agent':'Real2Sim-Research/1'})
            with urllib.request.urlopen(request,timeout=30) as response, part.open('wb') as stream:
                size=0
                while chunk:=response.read(1<<18):
                    size+=len(chunk)
                    if size>8_000_000:raise ValueError('Per-video acquisition budget exceeded')
                    stream.write(chunk)
                row['http_headers']={k:response.headers.get(k) for k in ['Content-Type','Content-Length','Last-Modified','ETag']}
            part.rename(media)
            row.update(actual_bytes=size,source_sha256=hashlib.sha256(media.read_bytes()).hexdigest(),path=str(media))
            row['expected_source_sha256']=source.get('source_sha256')
            if source.get('source_sha256') and row['source_sha256']!=source['source_sha256']:
                raise ValueError('Downloaded bytes differ from frozen source hash')
            probe=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
                                  '-show_entries','stream=codec_name,width,height,avg_frame_rate,nb_read_frames,duration',
                                  '-of','json',str(media)],capture_output=True,text=True,timeout=180)
            row['probe_returncode']=probe.returncode
            (directory/'ffprobe.json').write_text(probe.stdout)
            if probe.returncode:raise RuntimeError(probe.stderr[-1000:])
            row['video']=json.loads(probe.stdout)['streams'][0]
            with (directory/'decode.log').open('w') as log:
                result=subprocess.run(['ffmpeg','-v','error','-xerror','-threads','2','-i',str(media),
                                       '-map','0:v:0','-f','null','-'],stdout=log,stderr=log,timeout=180)
            row['decode_returncode']=result.returncode
            if result.returncode:raise RuntimeError('Full video decode failed')
            row['status']='verified'
        except Exception as error:
            row.update(status='failed',error=type(error).__name__+': '+str(error))
        row['wall_seconds']=time.monotonic()-t
        (directory/'receipt.json').write_text(json.dumps(row,indent=2))
    report={'schema':'real2sim.source-acquisition/1','cohort_id':cohort['cohort_id'],
            'cohort_sha256':hashlib.sha256(args.cohort.read_bytes()).hexdigest(),
            'expected_scene_count':cohort['expected_scene_count'],'sources':rows,
            'verified_count':sum(r['status']=='verified' for r in rows),
            'wall_seconds':time.monotonic()-start,'gpu_hours':0,'paid_api_requests':0,
            'scope':'Source bytes and decode only; no reconstruction, benchmark or license expansion'}
    report['acquisition_script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (out/'receipt.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if report['verified_count']==report['expected_scene_count'] else 1)
