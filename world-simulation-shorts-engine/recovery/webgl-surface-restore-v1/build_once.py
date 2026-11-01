#!/usr/bin/env python3
"""One bounded successful WebGL launch-option restoration; no GPU or existing tag write.

The only behavioral change restores --disable-vulkan-surface to the reviewed
launch profile. Its existing manifest/startup hash chain is updated. Capture and
verifier code remain unchanged. Full-image retention reuses the preserved
label355 release helper. All commands/API writes are single attempts.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = 'dimon3898-sys/yeonhwarok-free'
BASE = 'a4e02aad71d7b60225c3c22d8a81ef58a4d212fc'
PACKAGE = 'dimon3898-sys/world-simulation-shorts-engine'
IMAGE = 'ghcr.io/' + PACKAGE
PARENT_DIGEST = 'sha256:2f0f1ee316e4474adf1502335307297385c746c998dda66f43d204a7418aaf50'
PARENT = IMAGE + '@' + PARENT_DIGEST
OLD_TAG = 'capture-integrity-v1-41281172622'
IMAGE_ROOT = '/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
REC = 'world-simulation-shorts-engine/recovery/'
HANDOFF = REC + 'codex-to-gcube-handoff-v1/'
CAPTURE = HANDOFF + 'capture_vulkan.generated.mjs'
GENERATED = HANDOFF + 'backend/GENERATED_SOURCE_MANIFEST.json'
PROFILE = HANDOFF + 'backend/profile_contract.mjs'
PRESENTATION = HANDOFF + 'presentation_runtime_vulkan.generated.mjs'
SOURCES = (PROFILE,)
RESTORED_LINE = b"  '--disable-vulkan-surface',\n"
BASE_PROFILE_SHA = '4306430e64633d67745b706b7c4992b77d12bb1bf3a8d64352b82d07936d17b2'
BASE_PROFILE_BYTES = 10841
CAPTURE_SHA = '0161ac4177bb24b282aab28bb6f42b75d82841aedd81f8b574c8b8e90b33bffb'
PRESENTATION_SHA = '5fa5c63ef6793832c6a7d5569189c079fd375c70a4ade1489c6ac9e2a791c767'
GENERATED_SHA = 'c9122a200b0e918747824d5e73253d98d64b2a8746cfb72f3d5a656b0c4271ca'
RUNTIME = HANDOFF + 'RUNTIME_SOURCE_MANIFEST.json'
STARTUP = REC + 'studio-cold-start-v2/STARTUP_MANIFEST.json'
BOOTSTRAP = REC + 'studio-cold-start-v2/bootstrap.py'
BASE_PINS = {
    RUNTIME: '3d39d18b1e822e804404894af8197444daa95503b36ca4c32486c72e4b1a5240',
    STARTUP: '6c8d0d51b962f2081a5e12a8d41c00690a87012f5259d0e6cc602b546bc2eb43',
    BOOTSTRAP: '4cc5dde854a9dcbfe4a720f7e332f1ca6f5ceaa6467095927b6782e69c94ef26',
}


def need(value, code):
    if not value:
        raise RuntimeError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def source(path):
    need(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)), 'SOURCE_PATH_UNSAFE')
    raw = path.read_bytes()
    need(0 < len(raw) <= 1024 * 1024, 'SOURCE_SIZE_INVALID')
    return raw


def entrypoint(runtime_sha, startup_sha):
    return ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '-I', '-B',
            IMAGE_ROOT + '/' + BOOTSTRAP, '--startup-manifest', IMAGE_ROOT + '/' + STARTUP,
            '--startup-manifest-sha256', startup_sha, '--source-manifest', IMAGE_ROOT + '/' + RUNTIME,
            '--source-manifest-sha256', runtime_sha, '--export-root', '/world-storage']


def prepare(repo, context):
    """Package only the final four patched files, checking their exact baseline delta."""
    repo, context = repo.resolve(), context.absolute()
    need(not context.exists() and not context.is_relative_to(repo), 'FRESH_SEPARATE_CONTEXT_REQUIRED')
    overlay = {name: source(repo / name) for name in (*SOURCES, *BASE_PINS)}
    profile = overlay[PROFILE]
    need(profile.count(RESTORED_LINE) == 1 and
         sha(profile.replace(RESTORED_LINE, b'', 1)) == BASE_PROFILE_SHA,
         'EXACT_SINGLE_SUCCESS_OPTION_RESTORATION_REQUIRED')
    need(len(profile) == BASE_PROFILE_BYTES + len(RESTORED_LINE), 'PROFILE_DELTA_SIZE')
    for name, expected in ((CAPTURE, CAPTURE_SHA), (PRESENTATION, PRESENTATION_SHA), (GENERATED, GENERATED_SHA)):
        need(sha(source(repo / name)) == expected, 'UNCHANGED_CAPTURE_OR_GENERATED_SOURCE_CHANGED')
    runtime = json.loads(overlay[RUNTIME])
    need(runtime.get('schema') == 'WORLD_ENGINE_HANDOFF_RUNTIME_SOURCES_V1', 'RUNTIME_SCHEMA')
    rows = runtime['files']
    need(len(rows) == 355 and len({row['path'] for row in rows}) == 355, 'PRESERVED_SOURCE_COUNT')
    profile_rows = [r for r in rows if r['path'] == PROFILE]
    need(len(profile_rows) == 1 and profile_rows[0]['bytes'] == len(profile) and
         profile_rows[0]['sha256'] == sha(profile), 'PROFILE_RUNTIME_PIN_REQUIRED')
    reconstructed_runtime = json.loads(overlay[RUNTIME])
    previous = next(r for r in reconstructed_runtime['files'] if r['path'] == PROFILE)
    previous.update(bytes=BASE_PROFILE_BYTES, sha256=BASE_PROFILE_SHA)
    need(sha(encoded(reconstructed_runtime)) == BASE_PINS[RUNTIME], 'EXACT_ONE_RUNTIME_ROW_CHANGE_REQUIRED')
    need(overlay[RUNTIME] == encoded(runtime), 'RUNTIME_CANONICAL_BYTES_REQUIRED')
    runtime_sha = sha(overlay[RUNTIME])
    bootstrap = overlay[BOOTSTRAP]
    source_pin = ("SOURCE_SHA = '" + runtime_sha + "'").encode()
    need(bootstrap.count(source_pin) == 1, 'BOOTSTRAP_RUNTIME_LINK_REQUIRED')
    baseline_bootstrap, changed = re.subn(rb"(?m)^SOURCE_SHA = '[a-f0-9]{64}'$",
        ("SOURCE_SHA = '" + BASE_PINS[RUNTIME] + "'").encode(), bootstrap)
    need(changed == 1 and sha(baseline_bootstrap) == BASE_PINS[BOOTSTRAP], 'BOOTSTRAP_SINGLE_PIN_REQUIRED')
    startup = json.loads(overlay[STARTUP])
    need(startup['runtimeManifestSHA256'] == runtime_sha and
         startup['files']['bootstrap.py'] == {'bytes': len(bootstrap), 'sha256': sha(bootstrap)},
         'STARTUP_NEW_LINK_REQUIRED')
    baseline_startup = json.loads(overlay[STARTUP])
    baseline_startup['runtimeManifestSHA256'] = BASE_PINS[RUNTIME]
    baseline_startup['files']['bootstrap.py'] = {'bytes': len(baseline_bootstrap), 'sha256': BASE_PINS[BOOTSTRAP]}
    need(sha(encoded(baseline_startup)) == BASE_PINS[STARTUP], 'STARTUP_ONLY_REQUIRED_HASHES_CHANGED')
    need(overlay[STARTUP] == encoded(startup), 'STARTUP_CANONICAL_BYTES_REQUIRED')
    entry = entrypoint(runtime_sha, sha(overlay[STARTUP]))
    dockerfile = 'FROM ' + PARENT + '\n'
    for name in sorted(overlay):
        dockerfile += 'COPY --chown=0:0 --chmod=0644 ' + json.dumps(['overlay/' + name, IMAGE_ROOT + '/' + name]) + '\n'
    dockerfile += 'ENTRYPOINT ' + json.dumps(entry) + '\n'
    need(sum(map(len, overlay.values())) < 2 * 1024**2, 'CONTEXT_SIZE_LIMIT')
    context.mkdir(parents=True, mode=0o755)
    for name, raw in {**{'overlay/' + n: b for n, b in overlay.items()}, 'Dockerfile': dockerfile.encode()}.items():
        path = context / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        path.chmod(0o644)
    return {'schema': 'WORLD_ENGINE_WEBGL_SUCCESS_OPTION_RESTORE_OVERLAY_V1', 'status': 'PASS',
              'parentDigest': PARENT_DIGEST, 'baseCommit': BASE, 'runtimeSourceRows': 355,
              'changedSources': list(SOURCES), 'overlay': [
                  {'path': p, 'bytes': len(b), 'sha256': sha(b)} for p, b in sorted(overlay.items())],
              'runtimeManifestSHA256': runtime_sha, 'startupManifestSHA256': sha(overlay[STARTUP]),
              'entrypoint': entry, 'dockerfileSHA256': sha(dockerfile.encode()),
              'unchangedSourceRowsReused': 354, 'captureSourceSHA256': CAPTURE_SHA,
              'restoredOption': '--disable-vulkan-surface', 'restoredOptionExactlyOnce': True,
              'captureSourceUnchanged': True, 'webglContextSourceUnchanged': True,
              'generatedManifestUnchanged': True, 'integrityVerifierUnchanged': True,
              'oldPASSReruns': 0, 'gpuExecutions': 0, 'gpuCauseEstablished': False}


def run_command(args, *, input=None):
    return subprocess.check_output(args, input=input, text=True).strip()


def docker(*args):
    return run_command(['docker', '--host=unix:///var/run/docker.sock', *args])


def docker_once(args):
    process = subprocess.Popen(['docker', '--host=unix:///var/run/docker.sock', *args],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        print(line, end='', flush=True)
        if 'Retrying in ' in line:
            process.terminate()
            process.wait(timeout=10)
            raise RuntimeError('DOCKER_INTERNAL_RETRY_STOPPED_NO_REINVOKE')
    need(process.wait() == 0, 'DOCKER_COMMAND_FAILED_NO_RETRY')


def registry(reference):
    url = 'https://ghcr.io/token?' + urllib.parse.urlencode({'service': 'ghcr.io', 'scope': 'repository:' + PACKAGE + ':pull'})
    with urllib.request.urlopen(url, timeout=45) as response:
        token = json.load(response)['token']
    req = urllib.request.Request('https://ghcr.io/v2/' + PACKAGE + '/manifests/' + reference,
        headers={'Authorization': 'Bearer ' + token,
                 'Accept': 'application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json'})
    with urllib.request.urlopen(req, timeout=45) as response:
        raw = response.read(2 * 1024**2)
        digest = response.headers.get('Docker-Content-Digest')
    need(digest == 'sha256:' + sha(raw), 'REGISTRY_MANIFEST_HASH')
    return raw, digest


def old_tag():
    need(registry(OLD_TAG)[1] == PARENT_DIGEST, 'EXISTING_CAPTURE_INTEGRITY_TAG_CHANGED')


def absent(tag):
    try:
        registry(tag)
    except urllib.error.HTTPError as error:
        need(error.code == 404, 'TAG_ABSENCE_NOT_CONFIRMED')
        value = json.loads(error.read(16384))
        need(any(row.get('code') == 'MANIFEST_UNKNOWN' for row in value.get('errors', [])), 'TAG_ABSENCE_RESPONSE')
        return
    raise RuntimeError('NEW_TAG_ALREADY_EXISTS')


def retention(repo, temp):
    file = repo / (REC + 'label355-publication-v1/retain_label355_image.py')
    spec = importlib.util.spec_from_file_location('_surface_restore_reused_image_retention', file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = temp / 'surface-restore-retention'
    module.ROOT.mkdir()
    module.SOURCE = os.environ['GITHUB_SHA']
    module.PARENT = PARENT_DIGEST
    module.RELEASE_TAG = 'surface-restore-image-backup-' + os.environ['GITHUB_RUN_ID']
    return module


def main_run():
    need(os.environ.get('GITHUB_REPOSITORY') == REPO and os.environ.get('GITHUB_RUN_ATTEMPT') == '1', 'RUN_GUARD')
    need(os.environ.get('GITHUB_REF') == 'refs/heads/recovery/webgl-surface-restore-20261101', 'BRANCH_GUARD')
    repo = Path(os.environ['GITHUB_WORKSPACE']).resolve()
    temp = Path(os.environ['RUNNER_TEMP'])
    out = temp / 'surface-restore-evidence'
    out.mkdir()
    def write(name, value):
        with (out / name).open('x') as stream:
            json.dump(value, stream, sort_keys=True, indent=2)
            stream.write('\n')
    keep = None
    try:
        need(run_command(['git', 'rev-parse', 'HEAD']) == os.environ['GITHUB_SHA'], 'CHECKOUT_CHANGED')
        need(run_command(['git', 'rev-parse', 'HEAD^']) == BASE, 'EXPECTED_BASE_REQUIRED')
        old_tag()
        tag_name = 'surface-restore-v1-' + os.environ['GITHUB_RUN_ID']
        target = IMAGE + ':' + tag_name
        absent(tag_name)
        docker_root = docker('info', '--format', '{{.DockerRootDir}}')
        need(shutil.disk_usage(docker_root).free >= 12 * 1024**3, 'PREPULL_CAPACITY')
        auth_dir = temp / 'surface-restore-docker-auth'
        auth_dir.mkdir(mode=0o700)
        os.environ['DOCKER_CONFIG'] = str(auth_dir)
        run_command(['docker', '--host=unix:///var/run/docker.sock', 'login', 'ghcr.io', '-u', os.environ['GITHUB_ACTOR'], '--password-stdin'], input=os.environ['GH_TOKEN'])
        write('PREFLIGHT.json', {'status': 'PASS', 'parentDigest': PARENT_DIGEST, 'newTag': target,
              'runAttempt': 1, 'maxBuilds': 1, 'maxPublications': 1, 'retries': 0, 'gpuExecutions': 0})
        keep = retention(repo, temp)
        keep.reserve()
        write('PULL_ATTEMPT.json', {'attempt': 1, 'parent': PARENT})
        docker_once(['pull', PARENT])
        parent = json.loads(docker('image', 'inspect', PARENT))[0]
        need(PARENT in parent.get('RepoDigests', []), 'PARENT_DIGEST_NOT_PRESENT')
        need(parent['Config']['Entrypoint'] == entrypoint(BASE_PINS[RUNTIME], BASE_PINS[STARTUP]), 'PARENT_STARTUP_CHANGED')
        context = temp / 'surface-restore-context'
        plan = prepare(repo, context)
        write('CONTEXT.json', plan)
        required = parent['Size'] * 3 + 2 * 1024**3
        need(shutil.disk_usage(docker_root).free >= required, 'PREBUILD_ARCHIVE_CAPACITY')
        local_tag = 'world-engine-surface-restore:unpublished-' + os.environ['GITHUB_RUN_ID']
        os.environ['TAG'] = local_tag
        write('BUILD_ATTEMPT.json', {'attempt': 1, 'tag': local_tag})
        docker_once(['build', '--network', 'none', '--pull=false', '-t', local_tag, str(context)])
        keep.archive()
        candidate = json.loads(docker('image', 'inspect', local_tag))[0]
        expected_config = dict(parent['Config'])
        expected_config['Entrypoint'] = plan['entrypoint']
        need(candidate['Config'] == expected_config, 'NEW_CONFIG_DIFFERS_BEYOND_STARTUP_HASHES')
        need(candidate['RootFS']['Layers'][:len(parent['RootFS']['Layers'])] == parent['RootFS']['Layers'], 'PARENT_LAYERS_NOT_PRESERVED')
        probe = "import hashlib,json,pathlib; p=json.loads(" + repr(json.dumps(plan['overlay'])) + "); root=pathlib.Path(" + repr(IMAGE_ROOT) + "); assert all((lambda b:len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'])((root/r['path']).read_bytes()) for r in p); generated=json.loads((root/" + repr(GENERATED) + ").read_bytes()); pin=[r['variantSHA256'] for r in generated['variants'] if r['variant']=='capture_vulkan.generated.mjs']; assert pin==[" + repr(CAPTURE_SHA) + "]; assert hashlib.sha256((root/" + repr(CAPTURE) + ").read_bytes()).hexdigest()==pin[0]; print('SURFACE_RESTORE_CHANGED_FILES_MATCH')"
        need(docker('run', '--rm', '--network', 'none', '--read-only', '--user', '1000:1000', '--entrypoint', '/usr/bin/python3', local_tag, '-I', '-B', '-c', probe) == 'SURFACE_RESTORE_CHANGED_FILES_MATCH', 'CANDIDATE_CHANGED_FILES')
        write('CANDIDATE.json', {'status': 'PASS', 'imageID': candidate['Id'], 'parentDigest': PARENT_DIGEST,
              'changedFilesVerified': len(plan['overlay']), 'entrypoint': plan['entrypoint'],
              'unchangedParentLayersReused': len(parent['RootFS']['Layers']),
              'scope': 'NEW_OPTION_OVERLAY_BYTES_AND_PRESERVED_CONFIG_ONLY',
              'captureSourceSHA256': CAPTURE_SHA, 'capturePinMatchesActualBytes': True, 'oldPASSReruns': 0, 'gpuExecutions': 0})
        old_tag()
        absent(tag_name)
        docker('tag', local_tag, target)
        need(docker('image', 'inspect', '--format', '{{.Id}}', target) == candidate['Id'], 'TAG_IDENTITY')
        write('PUBLICATION_ATTEMPT.json', {'attempt': 1, 'tag': target, 'imageID': candidate['Id']})
        docker_once(['push', target])
        raw, digest = registry(tag_name)
        pinned, confirmed = registry(digest)
        manifest = json.loads(raw)
        need(raw == pinned and digest == confirmed and manifest['config']['digest'] == candidate['Id'], 'REMOTE_VERIFIED_IDENTITY')
        old_tag()
        write('RESULT.json', {'status': 'PASS', 'tag': target, 'digest': digest, 'imageID': candidate['Id'],
              'sourceCommit': os.environ['GITHUB_SHA'], 'imageRelease': keep.read('RETENTION_RESULT.json')['releaseURL'],
              'builds': 1, 'publications': 1, 'retries': 0, 'gpuExecutions': 0,
              'oldTagUnchanged': True, 'oldPASSReruns': 0, 'remoteStudioVerified': False,
              'successfulLaunchOptionRestored': True, 'priorCaptureFailureResolved': False, 'webgl2Verified': False, 'gpuStarts': 0, 'renders': 0})
    except Exception as error:
        write('BLOCKED.json', {'status': 'BLOCKED', 'errorType': type(error).__name__,
              'reason': str(error) if isinstance(error, RuntimeError) else 'COMMAND_OR_SERVICE_OPERATION_FAILED',
              'gpuExecutions': 0, 'automaticRetries': 0})
        raise
    finally:
        # Permanent evidence is part of the same reserved release. No credentials,
        # raw image inspection, process environment, or raw request input is saved.
        for path in sorted(out.glob('*.json')):
            raw = path.read_bytes()
            print('SURFACE_RESTORE_BUILD_EVIDENCE=' + json.dumps({'name': path.name, 'sha256': sha(raw), 'base64': base64.b64encode(raw).decode()}), flush=True)
            if keep is not None and (keep.ROOT / 'RELEASE.json').exists():
                keep.upload(keep.read('RELEASE.json'), path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=('prepare', 'run'))
    parser.add_argument('--repo', type=Path)
    parser.add_argument('--context', type=Path)
    args = parser.parse_args()
    if args.operation == 'prepare':
        need(args.repo is not None and args.context is not None, 'CONTEXT_ARGUMENTS_REQUIRED')
        print(json.dumps(prepare(args.repo, args.context), indent=2, sort_keys=True))
    else:
        main_run()
