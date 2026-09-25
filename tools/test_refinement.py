"""Small protocol fixtures. These are NOT visual reconstruction results."""
import copy
import json
import sys
import tempfile
import os
import subprocess
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'workflow'))
from r2s.core import Workflow, atomic_json, run_command
from r2s.contracts import ContractError
from r2s.media import file_hash
from r2s.refinement import DIMENSIONS, review, write_render_binding
from PIL import Image


def rejected(fn):
    try:
        fn()
    except ContractError:
        return
    raise AssertionError('Expected rejection')


with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    atomic_json(root / 'case.json', {'id': 'protocol_fixture', 'mode': 'single', 'workflow_profile': 'quality_v2', 'inputs': [], 'refinement': {'max_revisions': 2}})
    w = Workflow(root)
    # A reduced dependency graph isolates the runner without pretending to render a room.
    w.stages = [('agent_model', [], True), ('build_render', ['agent_model'], False), ('agent_review', ['build_render'], True), ('validate', ['agent_review'], False), ('report', ['validate'], False)]
    w.stage_map = {n: (deps, agent) for n, deps, agent in w.stages}
    fingerprint=w.fingerprint('agent_model')
    w.config['refinement']['max_seconds']=8000
    assert w.fingerprint('agent_model')==fingerprint
    w.config['refinement']['max_seconds']=7200
    calls = []
    def fixture_execute(name, retry=False):
        calls.append(name)
        count = w.state['stages'].get(name, {}).get('attempt', 0) + 1
        directory = root / name / str(count)
        directory.mkdir(parents=True)
        item = {'status': 'succeeded', 'attempt': count, 'directory': str(directory), 'outputs': []}
        w.state['stages'][name] = item
        if name == 'agent_review' and count == 1:
            item.update(status='changes_requested', response={'revision': {'stage': 'agent_model', 'reason': 'fixture defect', 'strategy': 'replace shape'}})
        return item['status']
    with patch.object(w, 'execute', fixture_execute), patch.object(w, 'valid', lambda n: w.state['stages'].get(n, {}).get('status') == 'succeeded'):
        assert w.run()['status'] == 'succeeded'
        assert calls == ['agent_model', 'build_render', 'agent_review', 'agent_model', 'build_render', 'agent_review', 'validate', 'report']
        assert w.state['refinement']['revisions'] == 1
        assert w.freeze()['outputs']
        w.state['stages']['report']['status'] = 'stale'
        rejected(w.freeze)
        w.state['refinement']['revisions'] = 2
        assert w.route_revision('agent_review')['reason'] == 'revision_budget'
        w.state['refinement']['revisions'] = 0
        w.state['refinement']['agent_review'] = {'stagnant': 3}
        assert w.route_revision('agent_review')['reason'] == 'no_visual_improvement'
        w.state['refinement']['elapsed_seconds'] = 7201
        assert w.run()['reason'] == 'time_budget'
    print('PASS routing, invalidation, persistent budgets, full freeze gate')
    w.state['refinement']['agent_review']={'best':{'directory':'fixture'},'stagnant':2}
    w.stage_map['agent_calibrate']=([],True)
    w.revise('agent_calibrate','New camera comparison series')
    assert 'best' not in w.state['refinement']['agent_review']
    assert w.state['refinement']['agent_review']['stagnant']==0
    marker=root/'orphan_was_alive'
    child="import time; from pathlib import Path; time.sleep(2); Path("+repr(str(marker))+").touch()"
    parent="import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',"+repr(child)+"]); time.sleep(20)"
    try:
        run_command([sys.executable,'-c',parent],root,os.environ.copy(),.5)
        raise AssertionError('Timeout expected')
    except subprocess.TimeoutExpired:pass
    time.sleep(2)
    assert not marker.exists(),'Timed-out worker left its child running'
    print('PASS budget expansion keeps fingerprints, manual calibration resets series, timeout kills child')

    build = root / 'build'; build.mkdir()
    Image.new('RGB', (20, 20), 'gray').save(root / 'original.png')
    Image.new('RGB', (20, 20), 'green').save(build / 'source_view.png')
    Image.new('RGB', (20, 20), 'blue').save(build / 'diagnostic_reverse.png')
    (build / 'scene.blend').write_bytes(b'NOT A BLENDER FILE: protocol fixture')
    atomic_json(build / 'scene.json', {'camera': {'image_size': [20, 20]}, 'model_version': 1})
    atomic_json(build / 'render_manifest.json', {'comparison_settings': {'fixture': True}})
    targets = [{'entity': 'chair', 'source_crop_xyxy': [2, 2, 18, 18], 'features': ['upholstery']}]
    packet = {'original_input_allowlist': [str(root / 'original.png')], 'appearance_targets': targets}
    binding = write_render_binding(packet, build)
    art = lambda p: {'path': str(p), 'sha256': file_hash(p), 'bytes': p.stat().st_size}
    packet.update(stage='agent_review', input_artifacts={'build_render': [art(build / 'render_binding.json')]})
    out = root / 'review'; out.mkdir()
    for p in build.glob('*.png'):
        (out / p.name).write_bytes(p.read_bytes())
    data = {'render_binding_sha256': file_hash(build / 'render_binding.json'),
            'checks': {key: {'status': 'revise', 'findings': 'Fixture only', 'evidence': ['source_view.png']} for key in DIMENSIONS},
            'per_object': [{'entity': 'chair', 'status': 'revise', 'findings': 'Fixture', 'source_crop': 'priority_000_source.png', 'render_crop': 'priority_000_render.png'}],
            'comparison': {'relation': 'baseline', 'findings': 'Fixture baseline'}}
    data['checks']['source_similarity']['evidence'] = ['source_reference.png', 'source_view.png']
    data['checks']['novel_structure']['evidence'] = ['diagnostic_reverse.png']
    atomic_json(out / 'appearance_review.json', data)
    response = {'status': 'changes_requested', 'artifacts': [p.name for p in out.iterdir()], 'revision': {'stage': 'agent_model', 'reason': 'Fixture', 'strategy': 'Replace fixture'}, 'issues': [{'entity': 'chair', 'defect': 'Fixture', 'evidence': ['source_view.png'], 'responsible_stage': 'agent_model'}]}
    review(out, response, packet, None)
    best = {'directory': str(out), 'review_sha256': file_hash(out / 'appearance_review.json'), 'protocol_sha256': binding['protocol_sha256'], 'image_hashes': list(binding['images'].values()), 'artifacts': [art(p) for p in out.iterdir()], 'source_stages': {}}
    # Work on a fresh review attempt, keeping the baseline immutable.
    revised = root / 'revised'; revised.mkdir()
    for p in out.iterdir():
        (revised / p.name).write_bytes(p.read_bytes())
    data['comparison'] = {'relation': 'worse', 'against': best['review_sha256'], 'protocol_sha256': binding['protocol_sha256'], 'findings': 'Fixture regression', 'before': ['source_view.png'], 'after': ['source_view.png']}
    atomic_json(revised / 'appearance_review.json', data)
    review(revised, response, packet, best)
    w.state['refinement']['agent_review'] = {'best': best, 'stagnant': 0}
    with patch.object(w, 'valid', lambda n: False):
        w.record_candidate('agent_review', revised, response, [art(p) for p in revised.iterdir()], data, binding)
    assert w.state['refinement']['agent_review']['best']['directory'] == str(out)
    assert w.state['refinement']['agent_review']['stagnant'] == 1
    complete = {**response, 'status': 'complete', 'issues': []}
    for c in data['checks'].values(): c['status'] = 'pass'
    data['per_object'][0]['status'] = 'pass'
    atomic_json(revised / 'appearance_review.json', data)
    rejected(lambda: review(revised, complete, packet, best))
    data['comparison']['relation'] = 'better'
    atomic_json(revised / 'appearance_review.json', data)
    review(revised, complete, packet, best)
    original_comparison=copy.deepcopy(data['comparison'])
    data['comparison'].update(before=['source_reference.png'],after=['source_reference.png'])
    atomic_json(revised / 'appearance_review.json', data)
    rejected(lambda: review(revised, complete, packet, best))
    data['comparison']=original_comparison
    atomic_json(revised / 'appearance_review.json', data)
    rejected(lambda: review(revised, {**complete,'artifacts':complete['artifacts']+['model.blend']}, packet, best))
    data['render_binding_sha256'] = '0' * 64
    atomic_json(revised / 'appearance_review.json', data)
    rejected(lambda: review(revised, complete, packet, best))
    data['render_binding_sha256'] = file_hash(build / 'render_binding.json')
    data['per_object'] = []
    atomic_json(revised / 'appearance_review.json', data)
    rejected(lambda: review(revised, complete, packet, best))
    data['per_object'] = [{'entity': 'chair', 'status': 'pass', 'findings': 'Fixture', 'source_crop': 'priority_000_source.png', 'render_crop': 'priority_000_render.png'}]
    atomic_json(revised / 'appearance_review.json', data)
    (revised / 'priority_000_render.png').write_bytes(b'changed evidence')
    rejected(lambda: review(revised, complete, packet, best))
    print('PASS current model/image binding, target coverage, real comparisons, regression protection')

print('All refinement protocol checks passed; no visual quality claim.')
