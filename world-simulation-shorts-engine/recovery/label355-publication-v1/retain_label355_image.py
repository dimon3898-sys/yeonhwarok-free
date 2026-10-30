#!/usr/bin/env python3
"""Retain this one candidate in a new Release before GHCR publication. No retries."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import urllib.parse
import urllib.request

REPO = 'dimon3898-sys/yeonhwarok-free'
SOURCE = 'af9347963b4405dac66cdbe0ad6c6898c3d42ea0'
PARENT = 'sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da'
ROOT = Path(os.environ['RUNNER_TEMP']) / 'label355-retention'
ROOT.mkdir(exist_ok=True)
API = 'https://api.github.com/repos/' + REPO
RELEASE_TAG = 'label355-image-backup-' + os.environ['GITHUB_RUN_ID']

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
        'name': 'Label355 candidate backup ' + os.environ['GITHUB_RUN_ID'],
        'body': 'One authorized candidate image backup. Not a video or GPU success claim. Existing images and tags are unchanged.',
        'draft': False, 'prerelease': True, 'make_latest': 'false'})
    write('RELEASE.json', release)
    write('RESERVATION.json', {'runID': os.environ['GITHUB_RUN_ID'], 'sourceCommit': SOURCE,
        'parentDigest': PARENT, 'maxBuilds': 1, 'maxGHCRPublications': 1, 'retries': 0})
    proof = upload(release, ROOT / 'RESERVATION.json')
    write('RESERVATION_RESULT.json', {'status': 'PASS', 'releaseURL': release['html_url'], 'asset': proof})
    print('LABEL355_RETENTION_RESERVED=' + release['html_url'], flush=True)

def archive():
    need(read('RESERVATION_RESULT.json')['status'] == 'PASS', 'RETENTION_NOT_RESERVED')
    release = read('RELEASE.json')
    docker = ['docker', '--host=unix:///var/run/docker.sock']
    image_id = subprocess.check_output(docker + ['image', 'inspect', '--format', '{{.Id}}', os.environ['TAG']], text=True).strip()
    tar = ROOT / 'candidate-image.tar'
    subprocess.run(docker + ['image', 'save', '--output', str(tar), os.environ['TAG']], check=True)
    with tarfile.open(tar) as archive_file:
        manifest = json.load(archive_file.extractfile('manifest.json'))
        need(len(manifest) == 1, 'ARCHIVE_SINGLE_IMAGE')
        config = archive_file.extractfile(manifest[0]['Config']).read()
        need('sha256:' + hashlib.sha256(config).hexdigest() == image_id, 'ARCHIVED_IMAGE_IDENTITY')
    compressor = subprocess.Popen(['gzip', '-1', '-c', str(tar)], stdout=subprocess.PIPE)
    try:
        subprocess.run(['split', '-b', '1900M', '-d', '-a', '3', '-', str(ROOT / 'candidate-image.tar.gz.part-')], stdin=compressor.stdout, check=True)
    finally:
        compressor.stdout.close()
    need(compressor.wait() == 0, 'IMAGE_COMPRESSION_FAILED')
    parts = sorted(ROOT.glob('candidate-image.tar.gz.part-*'))
    need(bool(parts), 'IMAGE_ARCHIVE_MISSING')
    assets = [upload(release, part) for part in parts]
    result = {'status': 'PASS', 'imageID': image_id, 'sourceCommit': SOURCE, 'parentDigest': PARENT,
        'releaseURL': release['html_url'], 'releaseTag': RELEASE_TAG, 'assets': assets,
        'restore': 'Concatenate parts in numeric order, gzip -dc, then docker load. No rebuild required.',
        'archiveBytes': sum(p.stat().st_size for p in parts), 'archiveFormat': 'docker-save-gzip-split', 'retries': 0}
    write('RETENTION_RESULT.json', result)
    upload(release, ROOT / 'RETENTION_RESULT.json')
    print('LABEL355_IMAGE_RETAINED=' + json.dumps(result, sort_keys=True), flush=True)

if __name__ == '__main__':
    {'reserve': reserve, 'archive': archive}[sys.argv[1]]()
