#!/usr/bin/env python3
"""Fixed CPU-only, read-only reuse of the approved Dropbox recovery proof.

This developer verification driver is not a production bootstrap stage. It can
restore only the already-approved synthetic checkpoint and never publishes a
checkpoint, restores execution authority, or starts a renderer. Separate Docker
containers must run ``restore`` and ``verify`` against the same private volume.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

PROOF_ID = '08398705cd4ffb90a7f68a26ee6f65a121c5efa62ad4f854c1aa50ea371b55a7'
CHECKPOINT_ID = '9fa8bdd8b3c4489409dc82c568c17e8a1e9646cb605d14eda5be534fc9d29796'
IMAGE_DIGEST = 'sha256:' + 'b' * 64
PARENT_ROOT = Path('/tmp/world-engine-production-restart')
STATE_ROOT = PARENT_ROOT / 'restore'
STATE_FILE = 'RESTART_PROBE.json'
CLAIM_FILE = 'SYNTHETIC-UNCHANGED-CLAIM.json'
CLAIM = {'schema': 'CPU_RESTART_PROBE_INERT_CLAIM_V1',
         'testOnly': True, 'executionAuthorityRestored': False,
         'renderAllowed': False, 'gpuExecuted': False}
CODE = re.compile(r'[A-Z][A-Z0-9_]{2,95}\Z')


def fail(code):
    raise RuntimeError(code)


def readonly_transport(store):
    """Keep the frozen exact DropboxStore type while denying remote mutation."""
    original = store._request
    counters = {'downloads': 0, 'remoteWrites': 0}

    def denied(*args, **kwargs):
        counters['remoteWrites'] += 1
        fail('PRODUCTION_RESTART_REMOTE_WRITE_FORBIDDEN')

    def request(endpoint, *, argument=None, data=None):
        if endpoint != 'download' or data is not None:
            return denied()
        counters['downloads'] += 1
        return original(endpoint, argument=argument, data=data)

    store._request = request
    store.put = denied
    store.publish_receipt = denied
    return counters


def inventory(cachemod, root):
    """Hash all retained bytes/metadata without following links or writing."""
    rows = []

    def walk(tree, prefix):
        for name in sorted(os.listdir(tree.fd)):
            info = os.stat(name, dir_fd=tree.fd, follow_symlinks=False)
            relative = prefix + name
            metadata = {'path': relative, 'uid': info.st_uid, 'gid': info.st_gid,
                        'mode': stat.S_IMODE(info.st_mode)}
            if stat.S_ISDIR(info.st_mode):
                rows.append({**metadata, 'kind': 'directory'})
                with tree.child(name) as child:
                    walk(child, relative + '/')
            elif stat.S_ISREG(info.st_mode):
                facts = tree.hash_file(name)
                rows.append({**metadata, 'kind': 'file', 'sha256': facts['sha256'],
                             'bytes': facts['bytes']})
            else:
                fail('PRODUCTION_RESTART_UNSAFE_RETAINED_PATH')

    with cachemod.PrivateTree(root) as tree:
        walk(tree, '')
    body = json.dumps(rows, sort_keys=True, separators=(',', ':')).encode('ascii')
    return hashlib.sha256(body).hexdigest()


def container_identity():
    # A hash is sufficient to require distinct Docker hostnames without exposing
    # any hostname value. CI also records the actual distinct container IDs.
    return hashlib.sha256(os.uname().nodename.encode('utf-8')).hexdigest()


def approved_snapshot(old, vault):
    """Authenticate the existing, unexpired proof and its exact checkpoint."""
    gate = old.preflight.require_external_proof(vault, PROOF_ID)
    proof = vault.load_manifest(PROOF_ID)
    if (gate.get('status') != 'PASS' or gate.get('proofId') != PROOF_ID
            or gate.get('externalStorageRecoveryVerified') is not True
            or gate.get('nvidiaRenderingVerified') is not False
            or proof.get('checkpointId') != CHECKPOINT_ID
            or proof.get('imageDigest') != IMAGE_DIGEST):
        fail('PRODUCTION_RESTART_APPROVED_PROOF_REQUIRED')
    saved = vault.load_manifest(CHECKPOINT_ID)
    if (saved.get('testOnly') is not True
            or saved.get('executionAuthorityRestored') is not False
            or saved.get('planSHA256') != proof.get('planSHA256')
            or saved.get('imageDigest') != IMAGE_DIGEST):
        fail('PRODUCTION_RESTART_SYNTHETIC_BINDING_REQUIRED')
    return proof


def operation(stage, old):
    if stage not in {'restore', 'verify'}:
        fail('PRODUCTION_RESTART_FIXED_STAGE_REQUIRED')
    if os.geteuid() != 1000 or os.getegid() != 1000:
        fail('PRODUCTION_RESTART_UID_GID_1000_REQUIRED')
    cachemod = old.checkpoint.modules()['cache']
    # CI creates only this new, local, UID1000/0700 test-volume directory. No
    # caller-supplied destination or existing production root is accepted.
    with cachemod.PrivateTree(PARENT_ROOT):
        pass
    vault = old.backend.make_vault_from_env()
    old.preflight.require_dropbox_transport(vault)
    counters = readonly_transport(vault.store)
    proof = approved_snapshot(old, vault)
    bindings = {'checkpointId': CHECKPOINT_ID, 'planSHA256': proof['planSHA256'],
                'imageDigest': IMAGE_DIGEST, 'proofId': PROOF_ID}
    identity = container_identity()
    if stage == 'restore':
        if STATE_ROOT.exists() or STATE_ROOT.is_symlink():
            fail('PRODUCTION_RESTART_FRESH_PROBE_ROOT_REQUIRED')
        result = old.checkpoint.restore(vault, CHECKPOINT_ID, STATE_ROOT,
            expected_plan_sha=proof['planSHA256'], expected_image_digest=IMAGE_DIGEST,
            production=False)
        if (result.get('restoreVerified') is not True or result.get('testOnly') is not True
                or result.get('completedScenes') != 2
                or result.get('nextIncompleteSceneIds') != ['external-probe-1']
                or result.get('executionAuthorityRestored') is not False
                or result.get('newOperatorApprovalRequired') is not True
                or result.get('externalDownloadVerified') is not True):
            fail('PRODUCTION_RESTART_FRESH_RESTORE_NOT_VERIFIED')
        with cachemod.PrivateTree(STATE_ROOT) as tree, tree.child('production') as production:
            production.write_json(CLAIM_FILE, CLAIM)
        retained = inventory(cachemod, STATE_ROOT)
        with cachemod.PrivateTree(PARENT_ROOT) as tree:
            tree.write_json(STATE_FILE, {**bindings, 'schema': 'CPU_CONTAINER_RESTART_PROBE_V1',
                'containerIdentitySHA256': identity, 'retainedTreeSHA256': retained,
                'testOnly': True, 'executionAuthorityRestored': False})
        same_bytes, distinct = False, False
    else:
        with cachemod.PrivateTree(PARENT_ROOT) as tree:
            receipt = tree.json(STATE_FILE)
        if (receipt.get('schema') != 'CPU_CONTAINER_RESTART_PROBE_V1'
                or any(receipt.get(name) != value for name, value in bindings.items())
                or receipt.get('testOnly') is not True
                or receipt.get('executionAuthorityRestored') is not False):
            fail('PRODUCTION_RESTART_RECEIPT_BINDING_MISMATCH')
        if receipt.get('containerIdentitySHA256') == identity:
            fail('PRODUCTION_RESTART_DISTINCT_CONTAINER_REQUIRED')
        before = inventory(cachemod, STATE_ROOT)
        if before != receipt.get('retainedTreeSHA256'):
            fail('PRODUCTION_RESTART_RETAINED_TREE_CHANGED')
        result = old.startup_restore._verify_existing(vault, CHECKPOINT_ID,
            proof['planSHA256'], IMAGE_DIGEST, STATE_ROOT, production=False)
        if (result.get('restoreVerified') is not True or result.get('testOnly') is not True
                or result.get('completedScenes') != 2
                or result.get('executionAuthorityRestored') is not False
                or result.get('newOperatorApprovalRequired') is not True):
            fail('PRODUCTION_RESTART_EXISTING_RESTORE_NOT_VERIFIED')
        with cachemod.PrivateTree(STATE_ROOT) as tree, tree.child('production') as production:
            if production.json(CLAIM_FILE) != CLAIM:
                fail('PRODUCTION_RESTART_INERT_CLAIM_CHANGED')
        retained = inventory(cachemod, STATE_ROOT)
        if retained != before:
            fail('PRODUCTION_RESTART_VERIFICATION_MODIFIED_CACHE')
        same_bytes, distinct = True, True
    if counters['remoteWrites'] != 0 or counters['downloads'] < 1:
        fail('PRODUCTION_RESTART_READ_ONLY_DOWNLOAD_REQUIRED')
    return {**bindings, 'schema': 'WORLD_ENGINE_CPU_CONTAINER_RESTART_RESULT_V1',
        'status': 'PASS', 'stage': stage, 'completedScenes': 2,
        'nextIncompleteSceneIds': ['external-probe-1'], 'retainedTreeSHA256': retained,
        'containerIdentitySHA256': identity, 'distinctContainerVerified': distinct,
        'retainedBytesAndClaimUnchanged': same_bytes, 'remoteWrites': 0,
        'authenticatedDownloads': counters['downloads'], 'syntheticMedia': True,
        'executionAuthorityRestored': False, 'newOperatorApprovalRequired': True,
        'renderAllowed': False, 'productionRenderingStarted': False, 'gpuExecuted': False}


def main(argv=None):
    try:
        arguments = list(sys.argv[1:] if argv is None else argv)
        if len(arguments) != 1 or arguments[0] not in {'restore', 'verify'}:
            fail('PRODUCTION_RESTART_FIXED_STAGE_REQUIRED')
        import production_runtime
        result = operation(arguments[0], production_runtime.install())
        print(json.dumps(result, sort_keys=True, separators=(',', ':')), flush=True)
        return 0
    except Exception as error:
        code = getattr(error, 'code', str(error))
        if not isinstance(code, str) or not CODE.fullmatch(code):
            code = 'PRODUCTION_RESTART_CPU_PROBE_FAILED'
        print(json.dumps({'status': 'FAIL', 'reasonCode': code,
                          'renderAllowed': False, 'productionRenderingStarted': False,
                          'gpuExecuted': False}, sort_keys=True), flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
