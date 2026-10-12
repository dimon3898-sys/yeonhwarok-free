#!/usr/bin/env python3
"""Pinned default-rule secret scan of new research/source bytes; never emit raw findings."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

PINNED_SHA256 = 'e18325d568268b6efb6cd0cc721f8bea5667f4cd1c8d03618ab61987f41269ad'

def digest(p):
    with p.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--scanner', required=True)
    parser.add_argument('--output')
    parser.add_argument('--git-tip')
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    root = Path(__file__).resolve().parent
    scanner = Path(args.scanner).resolve()
    if digest(scanner) != PINNED_SHA256 or subprocess.check_output([str(scanner), 'version']).decode().strip() != '8.24.3':
        raise SystemExit('Pinned scanner integrity/version failed')
    output = Path(args.output).resolve() if args.output else root / 'evidence/SECRET_SCAN.json'
    excluded = ('SECRET_SCAN', 'PERSISTENCE', 'POST_SCAN', 'POST_COMMIT')
    paths = [p for p in root.rglob('*') if p.is_file() and not p.name.startswith(excluded)]
    paths += [repo / 'world-simulation-shorts-engine/web/map_infographic_v1/detail_data_profile_v1.mjs',
              repo / 'world-simulation-shorts-engine/tests/detail_data_profile_v1.test.mjs']
    rows, summaries = [], []
    env = os.environ.copy()
    env.pop('GITLEAKS_CONFIG', None)
    env.pop('GITLEAKS_CONFIG_TOML', None)
    with tempfile.TemporaryDirectory(prefix='detail-admission-secret-scan-') as tmp:
        tmp = Path(tmp)
        stage = tmp / 'scope'
        stage.mkdir()
        config = tmp / 'trusted-default.toml'
        config.write_text('[extend]\nuseDefault = true\n')
        ignore = tmp / 'empty.gitleaksignore'
        ignore.write_text('')
        for source in sorted(set(paths)):
            if source.is_symlink():
                raise SystemExit('Unscanned symlink in required research scope')
            relative = source.resolve().relative_to(repo)
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            rows.append({'file':str(relative),'sha256':digest(source),'bytes':source.stat().st_size})
        common = ['--redact=100', '--max-decode-depth=3', '--ignore-gitleaks-allow', '--no-banner', '--no-color',
                  '--config',str(config),'--gitleaks-ignore-path',str(ignore),'--report-format=json']
        scans = [('new_worktree_bytes','dir',str(stage),[])]
        if args.git_tip:
            scans.append(('new_commit_history','git',str(repo),['--log-opts=9cf4661..'+args.git_tip]))
        for label, mode, target, extra in scans:
            report = tmp / (label+'.json')
            result = subprocess.run([str(scanner),mode,target,*extra,*common,'--report-path',str(report)],
                                    env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            findings=[]
            if report.exists():
                for row in json.loads(report.read_text()) or []:
                    findings.append({'file':row.get('File','').removeprefix(str(stage)+'/'),
                                     'rule':row.get('RuleID'),'start_line':row.get('StartLine'),'end_line':row.get('EndLine')})
            summaries.append({'scope':label,'exit_code':result.returncode,'report_created':report.exists(),
                              'findings_count':len(findings),'findings':findings})
    mutations=[r['file'] for r in rows if digest(repo/r['file']) != r['sha256']]
    passed=not mutations and all(r['exit_code']==0 and r['report_created'] and r['findings_count']==0 for r in summaries)
    payload={'schema':'DETAIL_SECRET_SCAN_V1','status':'PASS' if passed else 'FAIL',
             'scanner':{'name':'Gitleaks','version':'8.24.3','sha256':PINNED_SHA256,
                        'source':'https://github.com/gitleaks/gitleaks/releases/tag/v8.24.3'},
             'rules':'Embedded defaults; no custom allowlist; empty ignore list; allow comments ignored',
             'redaction_percent':100,'max_decode_depth':3,'input_files':rows,'input_mutations':mutations,
             'post_scan_exclusions':['SECRET_SCAN*','PERSISTENCE*','POST_SCAN*','POST_COMMIT*'],
             'git_range':None if not args.git_tip else '9cf4661..'+args.git_tip,'scans':summaries}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(payload,indent=2)+'\n')
    print(json.dumps({'status':payload['status'],'files':len(rows),'findings':[r['findings_count'] for r in summaries]}))
    return 0 if passed else 1

if __name__=='__main__':
    raise SystemExit(main())
