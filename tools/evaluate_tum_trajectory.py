"""Frozen-denominator, translation-only TUM trajectory evaluation (NumPy only).

Expected timestamps: JSON number list, {"timestamps": [...]}, or one number per
text line. TUM files have exactly timestamp tx ty tz qx qy qz qw per row.
Quaternions must be finite and nonzero; orientation is not scored. Nonunit
quaternions are accepted since their normalized rotation is well defined.
"""
import argparse
from bisect import bisect_left, bisect_right
import hashlib
import json
from pathlib import Path

import numpy as np

MAX_TIMESTAMP_DIFF_SECONDS = 0.02


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_trajectory(rows):
    values = np.asarray(rows, dtype=np.float64)
    if values.shape in ((0,), (0, 8)):
        return np.empty((0, 8), dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 8:
        raise ValueError('TUM trajectory must contain exactly eight columns')
    if not np.isfinite(values).all():
        raise ValueError('Nonfinite TUM value')
    if len(np.unique(values[:, 0])) != len(values):
        raise ValueError('Duplicate trajectory timestamp')
    if np.any(np.all(values[:, 4:] == 0, axis=1)):
        raise ValueError('Zero quaternion')
    return values[np.argsort(values[:, 0], kind='stable')]


def read_tum(path):
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(), 1):
        fields = line.split('#', 1)[0].split()
        if not fields:
            continue
        if len(fields) != 8:
            raise ValueError(f'{path}:{number}: expected eight TUM columns')
        rows.append([float(value) for value in fields])
    return validate_trajectory(rows)


def validate_expected(values):
    if not isinstance(values, (list, tuple, np.ndarray)) or any(isinstance(x, (bool, str)) for x in values):
        raise ValueError('Expected timestamps must be a numeric list')
    times = np.asarray(values, dtype=np.float64)
    if times.ndim != 1 or not len(times) or not np.isfinite(times).all():
        raise ValueError('Expected timestamps must be nonempty and finite')
    if np.any(np.diff(times) <= 0):
        raise ValueError('Frozen expected timestamps must be strictly increasing and unique')
    return times


def read_expected(path):
    text = Path(path).read_text(encoding='utf-8-sig')
    if text.lstrip().startswith(('[', '{')):
        data = json.loads(text)
        values = data['timestamps'] if isinstance(data, dict) else data
    else:
        values = []
        for line in text.splitlines():
            fields = line.split('#', 1)[0].split()
            if fields:
                if len(fields) != 1:
                    raise ValueError('Expected timestamp text requires one column')
                values.append(float(fields[0]))
    return validate_expected(values)


def associate(expected, actual):
    """One-to-one monotone maximum coverage, then minimum total absolute offset.

    Sparse dynamic programming with a Fenwick prefix tree; avoids a dense
    expected-by-ground-truth matrix. Updates are delayed per expected frame so
    neither trajectory samples nor expected observations can be reused.
    """
    actual = list(actual)
    # Nodes: matched count, cumulative error, previous node, expected idx, actual idx.
    nodes = [(0, 0., -1, -1, -1)]
    tree = [0] * (len(actual) + 1)

    def better(a, b):
        return max((a, b), key=lambda k: (nodes[k][0], -nodes[k][1], -k))

    def query(end):
        best = 0
        while end:
            best = better(best, tree[end])
            end -= end & -end
        return best

    for i, timestamp in enumerate(expected):
        pending = []
        lo = bisect_left(actual, timestamp - MAX_TIMESTAMP_DIFF_SECONDS)
        hi = bisect_right(actual, timestamp + MAX_TIMESTAMP_DIFF_SECONDS)
        for j in range(lo, hi):
            delta = abs(float(timestamp) - actual[j])
            if delta > MAX_TIMESTAMP_DIFF_SECONDS:
                continue
            previous = query(j)
            nodes.append((nodes[previous][0] + 1, nodes[previous][1] + delta, previous, i, j))
            pending.append((j + 1, len(nodes) - 1))
        for index, node in pending:
            while index < len(tree):
                tree[index] = better(tree[index], node)
                index += index & -index
    result = {}
    node = query(len(actual))
    while node:
        _, _, previous, i, j = nodes[node]
        result[i] = j
        node = previous
    return result


def align_translation(predicted, truth, allow_scale):
    """Fit truth = scale * (rotation @ predicted) + translation; det(R)=+1."""
    predicted, truth = np.asarray(predicted, float), np.asarray(truth, float)
    if predicted.shape != truth.shape or predicted.ndim != 2 or predicted.shape[1] != 3:
        raise ValueError('Matching Nx3 translation arrays required')
    if len(predicted) < 3:
        raise ValueError('At least three non-collinear correspondences required')
    if not np.isfinite(predicted).all() or not np.isfinite(truth).all():
        raise ValueError('Nonfinite translation input')
    px, gy = predicted.mean(axis=0), truth.mean(axis=0)
    x, y = predicted - px, truth - gy
    if np.linalg.matrix_rank(x) < 2 or np.linalg.matrix_rank(y) < 2:
        raise ValueError('Collinear or coincident trajectory cannot support this alignment')
    u, singular, vt = np.linalg.svd(y.T @ x / len(x))
    signs = np.ones(3)
    signs[-1] = -1. if np.linalg.det(u @ vt) < 0 else 1.
    rotation = u @ np.diag(signs) @ vt
    scale = float(np.dot(singular, signs) / np.mean(np.sum(x*x, axis=1))) if allow_scale else 1.
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError('Alignment has invalid fitted scale')
    translation = gy - scale * rotation @ px
    residual = np.linalg.norm(scale * predicted @ rotation.T + translation - truth, axis=1)
    if not np.isfinite(residual).all():
        raise ValueError('Nonfinite alignment result')
    return {'rmse_m': float(np.sqrt(np.mean(residual**2))),
            'mean_m': float(residual.mean()), 'median_m': float(np.median(residual)),
            'max_m': float(residual.max()), 'residuals_m': residual.tolist(),
            'alignment': {'rotation': rotation.tolist(), 'translation_m': translation.tolist(),
                          'scale': scale, 'rotation_determinant': float(np.linalg.det(rotation)),
                          'reflection_allowed': False}}


def evaluate(expected, predicted, truth):
    expected = validate_expected(expected)
    predicted, truth = validate_trajectory(predicted), validate_trajectory(truth)
    pm, gm = associate(expected, predicted[:, 0]), associate(expected, truth[:, 0])
    rows = []
    for i, timestamp in enumerate(expected):
        row = {'expected_ordinal': i, 'expected_timestamp': float(timestamp)}
        for label, mapping, data in [('prediction', pm, predicted), ('ground_truth', gm, truth)]:
            j = mapping.get(i)
            row[label] = None if j is None else {
                'timestamp': float(data[j, 0]), 'offset_seconds': float(data[j, 0] - timestamp),
                'translation': data[j, 1:4].tolist()}
        row['missing'] = [name for name in ('prediction', 'ground_truth') if row[name] is None]
        rows.append(row)
    complete = len(set(pm) & set(gm))
    result = {'schema': 'real2sim.tum-translation-ate/1',
              'status': 'incomplete', 'expected_count': len(expected),
              'matched_prediction_count': len(pm), 'matched_ground_truth_count': len(gm),
              'complete_correspondence_count': complete,
              'coverage': {'prediction': len(pm)/len(expected), 'ground_truth': len(gm)/len(expected),
                           'complete': complete/len(expected)},
              'missing_prediction_ordinals': [i for i in range(len(expected)) if i not in pm],
              'missing_ground_truth_ordinals': [i for i in range(len(expected)) if i not in gm],
              'unused_prediction_count': len(predicted)-len(pm),
              'unused_ground_truth_count': len(truth)-len(gm),
              'observations': rows, 'sim3_ate': None, 'se3_ate': None,
              'matching': {'max_timestamp_diff_seconds': MAX_TIMESTAMP_DIFF_SECONDS,
                           'rule': 'Independently associate prediction and GT to expected RGB timestamps; one-to-one monotone maximum count, then minimum sum absolute offset. No interpolation, offset fitting or resampling.'},
              'scope': 'Independent translation-only ATE implementation, not official TUM evaluator output. Sim(3) is an additional monocular diagnostic. Quaternion fields validated but orientation not scored. All expected RGB frames retained. No accuracy pass threshold or SOTA claim.',
              'scale_interpretation': 'Sim(3) scale is fitted from GT globally, not measured or recovered metric scale. SE(3) uses scale=1 and is interpretable as metric ATE only for predictions already in metres.'}
    if complete != len(expected):
        result['reason'] = 'Full-denominator ATE withheld: missing prediction or GT observations'
        return result
    x = np.asarray([row['prediction']['translation'] for row in rows])
    y = np.asarray([row['ground_truth']['translation'] for row in rows])
    try:
        sim3 = align_translation(x, y, True)
        se3 = align_translation(x, y, False)
    except (ValueError, np.linalg.LinAlgError) as error:
        result.update(status='unsupported_alignment', reason=str(error))
        return result
    result.update(status='evaluated', sim3_ate=sim3, se3_ate=se3)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ground-truth', type=Path, required=True)
    parser.add_argument('--prediction', type=Path, required=True)
    parser.add_argument('--expected-timestamps', '--expected-json', dest='expected_timestamps', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    inputs = {'ground_truth': args.ground_truth, 'prediction': args.prediction,
              'expected_timestamps': args.expected_timestamps}
    hashes = {key: file_sha(path) for key, path in inputs.items()}
    report = evaluate(read_expected(args.expected_timestamps), read_tum(args.prediction), read_tum(args.ground_truth))
    if hashes != {key: file_sha(path) for key, path in inputs.items()}:
        raise ValueError('Input changed during evaluation')
    report['inputs'] = {key: {'path': str(path.resolve()), 'sha256': hashes[key]} for key, path in inputs.items()}
    report['evaluator_sha256'] = file_sha(__file__)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
    print(json.dumps({key: report[key] for key in ('status', 'expected_count', 'coverage')}))


if __name__ == '__main__':
    main()
