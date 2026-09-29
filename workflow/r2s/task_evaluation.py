"""Numeric acceptance of a fixed-duration container placement simulation trace."""
import math

from .contracts import ContractError, digest


DEFAULT_PROTOCOL = {
    'hold_seconds': 2.0,
    'max_sample_gap_seconds': 0.05,
    'containment_tolerance_m': 0.002,
    'min_hand_distance_m': 0.1,
    'max_linear_speed_m_s': 0.02,
    'max_angular_speed_rad_s': 0.1,
    'require_hinge_closed': False,
    'hinge_closed_angle_rad': 0.0,
    'hinge_tolerance_rad': 0.05,
}


def _number(value, name, minimum=None):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ContractError('Task trace requires finite numeric ' + name)
    if minimum is not None and value < minimum:
        raise ContractError('Task trace value below minimum: ' + name)
    return value


def _vector(value, name):
    if not isinstance(value, list) or len(value) != 3:
        raise ContractError('Task trace requires a three-component ' + name)
    return [_number(v, name) for v in value]


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ContractError('Task trace requires ' + name)
    return value


def evaluate_container_task(trace, protocol):
    """Evaluate all end-window samples; never use producer success booleans.

    The caller freezes protocol before execution, captures a complete trace from
    the actual solver and retains failed/invalid episodes in the denominator.
    This pure evaluator validates numeric evidence and provenance declarations;
    it cannot authenticate how an external producer obtained those numbers.
    """
    if not isinstance(protocol, dict) or set(protocol) - (set(DEFAULT_PROTOCOL) | {'episode_duration_seconds'}):
        raise ContractError('Unknown task protocol field or non-object protocol')
    p = {**DEFAULT_PROTOCOL, **protocol}
    duration = _number(p.get('episode_duration_seconds'), 'episode_duration_seconds', 0)
    for key, value in p.items():
        if key == 'require_hinge_closed':
            if type(value) is not bool:
                raise ContractError('require_hinge_closed must be boolean')
        else:
            _number(value, key, None if key == 'hinge_closed_angle_rad' else 0)
    hold = p['hold_seconds']
    gap = p['max_sample_gap_seconds']
    if not 0 < hold <= duration or not 0 < gap <= hold / 2:
        raise ContractError('Task protocol requires 0 < gap <= hold/2 and 0 < hold <= duration')

    if not isinstance(trace, dict) or trace.get('schema_version') != 'real2sim.container_task_trace/1.0':
        raise ContractError('Unsupported container task trace schema')
    bounds = trace.get('container_inner_bounds_m')
    if not isinstance(bounds, list) or len(bounds) != 2:
        raise ContractError('Container bounds require local minimum and maximum corners')
    lower, upper = [_vector(v, 'container bounds') for v in bounds]
    if any(a >= b for a, b in zip(lower, upper)):
        raise ContractError('Container inner bounds must have positive extents')
    if trace.get('vertex_frame') != 'container_local':
        raise ContractError('Object vertices must use the container local frame')
    provenance = trace.get('provenance')
    if not isinstance(provenance, dict) or provenance.get('kind') not in {'simulation', 'reference'}:
        raise ContractError('Trace provenance must distinguish simulation from reference')
    _text(provenance.get('source_artifact'), 'trace source artifact')
    if provenance['kind'] == 'simulation':
        for key in ('engine', 'engine_version'):
            _text(provenance.get(key), key)
        model_hash = provenance.get('model_sha256')
        if not isinstance(model_hash, str) or len(model_hash) != 64 or any(c not in '0123456789abcdef' for c in model_hash):
            raise ContractError('Simulation trace requires a lowercase SHA256 of its model')
    state_edits = provenance.get('state_edits')
    if not isinstance(state_edits, list):
        raise ContractError('Trace requires explicit state_edits (empty when there were none after initial state)')

    samples = trace.get('samples')
    if not isinstance(samples, list) or len(samples) < 2:
        raise ContractError('Task trace requires at least two samples')
    times, margins, contacts, distances, speeds, angular_speeds, hinges = [], [], [], [], [], [], []
    vertex_count = None
    for sample in samples:
        if not isinstance(sample, dict):
            raise ContractError('Task sample must be an object')
        times.append(_number(sample.get('time_s'), 'time_s', 0))
        if len(times) > 1 and times[-1] <= times[-2]:
            raise ContractError('Task timestamps must strictly increase')
        vertices = sample.get('object_vertices_local_m')
        if not isinstance(vertices, list) or len(vertices) < 4:
            raise ContractError('Task sample requires complete object geometry, at least four vertices')
        vertices = [_vector(v, 'object vertex') for v in vertices]
        if vertex_count is not None and len(vertices) != vertex_count:
            raise ContractError('Object vertex count changed during task trace')
        vertex_count = len(vertices)
        if any(min(v[axis] for v in vertices) >= max(v[axis] for v in vertices) for axis in range(3)):
            raise ContractError('Task object must have nonzero extent in every axis')
        margins.append(min(min(v[axis] - lower[axis], upper[axis] - v[axis]) for v in vertices for axis in range(3)))
        count = sample.get('gripper_object_contact_count')
        if type(count) is not int or count < 0:
            raise ContractError('Gripper-object contact count must be a nonnegative integer')
        contacts.append(count)
        distances.append(_number(sample.get('hand_container_distance_m'), 'hand_container_distance_m', 0))
        speeds.append(_number(sample.get('object_linear_speed_m_s'), 'object_linear_speed_m_s', 0))
        angular_speeds.append(_number(sample.get('object_angular_speed_rad_s'), 'object_angular_speed_rad_s', 0))
        if p['require_hinge_closed'] or 'hinge_angle_rad' in sample:
            hinges.append(_number(sample.get('hinge_angle_rad'), 'hinge_angle_rad'))

    epsilon = 1e-9
    start = duration - hold
    # Include the sample immediately preceding the window boundary. This proves
    # at least hold_seconds of observed coverage instead of rounding it down.
    starts = [i for i, time in enumerate(times) if time <= start + epsilon]
    window_start = starts[-1] if starts else 0
    tail = slice(window_start, None)
    max_gap = max(b - a for a, b in zip(times, times[1:]))
    complete = (abs(times[0]) <= epsilon and abs(times[-1] - duration) <= epsilon
                and bool(starts) and times[-1] - times[window_start] >= hold - epsilon)
    sampled = max_gap <= gap + epsilon and len(times[tail]) >= math.ceil(hold / gap - epsilon) + 1
    tolerance = p['containment_tolerance_m']
    release_indices = [i for i in range(1, len(samples)) if contacts[i - 1] > 0 and contacts[i] == 0]
    release = release_indices[-1] if release_indices else None
    release_in_container = release is not None and min(margins[release - 1:release + 1]) >= -tolerance
    entered = release is not None and any(m < -tolerance for m in margins[:release])
    solver_origin = (provenance['kind'] == 'simulation'
                     and provenance.get('state_origin') == 'numerical_solver'
                     and provenance.get('object_pose_control') == 'solver_only'
                     and state_edits == [])
    checks = {
        'complete_fixed_episode': complete,
        'sufficient_sampling': sampled,
        'observed_entry': entered,
        'release_after_containment': release_in_container,
        'contained_for_hold': min(margins[tail]) >= -tolerance,
        'released_for_hold': max(contacts[tail]) == 0,
        'hand_withdrawn_for_hold': min(distances[tail]) >= p['min_hand_distance_m'],
        'linear_stability_for_hold': max(speeds[tail]) <= p['max_linear_speed_m_s'],
        'angular_stability_for_hold': max(angular_speeds[tail]) <= p['max_angular_speed_rad_s'],
    }
    if p['require_hinge_closed']:
        checks['hinge_closed_for_hold'] = max(abs(a - p['hinge_closed_angle_rad']) for a in hinges[tail]) <= p['hinge_tolerance_rad']
    numerical_pass = all(checks.values())
    reasons = [key for key, passed in checks.items() if not passed]
    if not solver_origin:
        reasons.append('reference_or_non_solver_object_motion')
    return {
        'schema_version': 'real2sim.container_task_evaluation/1.0',
        'status': 'passed' if numerical_pass and solver_origin else 'failed',
        'simulation_task_pass': numerical_pass and solver_origin,
        'numeric_criteria_pass': numerical_pass,
        'provenance_eligible': solver_origin,
        'checks': checks,
        'failure_reasons': reasons,
        'protocol': p,
        'protocol_sha256': digest(p),
        'trace_sha256': digest(trace),
        'metrics': {
            'sample_count': len(samples), 'hold_sample_count': len(times[tail]),
            'observed_duration_s': times[-1] - times[0],
            'observed_hold_duration_s': times[-1] - times[window_start],
            'max_sample_gap_s': max_gap,
            'last_release_time_s': None if release is None else times[release],
            'minimum_containment_margin_m': min(margins[tail]),
            'maximum_gripper_object_contacts': max(contacts[tail]),
            'minimum_hand_container_distance_m': min(distances[tail]),
            'maximum_linear_speed_m_s': max(speeds[tail]),
            'maximum_angular_speed_rad_s': max(angular_speeds[tail]),
            'maximum_hinge_error_rad': None if not p['require_hinge_closed'] else max(abs(a - p['hinge_closed_angle_rad']) for a in hinges[tail]),
        },
        'limitations': [
            'Only the supplied sampled trace is evaluated; sub-sample events may be missed.',
            'Producer provenance is declared, not authenticated by this pure evaluator.',
            'Caller must verify artifact hashes, full collision-vertex coverage, solver-only motion and actual contacts.',
            'A container-local axis-aligned inner box is a task region, not an independent collision or penetration audit.',
            'This result does not establish real-world calibration, generalization, dataset qualification or SOTA.',
        ],
    }
