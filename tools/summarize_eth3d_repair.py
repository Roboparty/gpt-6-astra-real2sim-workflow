"""Score frozen repair ablations on the unchanged, previously exposed ETH3D test.

No model selection is performed. Missing/failed candidates remain explicit.
"""
import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

from prepare_eth3d_camera_benchmark import sha, save
from summarize_eth3d_evaluation import ssim


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--truth', type=Path, required=True)
    p.add_argument('--depth-code', type=Path, required=True)
    p.add_argument('--variants', nargs='+', required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        raise ValueError('Preserve earlier reports; use a new output path')
    spec = importlib.util.spec_from_file_location('depth_metrics', a.depth_code)
    metric = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(metric)
    truth = np.load(a.truth / 'truth_grid.npz')['depth']
    views = json.loads((a.truth / 'views.json').read_text())
    tree = cKDTree(np.load(a.truth / 'laser_points.npy', mmap_mode='r'))
    report = dict(scope='Previously exposed test diagnostic; not an independent new benchmark',
                  requested_variants=a.variants, truth_sha256=sha(a.truth / 'truth_grid.npz'),
                  depth_code_sha256=sha(a.depth_code), variants=[])
    for name in a.variants:
        directory = a.root / name
        if not (directory / 'receipt.json').exists():
            report['variants'].append(dict(id=name, status='incomplete'))
            continue
        receipt = json.loads((directory / 'receipt.json').read_text())
        assert receipt['status'] == 'complete' and receipt['model_unchanged']
        assert receipt['source_truth_grid_sha256'] == report['truth_sha256']
        pred = np.load(directory / 'rendered_z.npy')
        assert pred.shape == truth.shape
        rows = [dict(frame_id=v['frame_id'], split=v['role'], **metric.metrics(pred[i], truth[i]))
                for i, v in enumerate(views)]
        depth = {}
        for split in ['reconstruction', 'heldout']:
            group = [r for r in rows if r['split'] == split]
            depth[split] = dict(views=len(group), GT_valid_pixels=sum(r['pixels_domain'] for r in group))
            for key in ['absrel', 'rmse_m', 'valid_coverage', 'missing_penalty_mae_m', 'delta1']:
                values = [r[key] for r in group if r[key] is not None]
                depth[split][key] = float(np.mean(values)) if values else None
        forward = tree.query(np.load(directory / 'model_surface_samples.npy'), workers=2)[0]
        reverse = np.load(directory / 'gt_to_model_m.npy')
        assert len(forward) == len(reverse) == 100000
        assert np.isfinite(forward).all() and np.isfinite(reverse).all()
        geometry = dict(model_to_laser_mean_m=float(forward.mean()), laser_to_model_mean_m=float(reverse.mean()),
                        symmetric_mean_m=float((forward.mean() + reverse.mean()) / 2))
        for threshold in [.01, .05, .1]:
            precision, recall = float(np.mean(forward <= threshold)), float(np.mean(reverse <= threshold))
            tag = str(round(threshold * 100)) + 'cm'
            geometry['precision_' + tag], geometry['recall_' + tag] = precision, recall
            geometry['fscore_' + tag] = 2 * precision * recall / (precision + recall) if precision + recall else 0.
        appearance = []
        for row in json.loads((directory / 'render_manifest.json').read_text()):
            x = np.asarray(Image.open(row['source']).convert('RGB').resize(tuple(row['size']), Image.Resampling.LANCZOS))
            y = np.asarray(Image.open(row['render']).convert('RGB'))
            assert x.shape == y.shape and sha(row['render']) == row['render_sha256']
            mse = float(np.mean((x.astype(float) - y.astype(float)) ** 2))
            appearance.append(dict(**row, psnr_db=float(10 * np.log10(255 ** 2 / max(mse, 1e-12))), ssim=ssim(x, y)))
        assert len(appearance) == 13 and sum(r['split'] == 'heldout' for r in appearance) == 8
        means = {split: {key: float(np.mean([r[key] for r in appearance if r['split'] == split]))
                        for key in ['psnr_db', 'ssim']} for split in ['reconstruction', 'heldout']}
        report['variants'].append(dict(id=name, status='complete', receipt=receipt, depth=depth,
                                       depth_per_view=rows, geometry=geometry, appearance=appearance, appearance_means=means))
    report['status'] = 'complete' if all(r['status'] == 'complete' for r in report['variants']) else 'incomplete'
    save(a.out, report)
    print(json.dumps({'status': report['status'], 'variants': len(report['variants'])}))


if __name__ == '__main__':
    main()
