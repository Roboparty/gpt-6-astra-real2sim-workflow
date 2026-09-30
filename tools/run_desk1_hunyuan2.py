"""One bounded remote Hunyuan3D-2 Desk1 attempt; never modifies the Pi3X env.

Start with existing Python: --protocol ARM.json --phase PHASE.json
    --annotations ANNOTATIONS.json --mode all
Data/model artifacts stay in protocol environment.data_root. No service API.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tarfile
import threading
import time
import traceback
import urllib.request


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 << 20), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
    temp.replace(path)


def command(argv, log, timeout, env):
    with log.open('w') as stream:
        process = subprocess.Popen(argv, stdout=stream, stderr=subprocess.STDOUT,
                                   env=env, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise TimeoutError('Owned command exceeded its bounded wall time; see '+str(log))
    if code:
        raise RuntimeError('Command failed with '+str(code)+'; see '+str(log))


def gpu_check(cfg, own_pid=None):
    data = subprocess.check_output(['nvidia-smi', '--query-gpu=index,uuid,memory.used,utilization.gpu',
                                    '--format=csv,noheader,nounits'], text=True)
    rows = [[item.strip() for item in line.split(',')] for line in data.splitlines()]
    row = next(row for row in rows if int(row[0]) == cfg['index'])
    if row[1] != cfg['uuid'] or cfg['index'] not in cfg['allowed_indices']:
        raise RuntimeError('GPU identity outside registered selection')
    apps = subprocess.check_output(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid,used_gpu_memory',
                                   '--format=csv,noheader,nounits'], text=True)
    for line in apps.splitlines():
        values = [item.strip() for item in line.split(',')]
        if values[0] == cfg['uuid'] and (own_pid is None or int(values[1]) != own_pid):
            raise RuntimeError('Selected GPU acquired external work; block without interference')
    if own_pid is None and (int(row[2]) > 100 or int(row[3]) != 0):
        raise RuntimeError('Selected GPU no longer idle')
    return {'selected': row, 'compute_processes': apps.splitlines()}


def hull(points):
    points = sorted(set(tuple(point) for point in points))
    def cross(o, a, b): return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lower, upper = [], []
    for point in points:
        while len(lower) > 1 and cross(lower[-2], lower[-1], point) <= 0: lower.pop()
        lower.append(point)
    for point in reversed(points):
        while len(upper) > 1 and cross(upper[-2], upper[-1], point) <= 0: upper.pop()
        upper.append(point)
    return lower[:-1]+upper[:-1]


def make_inputs(cfg, annotation, root):
    from PIL import Image, ImageDraw
    image = Image.open(cfg['source_image']).convert('RGB')
    if image.size != (1920, 1080) or annotation['annotation_raster'] != [1280, 720]:
        raise ValueError('Unexpected source/annotation raster')
    shapes = {}
    for box in annotation['boxes']:
        points = box['top_front_order'] + list(box['bottom_pixels'].values())
        shapes[box['id']] = hull([(round(x*1.5), round(y*1.5)) for x, y in points])
    endpoints = annotation['marker']['axis_pixels']
    shapes['expo_marker'] = hull([(round((x+12*math.cos(t*math.pi/32))*1.5),
                                  round((y+12*math.sin(t*math.pi/32))*1.5))
                                 for x, y in endpoints for t in range(64)])
    if list(shapes) != cfg['expected_objects']:
        raise ValueError('Fixed four-object identity/order changed')
    inputs = root/'inputs'; inputs.mkdir(exist_ok=False)
    rows = []
    for name, polygon in shapes.items():
        mask = Image.new('L', image.size, 0); ImageDraw.Draw(mask).polygon(polygon, fill=255)
        rgba = image.convert('RGBA'); rgba.putalpha(mask)
        mask.save(inputs/(name+'_mask.png')); rgba.save(inputs/(name+'_rgba.png'))
        rows.append({'id': name, 'polygon_xy': polygon, 'bbox_xyxy': list(mask.getbbox()),
                     'rgba_path': str(inputs/(name+'_rgba.png')),
                     'rgba_sha256': sha(inputs/(name+'_rgba.png')), 'mask_sha256': sha(inputs/(name+'_mask.png')),
                     'mask_pixels': mask.histogram()[255], 'source_rgb_unchanged': True})
    write(inputs/'manifest.json', {'source_sha256': cfg['source_sha256'], 'annotation_sha256': cfg['annotation_sha256'],
                                  'mask_recipe': cfg['mask_recipe'], 'objects': rows})
    return rows


def setup(cfg, root, code_root, env, resume=False):
    elapsed = time.time()-json.loads((root/'launch.json').read_text())['start_time_unix'] if resume else 0
    started = time.monotonic()-elapsed; limit = cfg['limits']['setup_wall_seconds']
    receipt = json.loads((root/'setup_receipt.json').read_text()) if resume else {
        'status': 'started', 'download_body_bytes': 0, 'resolver_reserved_bytes': 0,
        'metadata_conservative_allowance_bytes': 1 << 30, 'downloads': []}
    if resume and receipt.get('error'):
        receipt.setdefault('previous_errors', []).append({'error':receipt.pop('error'), 'traceback':receipt.pop('traceback', None), 'wall_seconds':receipt.get('wall_seconds')})
    receipt['status'] = 'started'; receipt['resumed_without_clock_reset'] = resume
    receipt_path = root/'setup_receipt.json'; write(receipt_path, receipt)
    def remaining():
        value = limit-(time.monotonic()-started)
        if value <= 0: raise TimeoutError('Registered setup deadline exhausted')
        if shutil.disk_usage(root).free < cfg['limits']['minimum_free_data_bytes']:
            raise RuntimeError('Data disk reserve exhausted')
        return value
    def download(url, target, expected=None):
        if target.exists():
            previous = next((r['sha256'] for r in receipt['downloads'] if r['file'] == str(target)), None)
            required = expected or previous
            if required and sha(target) == required:
                receipt.setdefault('verified_reuses', []).append({'file':str(target), 'sha256':required})
                return
            raise ValueError('Unverified existing download target')
        partial = target.with_suffix(target.suffix+'.partial'); count = 0
        with urllib.request.urlopen(url, timeout=min(30, remaining())) as response, partial.open('xb') as stream:
            for block in iter(lambda: response.read(1 << 20), b''):
                remaining(); receipt['download_body_bytes'] += len(block); count += len(block)
                if receipt['download_body_bytes']+receipt['resolver_reserved_bytes']+(1 << 30) > cfg['limits']['download_bytes']:
                    raise RuntimeError('25 GiB conservative download bound exhausted')
                stream.write(block)
        digest = sha(partial)
        if expected and digest != expected: raise ValueError('Downloaded file hash mismatch: '+target.name)
        partial.rename(target)
        receipt['downloads'].append({'file': str(target), 'bytes': count, 'sha256': digest})
        write(receipt_path, receipt)
    if resume == 'weights':
        try:
            remaining()
            if 'SHAPE_IMPORT_OK' not in (root/'shape_import.log').read_text() or 'No broken requirements found' not in (root/'pip_check.log').read_text():
                raise RuntimeError('Retained dependency/import readiness missing')
            weight_dir = root/'weights'/cfg['weight_subfolder']
            config_path = weight_dir/'config.yaml'
            binding = json.loads((root/'config_transport_recovery.json').read_text())
            if sha(config_path) != binding['sha256'] or binding['revision'] != cfg['weight_revision']:
                raise ValueError('Recovered exact-variant configuration mismatch')
            download((code_root/'weight_download_url.txt').read_text().strip(), weight_dir/cfg['weight_file'], cfg['weight_sha256'])
            if (weight_dir/cfg['weight_file']).stat().st_size != cfg['weight_bytes']: raise ValueError('Checkpoint size changed')
            receipt.update(status='ready', config_recovery=binding)
        except Exception as error:
            receipt.update(status='blocked', error=repr(error), traceback=traceback.format_exc())
        receipt['wall_seconds'] = time.monotonic()-started
        receipt['download_conservative_upper_bound_bytes'] = receipt['download_body_bytes']+receipt['resolver_reserved_bytes']+(1 << 30)
        write(receipt_path, receipt)
        return receipt
    try:
        cache = root/'resolver_retained'; cache.mkdir(exist_ok=True)
        def retain_wheels():
            for path in (root/'tmp').rglob('*.whl'):
                target = cache/path.name
                if not target.exists():
                    try: os.link(path, target)
                    except FileNotFoundError: pass
        if resume:
            restore = json.loads((root/'setup_resume.json').read_text())
            pid = restore['resolver_pid']; frozen_cmd = restore['resolver_cmdline']
            target = cache/restore['pymeshlab_filename']
            while True:
                remaining(); retain_wheels()
                proc = Path('/proc')/str(pid)
                if target.exists() and target.stat().st_size == restore['pymeshlab_bytes'] and sha(target) == restore['pymeshlab_sha256']:
                    if proc.exists() and (proc/'cmdline').read_bytes().decode().replace('\0',' ').strip() == frozen_cmd:
                        os.killpg(pid, signal.SIGTERM)
                    break
                if not proc.exists(): raise RuntimeError('Retained resolver ended before its current wheel completed')
                time.sleep(min(2, remaining()))
            retain_wheels()
            receipt['previous_resolver_body_bytes_retained'] = sum(path.stat().st_size for path in cache.glob('*.whl'))
            receipt['resolver_reserved_bytes'] = receipt['previous_resolver_body_bytes_retained']
            write(receipt_path, receipt)
        root.mkdir(parents=True, exist_ok=True); code_root.mkdir(parents=True, exist_ok=True)
        archive = root/'official_source.tar.gz'
        download('https://codeload.github.com/Tencent-Hunyuan/Hunyuan3D-2/tar.gz/'+cfg['code_commit'], archive)
        source = code_root/'source'
        if not source.exists():
            source.mkdir()
            with tarfile.open(archive, 'r:gz') as tar:
                for member in tar.getmembers():
                    remaining()
                    relative = Path(*Path(member.name).parts[1:])
                    if relative == Path('.') or not member.isfile(): continue
                    target = (source/relative).resolve()
                    if not target.is_relative_to(source.resolve()): raise ValueError('Invalid source archive member')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with tar.extractfile(member) as src, target.open('xb') as dst: shutil.copyfileobj(src, dst)
        receipt['source_tree_sha256'] = hashlib.sha256(json.dumps({str(p.relative_to(source)): sha(p)
            for p in source.rglob('*') if p.is_file()}, sort_keys=True).encode()).hexdigest()
        venv = root/'venv'
        if not venv.exists(): command([sys.executable, '-m', 'venv', '--without-pip', str(venv)], root/'venv.log', remaining(), env)
        site = venv/'lib/python3.10/site-packages'
        if not site.is_dir(): raise RuntimeError('This adapter requires the verified Python3.10 runtime')
        (site/'readonly_pi3x_torch.pth').write_text(cfg['environment']['readonly_base_site']+'\n')
        if not (code_root/'venv').exists(): os.symlink(venv, code_root/'venv', target_is_directory=True)
        python = str(venv/'bin/python'); wheels = root/'wheels'; wheels.mkdir(exist_ok=True)
        if resume:
            fresh = Path('/home/wqz/real2sim_fresh_20260921/runtime/venv/lib/python3.10/site-packages')
            info = fresh/'scipy-1.15.3.dist-info'
            if not info.is_dir() or 'Version: 1.15.3\n' not in (info/'METADATA').read_text():
                raise RuntimeError('Exact compatible read-only SciPy unavailable')
            receipt['readonly_scipy_metadata_sha256'] = sha(info/'METADATA')
            for path in (fresh/'scipy', fresh/'scipy.libs', info):
                if not (site/path.name).exists(): os.symlink(path, site/path.name, target_is_directory=True)
            # Quarantine incomplete files; expose only exact official-hash wheels to pip.
            for path in cache.glob('*.whl'):
                from packaging.utils import parse_wheel_filename
                name, version, _, _ = parse_wheel_filename(path.name)
                with urllib.request.urlopen('https://pypi.org/pypi/'+str(name)+'/'+str(version)+'/json', timeout=min(30,remaining())) as response:
                    metadata = json.load(response)
                item = next(item for item in metadata['urls'] if item['filename'] == path.name)
                if path.stat().st_size == item['size'] and sha(path) == item['digests']['sha256']:
                    if not (wheels/path.name).exists(): os.link(path, wheels/path.name)
                    receipt.setdefault('officially_verified_resolver_cache', []).append({'filename':path.name,'sha256':item['digests']['sha256']})
        constraints = root/'constraints.txt'; constraints.write_text('torch==2.5.1\ntorchvision==0.20.1\nnumpy==1.26.4\n')
        report = root/('pip_resolution_resume.json' if resume else 'pip_resolution.json')
        pip_args = [python, '-m', 'pip', 'install', '--dry-run', '--report', str(report), '--only-binary=:all:',
                    '--disable-pip-version-check', '--no-cache-dir', '--retries', '0', '--timeout', '30',
                    '--index-url', 'https://pypi.org/simple', '--find-links', str(wheels), '-c', str(constraints), *cfg['dependency_pins']]
        stop = threading.Event()
        def watcher():
            while not stop.wait(.5): retain_wheels()
        monitor = threading.Thread(target=watcher, daemon=True); monitor.start()
        try: command(pip_args, root/('pip_resolution_resume.log' if resume else 'pip_resolution.log'), remaining(), env)
        finally: retain_wheels(); stop.set(); monitor.join(timeout=2)
        plan = json.loads(report.read_text())['install']
        # Resolver can transfer wheels to inspect metadata. Charge full sizes conservatively.
        sizes = []
        for item in plan:
            url = item['download_info']['url']
            if not url.split('?', 1)[0].endswith('.whl'): raise ValueError('Binary wheel only')
            request = urllib.request.Request(url, method='HEAD')
            with urllib.request.urlopen(request, timeout=min(30, remaining())) as response:
                sizes.append(int(response.headers['Content-Length']))
        receipt['resolver_reserved_bytes'] = receipt.get('previous_resolver_body_bytes_retained',0)+sum(sizes)
        if receipt['download_body_bytes']+2*sum(sizes)+cfg['weight_bytes']+(1 << 30) > cfg['limits']['download_bytes']:
            raise RuntimeError('Resolved dependency+weight plan exceeds download budget')
        write(receipt_path, receipt)
        for item in plan:
            info = item['download_info']; url = info['url']; filename = url.rsplit('/', 1)[-1].split('?', 1)[0]
            saved = cache/filename
            if not (wheels/filename).exists() and saved.exists() and sha(saved) == info['archive_info']['hashes']['sha256']:
                os.link(saved, wheels/filename)
            download(url, wheels/filename, info['archive_info']['hashes']['sha256'])
        command([python, '-m', 'pip', 'install', '--no-index', '--no-deps', '--disable-pip-version-check',
                 *[str(path) for path in sorted(wheels.glob('*.whl'))]], root/'pip_install.log', remaining(), env)
        command([python, '-m', 'pip', 'check'], root/'pip_check.log', remaining(), env)
        # Import the exact shape implementation on CPU before downloading large weights.
        cpu_env = dict(env, PYTHONPATH=str(source), CUDA_VISIBLE_DEVICES='', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        command([python, '-c', 'from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline; print("SHAPE_IMPORT_OK")'],
                root/'shape_import.log', remaining(), cpu_env)
        weight_dir = root/'weights'/cfg['weight_subfolder']; weight_dir.mkdir(parents=True)
        model_url = 'https://huggingface.co/'+cfg['weight_repo']+'/resolve/'+cfg['weight_revision']+'/'+cfg['weight_subfolder']+'/'
        download(model_url+'config.yaml', weight_dir/'config.yaml')
        url_file = code_root/'weight_download_url.txt'
        url = url_file.read_text().strip() if url_file.exists() else model_url+cfg['weight_file']
        download(url, weight_dir/cfg['weight_file'], cfg['weight_sha256'])
        if (weight_dir/cfg['weight_file']).stat().st_size != cfg['weight_bytes']: raise ValueError('Checkpoint size changed')
        receipt['status'] = 'ready'
    except Exception as error:
        receipt.update(status='blocked', error=repr(error), traceback=traceback.format_exc())
    finally:
        if resume and (root/'setup_resume.json').exists():
            old = json.loads((root/'setup_resume.json').read_text()); proc = Path('/proc')/str(old['resolver_pid'])
            if proc.exists() and (proc/'cmdline').read_bytes().decode().replace('\0',' ').strip() == old['resolver_cmdline']:
                os.killpg(old['resolver_pid'], signal.SIGTERM)
        receipt['wall_seconds'] = time.monotonic()-started
        receipt['download_conservative_upper_bound_bytes'] = receipt['download_body_bytes']+receipt['resolver_reserved_bytes']+(1 << 30)
        write(receipt_path, receipt)
    return receipt


def infer(cfg, root, code_root, protocol_sha):
    started = time.monotonic()
    receipt = {'status': 'started', 'protocol_sha256': protocol_sha, 'script_sha256': sha(__file__),
               'expected_objects': 4, 'objects': [{'id': name, 'status': 'not_run', 'attempts': 0} for name in cfg['expected_objects']]}
    target = root/'inference_receipt.json'; write(target, receipt)
    try:
        receipt['gpu_preflight'] = gpu_check(cfg['gpu_selection'])
        if os.environ.get('CUDA_VISIBLE_DEVICES') != cfg['gpu_selection']['uuid']:
            raise ValueError('Wrong CUDA visibility')
        sys.path.insert(0, str(code_root/'source'))
        import numpy as np
        import torch
        from PIL import Image
        from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
        torch.set_num_threads(2); torch.manual_seed(2026); np.random.seed(2026)
        receipt['runtime'] = {'torch': torch.__version__, 'numpy': np.__version__, 'cuda': torch.version.cuda}
        checkpoint = root/'weights'/cfg['weight_subfolder']/cfg['weight_file']
        if sha(checkpoint) != cfg['weight_sha256']: raise ValueError('Weights changed after setup')
        pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(str(root/'weights'), subfolder=cfg['weight_subfolder'],
                                                                   device='cuda', dtype=torch.float16, use_safetensors=True, variant='fp16')
        receipt['checkpoint_loaded'] = True
        inputs = json.loads((root/'inputs/manifest.json').read_text())['objects']
        for item, row in zip(inputs, receipt['objects']):
            if item['id'] != row['id']: raise ValueError('Object identity changed')
            row['gpu_preflight'] = gpu_check(cfg['gpu_selection'], os.getpid())
            if time.monotonic()-started >= cfg['limits']['gpu_process_wall_seconds']: raise TimeoutError('GPU process budget')
            if sha(item['rgba_path']) != item['rgba_sha256']: raise ValueError('RGBA input changed')
            directory = root/'objects'/row['id']; directory.mkdir(parents=True)
            row.update(status='running', attempts=1, rgba_sha256=item['rgba_sha256']); write(target, receipt)
            forward = time.monotonic()
            try:
                torch.manual_seed(2026); np.random.seed(2026); torch.cuda.reset_peak_memory_stats()
                generator = torch.Generator(device='cuda').manual_seed(2026)
                with Image.open(item['rgba_path']) as image:
                    image.load()
                    torch.cuda.synchronize()
                    outputs = pipeline(image=image, num_inference_steps=30, octree_resolution=256,
                                       guidance_scale=5.0, generator=generator, mc_algo='mc', num_chunks=8000)
                torch.cuda.synchronize(); row['forward_wall_seconds'] = time.monotonic()-forward
                if len(outputs) != 1 or outputs[0] is None: raise ValueError('No mesh returned')
                mesh = outputs[0]
                if not len(mesh.vertices) or not len(mesh.faces) or not np.isfinite(mesh.vertices).all():
                    raise ValueError('Empty or nonfinite mesh')
                mesh.export(directory/'shape.ply'); mesh.export(directory/'shape.glb')
                row.update(status='generated', vertices=len(mesh.vertices), faces=len(mesh.faces),
                           watertight=bool(mesh.is_watertight), volume=float(mesh.volume),
                           bounds=mesh.bounds.tolist(), peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                           output_sha256={name:sha(directory/name) for name in ('shape.ply','shape.glb')})
                del mesh, outputs; torch.cuda.empty_cache()
            except Exception as error:
                row.update(status='failed', error=repr(error), wall_seconds=time.monotonic()-forward)
                write(target, receipt)
                if isinstance(error, (ImportError, NotImplementedError, TypeError, torch.cuda.OutOfMemoryError)):
                    raise RuntimeError('Unsupported runtime; no retry or later invocation') from error
            write(target, receipt)
        receipt['status'] = 'completed' if all(row['status']=='generated' for row in receipt['objects']) else 'incomplete'
    except Exception as error:
        receipt.update(status='blocked', error=repr(error), traceback=traceback.format_exc())
    finally:
        receipt['gpu_process_wall_seconds'] = time.monotonic()-started
        receipt['source_unchanged'] = sha(cfg['source_image']) == cfg['source_sha256']
        receipt['scope'] = 'Four shape-only object attempts, no GT/layout/metric-scale/texture recovery claim, no postprocessing or best-of selection.'
        write(target, receipt)
    print(json.dumps({'status': receipt['status'], 'objects': [{'id':row['id'],'status':row['status']} for row in receipt['objects']]}), flush=True)
    return receipt['status'] == 'completed'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('protocol', 'phase', 'annotations'): parser.add_argument('--'+key, type=Path, required=True)
    parser.add_argument('--mode', choices=('all', 'infer', 'resume-setup', 'resume-weights'), default='all')
    args = parser.parse_args(); cfg = json.loads(args.protocol.read_text())
    if sha(args.phase) != cfg['parent_protocol_sha256'] or sha(args.annotations) != cfg['annotation_sha256']:
        raise ValueError('Parent phase or input annotations changed')
    if sha(cfg['source_image']) != cfg['source_sha256']: raise ValueError('Source bytes changed')
    root = Path(cfg['environment']['data_root']); code_root = Path(cfg['environment']['code_root'])
    if args.mode == 'infer': return 0 if infer(cfg, root, code_root, sha(args.protocol)) else 1
    receipt_path = root/'receipt.json'
    resume = args.mode in ('resume-setup', 'resume-weights')
    if receipt_path.exists() and not resume: raise ValueError('One attempt only; retain earlier receipt')
    start = time.monotonic()-(time.time()-json.loads((root/'launch.json').read_text())['start_time_unix'] if resume else 0)
    receipt = json.loads(receipt_path.read_text()) if resume else {'schema':'real2sim.desk1-hunyuan2/1', 'status':'preparing', 'protocol_sha256':sha(args.protocol),
               'parent_protocol_sha256':sha(args.phase), 'annotation_sha256':sha(args.annotations), 'runner_sha256':sha(__file__),
               'expected_objects':4, 'objects':[{'id':name,'status':'not_run','attempts':0} for name in cfg['expected_objects']],
               'gpu_process_wall_seconds':0, 'paid_api_requests':0}
    if resume:
        if receipt.get('error'): receipt.setdefault('previous_errors', []).append(receipt.pop('error'))
        receipt['status'] = 'preparing'
        if receipt.get('setup_revision'): receipt.setdefault('previous_setup_revisions', []).append(receipt['setup_revision'])
        receipt['setup_revision'] = {'previous_runner_sha256':receipt['runner_sha256'], 'runner_sha256':sha(__file__),
                                    'reason':args.mode+'; unchanged original setup deadline, cumulative download charges and inference configuration'}
    write(receipt_path, receipt)
    base_site = Path(cfg['environment']['readonly_base_site'])
    def base_metadata():
        return {str(path.relative_to(base_site)): sha(path) for pattern in ('*.dist-info/METADATA', '*.dist-info/RECORD')
                for path in base_site.glob(pattern)}
    unchanged_base = base_metadata()
    if resume and receipt.get('base_environment_metadata_before') != hashlib.sha256(json.dumps(unchanged_base, sort_keys=True).encode()).hexdigest():
        raise RuntimeError('Original Pi3X metadata changed before setup-only continuation')
    receipt['base_environment_metadata_before'] = hashlib.sha256(json.dumps(unchanged_base, sort_keys=True).encode()).hexdigest()
    env = dict(os.environ, OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2', TOKENIZERS_PARALLELISM='false',
               PYTHONDONTWRITEBYTECODE='1',
               CUDA_VISIBLE_DEVICES='', HF_HUB_DISABLE_IMPLICIT_TOKEN='1', PIP_NO_CACHE_DIR='1', TMPDIR=str(root/'tmp'))
    (root/'tmp').mkdir(exist_ok=True)
    try:
        if resume:
            receipt['input_masks'] = json.loads((root/'inputs/manifest.json').read_text())['objects']
            if any(sha(item['rgba_path'])!=item['rgba_sha256'] for item in receipt['input_masks']): raise ValueError('Original RGBA inputs changed')
        else: receipt['input_masks'] = make_inputs(cfg, json.loads(args.annotations.read_text()), root)
        write(receipt_path, receipt)
        preparation = setup(cfg, root, code_root, env, 'weights' if args.mode=='resume-weights' else resume); receipt['setup_receipt_sha256'] = sha(root/'setup_receipt.json')
        if preparation['status'] != 'ready': raise RuntimeError('Setup blocked; '+preparation.get('error', 'unknown'))
        receipt['gpu_preflight'] = gpu_check(cfg['gpu_selection'])
        write(receipt_path, receipt)
        gpu_env = dict(env, CUDA_VISIBLE_DEVICES=cfg['gpu_selection']['uuid'], HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        argv = [str(root/'venv/bin/python'), str(Path(__file__).resolve()), '--mode', 'infer',
                '--protocol',str(args.protocol.resolve()),'--phase',str(args.phase.resolve()),'--annotations',str(args.annotations.resolve())]
        gpu_start = time.monotonic()
        try: command(argv, root/'inference.log', cfg['limits']['gpu_process_wall_seconds'], gpu_env)
        finally: receipt['gpu_process_wall_seconds'] = time.monotonic()-gpu_start
        receipt['status'] = 'completed'
    except Exception as error:
        receipt.update(status='blocked', error=repr(error))
    finally:
        if (root/'inference_receipt.json').exists():
            inference = json.loads((root/'inference_receipt.json').read_text()); receipt['objects'] = inference['objects']
            receipt['inference_receipt_sha256'] = sha(root/'inference_receipt.json')
        receipt['source_unchanged'] = sha(cfg['source_image']) == cfg['source_sha256']
        receipt['base_environment_metadata_unchanged'] = base_metadata() == unchanged_base
        if not receipt['base_environment_metadata_unchanged']: receipt['status'] = 'blocked'
        receipt['wall_seconds'] = time.monotonic()-start; write(receipt_path, receipt)
    print(json.dumps({'status':receipt['status'],'error':receipt.get('error'),'wall_seconds':receipt['wall_seconds']}), flush=True)
    return 0 if receipt['status']=='completed' else 1


if __name__ == '__main__':
    sys.exit(main())
