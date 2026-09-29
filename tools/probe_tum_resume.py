"""Bounded official-source range probes; preserve chunks without appending partials."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    cfg = json.loads(args.protocol.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    report = dict(schema='real2sim.tum-resume-probe/1', protocol_sha256=sha(args.protocol),
                  script_sha256=sha(__file__), expected_sequences=3, prepared_sequences=0,
                  sources=[], scope='Range availability and bounded throughput only; no complete archive or frame readiness.')
    if shutil.disk_usage(args.output).free < cfg['minimum_free_disk_bytes']:
        raise RuntimeError('Registered disk reserve unavailable')

    def probe(source):
        begin = time.monotonic()
        directory = args.output/source['id']; directory.mkdir()
        chunk, headers = directory/'range.bin', directory/'headers.txt'
        start = source['retained_partial_bytes']; end = start+cfg['probe_bytes_per_sequence']-1
        argv = ['curl', '--silent', '--show-error', '--fail', '--location',
                '--connect-timeout', '5', '--max-time', str(cfg['request_timeout_seconds']),
                '--max-filesize', str(cfg['probe_bytes_per_sequence']), '--range', f'{start}-{end}',
                '--dump-header', str(headers), '--output', str(chunk), '--write-out', '%{json}']
        if source.get('previous_etag'):
            argv += ['--header', 'If-Range: '+source['previous_etag']]
        argv.append(source['url'])
        row = dict(id=source['id'], requested_range=[start,end], status='failed')
        try:
            result = subprocess.run(argv, capture_output=True, text=True, timeout=cfg['request_timeout_seconds']+3)
            row.update(returncode=result.returncode, stderr=result.stderr)
            meta = json.loads(result.stdout) if result.stdout else {}
            row['http'] = {k:meta.get(k) for k in ('http_code','url_effective','size_download','speed_download','time_total')}
            lines = headers.read_text(errors='replace').splitlines() if headers.exists() else []
            values = {}
            for line in lines:
                if line.startswith('HTTP/'):
                    values={}
                elif ':' in line:
                    key,value=line.split(':',1); values[key.lower()]=value.strip()
            row['response_headers'] = {k:values.get(k) for k in ('content-range','content-length','etag','last-modified')}
            expected_range = f'bytes {start}-{end}/{source["archive_bytes"]}'
            valid = (result.returncode==0 and meta.get('http_code')==206 and
                     values.get('content-range')==expected_range and chunk.stat().st_size==cfg['probe_bytes_per_sequence'] and
                     (not source.get('previous_etag') or values.get('etag')==source['previous_etag']))
            row['status'] = 'range_verified' if valid else 'range_not_verified'
        except Exception as error:
            row['error'] = repr(error)
        row['retained_probe_bytes'] = chunk.stat().st_size if chunk.exists() else 0
        if chunk.exists(): row['probe_sha256'] = sha(chunk)
        row['wall_seconds'] = time.monotonic()-begin
        (directory/'receipt.json').write_text(json.dumps(row,indent=2))
        print(json.dumps(row),flush=True)
        return row

    with ThreadPoolExecutor(max_workers=cfg['parallel_requests']) as pool:
        report['sources']=list(pool.map(probe,cfg['sources']))
    report['wall_seconds']=time.monotonic()-started
    report['previous_acquisition_wall_seconds']=cfg['previous_acquisition_wall_seconds']
    report['cumulative_acquisition_wall_seconds']=cfg['previous_acquisition_wall_seconds']+report['wall_seconds']
    report['remaining_acquisition_wall_seconds']=cfg['shared_acquisition_cap_seconds']-report['cumulative_acquisition_wall_seconds']
    report['all_ranges_verified']=all(r['status']=='range_verified' for r in report['sources'])
    report['old_partials_modified']=False
    report['retained_probe_bytes']=sum(r['retained_probe_bytes'] for r in report['sources'])
    (args.output/'receipt.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
