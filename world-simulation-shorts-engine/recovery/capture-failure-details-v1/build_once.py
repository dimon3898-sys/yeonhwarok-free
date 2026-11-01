#!/usr/bin/env python3
"""One bounded capture-failure diagnostic overlay; no GPU or existing tag write.

The only runtime changes are two reviewed capture-diagnostic files and their
existing manifest/startup hash chain. Full-image retention reuses the preserved
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
BASE = 'd7045c7e0b3784b85faac3b1e375b7806388f684'
PACKAGE = 'dimon3898-sys/world-simulation-shorts-engine'
IMAGE = 'ghcr.io/' + PACKAGE
PARENT_DIGEST = 'sha256:db0594dda5a0965a5663632de38a009fe62356a4f479a607037060e0e1bea34e'
PARENT = IMAGE + '@' + PARENT_DIGEST
OLD_TAG = 'namibia-png-v1-41277841800'
IMAGE_ROOT = '/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
REC = 'world-simulation-shorts-engine/recovery/'
HANDOFF = REC + 'codex-to-gcube-handoff-v1/'
SOURCES = (HANDOFF + 'capture_vulkan.generated.mjs',
           HANDOFF + 'controller/safe_capture_export.py')
RUNTIME = HANDOFF + 'RUNTIME_SOURCE_MANIFEST.json'
STARTUP = REC + 'studio-cold-start-v2/STARTUP_MANIFEST.json'
BOOTSTRAP = REC + 'studio-cold-start-v2/bootstrap.py'
BASE_PINS = {
    RUNTIME: '9a31d9487191b7a4370a86728699c0b03f7224b24e59004cccbeae2a297ee402',
    STARTUP: '87bc41eb6e7f43e338b6895c0e5526a880092dc7838eda79c79039f950e19dd4',
    BOOTSTRAP: 'ff3b1dcb693093c67c4024fb31b91cbb95ee437764887803365bb64e3803facf',
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
    """Create the minimal context; no old source reads or build/test execution."""
    repo, context = repo.resolve(), context.absolute()
    need(not context.exists() and not context.is_relative_to(repo), 'FRESH_SEPARATE_CONTEXT_REQUIRED')
    original = {name: source(repo / name) for name in BASE_PINS}
    need(all(sha(original[name]) == pin for name, pin in BASE_PINS.items()), 'BASE_CHAIN_CHANGED')
    runtime = json.loads(original[RUNTIME])
    need(runtime.get('schema') == 'WORLD_ENGINE_HANDOFF_RUNTIME_SOURCES_V1', 'RUNTIME_SCHEMA')
    rows = runtime['files']
    need(len(rows) == 355 and len({row['path'] for row in rows}) == 355, 'PRESERVED_SOURCE_COUNT')
    old_rows = {row['path']: dict(row) for row in rows}
    need(set(SOURCES) <= old_rows.keys(), 'CHANGED_SOURCE_MISSING')
    overlay = {name: source(repo / name) for name in SOURCES}
    for row in rows:
        if row['path'] in overlay:
            raw = overlay[row['path']]
            row.update(bytes=len(raw), sha256=sha(raw))
    need({row['path'] for row in rows if row != old_rows[row['path']]} == set(SOURCES), 'EXACT_TWO_SOURCE_CHANGES_REQUIRED')
    overlay[RUNTIME] = encoded(runtime)
    runtime_sha = sha(overlay[RUNTIME])
    bootstrap, changed = re.subn(rb"(?m)^SOURCE_SHA = '[a-f0-9]{64}'$",
                                ("SOURCE_SHA = '" + runtime_sha + "'").encode(), original[BOOTSTRAP])
    need(changed == 1, 'BOOTSTRAP_SINGLE_PIN_REQUIRED')
    overlay[BOOTSTRAP] = bootstrap
    startup = json.loads(original[STARTUP])
    need(startup['runtimeManifestSHA256'] == BASE_PINS[RUNTIME], 'STARTUP_BASE_LINK')
    need(set(startup['files']) == {'bootstrap.py', 'worker.py'}, 'STARTUP_FILE_SET')
    startup['runtimeManifestSHA256'] = runtime_sha
    startup['files']['bootstrap.py'] = {'bytes': len(bootstrap), 'sha256': sha(bootstrap)}
    overlay[STARTUP] = encoded(startup)
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
    result = {'schema': 'WORLD_ENGINE_CAPTURE_DETAILS_OVERLAY_V1', 'status': 'PASS',
              'parentDigest': PARENT_DIGEST, 'baseCommit': BASE, 'runtimeSourceRows': 355,
              'changedSources': list(SOURCES), 'overlay': [
                  {'path': p, 'bytes': len(b), 'sha256': sha(b)} for p, b in sorted(overlay.items())],
              'runtimeManifestSHA256': runtime_sha, 'startupManifestSHA256': sha(overlay[STARTUP]),
              'entrypoint': entry, 'dockerfileSHA256': sha(dockerfile.encode()),
              'unchangedSourceRowsReused': 353, 'oldPASSReruns': 0, 'gpuExecutions': 0}
    return result


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
    need(registry(OLD_TAG)[1] == PARENT_DIGEST, 'EXISTING_NAMIBIA_TAG_CHANGED')


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
    spec = importlib.util.spec_from_file_location('_capture_details_reused_image_retention', file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = temp / 'capture-details-retention'
    module.ROOT.mkdir()
    module.SOURCE = os.environ['GITHUB_SHA']
    module.PARENT = PARENT_DIGEST
    module.RELEASE_TAG = 'capture-details-image-backup-' + os.environ['GITHUB_RUN_ID']
    return module


def main_run():
    need(os.environ.get('GITHUB_REPOSITORY') == REPO and os.environ.get('GITHUB_RUN_ATTEMPT') == '1', 'RUN_GUARD')
    need(os.environ.get('GITHUB_REF') == 'refs/heads/recovery/capture-failure-details-20261101', 'BRANCH_GUARD')
    repo = Path(os.environ['GITHUB_WORKSPACE']).resolve()
    temp = Path(os.environ['RUNNER_TEMP'])
    out = temp / 'capture-details-evidence'
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
        tag_name = 'capture-details-v1-' + os.environ['GITHUB_RUN_ID']
        target = IMAGE + ':' + tag_name
        absent(tag_name)
        docker_root = docker('info', '--format', '{{.DockerRootDir}}')
        need(shutil.disk_usage(docker_root).free >= 12 * 1024**3, 'PREPULL_CAPACITY')
        auth_dir = temp / 'capture-details-docker-auth'
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
        context = temp / 'capture-details-context'
        plan = prepare(repo, context)
        write('CONTEXT.json', plan)
        required = parent['Size'] * 3 + 2 * 1024**3
        need(shutil.disk_usage(docker_root).free >= required, 'PREBUILD_ARCHIVE_CAPACITY')
        local_tag = 'world-engine-capture-details:unpublished-' + os.environ['GITHUB_RUN_ID']
        os.environ['TAG'] = local_tag
        write('BUILD_ATTEMPT.json', {'attempt': 1, 'tag': local_tag})
        docker_once(['build', '--network', 'none', '--pull=false', '-t', local_tag, str(context)])
        keep.archive()
        candidate = json.loads(docker('image', 'inspect', local_tag))[0]
        expected_config = dict(parent['Config'])
        expected_config['Entrypoint'] = plan['entrypoint']
        need(candidate['Config'] == expected_config, 'NEW_CONFIG_DIFFERS_BEYOND_STARTUP_HASHES')
        need(candidate['RootFS']['Layers'][:len(parent['RootFS']['Layers'])] == parent['RootFS']['Layers'], 'PARENT_LAYERS_NOT_PRESERVED')
        probe = "import hashlib,json,pathlib; p=json.loads(" + repr(json.dumps(plan['overlay'])) + "); root=pathlib.Path(" + repr(IMAGE_ROOT) + "); assert all((lambda b:len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'])((root/r['path']).read_bytes()) for r in p); print('CAPTURE_DETAILS_CHANGED_FILES_MATCH')"
        need(docker('run', '--rm', '--network', 'none', '--read-only', '--user', '1000:1000', '--entrypoint', '/usr/bin/python3', local_tag, '-I', '-B', '-c', probe) == 'CAPTURE_DETAILS_CHANGED_FILES_MATCH', 'CANDIDATE_CHANGED_FILES')
        write('CANDIDATE.json', {'status': 'PASS', 'imageID': candidate['Id'], 'parentDigest': PARENT_DIGEST,
              'changedFilesVerified': len(plan['overlay']), 'entrypoint': plan['entrypoint'],
              'unchangedParentLayersReused': len(parent['RootFS']['Layers']),
              'scope': 'NEW_OVERLAY_BYTES_AND_PRESERVED_CONFIG_ONLY', 'oldPASSReruns': 0, 'gpuExecutions': 0})
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
              'priorCaptureFailureResolved': False, 'gpuStarts': 0, 'renders': 0})
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
            print('CAPTURE_DETAILS_BUILD_EVIDENCE=' + json.dumps({'name': path.name, 'sha256': sha(raw), 'base64': base64.b64encode(raw).decode()}), flush=True)
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
