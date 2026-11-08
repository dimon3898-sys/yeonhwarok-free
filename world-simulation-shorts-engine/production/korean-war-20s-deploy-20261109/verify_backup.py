"""Download exact released image bytes and prove an offline docker-load recovery.

No retries, registry publication, container execution, or authenticated redirects.
Reuse the established archive identity verifier supplied by the caller.
"""
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import urllib.parse
import urllib.request


def need(ok, code):
    if not ok:
        raise RuntimeError(code)


class AssetStream(io.RawIOBase):
    def __init__(self, assets):
        self.assets = iter(assets)
        self.stream = None
        self.receipts = []
        self.total = 0
        self.finished = False

    def readable(self):
        return True

    def readinto(self, buffer):
        while True:
            if self.finished:
                return 0
            if self.stream is None:
                try:
                    self.asset = next(self.assets)
                except StopIteration:
                    self.finished = True
                    return 0
                url = urllib.parse.urlparse(self.asset['browser_download_url'])
                need(url.scheme == 'https' and url.hostname == 'github.com'
                     and url.path.startswith('/dimon3898-sys/yeonhwarok-free/releases/download/'),
                     'BACKUP_DOWNLOAD_URL')
                # Public release asset URL: no token is ever attached to a redirect.
                self.stream = urllib.request.urlopen(self.asset['browser_download_url'], timeout=120)
                final = urllib.parse.urlparse(self.stream.url)
                need(final.scheme == 'https' and (final.hostname == 'github.com'
                     or final.hostname.endswith('.githubusercontent.com')),
                     'BACKUP_DOWNLOAD_DESTINATION')
                self.digest = hashlib.sha256()
                self.count = 0
            raw = self.stream.read(min(len(buffer), 1024 * 1024))
            if raw:
                self.count += len(raw)
                self.total += len(raw)
                need(self.count <= self.asset['size'], 'BACKUP_DOWNLOAD_OVERSIZE')
                self.digest.update(raw)
                buffer[:len(raw)] = raw
                return len(raw)
            self.stream.close()
            self.stream = None
            need(self.count == self.asset['size']
                 and 'sha256:' + self.digest.hexdigest() == self.asset['digest'],
                 'BACKUP_DOWNLOAD_HASH_OR_SIZE')
            self.receipts.append({'name': self.asset['name'], 'bytes': self.count,
                                  'sha256': self.digest.hexdigest()})

    def close(self):
        if self.stream is not None:
            self.stream.close()
        super().close()


def verify(keep, retained, destination, expected_id, *, original_tar_sha256=None):
    need(retained.get('status') == 'PASS' and retained.get('archiveRootDigest') == expected_id,
         'BACKUP_RETAINED_IDENTITY')
    assets = retained['assets']
    need(assets and len(assets) < 100 and
         all(row['name'] == 'candidate-image.tar.gz.part-' + str(i).zfill(3)
             and type(row['size']) is int and 0 < row['size'] < 2 * 1024**3
             and re.fullmatch(r'sha256:[a-f0-9]{64}', row['digest'])
             for i, row in enumerate(assets)), 'BACKUP_PART_ORDER_OR_IDENTITY')
    destination = Path(destination)
    digest = hashlib.sha256()
    stream = AssetStream(assets)
    try:
        with io.BufferedReader(stream) as buffered, gzip.GzipFile(fileobj=buffered, mode='rb') as decoded:
            with destination.open('xb') as output:
                while raw := decoded.read(1024 * 1024):
                    digest.update(raw)
                    output.write(raw)
            # Consume gzip/concatenation tail and final asset checks.
            need(decoded.read(1) == b'', 'BACKUP_GZIP_TRAILING_DATA')
        need(len(stream.receipts) == len(assets), 'BACKUP_NOT_ALL_ASSETS_DOWNLOADED')
        if original_tar_sha256 is not None:
            need(digest.hexdigest() == original_tar_sha256, 'BACKUP_ROUNDTRIP_TAR_IDENTITY')
        with tarfile.open(destination) as archive:
            identity = keep.archive_identity(archive, expected_id)
        need(identity['archiveRootDigest'] == expected_id
             and identity['configDigest'] == retained['configDigest']
             and identity['rootFSDiffIDs'] == retained['rootFSDiffIDs'], 'BACKUP_RESTORE_ARCHIVE_IDENTITY')
        docker = ['docker', '--host=unix:///var/run/docker.sock']
        subprocess.run(docker + ['load', '--input', str(destination)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        installed = json.loads(subprocess.check_output(docker + ['image', 'inspect', expected_id], text=True))[0]
        need(installed['Id'] == expected_id and installed['RootFS']['Layers'] == identity['rootFSDiffIDs'],
             'BACKUP_DOCKER_LOAD_IDENTITY')
        return {'status': 'PASS', 'scope': 'RELEASE_DOWNLOAD_HASH_ARCHIVE_AND_DOCKER_LOAD',
                'releaseURL': retained['releaseURL'], 'archiveRootDigest': expected_id,
                'configDigest': identity['configDigest'], 'imageManifestDigest': identity['imageManifestDigest'],
                'downloadedAssets': stream.receipts, 'downloadedBytes': stream.total,
                'restoredTarSHA256': digest.hexdigest(), 'dockerLoadVerified': True,
                'containerStarts': 0, 'gpuStarts': 0, 'renderedFrames': 0, 'retries': 0}
    finally:
        stream.close()
        destination.unlink(missing_ok=True)
