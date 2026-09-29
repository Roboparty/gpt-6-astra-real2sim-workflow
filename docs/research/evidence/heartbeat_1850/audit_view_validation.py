import hashlib
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageStat, ImageDraw

root = Path('/home/wqz/real2sim_capability_20260929/runs/portability_views_001')
protocol = Path('/home/wqz/real2sim_capability_20260929/runs/view_validation_code_001/docs/research/PORTABILITY_VIEWS_PROTOCOL_20260930.json')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
cfg = json.loads(protocol.read_text())
receipt = json.loads((root/'receipt.json').read_text())
comparison = json.loads((root/'comparison.json').read_text())
assert receipt['status'] == 'completed_diagnostic'
assert receipt['protocol_sha256'] == sha(protocol) == comparison['receipt_protocol_sha256']
assert receipt['comparison_sha256'] == sha(root/'comparison.json')
assert len(receipt['cells']) == receipt['expected_cells'] == 18
assert len(comparison['rows']) == comparison['expected_comparisons'] == 9
assert receipt['cross_arm_rigs_equal'] and receipt['sources_and_export_dependencies_unchanged']
audit = {'schema': 'real2sim.portability-views-independent-audit/1', 'status': 'passed',
         'receipt_sha256': sha(root/'receipt.json'), 'comparison_sha256': sha(root/'comparison.json'),
         'script_sha256': sha(Path(__file__)), 'cell_geometry': [], 'recomputed_metrics': [],
         'scope': 'Pillow ImageChops independent recomputation of NumPy metrics, source dependency and matrix checks. Single scene virtual-view diagnostic only.'}
for arm in cfg['arms']:
    for key in ('source_model', 'source_scene'):
        assert sha(Path(arm[key])) == arm[key+'_sha256']
    for rel, expected in arm['export_files_sha256'].items():
        assert sha(Path(arm['export_dir'])/rel) == expected
for cell in receipt['cells']:
    p = root/cell['arm']/cell['view']/cell['format']
    assert cell['status'] in {'rendered', 'rendered_geometry_failed'}
    assert sha(p/'render.png') == cell['render_sha256']
    assert sha(p/'geometry.json') == cell['geometry_sha256']
    geometry = json.loads((p/'geometry.json').read_text())
    audit['cell_geometry'].append(dict(arm=cell['arm'], view=cell['view'], format=cell['format'],
        **{k: geometry[k] for k in ('status', 'failures', 'maximum_bound_error_m', 'source_camera_matrix_max_error', 'source_camera_projection_max_error')}))
    delta = next(v['translation_world_m'] for v in cfg['views'] if v['id'] == cell['view'])
    camera = cell['diagnostic_camera']
    assert delta == camera['translation_world_m']
    for i in range(4):
        for j in range(4):
            wanted = camera['source_matrix_world'][i][j] + (delta[i] if i < 3 and j == 3 else 0)
            assert abs(camera['actual_matrix_world'][i][j]-wanted) < 1e-6
for execution in receipt['executions']:
    path = root/execution['arm']/execution['view']/'receipt.json'
    assert execution['receipt_sha256'] == sha(path)
    r = json.loads(path.read_text())
    assert r['sources_unchanged']
    assert r['protocol_sha256'] == execution['protocol_sha256']
    for cell in r['groups']:
        assert cell['rig_before'] == cell['rig_after'] and cell['rig_preserved']

def rgb(arm, view, fmt):
    return Image.open(root/arm/view/fmt/'render.png').convert('RGB')

def mae(a, b):
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean)/(3*255)

for row in comparison['rows']:
    view, fmt = row['view'], row['format']
    o, b = rgb('original', view, fmt), rgb('baked', view, fmt)
    on, bn = rgb('original', view, 'native'), rgb('baked', view, 'native')
    values = dict(original_format_to_original_native_mae=mae(o,on), baked_format_to_baked_native_mae=mae(b,bn),
                  baked_format_to_original_native_mae=mae(b,on), baked_native_to_original_native_mae=mae(bn,on))
    assert all(abs(value-row[key]) < 1e-12 for key,value in values.items())
    audit['recomputed_metrics'].append(dict(view=view, format=fmt, **values))
audit['strict_passed_cells'] = sum(c['status']=='passed' for c in audit['cell_geometry'])
(root/'independent_audit.json').write_text(json.dumps(audit,indent=2))
cols = [('original','native'),('baked','native'),('original','glb'),('baked','glb'),('original','usdc'),('baked','usdc')]
canvas = Image.new('RGB', (1536, 3*220), 'white'); draw = ImageDraw.Draw(canvas)
for y, view in enumerate(cfg['views']):
    for x,(arm,fmt) in enumerate(cols):
        im = rgb(arm,view['id'],fmt); im.thumbnail((256,192))
        canvas.paste(im,(x*256,y*220+28))
        draw.text((x*256+3,y*220+2),arm+' '+fmt,fill='black')
        draw.text((x*256+3,y*220+14),view['id'],fill='black')
canvas.save(root/'preview.jpg',quality=85)
print(json.dumps({'status':audit['status'],'strict_passed_cells':audit['strict_passed_cells'],'expected_cells':18,'all_nine_metrics_recomputed':True}))
