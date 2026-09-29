"""Mathematical and input-contract tests; synthetic oracles are not research ATE."""
import itertools
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from evaluate_tum_trajectory import (align_translation, associate, evaluate,
                                     read_expected, read_tum, validate_trajectory)


POINTS = np.array([[0., 0., 0.], [1., 0., 0.], [0., 2., 0.], [0., 0., 3.], [1., 2., 4.]])
ROTATION = np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])


def tum(points, times=None):
    rows = np.zeros((len(points), 8))
    rows[:, 0] = np.arange(len(points)) if times is None else times
    rows[:, 1:4], rows[:, 7] = points, 1.
    return rows


class TrajectoryTests(unittest.TestCase):
    def test_identity(self):
        result = evaluate(list(range(5)), tum(POINTS), tum(POINTS))
        self.assertEqual(result['status'], 'evaluated')
        self.assertLess(result['se3_ate']['rmse_m'], 1e-12)

    def test_known_rigid_transform(self):
        truth = POINTS @ ROTATION.T + [2., -5., 7.]
        result = align_translation(POINTS, truth, False)
        np.testing.assert_allclose(result['alignment']['rotation'], ROTATION, atol=1e-12)
        np.testing.assert_allclose(result['alignment']['translation_m'], [2, -5, 7], atol=1e-12)
        self.assertLess(result['rmse_m'], 1e-12)

    def test_known_similarity_and_scale_distinction(self):
        truth = 2.5 * POINTS @ ROTATION.T + [2., -5., 7.]
        result = evaluate(list(range(5)), tum(POINTS), tum(truth))
        self.assertAlmostEqual(result['sim3_ate']['alignment']['scale'], 2.5)
        self.assertLess(result['sim3_ate']['rmse_m'], 1e-12)
        self.assertGreater(result['se3_ate']['rmse_m'], 1.)
        self.assertEqual(result['se3_ate']['alignment']['scale'], 1.)

    def test_reflection_is_not_a_rotation(self):
        truth = POINTS * [-1, 1, 1]
        for scaled in (True, False):
            result = align_translation(POINTS, truth, scaled)
            self.assertGreater(result['rmse_m'], .1)
            self.assertAlmostEqual(result['alignment']['rotation_determinant'], 1.)

    def test_planar_noncollinear_is_supported(self):
        x = POINTS[:3]
        self.assertLess(align_translation(x, 3*x @ ROTATION.T + [1, 2, 3], True)['rmse_m'], 1e-12)

    def test_collinear_unsupported(self):
        x = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0]])
        result = evaluate([0, 1, 2], tum(x), tum(x))
        self.assertEqual(result['status'], 'unsupported_alignment')
        self.assertIsNone(result['sim3_ate'])

    def test_fewer_than_three_unsupported(self):
        result = evaluate([0, 1], tum(POINTS[:2]), tum(POINTS[:2]))
        self.assertEqual(result['status'], 'unsupported_alignment')

    def test_missing_prediction_keeps_denominator(self):
        result = evaluate(list(range(5)), tum(POINTS)[:-1], tum(POINTS))
        self.assertEqual(result['expected_count'], 5)
        self.assertEqual(len(result['observations']), 5)
        self.assertEqual(result['missing_prediction_ordinals'], [4])
        self.assertEqual(result['coverage']['complete'], .8)
        self.assertIsNone(result['sim3_ate'])
        self.assertIsNone(result['se3_ate'])

    def test_missing_gt_keeps_denominator(self):
        result = evaluate(list(range(5)), tum(POINTS), tum(POINTS)[1:])
        self.assertEqual(result['missing_ground_truth_ordinals'], [0])
        self.assertIsNone(result['sim3_ate'])

    def test_empty_prediction(self):
        result = evaluate(list(range(5)), [], tum(POINTS))
        self.assertEqual(result['coverage']['prediction'], 0.)
        self.assertEqual(result['missing_prediction_ordinals'], list(range(5)))

    def test_fixed_tolerance(self):
        self.assertEqual(associate([0.], [.02]), {0: 0})
        self.assertEqual(associate([0.], [.020001]), {})

    def test_no_timestamp_reuse(self):
        matches = associate([0., .01], [.005])
        self.assertEqual(len(matches), 1)

    def test_matching_does_not_sacrifice_coverage_for_nearest(self):
        # Greedy nearest takes expected .015 -> actual .016 and strands .034.
        self.assertEqual(associate([.015, .034], [0., .016]), {0: 0, 1: 1})

    def test_matching_minimum_offset(self):
        self.assertEqual(associate([0., .03], [-.018, .001, .029, .049]), {0: 1, 1: 2})

    def test_matching_against_exhaustive_oracle(self):
        rng = np.random.default_rng(17)
        for _ in range(30):
            expected = np.sort(rng.uniform(0, .1, 4))
            actual = np.sort(rng.uniform(0, .1, 5))
            candidates = []
            for count in range(5):
                for ei in itertools.combinations(range(4), count):
                    for ai in itertools.combinations(range(5), count):
                        errors = [abs(expected[i]-actual[j]) for i, j in zip(ei, ai)]
                        if all(error <= .02 for error in errors):
                            candidates.append((count, sum(errors)))
            best = min(candidates, key=lambda pair: (-pair[0], pair[1]))
            matches = associate(expected, actual)
            self.assertEqual(len(matches), best[0])
            self.assertAlmostEqual(sum(abs(expected[i]-actual[j]) for i, j in matches.items()), best[1])

    def test_duplicate_timestamp_rejected(self):
        values = tum(POINTS); values[1, 0] = 0
        with self.assertRaises(ValueError):
            validate_trajectory(values)

    def test_nonfinite_rejected(self):
        for invalid in (np.nan, np.inf, -np.inf):
            for column in range(8):
                values = tum(POINTS); values[0, column] = invalid
                with self.assertRaises(ValueError):
                    validate_trajectory(values)

    def test_wrong_column_shape_rejected(self):
        for rows in (np.empty((2, 0)), np.zeros((2, 7)), np.zeros((2, 9))):
            with self.assertRaises(ValueError):
                validate_trajectory(rows)

    def test_zero_quaternion_rejected(self):
        values = tum(POINTS); values[0, 4:] = 0
        with self.assertRaises(ValueError):
            validate_trajectory(values)

    def test_orientation_is_not_scored(self):
        values = tum(POINTS); values[:, 4:] = [2., 0., 0., 0.]
        result = evaluate(list(range(5)), values, tum(POINTS))
        self.assertLess(result['sim3_ate']['rmse_m'], 1e-12)

    def test_bad_expected_rejected(self):
        for times in ([], [0, 0, 1], [1, 0], [0, float('inf')], [False, 1], ['0', 1]):
            with self.assertRaises(ValueError):
                evaluate(times, tum(POINTS), tum(POINTS))

    def test_tum_parse_and_sort(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'trajectory.txt'
            path.write_text('# TUM\n1 1 0 0 0 0 0 1\n0 0 0 0 0 0 0 1 # origin\n')
            self.assertEqual(read_tum(path)[:, 0].tolist(), [0., 1.])
            path.write_text('0 0 0 0 0 0 1\n')
            with self.assertRaises(ValueError):
                read_tum(path)

    def test_expected_formats(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'expected'
            for text in ('[0, 1, 2]', '{"timestamps": [0, 1, 2]}', '# RGB\n0\n1\n2\n'):
                path.write_text(text)
                np.testing.assert_array_equal(read_expected(path), [0, 1, 2])

    def test_report_is_strict_json(self):
        for predicted in (tum(POINTS), []):
            json.dumps(evaluate(list(range(5)), predicted, tum(POINTS)), allow_nan=False)

    def test_cli_hashes_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            gt, pred, expected, output = [root/name for name in ('gt.txt', 'pred.txt', 'timestamps.json', 'report.json')]
            np.savetxt(gt, tum(POINTS), fmt='%.10f')
            np.savetxt(pred, tum(POINTS), fmt='%.10f')
            expected.write_text('[0, 1, 2, 3, 4]')
            command = [sys.executable, str(Path(__file__).with_name('evaluate_tum_trajectory.py')),
                       '--ground-truth', str(gt), '--prediction', str(pred), '--expected-json', str(expected),
                       '--output', str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text())
            self.assertEqual(report['status'], 'evaluated')
            for label, path in [('ground_truth', gt), ('prediction', pred), ('expected_timestamps', expected)]:
                self.assertEqual(report['inputs'][label]['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            before = output.read_bytes()
            retry = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(retry.returncode, 0)
            self.assertEqual(output.read_bytes(), before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
