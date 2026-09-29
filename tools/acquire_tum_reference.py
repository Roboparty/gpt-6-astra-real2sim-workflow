"""Bounded remote-only TUM acquisition with unchanged RGB and separate evaluator data."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import time
import urllib.request

from PIL import Image


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024**2),b''):h.update(block)
    return h.hexdigest()


def write(path,value):
    tmp=Path(str(path)+'.tmp');tmp.write_text(json.dumps(value,indent=2));tmp.replace(path)


def index(text):
    rows=[]
    for line in text.splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            timestamp,path=line.split();rows.append((float(timestamp),path))
    if not rows or any(rows[i][0]>=rows[i+1][0] for i in range(len(rows)-1)):
        raise ValueError('Empty, duplicate or unsorted timestamp index')
    return rows


def prepare_archive(protocol, protocol_path, directory, partial, row, guard):
    """Validate full archive and extract only the frozen RGB/evaluator members."""
    budget=protocol['budget']
    # Sequential tar parsing checks the complete archive before extracting only selected members.
    with tarfile.open(partial,'r:gz') as archive:
        members={m.name:m for m in archive.getmembers() if m.isfile()}
        prefix='rgbd_dataset_'+row['id']+'/'
        def read_member(name,cap=10485760):
            guard();member=members[prefix+name]
            if member.size>cap:raise ValueError('Unexpectedly large selected member')
            return archive.extractfile(member).read()
        rgb_text=read_member('rgb.txt');depth_text=read_member('depth.txt');truth=read_member('groundtruth.txt')
        rgb=index(rgb_text.decode());depth=index(depth_text.decode())
        inputs=directory/'inputs';inputs.mkdir();evaluation=directory/'evaluator';evaluation.mkdir()
        for name,data in [('rgb.txt',rgb_text),('depth.txt',depth_text),('groundtruth.txt',truth)]:
            (evaluation/name).write_bytes(data)
        selected=[];depth_rows=[];extracted=len(rgb_text)+len(depth_text)+len(truth)
        for ordinal,fraction in enumerate(protocol['time_fractions']):
            target=rgb[0][0]+fraction*(rgb[-1][0]-rgb[0][0]);stamp,name=min(rgb,key=lambda v:(abs(v[0]-target),v[0]))
            data=read_member(name);extracted+=len(data)
            if extracted>budget['max_extracted_bytes']/protocol['expected_sequences']:raise ValueError('Selected extraction cap reached')
            dest=inputs/f'rgb_{ordinal:02d}.png';dest.write_bytes(data)
            with Image.open(dest) as im:im.verify()
            with Image.open(dest) as im:size=list(im.size);mode=im.mode
            if size!=[640,480] or mode!='RGB':raise ValueError('Unexpected RGB format')
            selected.append({'ordinal':ordinal,'timestamp':stamp,'source_member':name,'path':str(dest),'sha256':sha(dest),'image_size':size})
            ds,dname=min(depth,key=lambda v:(abs(v[0]-stamp),v[0]));gap=abs(ds-stamp)
            dr={'rgb_ordinal':ordinal,'rgb_timestamp':stamp,'depth_timestamp':ds,'gap_seconds':gap,'matched':gap<=.02}
            if gap<=.02:
                dd=read_member(dname);extracted+=len(dd)
                if extracted>budget['max_extracted_bytes']/protocol['expected_sequences']:raise ValueError('Selected extraction cap reached')
                dest=evaluation/f'depth_{ordinal:02d}.png';dest.write_bytes(dd)
                with Image.open(dest) as im:im.verify()
                dr.update(path=str(dest),sha256=sha(dest))
            depth_rows.append(dr)
        if len({f['timestamp'] for f in selected})!=6:raise ValueError('Frame selection contains duplicate timestamps')
        write(inputs/'manifest.json',{'schema':'real2sim.tum-rgb-input/1','source_id':row['id'],
            'protocol_sha256':sha(protocol_path),'archive_sha256':row['archive_sha256'],'frames':selected,
            'role':'RGB-only development/reference diagnostic; not held-out generalization evidence'})
        write(evaluation/'manifest.json',{'schema':'real2sim.tum-evaluator-input/1','source_id':row['id'],
            'groundtruth_sha256':sha(evaluation/'groundtruth.txt'),'depth_matches':depth_rows,
            'scope':'Evaluation-only files; logical directory separation, not OS isolation'})
        row.update(rgb_count=len(rgb),depth_count=len(depth),selected_rgb_count=len(selected),
                   selected_depth_matches=sum(r['matched'] for r in depth_rows),selected_rgb=selected,
                   groundtruth_rows=sum(bool(l.strip()) and not l.lstrip().startswith('#') for l in truth.decode().splitlines()),
                   input_manifest_sha256=sha(inputs/'manifest.json'),evaluator_manifest_sha256=sha(evaluation/'manifest.json'),
                   extracted_bytes=extracted)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--protocol',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();protocol=json.loads(a.protocol.read_text());budget=protocol['budget']
    a.output.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    assert sum(s['archive_bytes'] for s in protocol['sources'])==budget['max_archive_bytes']
    assert len(protocol['sources'])==protocol['expected_sequences']==3
    def guard():
        if time.monotonic()-start>budget['acquisition_total_wall_seconds']:raise TimeoutError('Shared acquisition budget exhausted; retain all partial files')
        if shutil.disk_usage(a.output).free<budget['minimum_free_disk_bytes']:raise RuntimeError('Disk reserve reached; partial files retained')
    def acquire(source):
        row={'id':source['id'],'status':'started','expected_archive_bytes':source['archive_bytes']};t=time.monotonic()
        directory=a.output/source['id'];directory.mkdir();partial=directory/'source.tgz.partial'
        try:
            guard()
            with urllib.request.urlopen(source['url'],timeout=20) as response,partial.open('xb') as f:
                row['effective_url']=response.url;row['http_etag']=response.headers.get('ETag')
                if int(response.headers.get('Content-Length','-1'))!=source['archive_bytes']:raise ValueError('Official archive size changed')
                last=0
                while True:
                    guard();block=response.read(1024**2)
                    if not block:break
                    if f.tell()+len(block)>source['archive_bytes']:raise ValueError('Archive exceeds frozen byte budget')
                    f.write(block)
                    if time.monotonic()-last>10:
                        row['downloaded_bytes']=f.tell();write(directory/'progress.json',row);last=time.monotonic()
            if partial.stat().st_size!=source['archive_bytes']:raise ValueError('Truncated archive retained')
            row['archive_sha256']=sha(partial)
            prepare_archive(protocol, a.protocol, directory, partial, row, guard)
            partial.rename(directory/'source.tgz')
            row.update(status='prepared',archive_bytes=source['archive_bytes'])
        except Exception as exc:row.update(status='failed',error=repr(exc),retained_partial_bytes=partial.stat().st_size if partial.exists() else 0)
        row['wall_seconds']=time.monotonic()-t;write(directory/'receipt.json',row)
        print(json.dumps({'id':source['id'],'status':row['status'],'wall_seconds':row['wall_seconds']}),flush=True)
        return row
    with concurrent.futures.ThreadPoolExecutor(budget['parallel_downloads']) as pool:rows=list(pool.map(acquire,protocol['sources']))
    report={'schema':'real2sim.tum-acquisition/1','protocol_sha256':sha(a.protocol),'script_sha256':sha(__file__),
            'expected_sequences':3,'sources':rows,'prepared_sequences':sum(r['status']=='prepared' for r in rows),
            'wall_seconds':time.monotonic()-start,'gpu_hours':0,'paid_api_requests':0,'camera_trials':0,
            'scope':'Acquired sensor-reference data, not model accuracy or SOTA; no upstream cryptographic checksum claimed'}
    write(a.output/'receipt.json',report)


if __name__=='__main__':main()
