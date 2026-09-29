"""Read-only full gzip integrity and independent frozen frame-selection audit."""
import argparse
import gzip
import json
from pathlib import Path
import time

from acquire_tum_reference import sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('protocol','input','output'):
        parser.add_argument('--'+key,type=Path,required=True)
    a=parser.parse_args()
    if a.output.exists():raise ValueError('Audit output already exists')
    started=time.monotonic();cfg=json.loads(a.protocol.read_text());receipt=json.loads((a.input/'receipt.json').read_text())
    report=dict(schema='real2sim.tum-archive-selection-audit/1',protocol_sha256=sha(a.protocol),
                acquisition_receipt_sha256=sha(a.input/'receipt.json'),script_sha256=sha(__file__),
                expected_sequences=cfg['expected_sequences'],sources=[])
    for source in cfg['sources']:
        row=dict(id=source['id'],status='not_ready');report['sources'].append(row)
        try:
            acquired=next(x for x in receipt['sources'] if x['id']==source['id'])
            if acquired['status']!='prepared':raise ValueError('Acquisition not prepared')
            root=a.input/source['id'];archive=root/'source.tgz'
            if archive.stat().st_size!=source['archive_bytes'] or sha(archive)!=acquired['archive_sha256']:
                raise ValueError('Archive byte/hash mismatch')
            expanded=0
            with gzip.open(archive,'rb') as stream:
                while True:
                    chunk=stream.read(4*1024**2)
                    if not chunk:break
                    expanded+=len(chunk)
            row.update(full_gzip_crc_checked=True,expanded_tar_bytes=expanded,archive_sha256=acquired['archive_sha256'])
            frames=json.loads((root/'inputs/manifest.json').read_text())['frames']
            lines=[line.split() for line in (root/'evaluator/rgb.txt').read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')]
            timestamps=[float(line[0]) for line in lines]
            if not all(timestamps[i]<timestamps[i+1] for i in range(len(timestamps)-1)):
                raise ValueError('Nonmonotone original RGB index')
            if len(frames)!=len(cfg['time_fractions']):raise ValueError('Incomplete selected frame set')
            selections=[]
            for i,fraction in enumerate(cfg['time_fractions']):
                target=timestamps[0]+fraction*(timestamps[-1]-timestamps[0])
                # Independent sorted candidate implementation; earlier tie wins.
                k=sorted(range(len(lines)),key=lambda n:(abs(timestamps[n]-target),timestamps[n]))[0]
                if frames[i]['ordinal']!=i or frames[i]['timestamp']!=timestamps[k] or frames[i]['source_member']!=lines[k][1]:
                    raise ValueError('Selected frame differs from frozen fraction rule')
                if sha(root/'inputs'/f'rgb_{i:02d}.png')!=frames[i]['sha256']:
                    raise ValueError('Selected RGB bytes changed')
                selections.append(dict(ordinal=i,rgb_index=k,timestamp=timestamps[k],source_member=lines[k][1]))
            row.update(status='passed',frame_selection=selections)
        except Exception as error:row.update(status='failed',error=repr(error))
    report['passed_sequences']=sum(r['status']=='passed' for r in report['sources'])
    report['wall_seconds']=time.monotonic()-started
    report['scope']='Archive transport/integrity and fixed selection only. No upstream checksum attestation, model predictions, geometry accuracy or SOTA.'
    a.output.write_text(json.dumps(report,indent=2))
    print(json.dumps({'passed_sequences':report['passed_sequences'],'expected_sequences':report['expected_sequences'],'wall_seconds':report['wall_seconds']}))


if __name__=='__main__':main()
