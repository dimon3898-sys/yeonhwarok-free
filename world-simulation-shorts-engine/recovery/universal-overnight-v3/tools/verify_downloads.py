"""Verify commit-pinned, anonymous public downloads against local bytes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]


def verify(commit):
    if not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('EXACT_PUBLIC_COMMIT_REQUIRED')
    files = [p for directory in ('public-review', 'handoff')
             for p in sorted((ROOT / directory).iterdir()) if p.is_file()]
    if not files or any(p.is_symlink() for p in files):
        raise ValueError('PUBLIC_REGULAR_ARTIFACTS_REQUIRED')

    def check(file):
        expected_size = file.stat().st_size
        expected = hashlib.sha256(file.read_bytes()).hexdigest()
        relative = file.relative_to(REPO).as_posix()
        url = 'https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/' + commit + '/' + quote(relative, safe='/')
        digest, count = hashlib.sha256(), 0
        with urlopen(Request(url, headers={'User-Agent': 'WORLD-ENGINE-Public-Integrity-Check'}), timeout=30) as response:
            if response.status != 200:
                raise ValueError('PUBLIC_HTTP_200_REQUIRED')
            content_type = response.headers.get('Content-Type')
            for chunk in iter(lambda: response.read(1024 * 1024), b''):
                count += len(chunk)
                if count > expected_size:
                    raise ValueError('PUBLIC_DOWNLOAD_SIZE_MISMATCH')
                digest.update(chunk)
        if count != expected_size or digest.hexdigest() != expected:
            raise ValueError('PUBLIC_DOWNLOAD_SHA_MISMATCH')
        return {'file': relative, 'url': url, 'httpStatus': 200,
                'bytes': count, 'sha256': expected, 'downloadMatchesOriginal': True,
                'contentType': content_type}

    with ThreadPoolExecutor(max_workers=3) as workers:
        results = list(workers.map(check, files))
    report = {'schema': 'WORLD_ENGINE_OVERNIGHT_PUBLIC_DOWNLOAD_VERIFICATION_V1',
        'status': 'PASS', 'checkedAtUTC': datetime.now(timezone.utc).isoformat(),
        'publishCommit': commit, 'anonymousPublicDownloads': True,
        'gpuExecutionPerformed': False, 'artifacts': results}
    (ROOT / 'reports/DOWNLOAD_VERIFICATION.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    report = verify(args.commit)
    print(json.dumps({'status': report['status'], 'files': len(report['artifacts']),
                      'publishCommit': report['publishCommit']}))
