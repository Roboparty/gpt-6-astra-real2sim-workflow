"""Resume a frozen TUM cohort from verified prefix pieces within its old ledger."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import time

from acquire_tum_reference import prepare_archive, sha, write


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('protocol','resume','output'):
        parser.add_argument('--'+key,type=Path,required=True)
    a=parser.parse_args();protocol=json.loads(a.protocol.read_text());resume=json.loads(a.resume.read_text())
    if sha(a.protocol)!=resume['cohort_protocol_sha256']:
        raise ValueError('Cohort protocol changed')
    for name,value in resume['implementation_sha256'].items():
        if sha(Path(__file__).parent/name)!=value:raise ValueError('Implementation changed: '+name)
    if len(protocol['sources'])!=protocol['expected_sequences'] or len(resume['sources'])!=protocol['expected_sequences']:
        raise ValueError('Incomplete fixed cohort')
    a.output.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    remaining=protocol['budget']['acquisition_total_wall_seconds']-resume['spent_wall_seconds']
    def guard():
        if time.monotonic()-start>=remaining:raise TimeoutError('Original shared acquisition cap reached')
        if shutil.disk_usage(a.output).free<protocol['budget']['minimum_free_disk_bytes']:
            raise RuntimeError('Disk reserve reached')
    def acquire(source):
        t=time.monotonic();row=dict(id=source['id'],status='started',expected_archive_bytes=source['archive_bytes'])
        directory=a.output/source['id'];directory.mkdir();partial=directory/'source.tgz.partial'
        write(directory/'receipt.json',row)
        try:
            spec=next(s for s in resume['sources'] if s['id']==source['id']);guard()
            cursor=0
            with partial.open('xb') as out:
                for piece in spec['pieces']:
                    path=Path(piece['path'])
                    if piece['start']!=cursor or path.stat().st_size!=piece['bytes'] or sha(path)!=piece['sha256']:
                        raise ValueError('Noncontiguous or modified prefix piece')
                    with path.open('rb') as f:shutil.copyfileobj(f,out,4*1024**2)
                    cursor+=piece['bytes']
            if cursor<=0 or cursor>=source['archive_bytes']:raise ValueError('Unexpected prefix size')
            row['reused_prefix_bytes']=cursor;guard()
            budget_left=remaining-(time.monotonic()-start)
            argv=['curl','--silent','--show-error','--fail','--location','--connect-timeout','10',
                  '--max-time',str(budget_left),'--max-filesize',str(source['archive_bytes']),
                  '--continue-at','-','--header','If-Range: '+spec['etag'],
                  '--dump-header',str(directory/'headers.txt'),'--output',str(partial),
                  '--write-out','%{json}',source['url']]
            result=subprocess.run(argv,capture_output=True,text=True,timeout=budget_left+2)
            row.update(curl_returncode=result.returncode,curl_stderr=result.stderr)
            meta=json.loads(result.stdout) if result.stdout else {};row['curl']=meta
            headers={}
            for line in (directory/'headers.txt').read_text(errors='replace').splitlines():
                if line.startswith('HTTP/'):headers={}
                elif ':' in line:
                    key,value=line.split(':',1);headers[key.lower()]=value.strip()
            row['response_headers']={k:headers.get(k) for k in ('content-range','etag','content-length')}
            expected_range=f'bytes {cursor}-{source["archive_bytes"]-1}/{source["archive_bytes"]}'
            if (result.returncode!=0 or meta.get('http_code')!=206 or headers.get('content-range')!=expected_range or
                    headers.get('etag')!=spec['etag'] or partial.stat().st_size!=source['archive_bytes']):
                raise ValueError('Incomplete/mismatched resumed response; bytes retained but unqualified')
            guard();row['archive_sha256']=sha(partial);row['status']='downloaded';write(directory/'receipt.json',row)
            prepare_archive(protocol,a.protocol,directory,partial,row,guard)
            guard();partial.rename(directory/'source.tgz');row.update(status='prepared',archive_bytes=source['archive_bytes'])
        except Exception as error:
            row.update(status='failed',error=repr(error),retained_partial_bytes=partial.stat().st_size if partial.exists() else 0)
        row['wall_seconds']=time.monotonic()-t;write(directory/'receipt.json',row)
        print(json.dumps({k:row.get(k) for k in ('id','status','error','wall_seconds','selected_rgb_count','selected_depth_matches')}),flush=True)
        return row
    report=dict(schema='real2sim.tum-resumed-acquisition/1',status='started',cohort_protocol_sha256=sha(a.protocol),
                resume_manifest_sha256=sha(a.resume),script_sha256=sha(__file__),expected_sequences=3,
                previous_spent_wall_seconds=resume['spent_wall_seconds'],sources=[])
    write(a.output/'receipt.json',report)
    with ThreadPoolExecutor(max_workers=protocol['budget']['parallel_downloads']) as pool:
        report['sources']=list(pool.map(acquire,protocol['sources']))
    report['wall_seconds']=time.monotonic()-start
    report['cumulative_acquisition_wall_seconds']=resume['spent_wall_seconds']+report['wall_seconds']
    report['remaining_acquisition_wall_seconds']=max(0,900-report['cumulative_acquisition_wall_seconds'])
    report['prepared_sequences']=sum(r['status']=='prepared' for r in report['sources'])
    report['status']='prepared' if report['prepared_sequences']==3 else 'incomplete'
    report['scope']='Data preparation only; source HTTP identity and local SHA256, not upstream cryptographic attestation, reconstruction accuracy or SOTA.'
    write(a.output/'receipt.json',report)


if __name__=='__main__':main()
