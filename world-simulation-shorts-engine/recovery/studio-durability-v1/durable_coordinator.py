#!/usr/bin/env python3
"""Reuse the unchanged V3/V4 coordinator with verified durability barriers."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import sys

from parent import HERE, RECOVERY, load_file, runtime
from durable_backend import save

PROFILES = {'V4_ARCHIVAL_80S': 'verified-front-data-v4-recovery', 'UNIVERSAL_V3': 'universal-production-v3'}


def worker_command(command, coordinator, profile_id, studio_job_dir):
    command = list(command)
    expected = [sys.executable, '-B', str(coordinator.HERE / 'orchestrator.py')]
    if command[:3] == expected:
        if len(command) < 4 or command[3] != 'worker':
            raise RuntimeError('DURABILITY_FIXED_NATIVE_WORKER_REQUIRED')
        return [sys.executable, command[1], str(HERE / 'durable_coordinator.py'), '--profile', profile_id,
                '--studio-job-dir', str(studio_job_dir), *command[3:]]
    return command


class WorkerProcessAdapter:
    def __init__(self, original, coordinator, profile_id, studio_job_dir):
        self.original, self.coordinator = original, coordinator
        self.profile_id, self.studio_job_dir = profile_id, studio_job_dir

    def __getattr__(self, name):
        return getattr(self.original, name)

    def Popen(self, command, **kwargs):
        return self.original.Popen(worker_command(command, self.coordinator, self.profile_id,
                                                   self.studio_job_dir), **kwargs)


@contextmanager
def checkpoint_barriers(delivery, plan, audio, profile_id, control_root, coordinator_root):
    """Existing verified MP4 export first; authenticated external save second."""
    original_checkpoint = delivery.export_scene_checkpoint
    original_verify = delivery.verify_scene_checkpoint

    def checkpoint(*args, **kwargs):
        receipt = original_checkpoint(*args, **kwargs)
        save(plan, audio, profile_id, control_root, coordinator_root)
        return receipt

    def verify(*args, **kwargs):
        receipt = original_verify(*args, **kwargs)
        save(plan, audio, profile_id, control_root, coordinator_root)
        return receipt

    delivery.export_scene_checkpoint, delivery.verify_scene_checkpoint = checkpoint, verify
    try:
        yield
    finally:
        delivery.export_scene_checkpoint, delivery.verify_scene_checkpoint = original_checkpoint, original_verify


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--profile', required=True, choices=tuple(PROFILES))
    parser.add_argument('--studio-job-dir', required=True, type=Path)
    args, original_args = parser.parse_known_args(argv)
    if not original_args or original_args[0] not in {'start', 'status', 'worker', 'run'}:
        raise RuntimeError('DURABILITY_FIXED_COORDINATOR_ACTION_REQUIRED')
    coordinator = load_file('_durability_native_' + args.profile,
                            RECOVERY / PROFILES[args.profile] / 'orchestrator.py')
    # Keep the original CLI, approvals, wall deadline, job namespace and claims.
    coordinator.parent.subprocess = WorkerProcessAdapter(subprocess, coordinator, args.profile,
                                                         args.studio_job_dir)
    if original_args[0] == 'status':
        return coordinator.main(original_args)
    old = runtime()
    with old._cache().PrivateTree(args.studio_job_dir) as job:
        state, plan, audio = job.json('STATE.json'), job.json('PLAN.json'), job.json('AUDIO.json')
        if (state.get('profileId') != args.profile or state.get('jobId') != args.studio_job_dir.name
                or state.get('schema') != 'WORLD_ENGINE_STUDIO_JOB_V1'):
            raise RuntimeError('DURABILITY_STUDIO_CONTEXT_INVALID')
    control_root = args.studio_job_dir.parent
    coordinator_root = control_root / ('render-v4' if args.profile == 'V4_ARCHIVAL_80S' else 'render-v3')
    try:
        selected_root = Path(original_args[original_args.index('--control-root') + 1])
        selected_plan = Path(original_args[original_args.index('--plan') + 1])
    except (ValueError, IndexError):
        raise RuntimeError('DURABILITY_EXPLICIT_COORDINATOR_CONTEXT_REQUIRED') from None
    if selected_root != coordinator_root:
        raise RuntimeError('DURABILITY_COORDINATOR_ROOT_MISMATCH')
    with old._cache().PrivateTree(selected_plan.parent) as source:
        if source.json(selected_plan.name) != plan:
            raise RuntimeError('DURABILITY_COORDINATOR_PLAN_MISMATCH')
    # Verify independent external restore proof and the current input snapshot
    # before this child is allowed to reach the existing physical GPU lease.
    save(plan, audio, args.profile, control_root, coordinator_root)
    with coordinator._fixed_entry_modules():
        delivery = sys.modules['delivery']
        with checkpoint_barriers(delivery, plan, audio, args.profile, control_root, coordinator_root):
            return coordinator.parent.main(original_args)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'schema': 'WORLD_ENGINE_STUDIO_DURABILITY_COORDINATOR_V1', 'state': 'BLOCKED',
            'code': runtime()._safe(error), 'renderAllowed': False, 'gpuRenderingVerified': False}), flush=True)
        raise SystemExit(2)
