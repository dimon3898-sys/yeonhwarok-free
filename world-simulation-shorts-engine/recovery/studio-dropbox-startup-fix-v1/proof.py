#!/usr/bin/env python3
"""Additive, free CPU proof using the existing immutable image and Secrets.

No backup engine, OAuth, encryption, renderer, image or approved source changes.
The frozen proof container's working directory and key text encoding are adapted.
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
import sys

from adapter import IMAGE, DEST, PYTHON, adapt
from key_encoding import canonical_key

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASE = '1cd8ea4565238bd7d4c8c72c6374f78557b2dc1d'
BRANCH = 'development/dropbox-startup-fix-20261018'
NAMESPACE = 'world-simulation-shorts-engine/recovery/studio-dropbox-startup-fix-v1'
WORKFLOW = '.github/workflows/studio-dropbox-startup-fix-v1.yml'
MOBILE = HERE.parent / 'studio-dropbox-mobile-v1'
MOBILE_CI_SHA = '310ee9363f09449d1a8655d4ab31ffc2c14089b9d796e8a00128f9cf9e323807'
CODE = re.compile(r'[A-Z][A-Z0-9_]{2,95}\Z')


def location():
    path = Path(os.environ.get('RUNNER_TEMP', '/tmp')) / 'studio-dropbox-startup-proof-v1'
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def load_mobile():
    path = MOBILE / 'proof_ci.py'
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != MOBILE_CI_SHA:
        raise RuntimeError('STARTUP_FROZEN_MOBILE_HELPER_CHANGED')
    spec = importlib.util.spec_from_file_location('_startup_frozen_mobile', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.BRANCH, module.NAMESPACE, module.WORKFLOW = BRANCH, NAMESPACE, WORKFLOW
    module.location = location
    return module


def sources():
    manifest = json.loads((HERE / 'SOURCE_FILES.json').read_bytes())
    if manifest.get('protectedBase') != BASE or manifest.get('schema') != 'WORLD_ENGINE_DROPBOX_STARTUP_FIX_SOURCES_V1':
        raise RuntimeError('STARTUP_SOURCE_MANIFEST_REQUIRED')
    for entry in manifest['files']:
        name, digest = entry['path'], entry['sha256']
        path = HERE / name
        if (Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink()
                or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest):
            raise RuntimeError('STARTUP_SOURCE_SHA_MISMATCH')
    if hashlib.sha256((REPO / WORKFLOW).read_bytes()).hexdigest() != manifest['workflowSha256']:
        raise RuntimeError('STARTUP_WORKFLOW_SHA_MISMATCH')
    mobile_definition = json.loads((MOBILE / 'MOBILE_FILES.json').read_bytes())
    for name, digest in mobile_definition['files'].items():
        if hashlib.sha256((MOBILE / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError('STARTUP_PROTECTED_MOBILE_SOURCE_CHANGED')
    import subprocess
    changed = subprocess.run(['git', 'diff', '--name-only', BASE, '--'], cwd=REPO,
                             check=True, capture_output=True, text=True).stdout.splitlines()
    if any(not (name.startswith(NAMESPACE + '/') or name == WORKFLOW) for name in changed):
        raise RuntimeError('STARTUP_PROTECTED_SOURCE_CHANGED')
    return {'status': 'PASS', 'newFiles': len(manifest['files']) + 2, 'protectedChanges': 0}


def preflight(mobile, helper):
    sources()
    mobile.preflight(helper)
    value = helper.ci.state()
    value.update(startupProfile='DROPBOX_CPU_PROOF_FIXED_IMPORT_DIRECTORY_V1',
                 imageBuildRequested=False, imagePushRequested=False,
                 existingSecretsChanged=False, protectedSourceChanged=False)
    helper.ci.save(value)


def scan(mobile, helper):
    # Same pinned default scanner acquisition, all new files, no exceptions.
    previous = helper.ci.HERE
    try:
        helper.ci.HERE = HERE
        report = helper.ci.secret_scan()
    finally:
        helper.ci.HERE = previous
    value = helper.ci.state()
    value['secretScan'] = report
    helper.ci.save(value)


def pull(mobile, helper):
    value = helper.ci.state()
    if value.get('builder', {}).get('status') != 'PASS' or value.get('secretScan', {}).get('status') != 'PASS':
        raise RuntimeError('STARTUP_PREFLIGHT_AND_SCAN_REQUIRED')
    # Pull just the already audited immutable candidate, not its parent again.
    # This verifies its registry config, offline payload and protected parent manifests.
    with mobile.original_image_source_binding():
        helper.ci.pull()
    value = helper.ci.state()
    hashes = value.get('imageHashes', {})
    if (value.get('imageReference') != IMAGE or value.get('pullVerified') is not True
            or hashes.get('sourceCommit') != mobile.SOURCE_COMMIT
            or hashes.get('parentDurability', {}).get('status') != 'PASS'):
        raise RuntimeError('STARTUP_IMMUTABLE_SOURCE_VERIFICATION_REQUIRED')
    value.update(proofPrerequisitesVerified=True, protectedParentUnchanged=True,
                 inheritedDependenciesChanged=False, imageBuilt=False, imagePushed=False,
                 dependencyAuditReusedFromRun=39110576350,
                 verificationScope='SAME_IMMUTABLE_IMAGE_SOURCE_MANIFESTS_NO_DEPENDENCY_MUTATION')
    helper.ci.save(value)


def startup(mobile, helper):
    if helper.ci.state().get('proofPrerequisitesVerified') is not True:
        raise RuntimeError('STARTUP_IMMUTABLE_SOURCE_VERIFICATION_REQUIRED')
    # No credentials or network. Same fixed entry, before/after only Docker cwd.
    entry = DEST + '/offline_entry.py'
    code = ('import runpy,sys;sys.argv=[' + repr(entry) + ',"cli","--help"];'
            'runpy.run_path(' + repr(entry) + ',run_name="__main__")')
    base = ['docker', 'run', '--rm', '--network=none', '--user=1000:1000',
            '--read-only', '--memory=2g', '--cpus=2', '--pids-limit=256',
            '--restart=no', '--cap-drop=ALL', '--security-opt=no-new-privileges',
            '--tmpfs', '/tmp:rw,mode=1777', '--env', 'PYTHONDONTWRITEBYTECODE=1',
            '--entrypoint=' + PYTHON]
    before = helper.ci.run(base + [IMAGE, '-B', '-c', code], check=False)
    after = helper.ci.run(base + ['--workdir=' + DEST, IMAGE, '-B', '-c', code], check=False)
    try:
        first = json.loads(before.stdout.strip().splitlines()[-1])['errorCode']
    except (ValueError, IndexError, KeyError):
        first = 'STARTUP_UNEXPECTED_REPRODUCTION_RESULT'
    report = {'status': 'PASS' if before.returncode == 2 and first == 'DURABILITY_OFFLINE_STARTUP_FAILED' and after.returncode == 0 else 'FAIL',
              'beforeExitCode': before.returncode, 'beforeErrorCode': first,
              'afterExitCode': after.returncode, 'imageUnchanged': True,
              'credentialsUsed': False, 'networkEnabled': False, 'gpuExecuted': False}
    value = helper.ci.state()
    value['startupFix'] = report
    helper.ci.save(value)
    print(json.dumps(report, sort_keys=True))
    if report['status'] != 'PASS':
        raise RuntimeError('STARTUP_EXACT_CONTAINER_REPRODUCTION_REQUIRED')


@contextmanager
def corrected_external_command(helper):
    original = helper.ci.run
    calls = {'corrected': 0}

    def run(command, **kwargs):
        adjusted = adapt(command)
        if adjusted != command:
            calls['corrected'] += 1
        return original(adjusted, **kwargs)

    helper.ci.run = run
    try:
        yield calls
    finally:
        helper.ci.run = original


def external(mobile, helper):
    if helper.ci.state().get('startupFix', {}).get('status') != 'PASS':
        raise RuntimeError('STARTUP_CPU_REPRODUCTION_PASS_REQUIRED')
    # Only this process's copy changes representation; the original GitHub
    # Secret and the decoded recovery key bytes remain unchanged.
    name = 'WORLD_ENGINE_STUDIO_BACKUP_KEY'
    original_key = os.environ.get(name)
    normalized = canonical_key(original_key)
    value = helper.ci.state()
    value['keyEncoding'] = {'canonicalInputForFrozenReader': True,
                            'decodedKeyBytesPreserved': True,
                            'githubSecretChanged': False}
    helper.ci.save(value)
    try:
        os.environ[name] = normalized
        with corrected_external_command(helper) as calls:
            mobile.external(helper)
    finally:
        if original_key is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = original_key
    value = helper.ci.state()
    report = value.get('externalDurability', {})
    value['externalCommandCorrections'] = calls['corrected']
    helper.ci.save(value)
    if calls['corrected'] != 1:
        raise RuntimeError('STARTUP_EXACTLY_ONE_EXTERNAL_COMMAND_REQUIRED')
    if report.get('status') != 'PASS':
        raise RuntimeError('STARTUP_EXTERNAL_PROOF_NOT_VERIFIED')


def persist(mobile, helper):
    original = mobile.safe_proof

    def safe_proof(value, outcomes):
        proof = original(value, outcomes)
        proof['recoveryProfile'] = 'DROPBOX_CPU_PROOF_FIXED_IMPORT_DIRECTORY_V1'
        proof['startupReproductionVerified'] = value.get('startupFix', {}).get('status') == 'PASS'
        proof['externalCommandCorrections'] = value.get('externalCommandCorrections', 0)
        proof['keyMaterialPreserved'] = value.get('keyEncoding', {}).get('decodedKeyBytesPreserved') is True
        proof['existingSecretsChanged'] = False
        if proof['status'] == 'PASS' and (not proof['startupReproductionVerified'] or proof['externalCommandCorrections'] != 1):
            raise RuntimeError('STARTUP_VERIFIED_CORRECTION_REQUIRED')
        if proof['status'] != 'PASS':
            report = value.get('externalDurability', {})
            code = report.get('reasonCode', value.get('reasonCode', 'STARTUP_CPU_PROOF_NOT_COMPLETED'))
            proof['reasonCode'] = code if CODE.fullmatch(str(code)) else 'STARTUP_CPU_PROOF_NOT_COMPLETED'
        return proof

    mobile.safe_proof = safe_proof
    mobile.persist(helper)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('preflight', 'scan', 'pull', 'startup', 'external', 'persist'))
    args = parser.parse_args()
    mobile = load_mobile()
    helper = mobile.frozen_helper()
    try:
        globals()[args.phase](mobile, helper)
        return 0
    except Exception as error:
        # Provider/command text is never serialized. Preserve only known enums.
        code = str(error)
        code = code if CODE.fullmatch(code) else 'STARTUP_CPU_PROOF_PHASE_FAILED'
        value = helper.ci.state()
        value.update(failedPhase=args.phase, reasonCode=code)
        helper.ci.save(value)
        print(json.dumps({'status': 'FAIL', 'phase': args.phase, 'reasonCode': code, 'gpuExecuted': False}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
