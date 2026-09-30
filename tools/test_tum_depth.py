import unittest
import numpy as np
from evaluate_tum_depth import depth_metrics


class DepthMetricsTests(unittest.TestCase):
    def test_exact_z_and_zero_reference_mask(self):
        r=depth_metrics([[2,99],[4,2]],[[2,0],[4,2]])
        self.assertEqual(r['reference_valid_pixels'],3)
        self.assertEqual(r['abs_rel'],0)
        self.assertEqual(r['delta_1'],1)

    def test_known_scale_error(self):
        r=depth_metrics([[4,8]],[[2,4]])
        self.assertEqual(r['abs_rel'],1)
        self.assertAlmostEqual(r['rmse_m'],10**.5)
        self.assertEqual(r['delta_1'],0)

    def test_invalid_predictions_never_drop_from_denominator(self):
        for value in (float('nan'),float('inf'),0,-1):
            r=depth_metrics([[value,2]],[[2,2]])
            self.assertEqual(r['prediction_coverage'],.5)
            self.assertEqual(r['status'],'incomplete_prediction')
            self.assertIsNone(r['abs_rel'])

    def test_no_depth_is_unavailable(self):
        self.assertEqual(depth_metrics([[1,1]],[[0,0]])['status'],'unavailable')

    def test_reference_and_shape_guards(self):
        with self.assertRaises(ValueError):depth_metrics([[1]],[[float('nan')]])
        with self.assertRaises(ValueError):depth_metrics([[1]],[[-1]])
        with self.assertRaises(ValueError):depth_metrics([[1,2]],[[1]])


if __name__=='__main__':unittest.main()
