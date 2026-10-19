#!/usr/bin/env python3
"""Verify public commit-pinned HTTPS downloads without credentials."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse
import datetime
import hashlib
import io
import json
import re
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = 'world-simulation-shorts-engine/recovery/universal-integration-completion-v2/'
FILES = [
    'public-review/WORLD_ENGINE_UNIVERSAL_COMPLETION_V2_REVIEW.zip',
    'public-review/DOWNLOAD_SHA256SUMS', 'public-review/README.md',
    'reports/RESULT_KO.md', 'reports/FEATURE_LEDGER_151.csv', 'reports/UNWIRED_LEDGER_53.csv',
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit', required=True)
    commit = parser.parse_args().commit
    if not re.fullmatch('[a-f0-9]{40}', commit):
        raise RuntimeError('COMMIT_PIN_REQUIRED')
    base = 'https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/' + commit + '/' + NAMESPACE

    def check(name):
        request = urllib.request.Request(base + name, headers={'User-Agent': 'WORLD-ENGINE-public-review-verifier/1'})
        with urllib.request.urlopen(request, timeout=40) as response:
            status = response.status
            raw = response.read(16 * 1024**2 + 1)
        if status != 200 or not raw or len(raw) > 16 * 1024**2:
            raise RuntimeError('DOWNLOAD_HTTP_OR_SIZE_FAILED:' + name)
        original = (ROOT / name).read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != hashlib.sha256(original).hexdigest():
            raise RuntimeError('DOWNLOAD_SHA_MISMATCH:' + name)
        zip_verified = None
        if name.endswith('.zip'):
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                if archive.testzip() is not None:
                    raise RuntimeError('DOWNLOAD_ZIP_CORRUPT')
                for line in archive.read('SHA256SUMS').decode().splitlines():
                    digest, member = line.split('  ', 1)
                    if hashlib.sha256(archive.read(member)).hexdigest() != digest:
                        raise RuntimeError('DOWNLOAD_ZIP_MEMBER_SHA_MISMATCH')
                if any(name.endswith(('.py', '.mjs', '.yml', '.mp4', '.wav')) for name in archive.namelist()):
                    raise RuntimeError('DOWNLOAD_UNEXPECTED_SOURCE_OR_MEDIA')
                zip_verified = True
        return {'file': name, 'URL': base + name, 'HTTP': status, 'bytes': len(raw),
                'originalSHA256': actual, 'downloadSHA256': actual, 'SHA256Match': True,
                'downloadedZipMembersVerified': zip_verified}

    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(check, FILES))
    value = {'schema': 'WORLD_ENGINE_COMPLETION_PUBLIC_DOWNLOAD_RECEIPT_V1',
             'publicationCommit': commit, 'checkedAtUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'status': 'PASS', 'credentialUsed': False, 'files': results,
             'GPUExecuted': False, 'videoRendered': False}
    (ROOT / 'reports/PUBLIC_DOWNLOAD_VERIFICATION.json').write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'HTTP200AndSHA256Match': len(results),
                      'publicationCommit': commit, 'archiveSHA256': results[0]['downloadSHA256']}))


if __name__ == '__main__':
    main()
