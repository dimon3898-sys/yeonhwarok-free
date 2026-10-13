#!/usr/bin/env python3
"""Verify original immutable Flow review bytes using real HTTP GETs; never encode media."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import urllib.request

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    assert len(args.commit) == 40 and all(c in '0123456789abcdef' for c in args.commit)
    root = Path(__file__).resolve().parent
    repo = root.parents[2]
    public = root / 'public-review'
    files = sorted(p for p in public.iterdir() if p.is_file())
    assert len(files) == 10
    assert len([p for p in files if p.suffix == '.png']) == 8
    assert len([p for p in files if p.suffix == '.mp4']) == 1
    assert {p.name for p in files if not p.suffix} == {'SHA256SUMS'}
    assert all(p.suffix in {'.png', '.mp4', ''} and not p.is_symlink() for p in files)
    base = 'https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/' + args.commit + '/' + public.relative_to(repo).as_posix() + '/'
    with tempfile.TemporaryDirectory(prefix='flow-v2-public-review-get-') as temporary:
        temporary = Path(temporary)
        def check(source):
            original = source.read_bytes()
            relative = source.relative_to(repo).as_posix()
            assert original == subprocess.check_output(['git', 'show', args.commit + ':' + relative], cwd=repo)
            url = base + source.name
            request = urllib.request.Request(url, headers={'Accept-Encoding': 'identity'})
            with urllib.request.urlopen(request, timeout=60) as response:
                status = response.status
                downloaded = response.read()
            assert status == 200, url
            expected = hashlib.sha256(original).hexdigest()
            actual = hashlib.sha256(downloaded).hexdigest()
            assert actual == expected and downloaded == original, url
            (temporary / source.name).write_bytes(downloaded)
            return {'file': source.name, 'url': url, 'http_status': status, 'sha256': expected,
                    'download_sha256': actual, 'bytes': len(downloaded), 'matches_original_and_commit': True}
        with ThreadPoolExecutor(max_workers=3) as workers:
            rows = list(workers.map(check, files))
        by_name = {r['file']: r for r in rows}
        sums = (temporary / 'SHA256SUMS').read_text().splitlines()
        assert len(sums) == 9
        for line in sums:
            checksum, filename = line.split('  ', 1)
            assert by_name[filename]['sha256'] == checksum
    report = {'schema': 1, 'status': 'PASS', 'mediaCommit': args.commit, 'files': rows, 'verifiedFiles': 10,
              'publicReviewAllowedOnly': ['MP4', 'PNG', 'SHA256SUMS'], 'publicReviewOtherFiles': 0,
              'originalMp4Reencoded': False, 'downloadCopiesTemporaryOnlyNotRuntimeInputs': True,
              'permanentGateExecuted': False, 'eventFinal': False, 'userVideoApproved': False}
    (root / 'evidence/HTTP_DOWNLOAD_VERIFY.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'http200': len(rows), 'matchingOriginalSha256': len(rows), 'mediaCommit': args.commit}))

if __name__ == '__main__':
    main()
