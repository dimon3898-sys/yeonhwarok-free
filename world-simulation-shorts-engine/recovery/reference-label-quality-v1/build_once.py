#!/usr/bin/env python3
"""Build/publish one sealed opt-in map/label quality overlay; never run a GPU.
Reuse the existing complete-image retention helper before publication. Runtime
source, generated variants and startup hashes remain enforced. No retry.
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
BASE = 'f276f19fc3c61c77e17e3683a8b8302523a379dc'
BRANCH = 'quality/reference-labels-20261103-a1'
PACKAGE = 'dimon3898-sys/world-simulation-shorts-engine'
IMAGE = 'ghcr.io/' + PACKAGE
PARENT_DIGEST = 'sha256:9e9301dec376a780f4fb2287fe092282baaef3d6cfdfc93532ea6763d9f9b0cf'
PARENT = IMAGE + '@' + PARENT_DIGEST
OLD_TAG = 'capture-evidence-v1-41297725682'
IMAGE_ROOT = '/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
REC = 'world-simulation-shorts-engine/recovery/'
HERE = REC + 'reference-label-quality-v1/'
HANDOFF = REC + 'codex-to-gcube-handoff-v1/'
RUNTIME = HANDOFF + 'RUNTIME_SOURCE_MANIFEST.json'
GENERATED = HANDOFF + 'backend/GENERATED_SOURCE_MANIFEST.json'
PROFILE = HANDOFF + 'backend/profile_contract.mjs'
CAPTURE = HANDOFF + 'capture_vulkan.generated.mjs'
CAPTURE_ORIGINAL = REC + 'universal-presentation-v2/capture_presentation.mjs'
STARTUP = REC + 'studio-cold-start-v2/STARTUP_MANIFEST.json'
BOOTSTRAP = REC + 'studio-cold-start-v2/bootstrap.py'
BASE_PINS = {
 RUNTIME:'a9ab747b27ba1927c03bc4cbb1939a888a2afaaffcbf8b6f5ceb90b481fcfab2',
 GENERATED:'c9122a200b0e918747824d5e73253d98d64b2a8746cfb72f3d5a656b0c4271ca',
 BOOTSTRAP:'b3790c43c1db8236d00789bfd322622eade9f1c38f3dfed5204f59bf868a4efd',
 STARTUP:'af13464f56e309b1454dbd708d101e1b9d0bceedd705ac8833795f4ef869f918',
}
PROFILE_SHA = '4e78b2d9f18107d70fda3c266c48d72103f7eaa63015b4dd1c1bb65e697e79a6'
CAPTURE_BASE_PINS = {
 CAPTURE:'0161ac4177bb24b282aab28bb6f42b75d82841aedd81f8b574c8b8e90b33bffb',
 CAPTURE_ORIGINAL:'fc17ceb56499184a6f4ae6888d617f7b1b67e4fd508320eb295493161596753e',
}
CAPTURE_ALIAS_BEFORE = b'const trace=[],aliases=new Map([['
CAPTURE_ALIAS_AFTER = b"const trace=[],aliases=new Map([['/recovery/reference-director-v1/director_events.mjs',path.join(ENGINE,'recovery/reference-director-v1/director_events.mjs')],["
WORKFLOW = '.github/workflows/world-engine-reference-label-quality-once.yml'


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
    """Check sealed new bytes and unchanged inherited rows, then stage one overlay."""
    repo, context = repo.resolve(), context.absolute()
    need(not context.exists() and not context.is_relative_to(repo), 'FRESH_SEPARATE_CONTEXT_REQUIRED')
    plan = json.loads(source(repo / (HERE + 'SEALED_OVERLAY.json')))
    need(plan.get('schema') == 'WORLD_ENGINE_REFERENCE_LABEL_QUALITY_OVERLAY_V1' and
         plan.get('status') == 'PASS' and plan.get('sourceBaseCommit') == BASE, 'SEALED_QUALITY_OVERLAY_REQUIRED')
    baseline = {}
    for name, pin in BASE_PINS.items():
        raw = source(repo / (HERE + 'baseline/' + Path(name).name))
        need(sha(raw) == pin, 'BASELINE_PIN_MISMATCH')
        baseline[name] = raw
    previous = json.loads(baseline[RUNTIME])
    old_rows = {r['path']: r for r in previous['files']}
    need(len(old_rows) == 355, 'BASELINE_SOURCE_COUNT')
    declared = plan['overlay']
    need(len({r['path'] for r in declared}) == len(declared), 'DUPLICATE_OVERLAY_PATH')
    for r in declared:
        need(r['path'].startswith('world-simulation-shorts-engine/') and '..' not in Path(r['path']).parts,
             'OVERLAY_PATH_INVALID')
    overlay = {r['path']: source(repo / r['path']) for r in declared}
    need(all(r == {'path':r['path'],'bytes':len(overlay[r['path']]),'sha256':sha(overlay[r['path']])} for r in declared),
         'SEALED_OVERLAY_BYTES_CHANGED')
    need(set(overlay) == set(plan['changedSources'] + plan['addedRuntimeSources'] + [RUNTIME, BOOTSTRAP, STARTUP]),
         'EXACT_OVERLAY_SET_REQUIRED')
    need(sha(source(repo / PROFILE)) == PROFILE_SHA and PROFILE not in overlay, 'UNCHANGED_BROWSER_PROFILE_CHANGED')
    for name, pin in CAPTURE_BASE_PINS.items():
        base_capture = source(repo / (HERE + 'baseline/' + Path(name).name))
        need(sha(base_capture) == pin and base_capture.count(CAPTURE_ALIAS_BEFORE) == 1, 'CAPTURE_ALIAS_BASELINE_CHANGED')
        expected_capture = base_capture.replace(CAPTURE_ALIAS_BEFORE, CAPTURE_ALIAS_AFTER, 1)
        need(name in overlay and overlay[name] == expected_capture, 'CAPTURE_EXACT_FILE_ALIAS_ONLY')
    runtime = json.loads(overlay[RUNTIME]); rows = {r['path']:r for r in runtime['files']}
    need(len(rows) == len(runtime['files']) == plan['runtimeSourceRows'] and len(rows) == 355 + len(plan['addedRuntimeSources']),
         'SOURCE_COUNT_OR_DUPLICATE')
    need(set(rows) == set(old_rows) | set(plan['addedRuntimeSources']), 'EXACT_SOURCE_CLOSURE_REQUIRED')
    changed = sorted(p for p in old_rows if old_rows[p] != rows[p])
    need(changed == sorted(plan['changedSources']), 'EXACT_CHANGED_ROWS_REQUIRED')
    for name in changed + plan['addedRuntimeSources']:
        need(rows[name] == next(r for r in declared if r['path'] == name), 'RUNTIME_OVERLAY_LINK')
    need(overlay[RUNTIME] == encoded(runtime), 'RUNTIME_CANONICAL_BYTES_REQUIRED')
    runtime_sha = sha(overlay[RUNTIME])
    need(runtime_sha == plan['runtimeManifestSHA256'], 'SEALED_RUNTIME_PIN')
    bootstrap, count = re.subn(rb"(?m)^SOURCE_SHA = '[a-f0-9]{64}'$",
        ("SOURCE_SHA = '" + runtime_sha + "'").encode(), baseline[BOOTSTRAP])
    need(count == 1 and bootstrap == overlay[BOOTSTRAP], 'BOOTSTRAP_ONLY_RUNTIME_PIN_CHANGED')
    startup = json.loads(baseline[STARTUP])
    startup['runtimeManifestSHA256'] = runtime_sha
    startup['files']['bootstrap.py'] = {'bytes':len(bootstrap),'sha256':sha(bootstrap)}
    need(overlay[STARTUP] == encoded(startup) and sha(overlay[STARTUP]) == plan['startupManifestSHA256'],
         'STARTUP_ONLY_REQUIRED_HASHES_CHANGED')
    generated = json.loads(overlay[GENERATED])
    need(generated.get('schema') == 'WORLD_ENGINE_PINNED_GPU_ADAPTER_VARIANTS_V1' and len(generated['variants']) == 3,
         'GENERATED_VARIANT_SET_REQUIRED')
    for variant in generated['variants']:
        need(sha(source(repo / variant['original'])) == variant['originalSHA256'] and
             sha(source(repo / (HANDOFF + variant['variant']))) == variant['variantSHA256'], 'GENERATED_SOURCE_LINK')
    scene = plan['scene']; scene_raw = source(repo / scene['path'])
    need(scene == {'path':scene['path'],'bytes':len(scene_raw),'sha256':sha(scene_raw)}, 'QUALITY_SCENE_CHANGED')
    entry = entrypoint(runtime_sha, sha(overlay[STARTUP]))
    dockerfile = 'FROM ' + PARENT + '\n'
    # One additive layer; preserve source directory modes instead of chmod0644 on directories.
    dockerfile += 'COPY --chown=0:0 ' + json.dumps(['overlay/', IMAGE_ROOT + '/']) + '\n'
    dockerfile += 'ENTRYPOINT ' + json.dumps(entry) + '\n'
    need(sum(map(len, overlay.values())) < 3 * 1024**2, 'CONTEXT_SIZE_LIMIT')
    context.mkdir(parents=True, mode=0o755)
    for name, raw in {**{'overlay/' + n:b for n,b in overlay.items()}, 'Dockerfile':dockerfile.encode()}.items():
        path = context / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw); path.chmod(0o644)
    for path in context.rglob('*'):
        if path.is_dir(): path.chmod(0o755)
    return {**plan, 'parentDigest':PARENT_DIGEST, 'entrypoint':entry,
            'dockerfileSHA256':sha(dockerfile.encode()), 'unchangedSourceRowsReused':355-len(changed),
            'newFilesystemLayers':1, 'browserOptionsUnchanged':True, 'captureSourceUnchanged':False, 'captureSourceChange':'EXACT_REFERENCE_DIRECTOR_FILE_ALIAS_ONLY', 'oldPASSReruns':0, 'gpuExecutions':0}


def focused_validation(repo, plan):
    """Consume new focused results; do not rerun locked suites."""
    file = repo / (HERE + 'FOCUSED_RESULT.json')
    value = json.loads(source(file))
    need(value.get('schema') == 'WORLD_ENGINE_REFERENCE_LABEL_QUALITY_FOCUSED_V1' and
         value.get('status') == 'PASS' and value.get('sourceBaseCommit') == BASE and
         value.get('allRequiredChecksPassed') is True and value.get('gpuExecutions') == 0 and
         value.get('oldPASSReruns') == 0 and type(value.get('focusedTestsPassed')) is int and value['focusedTestsPassed'] > 0,
         'NEW_FOCUSED_VALIDATION_REQUIRED')
    need(value.get('overlay') == plan['overlay'] and value.get('scene') == plan['scene'], 'FOCUSED_VALIDATION_BYTES_CHANGED')
    return {'sha256':sha(file.read_bytes()),'focusedTestsPassed':value['focusedTestsPassed'],'oldPASSReruns':0,'gpuExecutions':0}


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
                 'Accept': 'application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json, application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json'})
    with urllib.request.urlopen(req, timeout=45) as response:
        raw = response.read(2 * 1024**2)
        digest = response.headers.get('Docker-Content-Digest')
    need(digest == 'sha256:' + sha(raw), 'REGISTRY_MANIFEST_HASH')
    return raw, digest


def old_tag():
    need(registry(OLD_TAG)[1] == PARENT_DIGEST, 'EXISTING_CAPTURE_EVIDENCE_TAG_CHANGED')


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
    file = repo / (HERE + 'retain_quality_image.py')
    spec = importlib.util.spec_from_file_location('_quality_labels_reused_image_retention', file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = temp / 'quality-labels-retention'
    module.ROOT.mkdir(exist_ok=True)
    module.SOURCE = os.environ['GITHUB_SHA']
    module.PARENT = PARENT_DIGEST
    module.RELEASE_TAG = 'quality-labels-image-backup-' + os.environ['GITHUB_RUN_ID']
    return module


def main_run():
    need(os.environ.get('GITHUB_REPOSITORY') == REPO and os.environ.get('GITHUB_RUN_ATTEMPT') == '1', 'RUN_GUARD')
    need(os.environ.get('GITHUB_REF') == 'refs/heads/' + BRANCH, 'BRANCH_GUARD')
    repo = Path(os.environ['GITHUB_WORKSPACE']).resolve()
    temp = Path(os.environ['RUNNER_TEMP'])
    out = temp / 'quality-labels-evidence'
    out.mkdir()
    def write(name, value):
        with (out / name).open('x') as stream:
            json.dump(value, stream, sort_keys=True, indent=2)
            stream.write('\n')
    keep = None
    try:
        need(run_command(['git', 'rev-parse', 'HEAD']) == os.environ['GITHUB_SHA'], 'CHECKOUT_CHANGED')
        need(run_command(['git', 'rev-parse', 'HEAD^']) == os.environ.get('QUALITY_EXPECTED_PARENT'), 'EXPECTED_PARENT_REQUIRED')
        need(run_command(['git','diff','--name-only','HEAD^','HEAD']).splitlines() == [WORKFLOW], 'ACTIVATION_WORKFLOW_ONLY')
        context = temp / 'quality-labels-context'
        plan = prepare(repo, context)
        focus = focused_validation(repo, plan)
        write('CONTEXT.json', plan)
        write('FOCUSED_VALIDATION.json', focus)
        old_tag()
        tag_name = 'quality-labels-v1-' + os.environ['GITHUB_RUN_ID']
        target = IMAGE + ':' + tag_name
        absent(tag_name)
        driver_status = json.loads(docker('info', '--format', '{{json .DriverStatus}}'))
        need(['driver-type','io.containerd.snapshotter.v1'] in driver_status, 'CONTAINERD_IMAGE_STORE_REQUIRED')
        docker_root = docker('info', '--format', '{{.DockerRootDir}}')
        need(shutil.disk_usage(docker_root).free >= 12 * 1024**3, 'PREPULL_CAPACITY')
        auth_dir = temp / 'quality-labels-docker-auth'
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
        required = parent['Size'] * 3 + 2 * 1024**3
        need(shutil.disk_usage(docker_root).free >= required, 'PREBUILD_ARCHIVE_CAPACITY')
        local_tag = 'world-engine-quality-labels:unpublished-' + os.environ['GITHUB_RUN_ID']
        os.environ['TAG'] = local_tag
        write('BUILD_ATTEMPT.json', {'attempt': 1, 'tag': local_tag})
        docker_once(['build', '--platform', 'linux/amd64', '--provenance=false', '--sbom=false', '--network', 'none', '--pull=false', '-t', local_tag, str(context)])
        keep.archive()
        candidate = json.loads(docker('image', 'inspect', local_tag))[0]
        retained = keep.read('RETENTION_RESULT.json')
        need(retained.get('status') == 'PASS' and retained.get('identityMode') == 'CONTAINERD_DESCRIPTOR_AND_CONFIG' and
             retained.get('imageID') == candidate['Id'] and
             retained.get('archiveRootDigest') == candidate['Id'] and
             retained.get('rootFSDiffIDs') == candidate['RootFS']['Layers'] and
             re.fullmatch(r'sha256:[a-f0-9]{64}',retained.get('configDigest','')), 'ARCHIVE_CANDIDATE_IDENTITY_BEFORE_PUBLICATION')
        expected_config = dict(parent['Config'])
        expected_config['Entrypoint'] = plan['entrypoint']
        need(candidate['Config'] == expected_config, 'NEW_CONFIG_DIFFERS_BEYOND_STARTUP_HASHES')
        need(candidate['RootFS']['Layers'][:len(parent['RootFS']['Layers'])] == parent['RootFS']['Layers'], 'PARENT_LAYERS_NOT_PRESERVED')
        need(len(candidate['RootFS']['Layers']) == len(parent['RootFS']['Layers']) + 1, 'EXACT_ONE_ADDITIVE_LAYER_REQUIRED')
        probe = "import hashlib,json,pathlib; p=json.loads(" + repr(json.dumps(plan['overlay'])) + "); root=pathlib.Path(" + repr(IMAGE_ROOT) + "); assert all((lambda b:len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'])((root/r['path']).read_bytes()) for r in p); assert len(json.loads((root/" + repr(RUNTIME) + ").read_bytes())['files'])==" + str(plan['runtimeSourceRows']) + "; print('QUALITY_LABELS_CHANGED_FILES_MATCH')"
        need(docker('run', '--rm', '--network', 'none', '--read-only', '--user', '1000:1000', '--entrypoint', '/usr/bin/python3', local_tag, '-I', '-B', '-c', probe) == 'QUALITY_LABELS_CHANGED_FILES_MATCH', 'CANDIDATE_CHANGED_FILES')
        write('CANDIDATE.json', {'status': 'PASS', 'imageID': candidate['Id'], 'parentDigest': PARENT_DIGEST,
              'changedFilesVerified': len(plan['overlay']), 'entrypoint': plan['entrypoint'],
              'unchangedParentLayersReused': len(parent['RootFS']['Layers']),
              'scope': 'NEW_QUALITY_OVERLAY_BYTES_AND_PRESERVED_CONFIG_ONLY',
              'captureProcessBehaviorPreserved': True, 'captureSourceChange': 'EXACT_REFERENCE_DIRECTOR_FILE_ALIAS_ONLY', 'browserOptionsUnchanged': True, 'oldPASSReruns': 0, 'gpuExecutions': 0})
        old_tag()
        absent(tag_name)
        docker('tag', local_tag, target)
        need(docker('image', 'inspect', '--format', '{{.Id}}', target) == candidate['Id'], 'TAG_IDENTITY')
        write('PUBLICATION_ATTEMPT.json', {'attempt': 1, 'tag': target, 'imageID': candidate['Id']})
        docker_once(['push', target])
        raw, digest = registry(tag_name)
        pinned, confirmed = registry(digest)
        manifest = json.loads(raw)
        archive_identity = keep.read('RETENTION_RESULT.json')
        need(raw == pinned and digest == confirmed and digest == archive_identity['archiveRootDigest'] == candidate['Id'], 'REMOTE_ROOT_DESCRIPTOR_IDENTITY')
        if 'manifests' in manifest:
            need(len(manifest['manifests']) == 1 and manifest['manifests'][0]['digest'] == archive_identity['imageManifestDigest'], 'REMOTE_SINGLE_PLATFORM_IDENTITY')
            image_raw, image_digest = registry(archive_identity['imageManifestDigest'])
            manifest = json.loads(image_raw)
            need(image_digest == archive_identity['imageManifestDigest'], 'REMOTE_IMAGE_MANIFEST_IDENTITY')
        need(manifest['config']['digest'] == archive_identity['configDigest'], 'REMOTE_CONFIG_IDENTITY')
        old_tag()
        write('RESULT.json', {'status': 'PASS', 'tag': target, 'digest': digest, 'imageID': candidate['Id'],
              'configDigest': archive_identity['configDigest'], 'imageManifestDigest': archive_identity['imageManifestDigest'],
              'sourceCommit': os.environ['GITHUB_SHA'], 'imageRelease': keep.read('RETENTION_RESULT.json')['releaseURL'],
              'builds': 1, 'publications': 1, 'retries': 0, 'gpuExecutions': 0,
              'oldTagUnchanged': True, 'oldPASSReruns': 0, 'remoteStudioVerified': False,
              'qualityScenePrepared': True, 'actualVideoQuality': 'NOT_RUN', 'webgl2VerifiedThisWork': False, 'gpuStarts': 0, 'renders': 0})
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
            print('QUALITY_LABELS_BUILD_EVIDENCE=' + json.dumps({'name': path.name, 'sha256': sha(raw), 'base64': base64.b64encode(raw).decode()}), flush=True)
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

