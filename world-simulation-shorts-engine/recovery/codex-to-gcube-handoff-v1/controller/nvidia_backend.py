"""Bounded, detached GPU backend for the new Studio profile only.

No render starts at import, construction or preflight. The unchanged Studio
coordinator supplies a private, plan-bound authorization after explicit consent.
The original common GPU lease remains the sole render lock.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import pwd
import stat
import json

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from common import PROFILE, RECOVERY, REPO, canonical, duration_contract, load, mvp, sha, validate_plan, verify_manifest

base = mvp()
JOB = re.compile(r'studio-[0-9a-f]{32}\Z')
REQUEST_ID = re.compile(r'owner-[0-9a-f]{32}\Z')
POLICY = {'validUntil', 'maxWallSeconds', 'maxRetries', 'maxCostAmount', 'currency', 'gpuHourlyRate'}


def _now():
    return datetime.now(timezone.utc).isoformat()


def cache():
    return base.load_original('cache')


def approval_limit(value, plan, image_digest, *, now=None):
    """Reuse the real frozen policy validator on actual approval fields."""
    if (not isinstance(value, dict) or set(value) != POLICY | {'schema', 'approved', 'planSHA256', 'imageDigest'}
            or value['schema'] != 'WORLD_ENGINE_UNIVERSAL_GPU_AUTHORIZATION_V1'
            or value['approved'] is not True or value['planSHA256'] != sha(canonical(plan))
            or value['imageDigest'] != image_digest):
        raise RuntimeError('HANDOFF_PLAN_BOUND_APPROVAL_REQUIRED')
    policy = {key: value[key] for key in POLICY}
    class PolicyView:
        def json(self, name, optional=False):
            if name != 'operator_policy.json':
                raise RuntimeError('HANDOFF_POLICY_ACCESS_INVALID')
            return policy
    # No true flag or substituted rate is injected. This executes the same
    # expiry, currency, Decimal cost, wall-time and retry checks as real start.
    base.StudioController._policy(None, PolicyView())
    expiry = datetime.fromisoformat(value['validUntil'])
    remaining = (expiry - (now or datetime.now(timezone.utc))).total_seconds()
    limit = min(600, value['maxWallSeconds'], int(remaining))
    if limit < 1:
        raise RuntimeError('HANDOFF_APPROVAL_EXPIRED')
    return {'maxWallSeconds': limit, 'maxRetries': 0}


def _runtime_environment(environ=None):
    # Owner/GitHub/Dropbox secret values have no purpose in this child. Preserve
    # only the existing graphics/runtime configuration, never print values.
    names = {'PATH', 'HOME', 'LANG', 'LC_ALL', 'TMPDIR', 'LD_LIBRARY_PATH',
        'LIBRARY_PATH', 'DISPLAY', 'WAYLAND_DISPLAY', 'XDG_RUNTIME_DIR',
        'NVIDIA_VISIBLE_DEVICES', 'NVIDIA_DRIVER_CAPABILITIES', 'VK_ICD_FILENAMES',
        '__GLX_VENDOR_LIBRARY_NAME', 'LIBGL_DRIVERS_PATH', 'CHROME_PATH',
        'PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH', 'WORLD_ENGINE_RENDER_MODE',
        'WORLD_ENGINE_STARTUP_MODE', 'WORLD_ENGINE_GPU_PROFILE', 'WORLD_ENGINE_NODE_DEPS',
        'WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST', 'GPU_BACKEND'}
    return {key: value for key, value in (os.environ if environ is None else environ).items() if key in names}


def lease_helper():
    directory = RECOVERY / 'universal-auto-video-v2'
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    file = directory / 'render_adapter.py'
    if sha(file.read_bytes()) != '669073cbd6f3fa9fbfae0a1472fd141a87c6616f1d25acf935a4173dfd32136d':
        raise RuntimeError('HANDOFF_COMMON_GPU_LEASE_CHANGED')
    return load('_handoff_original_common_gpu_lease', file)


def dependency_facts(environ=None, *, export_root=None):
    """Read existing module metadata, with no browser launch or installation."""
    environ = os.environ if environ is None else environ
    if not all(shutil.which(name) for name in ('node', 'ffmpeg', 'ffprobe')) or not Path('/usr/bin/chromium').is_file():
        raise RuntimeError('HANDOFF_RENDER_DEPENDENCIES_REQUIRED')
    deps = Path(environ.get('WORLD_ENGINE_NODE_DEPS', ''))
    if (not deps.is_absolute() or '..' in deps.parts or any(p.is_symlink() for p in (deps, *deps.parents))
            or not (deps / 'package.json').is_file()
            or export_root is not None and deps.resolve().is_relative_to(Path(export_root).resolve())):
        raise RuntimeError('HANDOFF_EXISTING_PLAYWRIGHT_ROOT_REQUIRED')
    pins = {
        'rtx-gpu-package-v1/dependency_contract.json': '39efd1ad351094df62c7941195e7eb5337e5ead81dde70c1c53c27d6a8103ba4',
        '../../cinematic-world-map/package.json': 'b5c91a7a3bf6326ffd396dc285e14b226cb1b6f0715268b055d303dc5833e7a2',
        '../../cinematic-world-map/package-lock.json': 'cd6d339f66be951cf2e7a261dc4e82147031c4965febe66078489c856332e088'}
    for relative, expected_sha in pins.items():
        file = RECOVERY / relative if not relative.startswith('../../') else REPO / relative[6:]
        if any(p.is_symlink() for p in (file, *file.parents)) or sha(file.read_bytes()) != expected_sha:
            raise RuntimeError('HANDOFF_DEPENDENCY_VERSION_CONTRACT_CHANGED')
    script = ("const p=require('node:path'),f=require('node:fs');"
        "const r=require('node:module').createRequire(p.join(process.argv[1],'package.json'));"
        "for(const name of ['playwright','playwright-core']){const n=f.realpathSync(r.resolve(name+'/package.json'));"
        "const q=p.relative(process.argv[1],n);if(q.startsWith('..')||p.isAbsolute(q))process.exit(2);}"
        "process.stdout.write(JSON.stringify({playwright:r('playwright/package.json').version,core:r('playwright-core/package.json').version,node:process.versions.node}));")
    result = subprocess.run(['node', '-e', script, str(deps)], capture_output=True, timeout=10, check=False)
    if result.returncode or len(result.stdout) > 4096:
        raise RuntimeError('HANDOFF_PLAYWRIGHT_RESOLUTION_FAILED')
    metadata = json.loads(result.stdout)
    expected = json.loads((RECOVERY / 'rtx-gpu-package-v1/dependency_contract.json').read_bytes())['versions']
    if (metadata.get('playwright') != expected['playwright'] or metadata.get('core') != expected['playwright']
            or metadata.get('node') != expected['node']):
        raise RuntimeError('HANDOFF_NODE_PLAYWRIGHT_VERSION_MISMATCH')
    return metadata


class NvidiaPresentationBackend:
    def __init__(self, manifest_file, expected_manifest_sha256, image_digest):
        self.manifest_file = Path(manifest_file)
        self.source_sha, self.image_digest = expected_manifest_sha256, image_digest

    def _verify(self, plan, profile):
        if profile != PROFILE:
            raise RuntimeError('HANDOFF_UNSUPPORTED_GPU_PROFILE')
        verify_manifest(self.manifest_file, self.source_sha, require_external=True)
        validate_plan(plan, image_digest=self.image_digest, source_sha=self.source_sha)
        if (os.environ.get('GPU_BACKEND') != 'vulkan'
                or os.environ.get('WORLD_ENGINE_RENDER_MODE') != 'gpu-required'
                or os.environ.get('WORLD_ENGINE_STARTUP_MODE', 'normal') != 'normal'
                or os.environ.get('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST') != self.image_digest):
            raise RuntimeError('HANDOFF_EXPLICIT_NORMAL_VULKAN_IMAGE_REQUIRED')
        if os.geteuid() != 1000 or os.getegid() != 1000:
            raise RuntimeError('HANDOFF_ENGINE_UID_GID_1000_REQUIRED')

    def preflight(self, plan, profile, *, control_root, export_root):
        checks = []
        def check(name, operation):
            try:
                result = operation()
                checks.append({'name': name, 'status': 'PASS',
                               **({'facts': result} if isinstance(result, dict) else {})})
            except Exception as error:
                code = str(error)
                if not re.fullmatch(r'[A-Z][A-Z0-9_]{1,95}', code):
                    code = 'HANDOFF_PREFLIGHT_OPERATION_FAILED'
                checks.append({'name': name, 'status': 'BLOCKED', 'code': code})
        check('NVIDIA_TEN_SECOND_SOURCE_AND_MODE' if isinstance(plan, dict) and plan.get('durationSeconds') == 10
              else 'NVIDIA_SIX_SECOND_SOURCE_AND_MODE', lambda: self._verify(plan, profile))
        if checks[-1]['status'] != 'PASS':
            return {'checks': checks, 'renderAllowed': False, 'gpuRenderingVerified': False,
                    'scope': PROFILE, 'hardwareCaptureNotYetPerformed': True}
        def private():
            with cache().PrivateTree(Path(control_root)):
                pass
            if (Path(control_root).resolve().is_relative_to(Path(export_root).resolve())
                    or Path(export_root).resolve().is_relative_to(Path(control_root).resolve())):
                raise RuntimeError('HANDOFF_PRIVATE_STATE_NOT_SHARED_EXPORT')
            return {'localPosixOnly': True}
        check('PRIVATE_STORAGE', private)
        def mounted_export():
            # Reuse only the original storage adapter's owned fresh probe and
            # mounted-view readback. No chmod/chown or existing data repair.
            directory = Path(control_root) / 'handoff-mount-preflight'
            with cache().PrivateTree(directory, create=True):
                pass
            storage = load('_handoff_preserved_export_storage', RECOVERY / 'gcube-storage-fix-v1/storage.py')
            session = storage.StorageSession.create(pwd.getpwuid(1000), base=directory, export_root=Path(export_root))
            facts = session.preflight()
            if facts.get('status') != 'PASS' or facts.get('mountedViewReadbackVerified') is not True:
                raise RuntimeError('HANDOFF_STORAGE_EXPORT_READBACK_REQUIRED')
            return {'mountedReadWriteVerified': True, 'externalDownloadVerified': False}
        check('STORAGE_EXPORT_MOUNT', mounted_export)
        def dependencies():
            return dependency_facts(export_root=export_root)
        check('RENDER_DEPENDENCIES', dependencies)
        def reserve():
            if shutil.disk_usage(control_root).free < 2 * 1024**3:
                raise RuntimeError('HANDOFF_PRIVATE_DISK_RESERVE_REQUIRED')
            stat = os.statvfs('/dev/shm')
            if stat.f_frsize * stat.f_blocks < 2 * 1024**3:
                raise RuntimeError('HANDOFF_TWO_GIB_SHARED_MEMORY_REQUIRED')
        check('DISK_AND_SHARED_MEMORY', reserve)
        def common_storage():
            original = lease_helper()
            path = Path(original.storage.PRIVATE_BASE)
            info = path.lstat()
            if (any(p.is_symlink() for p in (path, *path.parents)) or not stat.S_ISDIR(info.st_mode)
                    or info.st_uid != 1000 or info.st_gid != 1000 or stat.S_IMODE(info.st_mode) != 0o700):
                raise RuntimeError('HANDOFF_ORIGINAL_LEASE_PRIVATE_DIRECTORY_REQUIRED')
        check('ORIGINAL_COMMON_LEASE_PRIVATE_STORAGE', common_storage)
        # This is the existing liveness/hardware service, not a new basic GPU
        # test. Its strict public report is still rechecked by GateController.
        runtime = load('_handoff_preserved_health_runtime', RECOVERY / 'production-studio-mvp-v1/studio_runtime.py')
        check('EXISTING_PHYSICAL_GPU_HEALTH', runtime._health)
        timing = duration_contract(plan)
        result = {'checks': checks, 'renderAllowed': all(row['status'] == 'PASS' for row in checks),
                'gpuRenderingVerified': False, 'frames': timing['totalFrames'], 'scenes': len(plan.get('runtime', {}).get('segments', [])),
                'scope': PROFILE, 'hardwareCaptureNotYetPerformed': True}
        if timing['durationSeconds'] == 10:
            result['durationSeconds'] = 10
        return result

    def start_studio_job(self, plan, profile, approval_path, audio_spec, request_id, *, control_root, export_root):
        self._verify(plan, profile)
        timing = duration_contract(plan)
        if audio_spec != {'enabled': False} or not REQUEST_ID.fullmatch(str(request_id)):
            raise RuntimeError('HANDOFF_SILENT_OWNER_START_REQUIRED')
        control_root, export_root, approval_path = map(Path, (control_root, export_root, approval_path))
        expected = control_root / 'approvals' / request_id / 'authorization.json'
        if approval_path != expected:
            raise RuntimeError('HANDOFF_PRIVATE_APPROVAL_PATH_REQUIRED')
        with cache().PrivateTree(approval_path.parent) as private:
            approval = private.json(approval_path.name)
        approval_limit(approval, plan, self.image_digest)
        if not self.preflight(plan, profile, control_root=control_root, export_root=export_root)['renderAllowed']:
            raise RuntimeError('HANDOFF_PREFLIGHT_BLOCKED')
        job_id = 'studio-' + sha((request_id + sha(canonical(plan))).encode())[:32]
        with cache().PrivateTree(control_root) as private:
            with private.child('handoff-gpu-jobs', create=True) as jobs:
                if (jobs.path / job_id).exists():
                    raise RuntimeError('HANDOFF_EXISTING_JOB_MUST_NOT_RESTART')
                with jobs.child(job_id, create=True) as job:
                    state = {'jobId': job_id, 'state': 'QUEUED', 'phase': 'SOURCE_VERIFY',
                        'totalScenes': len(plan['runtime']['segments']), 'completedScenes': 0,
                        'processedFrames': 0, 'totalFrames': timing['totalFrames'], 'requiresGpu': True,
                        'gpuRenderingVerified': False, 'createdAt': _now()}
                    if timing['durationSeconds'] == 10:
                        state['durationSeconds'] = 10
                    bounded = approval_limit(approval, plan, self.image_digest)
                    state['executionDeadline'] = (datetime.now(timezone.utc) +
                        timedelta(seconds=bounded['maxWallSeconds'])).isoformat()
                    job.write_json('PLAN.json', plan)
                    job.write_json('APPROVAL.json', approval)
                    job.write_json('state.json', state)
                    log = os.open(job.path / 'worker.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                    try:
                        child = subprocess.Popen([sys.executable, str(HERE / 'nvidia_worker.py'),
                            '--job-root', str(job.path), '--plan-sha256', sha(canonical(plan)),
                            '--manifest-file', str(self.manifest_file), '--manifest-sha256', self.source_sha,
                            '--control-root', str(control_root), '--export-root', str(export_root)],
                            stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                            env=_runtime_environment(), start_new_session=True, close_fds=True)
                        fields = Path(f'/proc/{child.pid}/stat').read_text().rsplit(') ', 1)[1].split()
                        state.update(pid=child.pid, processStart=fields[19])
                        job.write_json('state.json', state, replace=True)
                        job.write_json('launch.json', {'pid': child.pid, 'processStart': fields[19]})
                    finally:
                        os.close(log)
        return state

    def studio_status(self, job_id, *, control_root, export_root):
        if not JOB.fullmatch(str(job_id)):
            raise RuntimeError('HANDOFF_JOB_ID_INVALID')
        path = Path(control_root) / 'handoff-gpu-jobs' / job_id
        if not path.exists():
            # Old job records/claims are preserved, not reinterpreted or reset.
            verify_manifest(self.manifest_file, self.source_sha, require_external=True)
            legacy = load('_handoff_preserved_job_status', RECOVERY / 'production-studio-mvp-v1/studio_runtime.py')
            return legacy.studio_status(job_id, control_root=control_root, export_root=export_root)
        with cache().PrivateTree(path) as job:
            state = job.json('state.json')
        if state.get('jobId') != job_id:
            raise RuntimeError('HANDOFF_JOB_STATE_CORRUPT')
        if state.get('state') in {'QUEUED', 'RUNNING'}:
            try:
                fields = Path(f"/proc/{state['pid']}/stat").read_text().rsplit(') ', 1)[1].split()
                alive = fields[19] == state.get('processStart') and fields[0] != 'Z'
            except (OSError, KeyError, IndexError):
                alive = False
            if not alive:
                try:
                    from capture_diagnostics_safe import preserve_before_cleanup
                    preserve_before_cleanup(path)
                except Exception:
                    pass  # The existing liveness response must remain available.
                # Preserve the ACTIVE claim. A deceased supervisor is not proof
                # that every renderer descendant stopped, nor permission for a
                # fresh GPU job. The global inherited lease also remains held
                # by the bounded cleanup supervisor until cleanup is verified.
                return {**state, 'state': 'RUNNING', 'phase': 'UNRESOLVED_CAPTURE_CLEANUP',
                        'errorCode': 'HANDOFF_UNRESOLVED_WORKER_OR_DESCENDANTS'}
        if state.get('state') == 'COMPLETED':
            verify_manifest(self.manifest_file, self.source_sha, require_external=True)
            delivery = load('_handoff_preserved_delivery_verify', RECOVERY / 'production-studio-mvp-v1/studio_delivery.py')
            delivery.verify_export(state['result'], export_root)
        return state

    def start_studio_recovery(self, *args, **kwargs):
        raise RuntimeError('HANDOFF_EXPLICIT_RECOVERY_NOT_SUPPORTED')

    def start_studio_revision(self, *args, **kwargs):
        raise RuntimeError('HANDOFF_REVISION_NOT_SUPPORTED')

