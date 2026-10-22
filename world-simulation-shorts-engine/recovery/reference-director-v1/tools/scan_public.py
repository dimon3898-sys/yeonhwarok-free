"""Bounded secret-pattern scan of this additive namespace; never print matches."""
from pathlib import Path
import argparse
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    'PRIVATE_KEY_BLOCK': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    'GITHUB_CLASSIC_TOKEN': re.compile(rb'\bgh[pousr]_[A-Za-z0-9]{30,}\b'),
    'GITHUB_FINE_GRAINED_TOKEN': re.compile(rb'\bgithub_pat_[A-Za-z0-9_]{35,}\b'),
    'AWS_ACCESS_KEY_ID': re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'DROPBOX_LONG_BEARER': re.compile(rb'\bsl\.[A-Za-z0-9_-]{50,}\b'),
}


def scan():
    rows, findings = [], []
    for path in sorted(ROOT.rglob('*')):
        relative = path.relative_to(ROOT).as_posix()
        if not path.is_file() or relative.startswith('public-review/') or relative == 'reports/SECRET_SCAN.json':
            continue
        if path.is_symlink():
            raise RuntimeError('RD_PUBLIC_SYMLINK_FORBIDDEN')
        raw = path.read_bytes()
        rows.append({'path': relative, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
        for name, rule in RULES.items():
            for match in rule.finditer(raw):
                findings.append({'path': relative, 'rule': name, 'line': raw[:match.start()].count(b'\n') + 1})
    return {'schema': 'WORLD_ENGINE_REFERENCE_PUBLIC_SECRET_PATTERN_SCAN_V1',
            'status': 'PASS' if not findings else 'FAIL', 'filesScanned': len(rows),
            'rules': list(RULES), 'findings': findings, 'matchedValuesPrinted': False,
            'scope': 'Explicit credential patterns, not a proof that all possible secret formats are detectable',
            'originalReferenceVideoIncluded': False, 'sourceFrameImagesIncluded': False,
            'fileSnapshot': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='SECRET_SCAN.json')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Z0-9_]+\.json', args.output):
        raise RuntimeError('RD_SAFE_SCAN_REPORT_NAME_REQUIRED')
    result = scan()
    output = ROOT / 'reports' / args.output
    with output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'fileSnapshot'}))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
