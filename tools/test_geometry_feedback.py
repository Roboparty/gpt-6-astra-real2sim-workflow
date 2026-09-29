"""Synthetic geometric perturbations: an analytic oracle, not real-scene qualification."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'workflow'))
from r2s.contracts import digest
from r2s.geometry_feedback import evaluate_geometry_feedback, file_sha256


def run(root):
    root.mkdir(parents=True, exist_ok=True)

    def record(path):
        return {'path': path.name, 'sha256': file_sha256(path)}

    def save_image(name, array):
        path = root / name
        Image.fromarray(array).save(path)
        return record(path)

    def save_json(name, value):
        path = root / name
        path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
        return path

    camera = {'image_size': [64, 64], 'rotation_world_to_cv': np.eye(3).tolist(),
              'position': [0, 0, 0], 'focal_px': 40., 'principal_point': [32., 32.]}
    source = np.zeros((64, 64), np.uint8)
    source[20:44, 20:44] = 255
    mask = save_image('source-mask.png', source)
    image = save_image('fit-source.png', np.full((64, 64, 3), 64, np.uint8))
    heldout_image = save_image('heldout-source.png', np.full((64, 64, 3), 96, np.uint8))
    obj = {'id': 'box', 'mask': mask, 'landmarks': [{'id': 'center', 'uv': [32, 32]}]}
    protocol = {'schema': 'real2sim.geometry-feedback-protocol/1.0',
                'thresholds': {'minimum_iou': .9, 'maximum_boundary_mean_px': 1., 'maximum_landmark_error_px': 1.},
                'views': [{'id': 'fit', 'role': 'fit', 'source': image, 'camera': camera, 'objects': [obj]},
                          {'id': 'heldout', 'role': 'heldout', 'source': heldout_image, 'camera': camera, 'objects': [obj]}]}
    model = save_json('model.json', {'note': 'Analytic synthetic test geometry; no external photograph'})
    candidate = {'schema': 'real2sim.geometry-feedback-candidate/1.0', 'protocol_sha256': digest(protocol),
                 'model': record(model), 'reconstruction_source_sha256': [image['sha256']],
                 'views': [{'id': name, 'camera': camera, 'render': image,
                            'objects': [{'id': 'box', 'mask': mask, 'landmarks': [{'id': 'center', 'xyz': [0, 0, 2]}]}]}
                           for name in ('fit', 'heldout')]}
    reports = {}

    def evaluate(name, value, passed=False, spec=None):
        report = evaluate_geometry_feedback(spec or protocol, value, root, root, root / (name + '_overlays'))
        assert (report['status'] == 'passed') == passed, (name, report)
        assert report['summary']['expected_objects'] == 2
        assert report['summary']['expected_masks'] == 2
        assert report['summary']['expected_landmarks'] == 2
        assert report['by_role']['heldout']['expected_objects'] == 1
        save_json(name + '-candidate.json', value)
        save_json(name + '-report.json', report)
        reports[name] = report
        return report

    exact = evaluate('identity', candidate, passed=True)
    assert exact['summary']['mean_iou_with_failures'] == 1
    assert exact['summary']['mean_boundary_px_with_failures'] == 0
    assert exact['summary']['mean_landmark_error_px_with_failures'] == 0

    translated = np.zeros_like(source)
    translated[20:44, 26:50] = 255
    altered = copy.deepcopy(candidate)
    altered['views'][1]['objects'][0]['mask'] = save_image('translated-mask.png', translated)
    altered['views'][1]['objects'][0]['landmarks'][0]['xyz'] = [.3, 0, 2]
    translated_report = evaluate('translation_6px', altered)
    score = translated_report['results'][1]['mask']
    # Intersection 18*24, union 30*24. This expected value is independent of the evaluator.
    assert abs(score['iou'] - .6) < 1e-12
    assert score['centroid_delta_xy_px'] == [6., 0.]
    assert translated_report['results'][1]['landmarks'][0]['error_px'] == 6
    assert translated_report['by_role']['fit']['pass_rate'] == 1
    assert translated_report['by_role']['heldout']['pass_rate'] == 0

    enlarged = np.zeros_like(source)
    enlarged[8:56, 8:56] = 255
    altered = copy.deepcopy(candidate)
    altered['views'][1]['objects'][0]['mask'] = save_image('enlarged-mask.png', enlarged)
    scaled_report = evaluate('scale_2x', altered)
    assert scaled_report['results'][1]['mask']['iou'] == .25
    assert scaled_report['results'][1]['mask']['bbox_scale_xy'] == [2., 2.]

    altered = copy.deepcopy(candidate)
    altered['views'][1]['objects'] = []
    missing_report = evaluate('missing_object', altered)
    assert missing_report['summary']['mean_iou_with_failures'] == .5
    assert missing_report['summary']['failed_objects'] == 1
    assert missing_report['summary']['failed_landmarks'] == 1

    altered = copy.deepcopy(candidate)
    altered['views'] = altered['views'][:1]
    evaluate('missing_view', altered)
    altered = copy.deepcopy(candidate)
    altered['views'][1]['objects'][0]['mask']['path'] = 'nonexistent.png'
    evaluate('unreadable_mask', altered)
    altered = copy.deepcopy(candidate)
    altered['views'][1]['camera']['focal_px'] = 50
    evaluate('camera_drift', altered)
    altered = copy.deepcopy(candidate)
    altered['views'][1]['objects'][0]['mask']['sha256'] = '0' * 64
    evaluate('stale_artifact', altered)
    altered = copy.deepcopy(candidate)
    altered['views'][1]['objects'][0]['landmarks'][0]['xyz'] = [0, 0, -2]
    evaluate('behind_camera', altered)
    altered = copy.deepcopy(candidate)
    altered['views'][1]['objects'][0]['landmarks'][0]['xyz'] = [1e308, 0, 1e-300]
    evaluate('projection_overflow', altered)
    altered = copy.deepcopy(candidate)
    altered['reconstruction_source_sha256'].append(heldout_image['sha256'])
    assert evaluate('heldout_leakage', altered)['summary']['failed_objects'] == 2
    altered = copy.deepcopy(candidate)
    altered['protocol_sha256'] = '0' * 64
    assert evaluate('changed_protocol', altered)['summary']['failed_objects'] == 2
    altered = copy.deepcopy(candidate)
    altered['views'][1]['objects'][0]['mask'] = save_image('empty-mask.png', np.zeros_like(source))
    evaluate('blank_render', altered)

    palette_candidate = copy.deepcopy(candidate)
    id_pixels = np.zeros((64, 64, 3), np.uint8)
    id_pixels[source > 0] = [17, 61, 149]
    id_record = save_image('id-render.png', id_pixels)
    for view in palette_candidate['views']:
        view['id_image'] = id_record
        view['palette'] = {'box': [17, 61, 149]}
        del view['objects'][0]['mask']
    evaluate('id_palette', palette_candidate, passed=True)
    extra_palette = copy.deepcopy(palette_candidate)
    for view in extra_palette['views']:
        view['palette']['unscored_occluder'] = [51, 52, 53]
    palette_report = evaluate('full_scene_palette', extra_palette, passed=True)
    assert palette_report['results'][0]['unscored_palette_entities'] == ['unscored_occluder']
    altered = copy.deepcopy(palette_candidate)
    altered['views'][1]['palette'] = {'box': [18, 61, 149]}
    evaluate('wrong_palette', altered)

    leaked_protocol = copy.deepcopy(protocol)
    leaked_protocol['views'][1]['source'] = image
    try:
        evaluate_geometry_feedback(leaked_protocol, candidate, root, root)
    except ValueError as exc:
        assert 'both fit and heldout' in str(exc)
    else:
        raise AssertionError('Duplicated fit image was accepted as heldout')

    protocol_path = save_json('protocol.json', protocol)
    candidate_path = save_json('candidate.json', candidate)
    cli = [sys.executable, str(Path(__file__).with_name('evaluate_geometry_feedback.py')),
           '--protocol', str(protocol_path), '--candidate', str(candidate_path),
           '--expected-protocol-sha256', digest(protocol), '--output', str(root / 'cli-report.json')]
    assert subprocess.run(cli, capture_output=True, text=True).returncode == 0
    cli[cli.index('--expected-protocol-sha256') + 1] = '0' * 64
    assert subprocess.run(cli, capture_output=True, text=True).returncode == 2
    evidence = {'status': 'passed', 'case_count': len(reports), 'protocol_sha256': digest(protocol),
                'cases': {name: {'status': report['status'], 'summary': report['summary']} for name, report in reports.items()},
                'interpretation': 'Software sensitivity/regression evidence only; no real scene or SOTA claim.'}
    save_json('synthetic-suite.json', evidence)
    print(json.dumps({'status': 'passed', 'case_count': len(reports), 'evidence_directory': str(root)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    if args.output_dir:
        run(args.output_dir.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix='real2sim-geometry-') as temp:
            run(Path(temp))
