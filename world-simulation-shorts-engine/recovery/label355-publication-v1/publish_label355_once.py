#!/usr/bin/env python3
"""One authorized label355 publication; reuse G2 registry and build receipts."""
import base64
import concurrent.futures
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = 'dimon3898-sys/yeonhwarok-free'
PACKAGE = 'dimon3898-sys/world-simulation-shorts-engine'
IMAGE = 'ghcr.io/' + PACKAGE
SOURCE = 'af9347963b4405dac66cdbe0ad6c6898c3d42ea0'
OLD_ID = 'sha256:a175c1b01fda0513625a171e74987951d8c11ad083d8583fc297f4fcff2271cc'
PARENT = 'sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da'
OLD_TAG = 'g2-diagnostics-v1-27f9fa5c133a-40767632198'
REL = Path('world-simulation-shorts-engine/recovery')
TEMP = Path(os.environ['RUNNER_TEMP'])
OUT = TEMP / 'label355-publication'
BUILT = TEMP / 'label355-evidence'
TAG_NAME = 'label355-v1-af9347963b44-' + os.environ['GITHUB_RUN_ID']
TAG = IMAGE + ':' + TAG_NAME
OUT.mkdir(exist_ok=True)

def need(ok, reason):
    if not ok:
        raise RuntimeError(reason)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def read(path):
    return json.loads(Path(path).read_bytes())

def write(name, data):
    with (OUT / name).open('x') as f:
        json.dump(data, f, sort_keys=True, indent=2)
        f.write('\n')

def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

g2 = module(REL / 'capture-diagnostics-g2-v1/build_g2_image.py', 'g2_reused')

def old_tag():
    _, digest = g2.registry(OLD_TAG)
    need(digest == PARENT, 'EXISTING_G2_TAG_CHANGED')

def absent():
    try:
        g2.registry(TAG_NAME)
    except urllib.error.HTTPError as error:
        raw = error.read(16384)
        need(error.code == 404, 'NEW_TAG_ABSENCE_NOT_CONFIRMED')
        body = json.loads(raw)
        need(any(row.get('code') == 'MANIFEST_UNKNOWN' for row in body.get('errors', [])), 'UNEXPECTED_ABSENCE_RESPONSE')
        return
    raise RuntimeError('NEW_TAG_ALREADY_EXISTS')

def docker(*args):
    return subprocess.check_output(['docker', '--host=unix:///var/run/docker.sock', *args], text=True).strip()

def preflight():
    need(os.environ['GITHUB_REPOSITORY'] == REPO and os.environ['GITHUB_RUN_ATTEMPT'] == '1', 'RUN_GUARD')
    need(subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == SOURCE, 'SOURCE_CHANGED')
    token = os.environ['GHCR_JOB_TOKEN']
    need(bool(token), 'TOKEN_MISSING')
    url = 'https://ghcr.io/token?' + urllib.parse.urlencode({'service': 'ghcr.io', 'scope': 'repository:' + PACKAGE + ':pull,push'})
    auth = base64.b64encode((os.environ['GITHUB_ACTOR'] + ':' + token).encode()).decode()
    with urllib.request.urlopen(urllib.request.Request(url, headers={'Authorization': 'Basic ' + auth}), timeout=45) as response:
        result = json.load(response)
    need(bool(result.get('token') or result.get('access_token')), 'GHCR_AUTHENTICATION_FAILED')
    old_tag()
    absent()
    write('GHCR_PREFLIGHT.json', {'status': 'PASS', 'newTag': TAG, 'newTagAbsent': True,
        'authenticatedScopeRequest': 'pull,push', 'permissionBasis': 'Live package Actions Admin for source repository plus job packages:write; authenticated GHCR token request accepted',
        'existingG2TagDigest': PARENT, 'sourceCommit': SOURCE, 'runAttempt': 1, 'registryWrites': 0,
        'maxBuildAttempts': 1, 'maxPublicationAttempts': 1, 'automaticWorkflowRetries': 0})

def comparison():
    current = read(BUILT / 'BUILD_RESULT.json')['imageId']
    write('IMAGE_ID_COMPARISON.json', {'status': 'COMPARED', 'previousImageID': OLD_ID,
        'newImageID': current, 'imageIDsEqual': current == OLD_ID, 'sourceCommit': SOURCE,
        'previousRunID': 41015249885, 'previousEvidenceCommit': '07ba1ad253bd1b1d055aa33f6f9386e1f9cb03f4',
        'acceptanceBasis': 'Same immutable source and parent; new actual installed SHA256 and OCI checks required. Image-ID equality alone is not the source-integrity gate.'})

def publish():
    backup = module(REL / 'label-packaging-v1/backup_build_evidence.py', 'backup_reused')
    receipts = {name: backup.safe_evidence_bytes(name, (BUILT / name).read_bytes()) for name in backup.ALLOW}
    installed = receipts['INSTALLED_RESULT.json']
    need(installed['runtimeManifestSHA256'] == '1427779c7a52af90f37478de3ba11e1ddb664149f5b13dbd87fb05142be0252e', 'PREVIOUS_RUNTIME_MANIFEST_MISMATCH')
    need(installed['startupManifestSHA256'] == 'f8afb5c2f944dea13f7a990a7c2c8e8c65c9c028bd7228f501aa6feace98ef89', 'PREVIOUS_STARTUP_MANIFEST_MISMATCH')
    current = receipts['BUILD_RESULT.json']['imageId']
    retained = read(TEMP / 'label355-retention/RETENTION_RESULT.json')
    need(retained['status'] == 'PASS' and retained['imageID'] == current, 'PERMANENT_IMAGE_BACKUP_REQUIRED')
    need(current == receipts['OCI_RESULT.json']['imageId'] == read(OUT / 'IMAGE_ID_COMPARISON.json')['newImageID'], 'RECEIPT_ID_MISMATCH')
    need(docker('image', 'inspect', '--format', '{{.Id}}', os.environ['TAG']) == current, 'CANDIDATE_CHANGED')
    need(read(OUT / 'GHCR_PREFLIGHT.json')['status'] == 'PASS', 'PREFLIGHT_REQUIRED')
    old_tag()
    absent()
    docker('tag', os.environ['TAG'], TAG)
    need(docker('image', 'inspect', '--format', '{{.Id}}', TAG) == current, 'TAG_ID_MISMATCH')
    write('PUBLICATION_ATTEMPT.json', {'status': 'STARTED', 'publicationAttempt': 1, 'retries': 0, 'tag': TAG, 'imageID': current})
    print('LABEL355_PUSH_STARTED=' + TAG, flush=True)
    process = subprocess.Popen(['docker', '--host=unix:///var/run/docker.sock', 'push', TAG], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        print(line, end='', flush=True)
        if 'Retrying in ' in line:
            process.terminate()
            process.wait(timeout=10)
            raise RuntimeError('PUSH_RETRY_REQUESTED_STOPPED_NO_REINVOKE')
    need(process.wait() == 0, 'PUSH_FAILED_NO_RETRY')
    write('PUSH_RESULT.json', {'status': 'PASS', 'tag': TAG, 'imageID': current, 'publicationAttempts': 1, 'retries': 0})

def remote():
    current = read(OUT / 'PUSH_RESULT.json')['imageID']
    raw, digest = g2.registry(TAG_NAME)
    by_digest, resolved = g2.registry(digest)
    need(raw == by_digest and resolved == digest, 'REMOTE_TAG_DIGEST_MISMATCH')
    manifest = json.loads(raw)
    need(manifest['config']['digest'] == current, 'REMOTE_IMAGE_DIFFERS_FROM_VERIFIED')
    scope = 'repository:' + PACKAGE + ':pull'
    url = 'https://ghcr.io/token?' + urllib.parse.urlencode({'service': 'ghcr.io', 'scope': scope})
    with urllib.request.urlopen(url, timeout=45) as response:
        anonymous = json.load(response)['token']
    def blob(descriptor, method):
        request = urllib.request.Request('https://ghcr.io/v2/' + PACKAGE + '/blobs/' + descriptor['digest'], method=method, headers={'Authorization': 'Bearer ' + anonymous})
        with urllib.request.urlopen(request, timeout=45) as response:
            need(response.status == 200, 'REMOTE_BLOB_INACCESSIBLE')
            if method == 'HEAD':
                need(int(response.headers['Content-Length']) == descriptor['size'], 'REMOTE_LAYER_SIZE_MISMATCH')
                return descriptor['digest']
            value = response.read(1024 * 1024)
            need(len(value) == descriptor['size'] and 'sha256:' + sha(value) == descriptor['digest'], 'REMOTE_CONFIG_HASH_MISMATCH')
            return value
    blob(manifest['config'], 'GET')
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        accessible = list(pool.map(lambda d: blob(d, 'HEAD'), manifest['layers']))
    old_tag()
    write('REMOTE_RESULT.json', {'status': 'PASS', 'tag': TAG, 'digest': digest,
        'imageID': current, 'manifestSHA256': sha(raw), 'manifestBytes': len(raw),
        'tagAndDigestBodiesIdentical': True, 'remoteConfigSHA256MatchesImageID': True,
        'anonymousAccess': True, 'remoteLayerHeadersVerified': len(accessible),
        'remoteCompressedLayerBytes': sum(x['size'] for x in manifest['layers']),
        'scope': 'ANONYMOUS_MANIFEST_CONFIG_GET_AND_ALL_LAYER_HEAD; no deployment or GPU execution',
        'existingG2TagUnchanged': True, 'existingG2Digest': PARENT, 'sourceCommit': SOURCE,
        'gpuExecuted': False, 'oldPASSSuitesRerun': False})

def export():
    allowed = ['GHCR_PREFLIGHT.json', 'IMAGE_ID_COMPARISON.json', 'PUBLICATION_ATTEMPT.json', 'PUSH_RESULT.json', 'REMOTE_RESULT.json']
    for name in allowed:
        path = OUT / name
        if path.exists():
            raw = path.read_bytes()
            need(len(raw) < 32768, 'SAFE_EVIDENCE_SIZE')
            print('LABEL355_PUBLISH_EVIDENCE=' + json.dumps({'name': name, 'bytes': len(raw), 'sha256': sha(raw), 'base64': base64.b64encode(raw).decode()}, sort_keys=True))

if __name__ == '__main__':
    modes = {'preflight': preflight, 'comparison': comparison, 'publish': publish, 'remote': remote, 'export': export}
    try:
        modes[sys.argv[1]]()
    except Exception as error:
        print('BLOCKED_' + type(error).__name__ + ':' + str(error), file=sys.stderr)
        sys.exit(1)
