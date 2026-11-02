#!/usr/bin/env python3
"""Reuse established Release retention with containerd descriptor/config identity.
Existing helper remains unchanged; one complete archive, no retries.
"""
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tarfile
import urllib.parse
import urllib.request

REPO = 'dimon3898-sys/yeonhwarok-free'
SOURCE = 'f276f19fc3c61c77e17e3683a8b8302523a379dc'
PARENT = 'sha256:9e9301dec376a780f4fb2287fe092282baaef3d6cfdfc93532ea6763d9f9b0cf'
ROOT = Path(os.environ['RUNNER_TEMP']) / 'quality-labels-retention'
ROOT.mkdir(exist_ok=True)
API = 'https://api.github.com/repos/' + REPO
RELEASE_TAG = 'quality-labels-image-backup-' + os.environ['GITHUB_RUN_ID']

def need(ok, reason):
    if not ok:
        raise RuntimeError(reason)

def write(name, obj):
    with (ROOT / name).open('x') as stream:
        json.dump(obj, stream, sort_keys=True, indent=2)
        stream.write('\n')

def read(name):
    return json.loads((ROOT / name).read_bytes())

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def api(url, obj=None, file=None):
    parsed = urllib.parse.urlparse(url)
    need(parsed.scheme == 'https' and parsed.hostname in ('api.github.com', 'uploads.github.com'), 'UNEXPECTED_API_HOST')
    need(parsed.path.startswith('/repos/' + REPO + '/releases'), 'UNEXPECTED_API_PATH')
    headers = {'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
               'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
    data = json.dumps(obj).encode() if obj is not None else None
    if obj is not None:
        headers['Content-Type'] = 'application/json'
    if file is not None:
        headers.update({'Content-Type': 'application/octet-stream', 'Content-Length': str(file.stat().st_size)})
        with file.open('rb') as stream:
            req = urllib.request.Request(url, data=stream, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=600) as response:
                return json.load(response)
    req = urllib.request.Request(url, data=data, headers=headers, method='POST' if obj is not None else 'GET')
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)

def upload(release, path):
    size = path.stat().st_size
    digest = 'sha256:' + sha(path)
    need(0 < size < 2 * 1024**3, 'RELEASE_ASSET_SIZE')
    url = release['upload_url'].split('{', 1)[0] + '?' + urllib.parse.urlencode({'name': path.name})
    asset = api(url, file=path)
    need(asset['state'] == 'uploaded' and asset['size'] == size and asset.get('digest') == digest, 'RELEASE_UPLOAD_IDENTITY')
    check = api(API + '/releases/assets/' + str(asset['id']))
    need(check['state'] == 'uploaded' and check['size'] == size and check.get('digest') == digest, 'RELEASE_READBACK_IDENTITY')
    return {k: check[k] for k in ('id', 'name', 'size', 'digest', 'browser_download_url')}

def reserve():
    need(os.environ['GITHUB_REPOSITORY'] == REPO and os.environ['GITHUB_RUN_ATTEMPT'] == '1', 'RUN_GUARD')
    release = api(API + '/releases', {'tag_name': RELEASE_TAG, 'target_commitish': os.environ['GITHUB_SHA'],
        'name': 'Quality labels candidate backup ' + os.environ['GITHUB_RUN_ID'],
        'body': 'One authorized candidate image backup. Not a video or GPU success claim. Existing images and tags are unchanged.',
        'draft': False, 'prerelease': True, 'make_latest': 'false'})
    write('RELEASE.json', release)
    write('RESERVATION.json', {'runID': os.environ['GITHUB_RUN_ID'], 'sourceCommit': SOURCE,
        'parentDigest': PARENT, 'maxBuilds': 1, 'maxGHCRPublications': 1, 'retries': 0})
    proof = upload(release, ROOT / 'RESERVATION.json')
    write('RESERVATION_RESULT.json', {'status': 'PASS', 'releaseURL': release['html_url'], 'asset': proof})
    print('QUALITY_LABELS_RETENTION_RESERVED=' + release['html_url'], flush=True)

def archive_identity(archive_file, image_id):
    """Verify Docker-compatible config and containerd descriptor separately."""
    members=archive_file.getmembers()
    need(len(members)==len({m.name for m in members}),'ARCHIVE_DUPLICATE_MEMBERS')
    def raw(name):
        need(isinstance(name,str) and not name.startswith('/') and '..' not in name.split('/'), 'ARCHIVE_PATH')
        member = archive_file.getmember(name)
        need(member.isfile() and member.size <= 4 * 1024**2, 'ARCHIVE_METADATA_SIZE')
        return archive_file.extractfile(member).read()
    def blob(digest):
        need(isinstance(digest,str) and re.fullmatch(r'sha256:[a-f0-9]{64}',digest), 'ARCHIVE_DIGEST')
        value = raw('blobs/sha256/' + digest[7:])
        need('sha256:' + hashlib.sha256(value).hexdigest() == digest, 'ARCHIVE_BLOB_IDENTITY')
        return json.loads(value)
    manifest = json.loads(raw('manifest.json'))
    need(len(manifest) == 1, 'ARCHIVE_SINGLE_IMAGE')
    config_raw = raw(manifest[0]['Config'])
    config_digest = 'sha256:' + hashlib.sha256(config_raw).hexdigest()
    config = json.loads(config_raw)
    need(config.get('os') == 'linux' and config.get('architecture') == 'amd64', 'ARCHIVE_PLATFORM')
    need(len(manifest[0]['Layers']) == len(config['rootfs']['diff_ids']), 'ARCHIVE_LAYER_COUNT')
    for name in manifest[0]['Layers']:
        need(not name.startswith('/') and '..' not in name.split('/'), 'ARCHIVE_LAYER_PATH')
        member = archive_file.getmember(name)
        need(member.isfile() and member.size > 0, 'ARCHIVE_LAYER_CONTENT_MISSING')
    if image_id == config_digest:
        for name, expected in zip(manifest[0]['Layers'],config['rootfs']['diff_ids'],strict=True):
            with archive_file.extractfile(name) as stream:
                need('sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()==expected,'ARCHIVE_LEGACY_LAYER_IDENTITY')
        return {'imageID':image_id,'configDigest':config_digest,'imageManifestDigest':None,'archiveRootDigest':None,
                'identityMode':'CLASSIC_CONFIG_ID','layerCount':len(manifest[0]['Layers']),'rootFSDiffIDs':config['rootfs']['diff_ids']}
    index = json.loads(raw('index.json'))
    roots = index.get('manifests', [])
    need(len(roots)==1 and roots[0].get('digest') == image_id, 'ARCHIVE_ROOT_DESCRIPTOR_IDENTITY')
    target = blob(image_id)
    image_manifest_digest = image_id
    if 'manifests' in target:
        choices = [r for r in target['manifests'] if r.get('platform',{}).get('os') == 'linux' and r.get('platform',{}).get('architecture') == 'amd64']
        need(len(choices) == 1 and len(target['manifests']) == 1, 'ARCHIVE_SINGLE_PLATFORM_DESCRIPTOR')
        image_manifest_digest = choices[0]['digest']; target = blob(image_manifest_digest)
    need(target.get('config',{}).get('digest') == config_digest, 'ARCHIVED_CONFIG_DESCRIPTOR_IDENTITY')
    need(len(target.get('layers',[])) == len(manifest[0]['Layers']), 'ARCHIVE_DESCRIPTOR_LAYER_COUNT')
    for compatible_name, descriptor in zip(manifest[0]['Layers'],target['layers'],strict=True):
        need(re.fullmatch(r'sha256:[a-f0-9]{64}',descriptor['digest']),'ARCHIVE_LAYER_DIGEST')
        name='blobs/sha256/'+descriptor['digest'].split(':',1)[1]
        need(compatible_name==name,'ARCHIVE_COMPATIBLE_LAYER_ORDER')
        member=archive_file.getmember(name)
        need(member.isfile() and member.size == descriptor['size'] and member.size > 0,'ARCHIVE_DESCRIPTOR_LAYER_MISSING')
        with archive_file.extractfile(member) as stream:
            need('sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()==descriptor['digest'],'ARCHIVE_LAYER_BLOB_IDENTITY')
    return {'imageID':image_id,'configDigest':config_digest,'imageManifestDigest':image_manifest_digest,
            'archiveRootDigest':image_id,'identityMode':'CONTAINERD_DESCRIPTOR_AND_CONFIG','layerCount':len(manifest[0]['Layers']),'rootFSDiffIDs':config['rootfs']['diff_ids']}


def archive():
    need(read('RESERVATION_RESULT.json')['status'] == 'PASS', 'RETENTION_NOT_RESERVED')
    release = read('RELEASE.json')
    docker = ['docker', '--host=unix:///var/run/docker.sock']
    image_id = subprocess.check_output(docker + ['image', 'inspect', '--format', '{{.Id}}', os.environ['TAG']], text=True).strip()
    tar = ROOT / 'candidate-image.tar'
    subprocess.run(docker + ['image', 'save', '--output', str(tar), os.environ['TAG']], check=True)
    identity_error = None
    try:
        with tarfile.open(tar) as archive_file:
            identity = archive_identity(archive_file, image_id)
    except Exception as error:
        # Preserve this one built candidate before stopping; never publish an unverified archive.
        identity_error = str(error) if isinstance(error, RuntimeError) else 'ARCHIVE_FORMAT_UNEXPECTED'
        identity = {'imageID':image_id,'identityMode':'QUARANTINED_UNVERIFIED','identityFailure':identity_error}
    compressor = subprocess.Popen(['gzip', '-1', '-c', str(tar)], stdout=subprocess.PIPE)
    try:
        subprocess.run(['split', '-b', '1900M', '-d', '-a', '3', '-', str(ROOT / 'candidate-image.tar.gz.part-')], stdin=compressor.stdout, check=True)
    finally:
        compressor.stdout.close()
    need(compressor.wait() == 0, 'IMAGE_COMPRESSION_FAILED')
    parts = sorted(ROOT.glob('candidate-image.tar.gz.part-*'))
    need(bool(parts), 'IMAGE_ARCHIVE_MISSING')
    assets = [upload(release, part) for part in parts]
    result = {'status': 'BLOCKED_ARCHIVE_IDENTITY' if identity_error else 'PASS', **identity, 'sourceCommit': SOURCE, 'parentDigest': PARENT,
        'releaseURL': release['html_url'], 'releaseTag': RELEASE_TAG, 'assets': assets,
        'restore': 'Concatenate parts in numeric order, gzip -dc, then docker load. No rebuild required.',
        'archiveBytes': sum(p.stat().st_size for p in parts), 'archiveFormat': 'docker-save-gzip-split', 'retries': 0}
    write('RETENTION_RESULT.json', result)
    upload(release, ROOT / 'RETENTION_RESULT.json')
    print('QUALITY_LABELS_IMAGE_RETAINED=' + json.dumps(result, sort_keys=True), flush=True)
    need(identity_error is None, 'ARCHIVE_IDENTITY_FAILED_CANDIDATE_QUARANTINED')

if __name__ == '__main__':
    {'reserve': reserve, 'archive': archive}[sys.argv[1]]()
