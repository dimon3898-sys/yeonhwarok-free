"""Read back public GitHub artifacts over verified HTTPS and compare actual bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit', required=True)
    parser.add_argument('--file', action='append', required=True)
    parser.add_argument('--download-root', type=Path, required=True)
    parser.add_argument('--report', type=Path, default=HERE / 'reports/DOWNLOAD_VERIFICATION.json')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-f0-9]{40}', args.commit):
        raise ValueError('IMMUTABLE_COMMIT_REQUIRED')
    args.download_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    rows = []
    for index, relative in enumerate(args.file):
        path = HERE / relative
        if (path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(HERE.resolve())
                or not relative.startswith(('public-review/', 'review-package/'))):
            raise ValueError('PUBLIC_REVIEW_ARTIFACT_REQUIRED')
        expected = hashlib.sha256(path.read_bytes()).hexdigest()
        url = ('https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/'
               + args.commit + '/' + urllib.parse.quote(path.relative_to(REPO).as_posix(), safe='/'))
        request = urllib.request.Request(url, headers={'User-Agent': 'WORLD-ENGINE-public-review-integrity/1'})
        actual, count = hashlib.sha256(), 0
        destination = args.download_root / (str(index) + '-' + path.name)
        with urllib.request.urlopen(request, timeout=60) as response, destination.open('xb') as output:
            status = response.status
            final_url = response.url
            if status != 200 or not final_url.startswith('https://'):
                raise ValueError('HTTPS_HTTP_200_REQUIRED')
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                count += len(chunk)
                if count > path.stat().st_size:
                    raise ValueError('DOWNLOAD_SIZE_EXCEEDED_EXPECTED')
                actual.update(chunk)
                output.write(chunk)
        row = {'file': relative, 'url': url, 'finalURL': final_url, 'httpStatus': status,
               'bytes': count, 'expectedBytes': path.stat().st_size,
               'expectedSHA256': expected, 'downloadSHA256': actual.hexdigest(),
               'status': 'PASS' if count == path.stat().st_size and actual.hexdigest() == expected else 'FAIL'}
        rows.append(row)
        print(json.dumps(row), flush=True)
        if row['status'] != 'PASS':
            raise ValueError('DOWNLOAD_SHA_OR_SIZE_MISMATCH')
    report = {'schema': 'WORLD_ENGINE_PUBLIC_DOWNLOAD_VERIFICATION_V1', 'commit': args.commit,
              'status': 'PASS', 'files': rows, 'tlsVerificationDisabled': False,
              'credentialUsedForPublicDownload': False}
    with args.report.open('x') as output:
        json.dump(report, output, indent=2)
        output.write('\n')
