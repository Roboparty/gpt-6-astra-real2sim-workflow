"""Freeze existing server-side videos by decoded presentation timestamps, never by FPS.

Run on the server holding source receipt paths:
  python tools/freeze_video_frames.py --source-receipt /remote/video_sources.json --output /remote/new-frame-freeze

No network/download operation exists. Every declared source retains a success or
failure row. This selects development images, not heldout evidence or a benchmark.
"""
import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import time


DEFAULT_POSITIONS = ('0', '0.2', '0.4', '0.6', '0.8', '1')


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            result.update(block)
    return result.hexdigest()


def decimal_fraction(value):
    if isinstance(value, bool) or value is None:
        raise ValueError('Timestamp/position must be a finite decimal number')
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('Timestamp/position is not decimal: ' + str(value)) from exc
    if not decimal.is_finite():
        raise ValueError('Timestamp/position must be finite')
    return Fraction(decimal)


def seconds(value):
    with localcontext() as context:
        context.prec = 50
        return str(Decimal(value.numerator) / Decimal(value.denominator))


def select_frames(timestamps, positions=DEFAULT_POSITIONS):
    """Exact rational arithmetic on ffprobe decimal PTS; never sort or repair inputs."""
    pts = [decimal_fraction(value) for value in timestamps]
    fractions = [decimal_fraction(value) for value in positions]
    if len(fractions) < 2 or fractions[0] != 0 or fractions[-1] != 1:
        raise ValueError('Positions must contain both endpoints, starting at 0 and ending at 1')
    if any(a >= b for a, b in zip(fractions, fractions[1:])):
        raise ValueError('Positions must be strictly increasing without duplicates')
    if len(pts) < len(fractions):
        raise ValueError('Clip is too short for the declared unique frame count')
    if any(a >= b for a, b in zip(pts, pts[1:])):
        raise ValueError('Decoded timestamps must be strictly increasing; duplicate or out-of-order PTS')
    selected = []
    for fraction in fractions:
        target = pts[0] + fraction * (pts[-1] - pts[0])
        index = min(range(len(pts)), key=lambda i: (abs(pts[i] - target), i))
        selected.append({'position_fraction': seconds(fraction), 'decoded_frame_index': index,
                         'target_timestamp_seconds': seconds(target),
                         'target_timestamp_exact': [str(target.numerator), str(target.denominator)],
                         'best_effort_timestamp_time': str(timestamps[index]),
                         'distance_to_target_seconds': seconds(abs(pts[index] - target))})
    if len({row['decoded_frame_index'] for row in selected}) != len(fractions):
        raise ValueError('Nearest-frame selection repeats a frame; no replacement or resampling allowed')
    return selected


def parse_probe(probe, expected_count=None):
    streams = probe.get('streams', [])
    if len(streams) != 1:
        raise ValueError('ffprobe must return exactly the selected v:0 stream')
    stream = streams[0]
    width, height = stream['width'], stream['height']
    if any(type(value) is not int or value <= 0 for value in (width, height)):
        raise ValueError('Invalid coded video dimensions')
    frames = probe.get('frames', [])
    if not frames:
        raise ValueError('ffprobe returned no decoded frames')
    if expected_count is not None and len(frames) != int(expected_count):
        raise ValueError('Decoded frame count differs from the source acquisition receipt')
    timestamps = []
    for index, frame in enumerate(frames):
        if frame.get('width') != width or frame.get('height') != height:
            raise ValueError('Frame dimensions change within the video at index ' + str(index))
        if 'best_effort_timestamp_time' not in frame:
            raise ValueError('Missing presentation timestamp at decoded index ' + str(index))
        timestamps.append(frame['best_effort_timestamp_time'])
    return timestamps, stream


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')


def run_recorded(argv, directory, name, timeout_seconds):
    command = {'argv': argv, 'timeout_seconds': timeout_seconds}
    write_json(directory / (name + '-command.json'), command)
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired as exc:
        for suffix, content in (('stdout', exc.stdout), ('stderr', exc.stderr)):
            if isinstance(content, bytes):
                content = content.decode('utf-8', errors='replace')
            (directory / (name + '.' + suffix)).write_text(content or '', encoding='utf-8')
        raise ValueError(name + ' timed out; partial outputs retained') from exc
    (directory / (name + '.stdout')).write_text(result.stdout, encoding='utf-8')
    (directory / (name + '.stderr')).write_text(result.stderr, encoding='utf-8')
    if result.returncode != 0:
        raise ValueError(name + ' failed, exit ' + str(result.returncode))
    # Both media commands use error-only logging. Do not accept concealed decode errors.
    if name in ('probe', 'extract') and result.stderr.strip():
        raise ValueError(name + ' reported decoding/processing errors despite a zero exit code')
    return result.stdout


def png_size(path):
    with path.open('rb') as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != b'\x89PNG\r\n\x1a\n' or header[12:16] != b'IHDR':
        raise ValueError('Invalid PNG header: ' + str(path))
    return list(struct.unpack('>II', header[16:24]))


def freeze_source(source, output, positions, ffprobe, ffmpeg, timeout_seconds):
    row = {'id': source.get('id'), 'source_path': source.get('path'),
           'expected_source_sha256': source.get('source_sha256'),
           'expected_frame_count': len(positions),
           'status': 'failed', 'selected_frames': [], 'error': None}
    started = time.monotonic()
    try:
        if source.get('status') != 'verified':
            raise ValueError('Source was not verified in the acquisition receipt')
        path = Path(source['path'])
        if not path.is_absolute():
            raise ValueError('Source path must be absolute on the acquisition server')
        row['source_sha256_before'] = sha256(path)
        if row['source_sha256_before'] != source['source_sha256']:
            raise ValueError('Source hash differs from acquisition receipt')
        row['source_bytes'] = path.stat().st_size
        if 'actual_bytes' in source and row['source_bytes'] != source['actual_bytes']:
            raise ValueError('Source byte size differs from acquisition receipt')
        probe_text = run_recorded([ffprobe, '-v', 'error', '-err_detect', 'explode',
            '-select_streams', 'v:0', '-show_frames', '-show_streams', '-show_entries',
            'frame=best_effort_timestamp_time,width,height:stream=index,codec_name,width,height,nb_frames,sample_aspect_ratio',
            '-of', 'json', str(path)], output, 'probe', timeout_seconds)
        row['probe_sha256'] = sha256(output / 'probe.stdout')
        timestamps, stream = parse_probe(json.loads(probe_text), source.get('video', {}).get('nb_read_frames'))
        row['video'] = stream
        row['decoded_frame_count'] = len(timestamps)
        selected = select_frames(timestamps, positions)
        row['first_timestamp_time'] = str(timestamps[0])
        row['last_timestamp_time'] = str(timestamps[-1])
        row['pts_span_seconds'] = seconds(decimal_fraction(timestamps[-1]) - decimal_fraction(timestamps[0]))
        row['selection'] = selected
        timing = {'decoded_frame_count': len(timestamps), 'order': 'ffprobe decoded presentation order; unmodified',
                  'best_effort_timestamp_time': timestamps, 'selection': selected}
        write_json(output / 'timing.json', timing)
        row['timing_sha256'] = sha256(output / 'timing.json')
        expression = '+'.join('eq(n\\,' + str(frame['decoded_frame_index']) + ')' for frame in selected)
        run_recorded([ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-xerror',
            '-err_detect', 'explode', '-noautorotate', '-i', str(path), '-map', '0:v:0',
            '-vf', 'select=' + expression, '-vsync', '0', '-c:v', 'png', '-threads', '1',
            '-start_number', '0', '-n', str(output / 'frame_%06d.png')], output, 'extract', timeout_seconds)
        files = sorted(output.glob('frame_*.png'))
        if len(files) != len(selected):
            raise ValueError('Extracted PNG count differs from frozen selection')
        for ordinal, selection in enumerate(selected):
            frame_path = output / f'frame_{ordinal:06d}.png'
            dimensions = png_size(frame_path)
            if dimensions != [stream['width'], stream['height']]:
                raise ValueError('PNG does not preserve the source coded pixel dimensions')
            row['selected_frames'].append({**selection, 'path': str(frame_path.resolve()),
                                           'sha256': sha256(frame_path), 'bytes': frame_path.stat().st_size,
                                           'image_size': dimensions})
        row['source_sha256_after'] = sha256(path)
        if row['source_sha256_after'] != row['source_sha256_before']:
            raise ValueError('Source changed during frame freezing')
        row['status'] = 'frozen'
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        row['error'] = str(exc)
    row['wall_seconds'] = time.monotonic() - started
    write_json(output / 'source-result.json', row)
    return row


def freeze_receipt(receipt_path, output, positions=DEFAULT_POSITIONS, ffprobe='ffprobe', ffmpeg='ffmpeg', timeout_seconds=300):
    """A new output directory is required; all input/source failures produce freeze.json."""
    receipt_path, output = Path(receipt_path).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    report = {'schema': 'real2sim.video-frame-freeze/1', 'status': 'failed',
              'source_receipt_path': str(receipt_path), 'sources': [], 'errors': [],
              'method': {'timestamp': 'best_effort_timestamp_time of every decoded v:0 frame',
                         'positions': [str(value) for value in positions],
                         'target': 'first_PTS + position * (last_PTS - first_PTS)',
                         'nearest': 'exact decimal-to-rational distance; ties choose smaller decoded index',
                         'duplicate_selection': 'fail; no replacement, sorting or resampling',
                         'raster': 'coded width/height, no resize, no autorotate; ffmpeg PNG conversion',
                         'source_docs': ['https://ffmpeg.org/ffprobe.html', 'https://ffmpeg.org/ffmpeg-filters.html#select_002c-aselect']},
              'gpu_hours': 0, 'paid_api_requests': 0,
              'scope': 'Development source frame freezing only; no reconstruction or benchmark result'}
    receipt = {}
    try:
        report['source_receipt_sha256'] = sha256(receipt_path)
        receipt = json.loads(receipt_path.read_text(encoding='utf-8-sig'))
        if not isinstance(receipt, dict):
            raise ValueError('Source receipt must be a JSON object')
        sources = receipt['sources']
        if not isinstance(sources, list) or any(not isinstance(source, dict) for source in sources):
            raise ValueError('Receipt sources must be a list of source objects')
        expected = receipt['expected_scene_count']
        report.update(cohort_id=receipt.get('cohort_id'), cohort_sha256=receipt.get('cohort_sha256'),
                      expected_scene_count=expected)
        if receipt.get('schema') != 'real2sim.source-acquisition/1':
            raise ValueError('Unsupported source acquisition receipt')
        if type(expected) is not int or expected <= 0 or expected != len(sources):
            raise ValueError('Receipt source count differs from the declared denominator')
        ids = [source.get('id') for source in sources]
        if any(not isinstance(key, str) or not key for key in ids) or len(Counter(ids)) != expected:
            raise ValueError('Receipt source IDs must be unique and nonempty')
        # Validate positions even if every actual source is missing.
        select_frames([str(value) for value in positions], positions)
        if timeout_seconds <= 0:
            raise ValueError('Timeout must be positive')
        report['tools'] = {name: run_recorded([binary, '-version'], output, name + '-version', timeout_seconds).splitlines()[0]
                           for name, binary in (('ffprobe', ffprobe), ('ffmpeg', ffmpeg))}
        for index, source in enumerate(sources):
            directory = output / f'source_{index:03d}'
            directory.mkdir()
            report['sources'].append(freeze_source(source, directory, positions, ffprobe, ffmpeg, timeout_seconds))
        if sha256(receipt_path) != report['source_receipt_sha256']:
            raise ValueError('Acquisition receipt changed during freezing')
    except (OSError, ValueError, KeyError, TypeError, IndexError, OverflowError) as exc:
        report['errors'].append(str(exc))
        sources = receipt.get('sources', []) if isinstance(receipt, dict) else []
        if not isinstance(sources, list):
            sources = []
        expected = report.get('expected_scene_count')
        if not isinstance(expected, int) or expected <= 0:
            expected = len(sources)
        # A malformed/missing row cannot shrink the declared cohort or invent a replacement clip.
        for index in range(len(report['sources']), expected):
            source = sources[index] if index < len(sources) else {}
            if not isinstance(source, dict):
                source = {}
            report['sources'].append({'id': source.get('id'), 'source_path': source.get('path'),
                                      'expected_frame_count': len(positions),
                                      'status': 'failed', 'selected_frames': [], 'error': str(exc)})
        if len(sources) > expected:
            report['unexpected_receipt_sources'] = sources[expected:]
        for source in report['sources']:
            if source['status'] == 'frozen':
                source.update(status='failed', extraction_status='completed_before_global_failure', error=str(exc))
    frozen = sum(source['status'] == 'frozen' for source in report['sources'])
    expected = report.get('expected_scene_count', len(report['sources']))
    if type(expected) is not int or expected < 0:
        expected = len(report['sources'])
    report.update(frozen_scene_count=frozen, failed_scene_count=expected-frozen,
                  expected_selected_frame_count=expected*len(positions),
                  selected_frame_count=sum(len(source['selected_frames']) for source in report['sources']),
                  frozen_frame_count=sum(len(source['selected_frames']) for source in report['sources'] if source['status'] == 'frozen'),
                  wall_seconds=time.monotonic()-started)
    if not report['errors'] and frozen == expected and expected > 0:
        report['status'] = 'frozen'
    write_json(output / 'freeze.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-receipt', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='New server-side output directory; never overwritten')
    parser.add_argument('--positions', nargs='+', default=DEFAULT_POSITIONS)
    parser.add_argument('--ffprobe', default='ffprobe')
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--timeout-seconds', type=int, default=300)
    args = parser.parse_args()
    report = freeze_receipt(args.source_receipt, args.output, args.positions, args.ffprobe, args.ffmpeg, args.timeout_seconds)
    print(json.dumps({key: report.get(key) for key in ('status', 'expected_scene_count', 'frozen_scene_count', 'failed_scene_count', 'selected_frame_count')}))
    return 0 if report['status'] == 'frozen' else 1


if __name__ == '__main__':
    raise SystemExit(main())
