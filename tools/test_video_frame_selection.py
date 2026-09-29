"""Run deterministic timestamp tests; --integration also exercises local FFmpeg.

The optional integration makes a tiny synthetic video on the execution server.
It never downloads media and compares selected PNG pixels to independently fully
decoded RGB frames, checking that selection uses actual decoded indices.
"""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import tempfile

from freeze_video_frames import DEFAULT_POSITIONS, freeze_receipt, parse_probe, select_frames, sha256


def rejects(call, expected):
    try:
        call()
    except (ValueError, KeyError) as exc:
        assert expected in str(exc), str(exc)
    else:
        raise AssertionError('Invalid input unexpectedly accepted: ' + expected)


def logic_tests():
    # Nonzero origin and irregular PTS: targets are 5, 5.4, 5.8, 6.2, 6.6, 7.
    irregular = ['5', '5.2', '5.5', '5.9', '6.1', '6.45', '6.9', '7']
    selected = select_frames(irregular)
    assert [row['decoded_frame_index'] for row in selected] == [0, 2, 3, 4, 5, 7]
    assert [row['target_timestamp_seconds'] for row in selected] == ['5', '5.4', '5.8', '6.2', '6.6', '7']
    # 0.3 and 0.5 are exactly equidistant from 0.4 in decimal arithmetic.
    tie = select_frames(['0', '.3', '.5', '.8', '1'], ['0', '.4', '1'])
    assert tie[1]['decoded_frame_index'] == 1
    assert tie[1]['distance_to_target_seconds'] == '0.1'
    # Repeated calls must produce precisely the same mapping and serialized metadata.
    assert json.dumps(selected, sort_keys=True) == json.dumps(select_frames(irregular), sort_keys=True)
    assert [row['decoded_frame_index'] for row in select_frames(DEFAULT_POSITIONS)] == list(range(6))
    rejects(lambda: select_frames(['0', '.2', '.2', '.6', '.8', '1']), 'duplicate or out-of-order')
    rejects(lambda: select_frames(['0', '.4', '.2', '.6', '.8', '1']), 'duplicate or out-of-order')
    rejects(lambda: select_frames(['0', '.2', '.4', '.6', '.8']), 'too short')
    rejects(lambda: select_frames(['0', '.01', '.02', '.03', '.04', '10']), 'repeats a frame')
    for invalid in ('NaN', 'Infinity', '-Infinity', None, True):
        rejects(lambda invalid=invalid: select_frames(['0', '.2', invalid, '.6', '.8', '1']), 'finite')
    rejects(lambda: select_frames(['0', '.2', 'N/A', '.6', '.8', '1']), 'not decimal')
    rejects(lambda: select_frames(irregular, ['0', '.5', '.5', '1']), 'strictly increasing')
    rejects(lambda: select_frames(irregular, ['.1', '.5', '1']), 'both endpoints')
    rejects(lambda: select_frames(irregular, ['0', '.5', '1.1']), 'both endpoints')
    probe = {'streams': [{'width': 16, 'height': 12}], 'frames': [
        {'best_effort_timestamp_time': value, 'width': 16, 'height': 12} for value in irregular]}
    assert parse_probe(probe, 8)[0] == irregular
    rejects(lambda: parse_probe(probe, 7), 'frame count differs')
    malformed = copy.deepcopy(probe)
    del malformed['frames'][3]['best_effort_timestamp_time']
    rejects(lambda: parse_probe(malformed), 'Missing presentation timestamp')
    changed_size = copy.deepcopy(probe)
    changed_size['frames'][3]['width'] = 17
    rejects(lambda: parse_probe(changed_size), 'dimensions change')
    # Invalid positions fail before media tools execute, still keeping three failed rows.
    with tempfile.TemporaryDirectory(prefix='r2s-frame-logic-') as directory:
        root = Path(directory)
        receipt = {'schema': 'real2sim.source-acquisition/1', 'expected_scene_count': 3,
                   'sources': [{'id': str(i), 'status': 'verified', 'path': str(root / f'missing_{i}.mp4'),
                                'source_sha256': '0'*64} for i in range(3)]}
        path = root / 'receipt.json'
        path.write_text(json.dumps(receipt))
        failed = freeze_receipt(path, root / 'invalid-positions', positions=['0', '.5', '.5', '1'])
        assert failed['status'] == 'failed'
        assert failed['failed_scene_count'] == 3 and len(failed['sources']) == 3
        assert (root / 'invalid-positions/freeze.json').is_file()
        missing = freeze_receipt(path, root / 'missing-tools', ffprobe=str(root / 'no-such-ffprobe'))
        assert missing['failed_scene_count'] == 3 and len(missing['sources']) == 3
        receipt['sources'].pop()
        path.write_text(json.dumps(receipt))
        short_receipt = freeze_receipt(path, root / 'missing-receipt-row')
        assert short_receipt['failed_scene_count'] == 3 and len(short_receipt['sources']) == 3
        assert short_receipt['sources'][2]['id'] is None  # Never invent a replacement clip.
    print('VIDEO_FRAME_SELECTION_LOGIC_OK')


def integration_tests(root, ffmpeg, ffprobe):
    root.mkdir(parents=True, exist_ok=True)
    video = root / 'synthetic.mkv'
    # FFV1 avoids lossy encoding uncertainty; color/raster differences reveal wrong indices.
    subprocess.run([ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
                    '-i', 'testsrc=size=16x12:rate=10:duration=2', '-c:v', 'ffv1', '-threads', '1',
                    '-n', str(video)], check=True)
    source = {'status': 'verified', 'path': str(video.resolve()), 'source_sha256': sha256(video),
              'actual_bytes': video.stat().st_size, 'video': {'nb_read_frames': '20'}}
    receipt = {'schema': 'real2sim.source-acquisition/1', 'cohort_id': 'synthetic-three-sources',
               'expected_scene_count': 3, 'sources': [{**source, 'id': str(i)} for i in range(3)]}
    receipt_path = root / 'receipt.json'
    receipt_path.write_text(json.dumps(receipt))
    report = freeze_receipt(receipt_path, root / 'freeze-a', ffmpeg=ffmpeg, ffprobe=ffprobe)
    assert report['status'] == 'frozen', report
    assert report['frozen_scene_count'] == 3 and report['selected_frame_count'] == 18
    expected_indices = [0, 4, 8, 11, 15, 19]  # Span 0..1.9s, nearest to .38s increments.
    assert [row['decoded_frame_index'] for row in report['sources'][0]['selected_frames']] == expected_indices
    full = subprocess.run([ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-noautorotate',
                           '-i', str(video), '-map', '0:v:0', '-vsync', '0', '-f', 'rawvideo',
                           '-pix_fmt', 'rgb24', '-threads', '1', '-'], capture_output=True, check=True).stdout
    stride = 16 * 12 * 3
    assert len(full) == stride * 20
    for frame in report['sources'][0]['selected_frames']:
        rgb = subprocess.run([ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', frame['path'],
                              '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-threads', '1', '-'],
                             capture_output=True, check=True).stdout
        index = frame['decoded_frame_index']
        assert rgb == full[stride*index:stride*(index+1)], ('Wrong decoded pixels', index)
    second = freeze_receipt(receipt_path, root / 'freeze-b', ffmpeg=ffmpeg, ffprobe=ffprobe)
    hashes = lambda result: [[row['sha256'] for row in source['selected_frames']] for source in result['sources']]
    assert hashes(report) == hashes(second), 'Identical inputs produced different PNG bytes'
    receipt['sources'][1]['path'] = str(root / 'missing.mp4')
    receipt_path.write_text(json.dumps(receipt))
    missing = freeze_receipt(receipt_path, root / 'freeze-missing', ffmpeg=ffmpeg, ffprobe=ffprobe)
    assert missing['status'] == 'failed' and missing['failed_scene_count'] == 1
    assert missing['frozen_scene_count'] == 2 and len(missing['sources']) == 3
    assert missing['sources'][1]['id'] == '1' and missing['sources'][1]['selected_frames'] == []
    evidence = {'status': 'passed', 'expected_indices': expected_indices,
                'pixel_check': 'selected PNG decoded RGB equals independently fully decoded source RGB at frozen index',
                'repeat_png_hashes_identical': True, 'missing_source_retained_in_denominator': True,
                'synthetic_source_sha256': sha256(video)}
    (root / 'integration-result.json').write_text(json.dumps(evidence, indent=2))
    print('VIDEO_FRAME_SELECTION_INTEGRATION_OK', json.dumps(evidence))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--integration', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--ffprobe', default='ffprobe')
    args = parser.parse_args()
    logic_tests()
    if args.integration:
        if args.output_dir:
            integration_tests(args.output_dir.resolve(), args.ffmpeg, args.ffprobe)
        else:
            with tempfile.TemporaryDirectory(prefix='r2s-frame-integration-') as directory:
                integration_tests(Path(directory), args.ffmpeg, args.ffprobe)
