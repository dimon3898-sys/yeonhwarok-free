#!/usr/bin/env python3
"""Free proof-only adapter for the already built Dropbox offline image.

No image is built/pushed and no GPU/production render is requested. The frozen
helper is reused for immutable pull, protected parent/dependency verification,
private Secret mounting, OAuth refresh and encrypted fresh-process restore.
Only allowlisted, bounded, non-secret proof fields enter this candidate branch.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
NAMESPACE = 'world-simulation-shorts-engine/recovery/studio-dropbox-mobile-v1'
BRANCH = 'development/dropbox-mobile-connect-v1-20261018'
WORKFLOW = '.github/workflows/studio-dropbox-mobile-v1.yml'
OFFLINE = HERE.parent / 'studio-dropbox-offline-v1' / 'ci.py'
OFFLINE_CI_SHA = 'f8c269c1940ad77211e44e67b5fde95d26c822055aa0dc2d7eaea2b49d112680'
SOURCE_COMMIT = '86b3a159eec2b3fefc6ee9248e102a61ad34288a'
SOURCE_TAG = 'studio-dropbox-offline-v1-165a348-39100005538-1'
SOURCE_DIGEST = 'sha256:6d2e87fc8fb7f10edc2ebb7f77b5d666e329904b9c37f7f060b289f943bdd9d0'
SOURCE_IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@' + SOURCE_DIGEST
SCHEMA = 'WORLD_ENGINE_MOBILE_DROPBOX_PROOF_V1'
HASH = re.compile(r'[a-f0-9]{64}\Z')
COMMIT = re.compile(r'[a-f0-9]{40}\Z')
CODE = re.compile(r'[A-Z][A-Z0-9_]{1,94}\Z')


def frozen_helper():
    if (OFFLINE.is_symlink() or not OFFLINE.is_file()
            or hashlib.sha256(OFFLINE.read_bytes()).hexdigest() != OFFLINE_CI_SHA):
        raise RuntimeError('MOBILE_FROZEN_OFFLINE_HELPER_SHA_MISMATCH')
    spec = importlib.util.spec_from_file_location('_mobile_frozen_offline_ci', OFFLINE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Rebind only in-memory evidence/branch settings. The frozen helper's HERE
    # remains its original source directory for exact generated manifest checks.
    module.ci.BRANCH = BRANCH
    module.ci.NAMESPACE = NAMESPACE
    module.ci.WORKFLOW = WORKFLOW
    module.location = location
    module.ci.location = location
    return module


def location():
    root = Path(os.environ.get('RUNNER_TEMP', '/tmp')) / 'studio-dropbox-mobile-proof-v1'
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


@contextmanager
def original_image_source_binding():
    """Verify old image against its own source, never claim it is the new UI.

    Frozen image_hashes/generated_manifest intentionally use GITHUB_SHA. Scope
    that variable only while executing their old-image verification. The live
    mobile request commit is separately retained as requestSourceCommit.
    """
    names = ('GITHUB_SHA', 'RESULT_PUBLISHED_TAG', 'RESULT_PUBLISHED_DIGEST')
    previous = {name: os.environ.get(name) for name in names}
    os.environ.update(GITHUB_SHA=SOURCE_COMMIT, RESULT_PUBLISHED_TAG=SOURCE_TAG,
                      RESULT_PUBLISHED_DIGEST=SOURCE_DIGEST)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def preflight(helper):
    value = helper.ci.state()
    if not COMMIT.fullmatch(os.environ.get('GITHUB_SHA', '')):
        raise RuntimeError('MOBILE_REQUEST_SOURCE_COMMIT_REQUIRED')
    value.update(builder=helper.ci.require_free_runner(), requestSourceCommit=os.environ['GITHUB_SHA'],
                 sourceImage=SOURCE_IMAGE, imageSourceCommit=SOURCE_COMMIT,
                 imageBuildRequested=False, imagePushRequested=False)
    helper.ci.save(value)


def scan(helper):
    # Reuse the old helper's verified scanner acquisition and unchanged old
    # source scan. The new validator independently scans EVERY additive file
    # with the exact same default scanner; it may classify only pinned vendor
    # function names, never skip a file or relax a scanner rule.
    helper.ci.secret_scan()
    scanner = location() / 'scanner' / 'gitleaks'
    result = helper.ci.run([__import__('sys').executable, '-B', str(HERE / 'validate.py'),
                            '--scanner', str(scanner)], timeout=180, check=False)
    try:
        document = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError('MOBILE_ADDITIVE_SOURCE_VALIDATION_REQUIRED') from None
    report = document.get('secretScan', {}) if isinstance(document, dict) else {}
    if (result.returncode or document.get('status') != 'PASS'
            or type(document.get('files')) is not int or document['files'] <= 0
            or document.get('protectedChanges') != 0 or document.get('gpuExecuted') is not False
            or report.get('status') != 'PASS' or report.get('findings') != 0
            or type(report.get('rawFindings')) is not int
            or type(report.get('classifiedVendorFunctionNames')) is not int
            or not 0 <= report['rawFindings'] <= 100
            or report['rawFindings'] != report['classifiedVendorFunctionNames']):
        raise RuntimeError('MOBILE_ADDITIVE_SOURCE_VALIDATION_REQUIRED')
    value = helper.ci.state()
    value['secretScan'] = {key: report[key] for key in ('status', 'findings', 'rawFindings',
                                                       'classifiedVendorFunctionNames')}
    value['additiveSourceFilesVerified'] = document['files']
    helper.ci.save(value)


def pull(helper):
    value = helper.ci.state()
    if value.get('builder', {}).get('status') != 'PASS':
        raise RuntimeError('MOBILE_FREE_RUNNER_REQUIRED')
    if value.get('secretScan', {}).get('status') != 'PASS':
        raise RuntimeError('MOBILE_SECRET_SCAN_REQUIRED')
    with original_image_source_binding():
        helper.pull()
    value = helper.ci.state()
    if (value.get('imageReference') != SOURCE_IMAGE or value.get('imageDigest') != SOURCE_DIGEST
            or value.get('pullVerified') is not True or value.get('protectedParentUnchanged') is not True
            or value.get('inheritedDependenciesChanged') is not False
            or value.get('imageHashes', {}).get('sourceCommit') != SOURCE_COMMIT):
        raise RuntimeError('MOBILE_FROZEN_IMAGE_VERIFICATION_FAILED')
    value['proofPrerequisitesVerified'] = True
    helper.ci.save(value)


def ui(helper):
    value = helper.ci.state()
    if value.get('proofPrerequisitesVerified') is not True:
        raise RuntimeError('MOBILE_IMMUTABLE_SOURCE_PROTECTION_REQUIRED')
    dest = '/opt/world-engine-studio-dropbox-mobile'
    base = ['docker', 'run', '--rm', '--network=none', '--user=1000:1000', '--read-only',
            '--memory=4g', '--cpus=2', '--pids-limit=512', '--restart=no', '--shm-size=2g',
            '--cap-drop=ALL', '--security-opt=no-new-privileges', '--tmpfs', '/tmp:rw,mode=1777',
            '--mount', 'type=bind,source=' + str(HERE) + ',target=' + dest + ',readonly',
            '--env', 'HOME=/tmp', '--env', 'TMPDIR=/tmp',
            '--env', 'NODE_PATH=/opt/rtx-package/repo/cinematic-world-map/node_modules',
            '--env', 'CHROMIUM_EXECUTABLE=/usr/bin/chromium',
            '--entrypoint=/usr/local/bin/node', SOURCE_IMAGE]
    for script in ('test_core.mjs', 'mobile_probe.mjs', 'vendor_probe.mjs'):
        result = helper.ci.run(base + [dest + '/tests/' + script], timeout=180, check=False)
        # These tests have no provider credentials and make no external request.
        print(helper.ci.bounded(result.stdout))
        print(helper.ci.bounded(result.stderr), file=__import__('sys').stderr)
        if result.returncode:
            raise RuntimeError('MOBILE_CPU_BROWSER_PROBE_FAILED')
    value['mobileCpuTestsPassed'] = True
    helper.ci.save(value)


def external(helper):
    value = helper.ci.state()
    if value.get('proofPrerequisitesVerified') is not True:
        raise RuntimeError('MOBILE_IMMUTABLE_SOURCE_PROTECTION_REQUIRED')
    # This existing implementation owns Secret files, OAuth/network, encryption,
    # metadata scope check, restore and cleanup; none are reimplemented here.
    helper.external()


def identifiers():
    run, attempt = os.environ.get('GITHUB_RUN_ID', ''), os.environ.get('GITHUB_RUN_ATTEMPT', '')
    if not re.fullmatch(r'[1-9][0-9]{0,19}', run) or not re.fullmatch(r'[1-9][0-9]{0,7}', attempt):
        raise RuntimeError('MOBILE_PROOF_RUN_ID_REQUIRED')
    return int(run), int(attempt)


def safe_proof(value, outcomes):
    run, attempt = identifiers()
    proof = {'schema': SCHEMA, 'status': 'BLOCKED', 'reasonCode': 'MOBILE_PROOF_NOT_COMPLETED',
             'runId': run, 'attempt': attempt, 'sourceImage': SOURCE_IMAGE,
             'imageSourceCommit': SOURCE_COMMIT, 'offlineTokenRefreshVerified': False,
             'metadataReadVerified': False, 'externalStorageRecoveryVerified': False,
             'gpuExecuted': False, 'productionRenderingStarted': False}
    commit = value.get('requestSourceCommit')
    if COMMIT.fullmatch(str(commit)):
        proof['requestSourceCommit'] = commit
    report = value.get('externalDurability', {})
    complete = (not value.get('failedPhase') and value.get('proofPrerequisitesVerified') is True
                and value.get('pullVerified') is True and value.get('protectedParentUnchanged') is True
                and value.get('inheritedDependenciesChanged') is False
                and value.get('imageReference') == SOURCE_IMAGE
                and value.get('imageDigest') == SOURCE_DIGEST
                and value.get('imageHashes', {}).get('sourceCommit') == SOURCE_COMMIT
                and value.get('secretScan', {}).get('status') == 'PASS'
                and report.get('status') == 'PASS'
                and all(report.get(name) is True for name in ('offlineTokenRefreshVerified',
                        'metadataReadVerified', 'externalStorageRecoveryVerified'))
                and report.get('gpuExecuted') is False
                and report.get('productionRenderingStarted') is False
                and report.get('productionApprovalGranted') is False
                and report.get('secretFilesRemoved') is True
                and report.get('syntheticMedia') is True
                and all(HASH.fullmatch(str(report.get(name))) for name in ('proofId', 'checkpointId'))
                and type(report.get('expiresUnix')) is int and report['expiresUnix'] > int(time.time())
                and not any(item in ('failure', 'cancelled', 'skipped') for item in outcomes.values())
                and all(outcomes.get(name) == 'success' for name in ('preflight', 'scan', 'pull', 'external')))
    if complete:
        proof.update(status='PASS', reasonCode='MOBILE_DROPBOX_CPU_RECOVERY_VERIFIED',
                     offlineTokenRefreshVerified=True, metadataReadVerified=True,
                     externalStorageRecoveryVerified=True, proofId=report['proofId'],
                     checkpointId=report['checkpointId'], expiresUnix=report['expiresUnix'])
    elif report.get('reasonCode') == 'OFFLINE_EXTERNAL_SECRETS_NOT_BOUND':
        proof['reasonCode'] = 'MOBILE_DROPBOX_SECRETS_NOT_BOUND'
    elif value.get('failedPhase') or any(item == 'failure' for item in outcomes.values()):
        proof.update(status='FAIL', reasonCode='MOBILE_CPU_PROOF_FAILED')
    else:
        code = report.get('reasonCode', value.get('reasonCode', 'MOBILE_PROOF_NOT_COMPLETED'))
        proof['reasonCode'] = code if CODE.fullmatch(str(code)) else 'MOBILE_CPU_PROOF_FAILED'
    return proof


def persist(helper):
    outcomes = json.loads(os.environ.get('RESULT_STEP_OUTCOMES', '{}'))
    allowed = {'preflight', 'scan', 'pull', 'external'}
    if (not isinstance(outcomes, dict) or set(outcomes) - allowed
            or any(item not in ('success', 'failure', 'cancelled', 'skipped', '') for item in outcomes.values())):
        raise RuntimeError('MOBILE_SAFE_STEP_OUTCOMES_REQUIRED')
    document = safe_proof(helper.ci.state(), outcomes)
    raw = (json.dumps(document, indent=2, sort_keys=True) + '\n').encode()
    if len(raw) > 8192:
        raise RuntimeError('MOBILE_BOUNDED_PROOF_REQUIRED')
    relative = Path(NAMESPACE) / 'runs' / (str(document['runId']) + '-' + str(document['attempt']))
    artifact = str(relative / 'proof.json')
    sums = str(relative / 'SHA256SUMS')
    payload = {artifact: raw, sums: (hashlib.sha256(raw).hexdigest() + '  proof.json\n').encode()}
    helper.ci.run(['git', 'fetch', '--filter=blob:none', 'origin', BRANCH], timeout=180)
    helper.ci.run(['git', 'switch', '--detach', 'FETCH_HEAD'])
    for name, body in payload.items():
        destination = REPO / name
        if destination.exists() or destination.is_symlink():
            raise RuntimeError('MOBILE_EXISTING_PROOF_OVERWRITE_FORBIDDEN')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
    helper.ci.run(['git', 'config', 'user.name', 'github-actions[bot]'])
    helper.ci.run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'])
    helper.ci.run(['git', 'add', '--', *sorted(payload)])
    staged = helper.ci.run(['git', 'diff', '--cached', '--name-only']).stdout.splitlines()
    if sorted(staged) != sorted(payload):
        raise RuntimeError('MOBILE_BOUNDED_PROOF_COMMIT_REQUIRED')
    helper.ci.run(['git', 'diff', '--cached', '--check'])
    helper.ci.run(['git', 'commit', '-m', 'docs(dropbox): persist mobile CPU recovery proof [skip ci]'])
    helper.ci.run(['git', 'push', 'origin', 'HEAD:refs/heads/' + BRANCH], timeout=180)
    print(json.dumps(document, sort_keys=True))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('preflight', 'scan', 'pull', 'ui', 'external', 'persist'))
    args = parser.parse_args(argv)
    helper = frozen_helper()
    try:
        globals()[args.phase](helper)
    except Exception:
        value = helper.ci.state()
        # Raw exception/HTTP output can contain secrets; only a fixed code leaves.
        value.update(failedPhase=args.phase, reasonCode='MOBILE_CPU_PROOF_FAILED')
        helper.ci.save(value)
        print(json.dumps({'status': 'FAIL', 'reasonCode': 'MOBILE_CPU_PROOF_FAILED',
                          'phase': args.phase, 'gpuExecuted': False}))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
