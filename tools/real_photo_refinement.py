"""Interactive real-photo regression of the model -> render -> review loop.

Uses an existing independently built scene, not V5 assets. This reduced graph is
a local-edit integration experiment, NOT a fresh reconstruction or full delivery.
All judgements must be authored by an Agent after actually inspecting new renders.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'workflow'))
from r2s.core import Workflow, atomic_json
from r2s.media import file_hash


def local_workflow(case):
    w = Workflow(case)
    w.stages = [('agent_observe', [], True), ('agent_model', ['agent_observe'], True),
                ('build_render', ['agent_model'], False), ('agent_review', ['build_render', 'agent_observe'], True)]
    w.stage_map = {n: (deps, agent) for n, deps, agent in w.stages}
    return w


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['init', 'run', 'accept'])
    p.add_argument('case', type=Path)
    p.add_argument('--source-root', type=Path)
    p.add_argument('--blender')
    p.add_argument('--stage')
    p.add_argument('--response', type=Path)
    a = p.parse_args()
    if a.action == 'init':
        a.case.mkdir(parents=True, exist_ok=False)
        if not a.source_root or not a.blender:
            p.error('init needs --source-root and --blender')
        source = a.source_root / 'inputs/utility_room_original.jpg'
        atomic_json(a.case / 'case.json', {'id': 'real_photo_local_refinement', 'mode': 'single', 'branch': 'A',
            'workflow_profile': 'quality_v2', 'scope': 'Existing real-photo scene local-edit regression, reduced four-stage graph; not fresh reconstruction or full-scene certification',
            'inputs': [{'path': str(source), 'sha256': file_hash(source)}], 'refinement': {'max_revisions': 4, 'max_stagnant': 3, 'max_seconds': 3600, 'surface_contract_version': 0},
            'stages': {'build_render': {'command': [sys.executable, str(Path(__file__).with_name('render_refinement_probe.py')), '{packet}'],
                'parameters': {'blender': a.blender, 'threads': 4}, 'timeout_seconds': 1800}}})
    w = local_workflow(a.case)
    if a.action == 'accept':
        if not a.stage or not a.response:
            p.error('accept needs --stage and --response')
        print(json.dumps({'accepted': w.accept(a.stage, a.response)}))
    else:
        print(json.dumps(w.run(), indent=2))


if __name__ == '__main__':
    main()
