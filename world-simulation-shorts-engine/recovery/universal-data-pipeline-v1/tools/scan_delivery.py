"""Scan this additive delivery for credential-shaped bytes, not variable names."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
PATTERNS = {
    'githubToken': rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})\b',
    'privateKey': rb'-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----',
    'awsAccessKey': rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'dropboxLongToken': rb'\bsl\.[A-Za-z0-9_-]{60,}\b',
    'bearerCredential': rb'(?i)authorization[\"\x27]?\s*[:=]\s*[\"\x27]?bearer\s+[A-Za-z0-9_.-]{30,}',
}
EXCLUDED = {'SECRET_SCAN.json', 'SHA256SUMS'}
files, findings = [], []
for file in sorted(HERE.rglob('*')):
    if not file.is_file() or file.name in EXCLUDED:
        continue
    if file.is_symlink():
        raise ValueError('DELIVERY_SYMLINK_FORBIDDEN')
    raw = file.read_bytes()
    path = file.relative_to(REPO).as_posix()
    files.append({'path': path, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    if file.suffix.lower() in {'.mp4', '.png', '.zip', '.jpg', '.woff', '.woff2'}:
        continue
    for label, expression in PATTERNS.items():
        matches = list(re.finditer(expression, raw))
        if matches:
            # Never record the matched credential itself.
            findings.append({'path': path, 'kind': label, 'count': len(matches)})
changed = subprocess.check_output(['git', 'diff', '--name-only', 'e39969cbc76a071d34a38440d9551425e6d5e545'],
                                  cwd=REPO, text=True).splitlines()
prefix = HERE.relative_to(REPO).as_posix() + '/'
outside = [path for path in changed if not path.startswith(prefix)]
result = {'schema': 'WORLD_ENGINE_DATA_SECRET_SCAN_V1',
          'status': 'PASS' if not findings and not outside else 'FAIL',
          'credentialFindings': findings, 'changedOutsideNewNamespace': outside,
          'scannedFiles': len(files), 'method': 'bounded credential-pattern scan plus tracked baseline diff',
          'limitations': 'Pattern scan is not a formal guarantee that every possible secret format is absent.',
          'files': files}
destination = HERE / 'reports/SECRET_SCAN.json'
destination.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k != 'files'}))
raise SystemExit(0 if result['status'] == 'PASS' else 1)
