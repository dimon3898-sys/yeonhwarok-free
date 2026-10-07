"""Extract the exact already-calibrated offline speech profile at image build.

No system/graphics packages are replaced. HTTPS package bytes are pinned; the
original GPL copyright/source notices are retained alongside isolated files.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request
from urllib.parse import urlsplit


def prepare(manifest, destination):
    record = json.loads(Path(manifest).read_text())
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    def download(package):
        if not package['url'].startswith('https://archive.ubuntu.com/ubuntu/pool/'):
            raise RuntimeError('TTS_PACKAGE_SOURCE_INVALID')
        with urllib.request.urlopen(package['url'], timeout=60) as response:
            data = response.read(16 * 1024 * 1024 + 1)
        if len(data) != package['size'] or hashlib.sha256(data).hexdigest() != package['sha256']:
            raise RuntimeError('TTS_PACKAGE_HASH_MISMATCH')
        return data
    for package in record['packages']:
        data = download(package)
        file = root / (package['name'] + '.deb')
        file.write_bytes(data)
        subprocess.run(['dpkg-deb', '-x', str(file), str(root)], check=True)
        file.unlink()
    for relative, expected in record['calibrated_files'].items():
        if hashlib.sha256((root/relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError('TTS_CALIBRATED_FILE_MISMATCH')
    source = root/'corresponding-source'
    source.mkdir()
    for archive in record['source_archives']:
        (source/Path(urlsplit(archive['url']).path).name).write_bytes(download(archive))
    (root/'SOURCE_PACKAGES.json').write_text(json.dumps(record, indent=2))


if __name__ == '__main__':
    import sys
    prepare(sys.argv[1], sys.argv[2])
