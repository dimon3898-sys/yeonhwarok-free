"""Fresh, authenticated external-recovery evidence before paid production.

A Dropbox-capable class alone is not evidence of a successful backup. This
gate requires an AEAD-authenticated, short-lived receipt created by the real
CPU external-check path. Its media is explicitly synthetic and never confers
NVIDIA/rendering approval or revives an operator budget.
"""
from __future__ import annotations

import hashlib
import json
import time

from stores import BackupError, DropboxStore, OID

SCHEMA = 'WORLD_ENGINE_STUDIO_EXTERNAL_RECOVERY_PROOF_V1'
SCOPE = 'REAL_DROPBOX_API_UPLOAD_DOWNLOAD_FRESH_RESTORE'
TTL_SECONDS = 7 * 24 * 60 * 60
PROVIDER = 'DROPBOX_API_V2'


def require_dropbox_transport(vault):
    # No local-mount flag, subclass, or injected store may admit production.
    # Tests can mock network I/O, but their results remain test evidence only.
    if type(getattr(vault, 'store', None)) is not DropboxStore:
        raise BackupError('DURABILITY_REAL_DROPBOX_TRANSPORT_REQUIRED')
    if vault.store.external_verified is not True:
        raise BackupError('DURABILITY_REAL_DROPBOX_TRANSPORT_REQUIRED')
    return vault.store


def provider_binding(vault):
    store = require_dropbox_transport(vault)
    body = json.dumps({'provider': PROVIDER, 'prefix': store.prefix},
                      sort_keys=True, separators=(',', ':')).encode('ascii')
    return hashlib.sha256(body).hexdigest()


def require_external_proof(vault, proof_id):
    """Download and authenticate a current proof, without starting any job."""
    binding = provider_binding(vault)
    if not isinstance(proof_id, str) or not OID.fullmatch(proof_id):
        raise BackupError('DURABILITY_EXTERNAL_PROOF_REQUIRED')
    proof = vault.load_manifest(proof_id)
    fields = {'schema', 'scope', 'provider', 'providerBindingSHA256',
              'createdUnix', 'expiresUnix', 'checkpointId', 'planSHA256',
              'imageDigest', 'completedScenes', 'restoredScenes',
              'nextIncompleteSceneIds', 'mediaProvenance',
              'externalDownloadVerified', 'freshRestoreVerified',
              'nvidiaRenderingVerified', 'executionAuthorityRestored'}
    if (not isinstance(proof, dict) or set(proof) != fields
            or proof['schema'] != SCHEMA or proof['scope'] != SCOPE
            or proof['provider'] != PROVIDER
            or proof['providerBindingSHA256'] != binding
            or proof['mediaProvenance'] != 'CPU_SYNTHETIC_TEST_ONLY'
            or proof['externalDownloadVerified'] is not True
            or proof['freshRestoreVerified'] is not True
            or proof['nvidiaRenderingVerified'] is not False
            or proof['executionAuthorityRestored'] is not False):
        raise BackupError('DURABILITY_EXTERNAL_PROOF_INVALID')
    now = time.time()
    if (type(proof['createdUnix']) is not int or type(proof['expiresUnix']) is not int
            or proof['createdUnix'] < 0 or proof['createdUnix'] > now + 30
            or proof['expiresUnix'] - proof['createdUnix'] != TTL_SECONDS
            or now >= proof['expiresUnix']):
        raise BackupError('DURABILITY_EXTERNAL_PROOF_EXPIRED')
    if (not isinstance(proof['checkpointId'], str) or not OID.fullmatch(proof['checkpointId'])
            or not isinstance(proof['planSHA256'], str) or not OID.fullmatch(proof['planSHA256'])
            or not isinstance(proof['imageDigest'], str)
            or proof['imageDigest'] != 'sha256:' + 'b' * 64
            or type(proof['completedScenes']) is not int or proof['completedScenes'] != 2
            or proof['restoredScenes'] != 2 or type(proof['restoredScenes']) is not int
            or proof['nextIncompleteSceneIds'] != ['external-probe-1']):
        raise BackupError('DURABILITY_EXTERNAL_PROOF_INVALID')
    # Retained remote checkpoint must still exist and retain honest CPU-only
    # provenance. Authentication is bound to this recovery key by the vault.
    import checkpoint
    saved = vault.load_manifest(proof['checkpointId'])
    if (not isinstance(saved, dict) or saved.get('schema') != checkpoint.SCHEMA or saved.get('testOnly') is not True
            or saved.get('executionAuthorityRestored') is not False
            or saved.get('planSHA256') != proof['planSHA256']
            or saved.get('imageDigest') != proof['imageDigest']
            or checkpoint.sha(saved.get('plan')) != proof['planSHA256']
            or not isinstance(saved.get('scenes'), list) or len(saved['scenes']) != 2
            or any(not isinstance(row, dict)
                   or row.get('segment', {}).get('testOnly') is not True
                   or row.get('segment', {}).get('hardwareVerified') is not False
                   for row in saved['scenes'])):
        raise BackupError('DURABILITY_EXTERNAL_PROOF_CHECKPOINT_INVALID')
    checkpoint._inputs(saved.get('plan'), saved.get('audio'), saved.get('profileId'), False)
    for row in saved['scenes']:
        files = row.get('files')
        if not isinstance(files, list) or not 1 <= len(files) <= 12:
            raise BackupError('DURABILITY_EXTERNAL_PROOF_CHECKPOINT_INVALID')
        for artifact in files:
            if not isinstance(artifact, dict) or set(artifact) != {'name', 'descriptor'}:
                raise BackupError('DURABILITY_EXTERNAL_PROOF_CHECKPOINT_INVALID')
            vault.verify_descriptor(artifact['descriptor'])
    return {'status': 'PASS', 'proofId': proof_id, 'expiresUnix': proof['expiresUnix'],
            'externalStorageRecoveryVerified': True, 'nvidiaRenderingVerified': False}
