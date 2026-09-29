"""Isolated remote Pi3X preparation with resumable weights and owned processes.

No inference, GPU initialization or edits to existing Python environments.
Signed download URLs are read from a mode-600 file and never logged.
"""
import argparse
import calendar
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request

COMMIT = '9fa3ddb3f8d53041f8b2738df404f62223bbaa7b'
WEIGHT_BYTES = 5440325620
WEIGHT_SHA256 = '69972d6e1c4492cb4d737a84fe940e357087d81c52f5c9b7c160b49c1f41669a'
GIB = 1024 ** 3


def write_json(path, data):
    temp = Path(str(path) + '.tmp')
    temp.write_text(json.dumps(data, indent=2), encoding='utf-8')
    temp.replace(path)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 ** 2), b''):
            digest.update(block)
    return digest.hexdigest()


def process_ticks(pid):
    try:
        # Fields after the final ')' begin at proc field 3 (state).
        return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def preserve_wheels(base):
    """Keep unverified pip downloads without duplicating their file data."""
    base = base.resolve()
    tmp, keep = (base / 'tmp').resolve(), (base / 'wheel_partials').resolve()
    if not tmp.is_relative_to(base) or not keep.is_relative_to(base):
        raise RuntimeError('Wheel preservation must stay inside the owned runtime base')
    keep.mkdir(exist_ok=True)
    manifest_path = keep / 'manifest.json'
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {'files': []}
    rows = {row['preserved_hardlink']: row for row in old['files']}
    for candidate in tmp.rglob('*.whl'):
        source = candidate.resolve()
        if not source.is_relative_to(tmp) or not source.is_file():
            continue
        name = hashlib.sha256(str(source).encode()).hexdigest()[:12] + '-' + source.name + '.unverified'
        target = (keep / name).resolve()
        if not target.is_relative_to(keep) or source.stat().st_dev != keep.stat().st_dev:
            raise RuntimeError('Wheel preservation requires same-device owned paths')
        if target.exists():
            if not os.path.samefile(source, target):
                raise RuntimeError('Conflicting preserved wheel; retained for inspection')
        else:
            os.link(source, target)
        rows[str(target)] = {'source': str(source), 'preserved_hardlink': str(target),
                            'status': 'unverified', 'device': source.stat().st_dev,
                            'inode': source.stat().st_ino,
                            'reuse_requires': 'Verify full wheel against official PyPI SHA256 before installation; partial needs explicit resume'}
    for row in rows.values():
        target = Path(row['preserved_hardlink']).resolve()
        if not target.is_relative_to(keep):
            raise RuntimeError('Saved wheel manifest escapes the owned directory')
        row['bytes_at_snapshot'] = target.stat().st_size
    result = {'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'method': 'same-filesystem hardlinks; no second file-data copy',
              'scope': str(tmp), 'files': list(rows.values()),
              'total_logical_bytes_at_snapshot': sum(row['bytes_at_snapshot'] for row in rows.values()),
              'installed_from_preserved_files': False}
    write_json(manifest_path, result)
    return {'file_count': len(rows), 'preserved_bytes': result['total_logical_bytes_at_snapshot'],
            'manifest': str(manifest_path), 'all_files_unverified': True}


class Preparation:
    def __init__(self, base, attempt):
        self.base, self.attempt = base, attempt
        budget = json.loads((base / 'preparation_budget.json').read_text())
        self.started = time.monotonic() - (time.time() - budget['started_epoch'])
        self.state = {'status': 'running', 'phase': 'preflight', 'pid': os.getpid(),
                      'start_ticks': process_ticks(os.getpid()), 'timeout_seconds': 1800,
                      'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                      'gpu_used': False, 'inference_run': False}
        self.child = None

    def save(self, **updates):
        self.state.update(updates)
        self.state['elapsed_seconds'] = time.monotonic() - self.started
        self.state['disk_free_bytes'] = shutil.disk_usage(self.base).free
        self.state['minimum_free_bytes'] = min(self.state.get('minimum_free_bytes', self.state['disk_free_bytes']), self.state['disk_free_bytes'])
        write_json(self.attempt / 'state.json', self.state)

    def guard(self, install=False):
        if time.monotonic() - self.started > 1800:
            raise TimeoutError('Preparation exceeded its fixed 1800 second budget; partial artifacts retained')
        # The installer gets one GiB of reaction headroom above the hard reserve.
        threshold = (5 if install else 4.25) * GIB
        if shutil.disk_usage(self.base).free < threshold:
            raise RuntimeError('Disk guard stopped owned work before the 4 GiB reserve; partial artifacts retained')

    def download(self, url, partial, final, expected=None, checksum=None, maximum=None):
        self.guard()
        if final.exists():
            if expected is not None and final.stat().st_size != expected:
                raise RuntimeError('Existing final artifact has wrong size; preserved for inspection')
            if checksum and sha(final) != checksum:
                raise RuntimeError('Existing final artifact has wrong hash; preserved for inspection')
            return
        offset = partial.stat().st_size if partial.exists() else 0
        if expected is not None and offset > expected:
            raise RuntimeError('Existing partial is larger than expected; preserved for inspection')
        if expected is None or offset < expected:
            headers = {'Range': f'bytes={offset}-'} if offset else {}
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
                if offset and (response.status != 206 or not response.headers.get('Content-Range', '').startswith(f'bytes {offset}-')):
                    raise RuntimeError('Server did not honor resume range; existing partial preserved')
                last_save = 0
                with partial.open('ab' if offset else 'wb') as output:
                    while True:
                        self.guard()
                        block = response.read(4 * 1024 ** 2)
                        if not block:
                            break
                        if maximum is not None and output.tell() + len(block) > maximum:
                            raise RuntimeError('Download exceeds its frozen size budget')
                        output.write(block)
                        if time.monotonic() - last_save > 3:
                            output.flush()
                            self.save(download_file=partial.name, downloaded_bytes=output.tell(), expected_bytes=expected)
                            last_save = time.monotonic()
        if expected is not None and partial.stat().st_size != expected:
            raise RuntimeError('Incomplete download retained for resume')
        if checksum and sha(partial) != checksum:
            raise RuntimeError('Downloaded checksum mismatch; partial retained and not promoted')
        partial.replace(final)

    def command(self, argv, label, cwd=None):
        self.guard(install=True)
        environment = os.environ.copy()
        environment.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2',
                           OPENBLAS_NUM_THREADS='2', PIP_NO_CACHE_DIR='1',
                           TMPDIR=str(self.base / 'tmp'), HF_HUB_OFFLINE='1',
                           HF_HUB_DISABLE_TELEMETRY='1', PYTHONDONTWRITEBYTECODE='1')
        with (self.attempt / f'{label}.log').open('w') as log:
            self.child = subprocess.Popen(argv, cwd=cwd, env=environment, stdout=log,
                                          stderr=subprocess.STDOUT, start_new_session=True)
            self.save(child_pid=self.child.pid, child_start_ticks=process_ticks(self.child.pid), phase=label)
            try:
                last_save = 0
                while self.child.poll() is None:
                    self.guard(install=True)
                    if time.monotonic() - last_save > 3:
                        self.save()
                        last_save = time.monotonic()
                    time.sleep(0.25)
                if self.child.returncode:
                    raise RuntimeError(f'{label} exited {self.child.returncode}; see retained log')
            except BaseException:
                try:
                    self.save(wheel_preservation=preserve_wheels(self.base))
                except Exception as preservation_error:
                    self.state['wheel_preservation_error'] = type(preservation_error).__name__
                if self.child.poll() is None:
                    os.killpg(self.child.pid, signal.SIGTERM)
                    try:
                        self.child.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        os.killpg(self.child.pid, signal.SIGKILL)
                        self.child.wait()
                raise
            finally:
                self.child = None
                self.save(child_pid=None, child_start_ticks=None)

    def run(self):
        try:
            (self.base / 'tmp').mkdir(exist_ok=True)
            estimate = {
                'weight_bytes_exact': WEIGHT_BYTES,
                'known_major_binary_wheels_bytes_from_pypi': 3021891246,
                'venv_expansion_allowance_bytes_assumed': 8 * GIB,
                'source_archive_cap_bytes': 50 * 1024 ** 2,
                'estimated_peak_additional_bytes': WEIGHT_BYTES + 3021891246 + 8 * GIB + 50 * 1024 ** 2,
                'estimate_is_not_measured_install_peak': True,
                'hard_disk_reserve_bytes': 4 * GIB,
                'installer_stop_threshold_bytes': 5 * GIB,
                'no_existing_environment_changes': True,
                'single_weight_file_no_hf_cache': True,
                'code_commit': COMMIT, 'checkpoint_sha256': WEIGHT_SHA256,
                'script_sha256': sha(__file__),
            }
            write_json(self.attempt / 'preparation_plan.json', estimate)
            self.save()
            partial = self.base / 'model.safetensors.partial'
            already = partial.stat().st_size if partial.exists() else 0
            if (self.base / 'model.safetensors').exists():
                already = WEIGHT_BYTES
            if shutil.disk_usage(self.base).free < estimate['estimated_peak_additional_bytes'] - already + 4 * GIB:
                raise RuntimeError('Initial free space below conservative preparation estimate plus reserve')
            url_file = self.base / 'download_url.txt'
            if url_file.stat().st_mode & 0o077:
                raise RuntimeError('Signed URL file must not be group/world readable')
            url = url_file.read_text().strip()
            if not url.startswith('https://'):
                raise RuntimeError('Weight transport must use HTTPS')
            self.save(phase='download_weights')
            self.download(url, partial, self.base / 'model.safetensors', WEIGHT_BYTES, WEIGHT_SHA256, WEIGHT_BYTES)
            del url
            self.save(phase='download_source', weight_verified=True, weight_sha256=WEIGHT_SHA256)
            archive = self.base / 'pi3_source.tar.gz'
            self.download('https://codeload.github.com/yyfz/Pi3/tar.gz/' + COMMIT,
                          self.base / 'pi3_source.tar.gz.partial', archive, maximum=50 * 1024 ** 2)
            source = self.base / 'source'
            source.mkdir(exist_ok=True)
            prefix = 'Pi3-' + COMMIT + '/'
            with tarfile.open(archive) as bundle:
                for member in bundle.getmembers():
                    if not member.isfile() or not member.name.startswith(prefix):
                        continue
                    relative = Path(member.name[len(prefix):])
                    if '..' in relative.parts or relative.is_absolute():
                        raise RuntimeError('Unsafe source archive path')
                    if not (str(relative).startswith('pi3/') or str(relative) in {'requirements.txt', 'pyproject.toml', 'LICENSE', 'README.md', 'example_mm.py'}):
                        continue
                    target = source / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.extractfile(member) as input_file:
                        target.write_bytes(input_file.read())
            write_json(self.attempt / 'source_manifest.json', {'commit': COMMIT, 'archive_sha256': sha(archive),
                       'files': {str(p.relative_to(source)): sha(p) for p in source.rglob('*') if p.is_file()}})
            venv = self.base / 'venv'
            if not (venv / 'bin/python').exists():
                self.command([sys.executable, '-m', 'venv', str(venv)], 'create_venv')
            python = str(venv / 'bin/python')
            self.command([python, '-m', 'pip', 'install', '--no-cache-dir', 'pip==24.3.1'], 'bootstrap_pip')
            self.command([python, '-m', 'pip', 'install', '--no-cache-dir', '--report',
                          str(self.attempt / 'install_report.json'), '-r', str(source / 'requirements.txt')], 'install_dependencies')
            smoke = """
import importlib.metadata,json,sys,torch
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from pi3.models.pi3x import Pi3X
model=Pi3X(use_multimodal=False).eval()
report={'python':sys.version,'torch':torch.__version__,'torchvision':importlib.metadata.version('torchvision'),
        'numpy':importlib.metadata.version('numpy'),'checkpoint_loaded':False,'forward_run':False,
        'cuda_initialized':torch.cuda.is_initialized(),'all_parameters_on_cpu':all(p.device.type=='cpu' for p in model.parameters()),
        'parameter_count':sum(p.numel() for p in model.parameters()),
        'parameter_bytes':sum(p.numel()*p.element_size() for p in model.parameters())}
assert report['torch'].split('+')[0]=='2.5.1' and report['torchvision']=='0.20.1' and report['numpy']=='1.26.4'
assert not report['cuda_initialized'] and report['all_parameters_on_cpu']
Path(sys.argv[2]).write_text(json.dumps(report,indent=2));print(json.dumps(report))
"""
            self.command([python, '-c', smoke, str(source), str(self.attempt / 'cpu_construction.json')], 'cpu_construction')
            self.save(status='ready', phase='complete', inference_run=False, gpu_used=False,
                      venv_python=python, source_directory=str(source), weight_path=str(self.base / 'model.safetensors'))
        except urllib.error.HTTPError as exc:
            self.save(status='blocked', error_type='HTTPError', http_status=exc.code,
                      action='Refresh the official signed URL via HEAD if expired; preserve partial file.')
        except BaseException as exc:
            # Never log exception URLs or traceback locals containing signed URLs.
            detail = str(exc)
            if 'https://' in detail:
                detail = 'Network operation failed; signed URL redacted'
            self.save(status='blocked', error_type=type(exc).__name__, error=detail)
        print(json.dumps(self.state), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start', 'status', 'preserve', 'worker'])
    parser.add_argument('--base', required=True)
    parser.add_argument('--attempt')
    args = parser.parse_args()
    base = Path(args.base).resolve()
    if args.action == 'preserve':
        print(json.dumps(preserve_wheels(base), indent=2))
        return
    if args.action == 'worker':
        Preparation(base, Path(args.attempt)).run()
        return
    launch_path = base / 'launch.json'
    if args.action == 'status':
        launch = json.loads(launch_path.read_text())
        state_path = Path(launch['attempt_directory']) / 'state.json'
        state = json.loads(state_path.read_text()) if state_path.exists() else {'status': 'starting'}
        ticks = process_ticks(launch['pid'])
        print(json.dumps({'launch': launch, 'worker_identity_alive': ticks is not None and ticks == launch['start_ticks'], 'state': state}, indent=2))
        return
    base.mkdir(parents=True, exist_ok=True)
    if launch_path.exists():
        existing = json.loads(launch_path.read_text())
        ticks = process_ticks(existing['pid'])
        if ticks is not None and ticks == existing['start_ticks']:
            raise RuntimeError('Preparation is already running; use status')
    budget_path = base / 'preparation_budget.json'
    if not budget_path.exists():
        initial_epoch = calendar.timegm(time.strptime(existing['started_utc'], '%Y-%m-%dT%H:%M:%SZ')) if launch_path.exists() else time.time()
        write_json(budget_path, {'started_epoch': initial_epoch, 'timeout_seconds': 1800,
                                'scope': 'Shared preparation budget across compatibility retries'})
    if time.time() - json.loads(budget_path.read_text())['started_epoch'] >= 1800:
        raise RuntimeError('Shared preparation time budget exhausted; do not reset it on resume')
    attempt = base / ('prepare_' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()))
    attempt.mkdir(exist_ok=False)
    shutil.copy2(__file__, attempt / 'prepare_helper.py')
    with (attempt / 'worker.log').open('w') as log:
        worker = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'worker', '--base', str(base),
                                   '--attempt', str(attempt)], stdout=log, stderr=subprocess.STDOUT,
                                   stdin=subprocess.DEVNULL, start_new_session=True)
    launch = {'pid': worker.pid, 'start_ticks': process_ticks(worker.pid), 'attempt_directory': str(attempt),
              'log': str(attempt / 'worker.log'), 'script_sha256': sha(__file__),
              'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    write_json(launch_path, launch)
    print(json.dumps(launch, indent=2))


if __name__ == '__main__':
    main()
