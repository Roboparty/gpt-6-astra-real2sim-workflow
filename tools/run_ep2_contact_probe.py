"""Run the pinned external DROID ep2 simulation and observe every actual mj_step.

Execute on the remote host only. The source checkout remains immutable; all
inputs, adaptations, controls, trajectories and failures live in a new run.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET

COMMIT = '736da5c2c6da040a653e581b8f8052ae5559ad51'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, default=lambda v: v.tolist()), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--run', required=True)
    parser.add_argument('--attempt', type=int, choices=[1, 2, 3], default=1)
    args = parser.parse_args()
    source = Path(args.source).resolve()
    run = Path(args.run).resolve()
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if head != COMMIT:
        raise RuntimeError('Wrong external source commit')
    if sum(p.stat().st_size for p in source.rglob('*') if p.is_file()) > 500_000_000:
        raise RuntimeError('Source too large for source plus run 1 GB budget')
    run.mkdir(parents=True, exist_ok=True)
    attempt = run / f'attempt_{args.attempt:02d}'
    attempt.mkdir(exist_ok=False)
    config = {
        'source_url': 'https://github.com/lingxiao-guo/GPT6-real2sim',
        'source_commit': COMMIT, 'attempt': args.attempt,
        'task': 'DROID ep2 passive faucet lever contact operation',
        'timeout_seconds': 600, 'cpu_threads': 2, 'gpu': False,
        'nominal_call': {'label': 'fresh_nominal', 'friction_scale': 1.0,
                         'offset': [0, 0, 0], 'render': False, 'observed': True, 'timestep': None},
        'frozen_original_criteria': {'final_logged_hinge_angle_rad_gt': 0.55,
                                     'handle_contact_seconds_gt': 0.03,
                                     'pre_13s_max_drift_deg_lt': 2.0},
        'retries': 'At most two compatibility-only retries; no trajectory or physical parameter search.',
        'script_sha256': sha(__file__),
        'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    write_json(attempt / 'experiment_config.json', config)
    started = time.monotonic()
    records, contact_records, pair_counts = [], [], {}
    result = {'status': 'incomplete', 'fresh_simulation': False, 'attempt': args.attempt}
    try:
        for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
            os.environ[key] = '2'
        os.environ['CUDA_VISIBLE_DEVICES'] = ''
        os.nice(5)
        if hasattr(os, 'sched_getaffinity'):
            os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:2])
        import numpy as np
        import mujoco
        inputs = attempt / 'input'
        shutil.copytree(source / 'real2sim_ep2', inputs)
        original_hashes = {str(p.relative_to(inputs)): sha(p) for p in inputs.rglob('*') if p.is_file()}
        write_json(attempt / 'source_hashes.json', original_hashes)
        common = inputs / 'common.py'
        original = common.read_text()
        replacement = original.replace('import h5py\n', 'try:\n    import h5py\nexcept ImportError:\n    h5py = None  # NPZ fallback needs no raw HDF5 dependency.\n')
        if replacement == original:
            raise RuntimeError('Expected single optional-dependency adaptation not found')
        common.write_text(replacement)
        (attempt / 'compatibility.patch').write_text(''.join(difflib.unified_diff(
            original.splitlines(True), replacement.splitlines(True), fromfile='original/common.py', tofile='input/common.py')))
        write_json(attempt / 'adaptation.json', {'kind': 'unused_h5py_optional_import',
                    'original_sha256': original_hashes['common.py'], 'adapted_sha256': sha(common),
                    'physics_parameters_changed': False, 'trajectory_changed': False,
                    'initial_pose_changed': False, 'patch_sha256': sha(attempt / 'compatibility.patch')})
        sys.path.insert(0, str(inputs))
        import common as upstream_common
        if (upstream_common.DATA / 'trajectory.h5').exists():
            raise RuntimeError('Unexpected raw dataset path would bypass frozen numerical input')
        import simulate
        xml = ET.parse(inputs / 'scene.xml').getroot()
        if any(e.get('joint') == 'faucet_hinge' for e in xml.findall('./actuator/*')):
            raise RuntimeError('Unexpected faucet actuator')
        if any('faucet' in str(e.attrib) for e in xml.findall('./equality/*')):
            raise RuntimeError('Unexpected faucet equality constraint')
        model = mujoco.MjModel.from_xml_path(str(inputs / 'scene.xml'))
        hinge = model.joint('faucet_hinge')
        geom_names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, i) or str(i) for i in range(model.ngeom)]
        control_limits = model.actuator_ctrlrange.copy()
        setup = {
            'engine': 'MuJoCo', 'engine_version': mujoco.__version__,
            'nq': model.nq, 'nv': model.nv, 'nu': model.nu,
            'timestep_s': model.opt.timestep, 'hinge_joint_id': hinge.id,
            'hinge_qposadr': int(hinge.qposadr[0]),
            'hinge_frictionloss_Nm': float(model.dof_frictionloss[hinge.dofadr[0]]),
            'hinge_damping': float(model.dof_damping[hinge.dofadr[0]]),
            'handle_mass_kg': float(model.body_mass[model.body('faucet_handle').id]),
            'actuator_joint_ids': model.actuator_trnid[:, 0].tolist(),
            'faucet_actuator_present': bool(hinge.id in model.actuator_trnid[:, 0]),
            'control_limits': control_limits.tolist(), 'geom_names': geom_names,
            'model_sha256': sha(inputs / 'scene.xml'),
            'reference_trajectory_sha256': sha(inputs / 'recorded_trajectory.npz'),
            'simulate_source_sha256': sha(inputs / 'simulate.py'),
            'cpu_affinity': sorted(os.sched_getaffinity(0)),
        }
        write_json(attempt / 'runtime_setup.json', setup)
        if setup['faucet_actuator_present']:
            raise RuntimeError('Runtime faucet unexpectedly actuated')
        original_step = mujoco.mj_step
        previous_post = None
        state_discontinuities = []
        last_data = None

        def observed_step(m, d, *positional, **keywords):
            nonlocal previous_post, last_data
            index = len(records)
            if previous_post is not None:
                delta = float(np.max(abs(np.concatenate([d.qpos, d.qvel]) - previous_post)))
                if delta != 0:
                    state_discontinuities.append({'step': index, 'maximum_change': delta})
            controls = d.ctrl.copy()
            original_step(m, d, *positional, **keywords)
            previous_post = np.concatenate([d.qpos, d.qvel]).copy()
            last_data = d
            handle_count, gripper_handle_count, penetration = 0, 0, 0.0
            for contact_index, contact in enumerate(d.contact):
                g1, g2 = int(contact.geom1), int(contact.geom2)
                n1, n2 = geom_names[g1], geom_names[g2]
                is_handle = 'handle_' in n1 or 'handle_' in n2
                penetration = max(penetration, max(0.0, -float(contact.dist)))
                if not is_handle:
                    continue
                handle_count += 1
                other = n2 if 'handle_' in n1 else n1
                is_gripper = any(word in other for word in ('finger', 'knuckle', 'robotiq'))
                gripper_handle_count += int(is_gripper)
                force = np.zeros(6)
                mujoco.mj_contactForce(m, d, contact_index, force)
                contact_records.append([index, g1, g2, float(contact.dist), *force])
                pair = ' / '.join(sorted([n1, n2]))
                pair_counts[pair] = pair_counts.get(pair, 0) + 1
            records.append((float(d.time), controls, d.qpos.copy(), d.qvel.copy(),
                            int(d.ncon), handle_count, gripper_handle_count, penetration))

        def timeout_handler(signum, frame):
            raise TimeoutError('Frozen 600-second simulation budget exceeded')

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(600)
        mujoco.mj_step = observed_step
        simulation_started = time.monotonic()
        try:
            original_result = simulate.run(**config['nominal_call'])
        finally:
            mujoco.mj_step = original_step
            signal.alarm(0)
        actual_runtime = time.monotonic() - simulation_started
        # Recompute the exact historical predicate from the NEWLY generated log;
        # historical replay files were not checked out and are never read here.
        fresh_log = np.load(inputs / 'fresh_nominal_replay.npz')['log']
        dt = float(model.opt.timestep)
        first_active = next(i for i in range(len(records)) if i * dt - 0.3 >= 0)
        initial = float(records[first_active][2][hinge.qposadr[0]])
        end_angle = float(fresh_log[-1, 1])
        contact_seconds = sum(row[5] > 0 for row in records[first_active:]) * dt
        drift = float(np.degrees(np.max(abs(fresh_log[fresh_log[:, 0] < 13, 1] - initial))))
        recomputed = end_angle > .55 and contact_seconds > .03 and drift < 2
        control_array = np.array([row[1] for row in records])
        finite = all(np.isfinite(row[2]).all() and np.isfinite(row[3]).all() for row in records)
        within_controls = bool(np.all(control_array >= control_limits[:, 0] - 1e-12) and np.all(control_array <= control_limits[:, 1] + 1e-12))
        warnings = {str(i): int(w.number) for i, w in enumerate(last_data.warning) if w.number}
        result.update(status='completed', fresh_simulation=True, simulation_runtime_seconds=actual_runtime,
                      mj_step_calls=len(records), simulation_integrated_seconds=records[-1][0],
                      initial_handle_deg=float(np.degrees(initial)), final_logged_handle_deg=float(np.degrees(end_angle)),
                      final_solver_handle_deg=float(np.degrees(records[-1][2][hinge.qposadr[0]])),
                      contact_seconds_recomputed=contact_seconds, pre_interaction_drift_deg_recomputed=drift,
                      original_task_pass_recomputed=bool(recomputed), original_result_task_pass=original_result['task_rotation_achieved'],
                      result_agrees_with_recomputation=bool(recomputed == original_result['task_rotation_achieved']),
                      gripper_handle_contact_steps=sum(row[6] > 0 for row in records[first_active:]),
                      gripper_handle_contact_seconds=sum(row[6] > 0 for row in records[first_active:]) * dt,
                      total_handle_contact_entries=len(contact_records), contact_pair_entry_counts=pair_counts,
                      all_states_finite=bool(finite), control_limits_respected=within_controls,
                      solver_warnings=warnings, state_discontinuities_between_steps=state_discontinuities,
                      no_between_step_state_injection=(state_discontinuities == []),
                      historical_replay_read=False, original_result=original_result)
    except BaseException as exc:
        result.update(status='failed', error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc(),
                      fresh_simulation=bool(records), mj_step_calls=len(records))
        (attempt / 'failure.txt').write_text(result['traceback'])
    finally:
        if records:
            import numpy as np
            np.savez_compressed(attempt / 'actual_controls_and_states.npz',
                time=np.array([r[0] for r in records]), controls=np.array([r[1] for r in records]),
                qpos=np.array([r[2] for r in records]), qvel=np.array([r[3] for r in records]),
                all_contact_counts=np.array([r[4] for r in records]),
                handle_contact_counts=np.array([r[5] for r in records]),
                gripper_handle_contact_counts=np.array([r[6] for r in records]),
                max_penetration_m=np.array([r[7] for r in records]))
            np.savez_compressed(attempt / 'actual_handle_contacts.npz', contacts=np.array(contact_records))
            result['actual_controls_and_states_sha256'] = sha(attempt / 'actual_controls_and_states.npz')
            result['actual_handle_contacts_sha256'] = sha(attempt / 'actual_handle_contacts.npz')
        result['total_runtime_seconds'] = time.monotonic() - started
        result['experiment_config_sha256'] = sha(attempt / 'experiment_config.json')
        result['limitations'] = [
            'Reproduces a third-party nominal controller/model under current MuJoCo, not our room reconstruction.',
            'Original endpoint predicate is lever angle/contact/drift, not validated water-flow shutoff.',
            'Original unintended-contact exclusions and physical priors remain unchanged.',
            'No physical parameter search or adaptation was performed; no general SOTA conclusion follows.',
        ]
        write_json(attempt / 'result.json', result)
        print(json.dumps({k: v for k, v in result.items() if k not in {'original_result', 'traceback', 'contact_pair_entry_counts'}}, indent=2))
    return 0 if result['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
