"""Explicit CPU-only backup transport proof and fresh-root recovery tools.

This CLI cannot render a production video, start a GPU, restore approvals or
delete an old job. Secrets are private files, never command arguments/output.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

import checkpoint
from preflight import (PROVIDER, SCHEMA, SCOPE, TTL_SECONDS, provider_binding,
                       require_dropbox_transport, require_external_proof)
from stores import BackupError


def _require_account():
    if os.geteuid() != 1000 or os.getegid() != 1000:
        raise BackupError('DURABILITY_UID_GID_1000_REQUIRED')


def _cpu_fixture(base):
    """Three 1s synthetic scenes, two real decoded cached MP4s, no GPU flags."""
    media = base / 'synthetic.mp4'
    try:
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-f', 'lavfi',
            '-i', 'testsrc2=size=64x96:rate=30', '-frames:v', '30', '-c:v', 'libx264',
            '-threads', '1', '-preset', 'ultrafast', '-crf', '18', '-bf', '0',
            '-pix_fmt', 'yuv420p', str(media)], check=True, capture_output=True, timeout=30)
    except Exception:
        raise BackupError('DURABILITY_CPU_PROBE_MEDIA_FAILED') from None
    media.chmod(0o600)
    plan = {'testOnly': True, 'durationSeconds': 3, 'fps': 30, 'totalFrames': 90,
            'resolution': {'width': 64, 'height': 96}, 'aspectRatio': '2:3',
            'renderProfile': {'imageDigest': 'sha256:' + 'b' * 64},
            'sourceManifest': {'sha256': 'c' * 64,
                               'records': [{'kind': 'CPU_SYNTHETIC_STORAGE_PROBE'}]},
            'scenes': [{'sceneId': 'external-probe-' + str(i),
                        'startFrame': i * 30, 'endFrame': (i + 1) * 30} for i in range(3)]}
    audio = {'enabled': False, 'gain': 0.5, 'cues': []}
    private = base / 'probe-source'
    cachemod, compose = checkpoint.modules()['cache'], checkpoint.modules()['compose']
    with cachemod.PrivateTree(private, create=True) as root, root.child('render-v3', create=True) as native:
        with native.child('cache', create=True) as cachetree:
            cache = cachemod.SceneCache(cachetree.path)
            try:
                for index in (0, 2):
                    scene = plan['scenes'][index]
                    key = checkpoint._key(plan, index)
                    attempt = cache.begin(key)
                    shutil.copyfile(media, attempt / 'segment.mp4')
                    (attempt / 'segment.mp4').chmod(0o600)
                    checked = compose.verify_segment(attempt / 'segment.mp4', scene, plan)
                    cache.complete(key, attempt, {**checked, **scene,
                        'path': str(attempt / 'segment.mp4'), 'testOnly': True,
                        'hardwareVerified': False, 'artifacts': ['segment.mp4']})
            finally:
                cache.close()
    return plan, audio, private


def external_check(vault, private_work_root):
    """Real Dropbox roundtrip plus original private-state loss/fresh recovery.

    Only files created inside this invocation's TemporaryDirectory are removed.
    The remote encrypted probe is additive and retained as proof evidence.
    """
    _require_account()
    require_dropbox_transport(vault)
    cachemod = checkpoint.modules()['cache']
    with cachemod.PrivateTree(Path(private_work_root)):
        pass
    with tempfile.TemporaryDirectory(prefix='external-probe-', dir=private_work_root) as temporary:
        base = Path(temporary)
        plan, audio, private = _cpu_fixture(base)
        receipt = checkpoint.Checkpoints(vault, production=False).save(
            plan, audio, 'UNIVERSAL_V3', private, coordinator_root=private / 'render-v3')
        if (receipt['completedScenes'] != 2 or receipt['externalDownloadVerified'] is not True
                or receipt['remotePersistenceVerified'] is not True):
            raise BackupError('DURABILITY_EXTERNAL_PROBE_BACKUP_FAILED')
        # Deliberately remove ONLY this newly created synthetic source to prove
        # restoration cannot depend on retained local private files.
        shutil.rmtree(private)
        restored = checkpoint.restore(vault, receipt['checkpointId'], base / 'fresh-restored',
            expected_plan_sha=checkpoint.sha(plan),
            expected_image_digest=plan['renderProfile']['imageDigest'], production=False)
        if (restored.get('restoreVerified') is not True or restored.get('testOnly') is not True
                or restored.get('completedScenes') != 2
                or restored.get('nextIncompleteSceneIds') != ['external-probe-1']
                or restored.get('externalDownloadVerified') is not True
                or restored.get('executionAuthorityRestored') is not False
                or restored.get('newOperatorApprovalRequired') is not True):
            raise BackupError('DURABILITY_EXTERNAL_PROBE_RESTORE_FAILED')
        created = int(time.time())
        proof = {'schema': SCHEMA, 'scope': SCOPE, 'provider': PROVIDER,
            'providerBindingSHA256': provider_binding(vault),
            'createdUnix': created, 'expiresUnix': created + TTL_SECONDS,
            'checkpointId': receipt['checkpointId'], 'planSHA256': checkpoint.sha(plan),
            'imageDigest': plan['renderProfile']['imageDigest'], 'completedScenes': 2,
            'restoredScenes': 2, 'nextIncompleteSceneIds': ['external-probe-1'],
            'mediaProvenance': 'CPU_SYNTHETIC_TEST_ONLY', 'externalDownloadVerified': True,
            'freshRestoreVerified': True, 'nvidiaRenderingVerified': False,
            'executionAuthorityRestored': False}
        proof_id = vault.save_manifest(proof)
        gate = require_external_proof(vault, proof_id)
        return {**gate, 'checkpointId': receipt['checkpointId'], 'syntheticMedia': True,
                'productionRenderingStarted': False, 'productionApprovalGranted': False}


def list_checkpoints(vault, limit=128):
    _require_account()
    require_dropbox_transport(vault)
    rows = vault.list_receipts(limit=limit)
    result = []
    for row in rows:
        manifest = row['manifest']
        if manifest.get('schema') != 'WORLD_ENGINE_STUDIO_DURABLE_RECEIPT_V1':
            raise BackupError('DURABILITY_RECEIPT_SCHEMA_INVALID')
        saved = vault.load_manifest(manifest['checkpointId'])
        if (saved.get('schema') != checkpoint.SCHEMA
                or saved.get('planSHA256') != manifest['planSHA256']
                or saved.get('testOnly') is not manifest['testOnly']
                or not isinstance(saved.get('scenes'), list)
                or len(saved['scenes']) != manifest['completedScenes']):
            raise BackupError('DURABILITY_RECEIPT_CHECKPOINT_MISMATCH')
        # No Scene JSON, source paths, auth state or token values are printed.
        result.append({**{key: manifest[key] for key in ('checkpointId', 'planSHA256',
            'completedScenes', 'createdUnixNs', 'testOnly')},
            'audioSHA256': saved.get('audioSHA256'), 'profileId': saved.get('profileId'),
            'imageDigest': saved.get('imageDigest')})
    result.sort(key=lambda item: (item['planSHA256'], -item['completedScenes'], -item['createdUnixNs']))
    return {'status': 'PASS', 'checkpoints': result,
            'nvidiaRenderingVerified': False, 'executionAuthorityRestored': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    probe = sub.add_parser('external-check', help='free CPU/Dropbox recovery proof, no GPU')
    probe.add_argument('--private-work-root', required=True)
    listing = sub.add_parser('list-checkpoints', help='authenticated receipt metadata only')
    listing.add_argument('--limit', type=int, default=128)
    restore = sub.add_parser('restore', help='CPU-only restore into a fresh private Studio root')
    restore.add_argument('--checkpoint-id', required=True)
    restore.add_argument('--state-root', required=True)
    restore.add_argument('--plan-sha256', required=True)
    restore.add_argument('--image-digest', required=True)
    args = parser.parse_args(argv)
    try:
        _require_account()
        from durable_backend import make_vault_from_env
        vault = make_vault_from_env()
        require_dropbox_transport(vault)
        if args.command == 'external-check':
            result = external_check(vault, args.private_work_root)
        elif args.command == 'list-checkpoints':
            if not 1 <= args.limit <= 256:
                raise BackupError('DURABILITY_RECEIPT_LIMIT_INVALID')
            result = list_checkpoints(vault, args.limit)
        else:
            result = checkpoint.restore(vault, args.checkpoint_id, args.state_root,
                expected_plan_sha=args.plan_sha256, expected_image_digest=args.image_digest,
                production=True)
            result.update({'status': 'PASS',
                'restoredSceneJSON': str(Path(args.state_root) / 'production' / 'PLAN.json'),
                'restoredAudioSettings': str(Path(args.state_root) / 'production' / 'AUDIO.json'),
                'productionRenderingStarted': False})
        print(json.dumps(result, sort_keys=True, separators=(',', ':')))
        return 0
    except Exception as error:
        code = getattr(error, 'code', str(error))
        if not isinstance(code, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{3,100}', code):
            code = 'DURABILITY_CPU_OPERATION_FAILED'
        print(json.dumps({'status': 'BLOCKED', 'errorCode': code,
                          'productionRenderingStarted': False}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
