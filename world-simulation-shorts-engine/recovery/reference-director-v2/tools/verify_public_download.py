"""Download this exact public handoff; do not infer access from a Git push."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import io
import json
import re
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parents[1]
PREFIX = 'https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/'
RELATIVE = 'world-simulation-shorts-engine/recovery/reference-director-v2/'
NAME = 'WORLD_ENGINE_REFERENCE_DIRECTOR_V2_REVIEW.zip'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def fetch(url, expected):
    with urllib.request.urlopen(url, timeout=45) as response:
        status = response.status
        if status != 200:
            raise RuntimeError('R2_PUBLIC_HTTP_200_REQUIRED')
        raw = response.read(24 * 1024 * 1024 + 1)
    if len(raw) > 24 * 1024 * 1024 or digest(raw) != digest(expected):
        raise RuntimeError('R2_PUBLIC_DOWNLOAD_SHA_OR_SIZE_MISMATCH')
    return raw, {'url': url, 'httpStatus': status, 'bytes': len(raw),
                 'sha256': digest(raw), 'localSHA256Matched': True}


def verify(commit):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise RuntimeError('R2_IMMUTABLE_REMOTE_COMMIT_REQUIRED')
    rows = []
    base = PREFIX + commit + '/' + RELATIVE
    raw, row = fetch(base + 'public-review/' + NAME,
                     (HERE / 'public-review' / NAME).read_bytes())
    rows.append(row)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('R2_EXTERNAL_ZIP_CRC_FAILED')
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise RuntimeError('R2_EXTERNAL_ZIP_DUPLICATE_PATH')
        for name in names:
            if PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts:
                raise RuntimeError('R2_EXTERNAL_ZIP_UNSAFE_PATH')
        hashes = archive.read('SHA256SUMS').decode().splitlines()
        for line in hashes:
            expected, name = line.split('  ', 1)
            if not re.fullmatch(r'[0-9a-f]{64}', expected):
                raise RuntimeError('R2_EXTERNAL_INVALID_CHECKSUM')
            if digest(archive.read(name)) != expected:
                raise RuntimeError('R2_EXTERNAL_INTERNAL_SHA_MISMATCH')
        if set(names) != {line.split('  ', 1)[1] for line in hashes} | {'SHA256SUMS'}:
            raise RuntimeError('R2_EXTERNAL_ZIP_UNENUMERATED_FILE')
    for relative in ['public-review/SHA256SUMS', 'README_REVIEW.md',
                     'evidence/GRAPHIC_COMPONENT_UNIT_CONTACT_SHEET.png']:
        _, row = fetch(base + relative, (HERE / relative).read_bytes())
        rows.append(row)
    result = {'schema': 'WORLD_ENGINE_REFERENCE_DIRECTOR_EXTERNAL_DOWNLOAD_V2',
              'status': 'PASS', 'remoteArtifactCommit': commit, 'files': rows,
              'externalZipInternalSHAEntriesVerified': len(hashes),
              'externalZipCRCVerified': True, 'studioMP4Created': False,
              'paidGpuOrApiUsed': False, 'qualityPassClaimed': False}
    output = HERE / 'reports/PUBLIC_DOWNLOAD_VERIFICATION.json'
    with output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit', required=True)
    verify(parser.parse_args().commit)
