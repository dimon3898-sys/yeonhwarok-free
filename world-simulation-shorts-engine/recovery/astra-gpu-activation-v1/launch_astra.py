#!/usr/bin/env python3
"""Explicit ASTRA orchestration using inherited admission, storage and source checks.

This namespace adds no probe replacement, GPU bypass or arbitrary executable API.
"""
from __future__ import annotations

from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ENGINE_HERE = Path('/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/astra-gpu-activation-v1')
if not ENGINE_HERE.is_dir():
    ENGINE_HERE = HERE
STORAGE_DIR = Path('/opt/world-engine-storage-fix')
if not (STORAGE_DIR / 'launch.py').is_file():
    STORAGE_DIR = HERE.parent / 'gcube-storage-fix-v1'
# The original launcher loads its own unchanged startup/records dependencies.
sys.path.insert(0, str(STORAGE_DIR))
sys.path.insert(0, str(ENGINE_HERE))
spec = importlib.util.spec_from_file_location('_astra_inherited_storage_launch', STORAGE_DIR / 'launch.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
import prepare_activation

HASH = re.compile(r'[0-9a-f]{64}\Z')


def _native_command(admission):
    return ['node', str(ENGINE_HERE / 'capture_astra.mjs'), '--admission-file',
            str(admission.admission_file), '--output-root', str(admission.output_root)]


def render_astra(gpu, admission, config):
    """New fixed-command orchestration; inherit exact allocation and kill APIs."""
    if admission.test_only:
        raise gpu.LauncherError('TEST_ADMISSION_NOT_EXECUTABLE')
    config.validate()
    allocation = admission.private_report['allocation']
    baseline_used = allocation['memory_total_mib'] - allocation['memory_free_mib']
    budget = admission.safe_report['vramBudgetBytes']
    process = None
    deadline = time.monotonic() + config.render_timeout_seconds
    signals = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)
    previous = {number: signal.getsignal(number) for number in signals}
    def interrupted(number, frame):
        raise gpu.LauncherError('GPU_RENDER_INTERRUPTED')
    try:
        for number in signals:
            signal.signal(number, interrupted)
        process = subprocess.Popen(_native_command(admission), cwd=gpu.ENGINE_ROOT,
                                   env=admission.environ, start_new_session=True)
        while process.poll() is None:
            if time.monotonic() >= deadline:
                raise gpu.LauncherError('GPU_RENDER_DEADLINE_EXCEEDED')
            current = gpu.query_allocation(admission.environ, subprocess.run)
            if any(current[key] != allocation[key] for key in ('uuid', 'model', 'driver_version', 'memory_total_mib')):
                raise gpu.LauncherError('GPU_ALLOCATION_CHANGED_DURING_RENDER')
            growth = max(0, current['memory_total_mib'] - current['memory_free_mib'] - baseline_used) * gpu.MIB
            if growth > budget or current['memory_free_mib'] * gpu.MIB < gpu.RESERVED_MEMORY_BYTES:
                raise gpu.LauncherError('GPU_RENDER_VRAM_BUDGET_EXCEEDED')
            time.sleep(min(1., max(0., deadline - time.monotonic())))
        if process.returncode != 0:
            raise gpu.LauncherError('GPU_RENDER_PROCESS_FAILED')
    except (OSError, subprocess.SubprocessError):
        raise gpu.LauncherError('GPU_RENDER_PROCESS_FAILED') from None
    finally:
        try:
            if process is not None and process.poll() is None:
                gpu._stop_render(process)
        finally:
            for number, handler in previous.items():
                signal.signal(number, handler)
    return 0


def _capture_receipt(session, result, activation, *, test_only=False):
    """Bind exported public bytes to the actual ASTRA source-material capture.

    The original export receipt remains untouched. No diagnostic or source bytes
    are added to public-review. Shared readback is not external durability.
    """
    name = result.get('directory')
    if not isinstance(name, str) or not re.fullmatch(r'capture-[0-9a-f]{12}-[0-9a-f]{24}', name):
        raise base.storage.StorageError('STORAGE_VALIDATION_FAILED')
    private = export = unit = capture = report_fd = None
    try:
        private = session._private_fd()
        export = session._export_fd(private)
        unit = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=export)
        # Read the original completion unit through the same no-follow anchor.
        fd = os.open('EXPORT_COMPLETE.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=unit)
        try:
            base.storage._file_info(fd)
            complete = json.loads(base.storage._read_fd(fd))
        finally:
            os.close(fd)
        capture_id = complete.get('captureId')
        if (not isinstance(capture_id, str) or not HASH.fullmatch(capture_id)
                or complete.get('status') != 'COMPLETE' or complete.get('files') != result.get('files')):
            raise ValueError()
        capture_root = os.open('captures', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=private)
        try:
            capture = os.open(capture_id, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=capture_root)
        finally:
            os.close(capture_root)
        base.storage._private_check(capture, session.account)
        report_fd = os.open('REPORT.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=capture)
        info = base.storage._file_info(report_fd, uid=1000, private=True)
        if not 1 <= info.st_size <= base.storage.CAPTURE_REPORT_MAX_BYTES:
            raise ValueError()
        report = json.loads(base.storage._read_fd(report_fd, limit=base.storage.CAPTURE_REPORT_MAX_BYTES))
        if (report.get('schema') != 'RTX_GPU_HARDWARE_CAPTURE_V1'
                or report.get('status') != 'CAPTURE_TECHNICAL_PASS'
                or report.get('signature') != capture_id or report.get('astraApplied') is not True
                or report.get('activationSha256') != activation['activationSha256']
                or report.get('bundleManifestSha256') != activation['bundleManifestSha256']
                or report.get('astraProfileId') != activation['profileId']
                or len(report.get('frames', [])) != 150):
            raise ValueError()
        for key in ('runtimeSourceSignature', 'extensionManifestSha256'):
            if not isinstance(report.get(key), str) or not HASH.fullmatch(report[key]):
                raise ValueError()
        receipt = {'schema':'WORLD_ENGINE_ASTRA_CAPTURE_RECEIPT_V1', 'status':'COMPLETE',
                   'profile':'ASTRA_GPU_ACTIVATION_V1', 'profileId':activation['profileId'],
                   'captureId':capture_id, 'materialPlanSha256':report['runtimeSourceSignature'],
                   'activationSha256':activation['activationSha256'],
                   'bundleManifestSha256':activation['bundleManifestSha256'],
                   'extensionManifestSha256':report['extensionManifestSha256'],
                   'astraApplied':True, 'gpuRenderingVerified':not test_only, 'testOnly':test_only,
                   'visualQualityVerified':False, 'mountedViewReadbackVerified':True,
                   'remotePersistenceVerified':False, 'externalDownloadVerified':False}
        base.storage._new_file(unit, 'ASTRA_COMPLETE.json',
                              (json.dumps(receipt, sort_keys=True) + '\n').encode())
        base.storage._shared_fsync(unit)
        return receipt
    except base.storage.StorageError:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        raise base.storage.StorageError('STORAGE_VALIDATION_FAILED') from None
    finally:
        for fd in (report_fd, capture, unit, export, private):
            if fd is not None:
                os.close(fd)


def _render_and_export(gpu, config, session, activation):
    # Common immutable inherited lock serializes old and ASTRA GPU jobs.
    with gpu.capture_guard(base.storage.PRIVATE_BASE):
        admission = gpu.admit_gpu(config)  # Original native gate, now serialized with capture.
        if admission.test_only:
            raise base.startup.StartupFailure('NVIDIA', 'TEST_SEAM_PRODUCTION_DISPATCH_BLOCKED', 2)
        render_astra(gpu, admission, config)
        report = session.export_results()
        if (not isinstance(report, dict) or report.get('status') != 'EXPORTED'
                or report.get('captures') != 1 or report.get('files') != 7
                or report.get('mountedViewReadbackVerified') is not True
                or report.get('privateDataAllowed') is not False
                or report.get('remotePersistenceVerified') is not False
                or report.get('externalDownloadVerified') is not False):
            raise base.storage.StorageError('STORAGE_VALIDATION_FAILED')
        for result in report['results']:
            _capture_receipt(session, result, activation)
        if not base._emit_export_location(session, report, test_only=False):
            raise base.storage.StorageError('STORAGE_VALIDATION_FAILED')
        return 0


def main(argv=None):
    session = None
    try:
        parser = base.startup.SafeArgumentParser(description=__doc__)
        parser.add_argument('--render-astra-65422', '--render-65422', action='store_true', required=True,
                            dest='render_astra')
        parser.add_argument('--vram-budget-gib', type=float, default=8.)
        parser.add_argument('--port', type=int, default=8000)
        args = parser.parse_args(argv)
        if os.environ.get('WORLD_ENGINE_STARTUP_MODE', 'normal') != 'normal':
            raise base.startup.StartupFailure('CONFIGURATION', 'DIAGNOSTIC_RENDER_FORBIDDEN', 2)
        prepare_activation.verify_extension()
        native = base.startup.NativeOperations()
        session = base.storage.StorageSession.create(native.account())
        selected = base.StorageOperations(native, session, mode='normal', test_only=False)
        # Reuse original bootstrap/source/dependency gates before preparing CPU data.
        selected.bootstrap().prepare_environment(selected.account())
        selected.source()
        if selected.dependencies().get('status') != 'PASS':
            raise base.startup.StartupFailure('DEPENDENCY', 'CPU_DEPENDENCY_CHECK_FAILED')
        activation = prepare_activation.prepare_activation(session.private_root)
        os.environ['WORLD_ENGINE_ASTRA_ACTIVATION_FILE'] = str(activation['activationFile'])
        os.environ['WORLD_ENGINE_ASTRA_ACTIVATION_SHA256'] = activation['activationSha256']
        gpu = native.gpu()
        config = gpu.LauncherConfig(budget_gib=args.vram_budget_gib, port=args.port, storage_root=session.private_root)
        return _render_and_export(gpu, config, session, activation)
    except Exception as error:
        if isinstance(error, base.storage.StorageError):
            record = base._storage_failure(error, mode='normal', test_only=False)
        else:
            record = base.startup._failure('NVIDIA', error, mode='normal', test_only=False)
        base._publish(record, session, mode='normal', test_only=False)
        return record['exitCode']


if __name__ == '__main__':
    raise SystemExit(main())
