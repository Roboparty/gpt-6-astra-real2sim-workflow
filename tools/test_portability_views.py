"""Negative camera contracts and the distinction between transfer and bake drift."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


render = load('render_interchange_appearance')
runner = load('run_portability_view_validation')


class ViewContracts(unittest.TestCase):
    def test_default_does_not_request_a_camera_change(self):
        self.assertIsNone(render.camera_translation({}))

    def test_camera_translation_contract(self):
        self.assertEqual(render.camera_translation({'diagnostic_camera_translation_world_m': [-.3, 0, 0]}), [-.3, 0, 0])
        for value in ([0, 0], [0, 0, 0, 0], [True, 0, 0], [float('nan'), 0, 0],
                      [float('inf'), 0, 0], ['0', 0, 0], {'x': 0}, '0,0,0'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                render.camera_translation({'diagnostic_camera_translation_world_m': value})

    def test_transfer_error_is_separate_from_native_drift_and_missing_cells_remain(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cfg = {'views': [{'id': 'v'}], 'formats': ['native', 'glb', 'usdc'], 'render': {'width': 2, 'height': 2}}
            cells = []
            for arm, value in [('original', 0), ('baked', 255)]:
                for fmt in cfg['formats']:
                    path = root/arm/'v'/fmt/'render.png'
                    path.parent.mkdir(parents=True)
                    Image.new('RGB', (2, 2), (value,)*3).save(path)
                    cells.append(dict(arm=arm, view='v', format=fmt, status='rendered', render_sha256=runner.sha(path)))
            rows = runner.score(cfg, root, {'cells': cells})['rows']
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[1]['baked_format_to_baked_native_mae'], 0)
            self.assertEqual(rows[1]['baked_format_to_original_native_mae'], 1)
            self.assertEqual(rows[1]['baked_native_to_original_native_mae'], 1)
            cells[-1]['status'] = 'failed'
            result = runner.score(cfg, root, {'cells': cells})
            self.assertEqual(result['expected_comparisons'], 3)
            self.assertEqual(result['rows'][-1]['status'], 'unavailable')
            cells[-1]['status'] = 'rendered'
            Image.new('RGB', (2, 2), (127,)*3).save(root/'baked'/'v'/'usdc'/'render.png')
            with self.assertRaisesRegex(ValueError, 'Changed rendered image'):
                runner.score(cfg, root, {'cells': cells})


if __name__ == '__main__':
    unittest.main()
