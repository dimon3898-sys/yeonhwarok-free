#!/usr/bin/env python3
"""Final verification only: scan frozen required text and final-freeze text, with no raw findings."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

PINNED_SHA = 'e18325d568268b6efb6cd0cc721f8bea5667f4cd1c8d03618ab61987f41269ad'
TEXT_SUFFIXES = {'.json', '.geojson', '.osm', '.prj', '.tfw', '.js', '.mjs', '.py', '.md', '.txt', '.lock', '.html', '.css', '.toml', '.yaml', '.yml', '.csv', '.log', '.sh', ''}

def digest(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--scanner', required=True)
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    root = Path(__file__).resolve().parent
    scanner = Path(args.scanner).resolve()
    assert digest(scanner) == PINNED_SHA
    assert subprocess.check_output([str(scanner), 'version'], text=True).strip() == '8.24.3'
    inventory = repo / 'world-simulation-shorts-engine/recovery/event-v1-v3-visual-detail/manifests/HASH_MANIFEST.json'
    frozen = json.loads(inventory.read_text())['required_files']
    paths = {repo / r['path'] for r in frozen}
    paths.add(inventory)
    paths.update(p for p in root.rglob('*') if p.is_file() and p.name != 'SECRET_SCAN.json')
    rows, binary = [], []
    env = os.environ.copy()
    env.pop('GITLEAKS_CONFIG', None)
    env.pop('GITLEAKS_CONFIG_TOML', None)
    with tempfile.TemporaryDirectory(prefix='event-v1-final-secret-scan-') as tmpname:
        tmp = Path(tmpname)
        stage = tmp / 'scope'
        stage.mkdir()
        config = tmp / 'defaults.toml'
        config.write_text('[extend]\nuseDefault = true\n')
        ignore = tmp / 'empty.gitleaksignore'
        ignore.write_text('')
        for p in sorted(paths):
            assert p.is_file() and not p.is_symlink()
            relative = p.resolve().relative_to(repo)
            if p.suffix.lower() not in TEXT_SUFFIXES and p.name != 'SHA256SUMS':
                binary.append({'file': str(relative), 'bytes': p.stat().st_size,
                               'scope': 'Binary asset; approved/reproduction SHA checks, not text secret scan'})
                continue
            data = p.read_bytes()
            assert b'\x00' not in data, 'Unexpected binary bytes in declared text input: ' + str(relative)
            data.decode('utf-8')
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, target)
            rows.append({'file': str(relative), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
        report = tmp / 'findings.json'
        command = [str(scanner), 'dir', str(stage), '--redact=100', '--max-decode-depth=3',
                   '--ignore-gitleaks-allow', '--no-banner', '--no-color', '--config', str(config),
                   '--gitleaks-ignore-path', str(ignore), '--report-format=json', '--report-path', str(report)]
        run = subprocess.run(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        findings = []
        report_created = report.exists()
        if report_created:
            for item in json.loads(report.read_text()) or []:
                findings.append({'file': item.get('File', '').removeprefix(str(stage) + '/'),
                                 'rule': item.get('RuleID'), 'start_line': item.get('StartLine'),
                                 'end_line': item.get('EndLine')})
    changed = [r['file'] for r in rows if digest(repo / r['file']) != r['sha256']]
    passed = run.returncode == 0 and report_created and not findings and not changed
    payload = {'schema': 'EVENT_SYSTEM_V1_FINAL_SECRET_SCAN_V1', 'status': 'PASS' if passed else 'FAIL',
               'scanner': {'name': 'Gitleaks', 'version': '8.24.3', 'sha256': PINNED_SHA},
               'rules': 'Pinned embedded defaults; empty ignore list; no custom allowlist; allow comments ignored',
               'redaction_percent': 100, 'max_decode_depth': 3, 'exit_code': run.returncode, 'report_created': report_created,
               'findings_count': len(findings), 'findings': findings, 'input_mutations': changed,
               'input_files': rows, 'binary_inputs_not_claimed_as_text_scan': binary,
               'self_receipt_excluded': 'SECRET_SCAN.json', 'required_temp_only_files': []}
    (root / 'evidence/SECRET_SCAN.json').write_text(json.dumps(payload, indent=2) + '\n')
    print(json.dumps({'status': payload['status'], 'text_files': len(rows), 'findings': len(findings),
                      'input_mutations': len(changed)}))
    return 0 if passed else 1

if __name__ == '__main__':
    raise SystemExit(main())
