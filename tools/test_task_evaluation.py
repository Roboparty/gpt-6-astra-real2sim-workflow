"""Synthetic numeric fixtures test evaluator logic, not physical task success."""
import copy
from itertools import product
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'workflow'))
from r2s.contracts import ContractError
from r2s.task_evaluation import evaluate_container_task


def fixture():
    samples = []
    for step in range(41):
        x = 1.2 if step < 10 else 0.5
        samples.append({
            'time_s': step / 10,
            'object_vertices_local_m': [[x + dx, 0.5 + dy, 0.2 + dz]
                                        for dx, dy, dz in product([-0.05, 0.05], repeat=3)],
            'gripper_object_contact_count': 2 if step < 15 else 0,
            'hand_container_distance_m': 0.02 if step < 16 else 0.2,
            'object_linear_speed_m_s': 0.1 if step < 18 else 0.001,
            'object_angular_speed_rad_s': 0.1 if step < 18 else 0.001,
            'hinge_angle_rad': 1.0 if step < 19 else 0.01,
        })
    return {
        'schema_version': 'real2sim.container_task_trace/1.0',
        'vertex_frame': 'container_local',
        'container_inner_bounds_m': [[0, 0, 0], [1, 1, 1]],
        # Deliberate fixture declaration exercises the provenance gate. This
        # file does not execute that solver or authenticate its declaration.
        'provenance': {'kind': 'simulation', 'engine': 'test_fixture_engine',
                       'engine_version': 'fixture_only', 'model_sha256': 'a' * 64,
                       'source_artifact': 'synthetic_fixture_not_a_real_episode.json',
                       'state_origin': 'numerical_solver', 'object_pose_control': 'solver_only',
                       'state_edits': []},
        'samples': samples,
    }


def main():
    protocol = {'episode_duration_seconds': 4, 'hold_seconds': 2,
                'max_sample_gap_seconds': 0.1, 'require_hinge_closed': True}
    trace = fixture()
    before = copy.deepcopy(trace)
    report = evaluate_container_task(trace, protocol)
    assert trace == before
    assert report['simulation_task_pass'] and report['numeric_criteria_pass']
    assert report['metrics']['hold_sample_count'] == 21
    assert report['metrics']['observed_hold_duration_s'] == 2
    assert report['metrics']['last_release_time_s'] == 1.5
    assert len(report['trace_sha256']) == len(report['protocol_sha256']) == 64

    failures = [
        ('release_after_containment', lambda t: [s.update(gripper_object_contact_count=0) for s in t['samples'][5:]]),
        ('contained_for_hold', lambda t: t['samples'][-1]['object_vertices_local_m'][0].__setitem__(2, -0.1)),
        ('hinge_closed_for_hold', lambda t: t['samples'][-1].update(hinge_angle_rad=0.5)),
        ('hinge_closed_for_hold', lambda t: t['samples'][25].update(hinge_angle_rad=0.5)),
        ('released_for_hold', lambda t: t['samples'][-1].update(gripper_object_contact_count=1)),
        ('hand_withdrawn_for_hold', lambda t: t['samples'][25].update(hand_container_distance_m=0.02)),
        ('linear_stability_for_hold', lambda t: t['samples'][25].update(object_linear_speed_m_s=0.2)),
        ('angular_stability_for_hold', lambda t: t['samples'][25].update(object_angular_speed_rad_s=0.2)),
        ('sufficient_sampling', lambda t: t['samples'].pop(30)),
        ('sufficient_sampling', lambda t: t['samples'].pop(5)),
        ('complete_fixed_episode', lambda t: t['samples'].pop()),
        ('complete_fixed_episode', lambda t: t['samples'].pop(0)),
        ('release_after_containment', lambda t: [s.update(gripper_object_contact_count=0) for s in t['samples']]),
        ('observed_entry', lambda t: [s.update(object_vertices_local_m=copy.deepcopy(t['samples'][-1]['object_vertices_local_m'])) for s in t['samples']]),
    ]
    for reason, mutate in failures:
        bad = fixture()
        mutate(bad)
        result = evaluate_container_task(bad, protocol)
        assert not result['simulation_task_pass'], reason
        assert reason in result['failure_reasons'], (reason, result['failure_reasons'])
        assert result['metrics']['sample_count'] == len(bad['samples'])

    for update in ({'kind': 'reference'}, {'object_pose_control': 'keyframed'},
                   {'state_origin': 'reference_animation'},
                   {'state_edits': [{'time_s': 1.0, 'target': 'object', 'kind': 'reset'}]}):
        nonphysical = fixture()
        nonphysical['provenance'].update(update)
        result = evaluate_container_task(nonphysical, protocol)
        assert result['numeric_criteria_pass'] and not result['simulation_task_pass']
        assert not result['provenance_eligible']

    no_hinge = fixture()
    for sample in no_hinge['samples']:
        del sample['hinge_angle_rad']
    static_protocol = {**protocol, 'require_hinge_closed': False}
    assert evaluate_container_task(no_hinge, static_protocol)['simulation_task_pass']
    assert 'hinge_closed_for_hold' not in evaluate_container_task(no_hinge, static_protocol)['checks']
    assert evaluate_container_task(no_hinge, static_protocol)['protocol_sha256'] != report['protocol_sha256']

    malformed = [
        lambda t: t['samples'][25].update(time_s=float('nan')),
        lambda t: t['samples'][25].update(time_s=t['samples'][24]['time_s']),
        lambda t: t['samples'][25].update(object_linear_speed_m_s=float('inf')),
        lambda t: t['samples'][25].update(object_angular_speed_rad_s=-0.1),
        lambda t: t['samples'][25].update(hand_container_distance_m=True),
        lambda t: t['samples'][25].update(gripper_object_contact_count=True),
        lambda t: t['samples'][25].update(gripper_object_contact_count=0.5),
        lambda t: t['samples'][25].pop('hinge_angle_rad'),
        lambda t: t['samples'][25]['object_vertices_local_m'][0].__setitem__(1, float('nan')),
        lambda t: t['samples'][25]['object_vertices_local_m'].pop(),
        lambda t: t.update(container_inner_bounds_m=[[0, 0, 0], [0, 1, 1]]),
        lambda t: t.update(vertex_frame='world'),
        lambda t: t['provenance'].pop('state_edits'),
        lambda t: t['provenance'].update(model_sha256='missing'),
    ]
    for mutate in malformed:
        bad = fixture()
        mutate(bad)
        try:
            evaluate_container_task(bad, protocol)
        except ContractError:
            continue
        raise AssertionError('Malformed numeric/provenance trace accepted')
    for bad_protocol in ({}, {**protocol, 'hold_seconds': 5}, {**protocol, 'max_sample_gap_seconds': 0},
                         {**protocol, 'min_hand_distance_m': float('nan')},
                         {**protocol, 'require_hinge_closed': 'false'}):
        try:
            evaluate_container_task(trace, bad_protocol)
        except ContractError:
            continue
        raise AssertionError('Invalid frozen protocol accepted')
    trace['success'] = False
    assert evaluate_container_task(trace, protocol)['simulation_task_pass'], 'Producer success flag must be ignored'
    trace['samples'][-1]['object_vertices_local_m'][0][0] = 1.5
    trace['success'] = True
    assert not evaluate_container_task(trace, protocol)['simulation_task_pass'], 'Producer success cannot override numeric failure'
    print(f'PASS task evaluator: synthetic success, {len(failures)} numeric failures, four nonphysical origins, optional hinge, {len(malformed)} malformed traces and five invalid protocols')


if __name__ == '__main__':
    main()
