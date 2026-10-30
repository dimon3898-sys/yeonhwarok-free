#!/usr/bin/env python3
"""Run the unchanged review CLI once with deny-by-default external operations."""
import hashlib
import json
from pathlib import Path
import sys

publisher = Path(sys.argv[1]).resolve()
audit_path = Path(sys.argv[2]).resolve()
root = Path.cwd().resolve()
backup = root / 'label355-safe-evidence/world-simulation-shorts-engine/recovery/label-packaging-v1/backup_build_evidence.py'
g2 = root / 'world-simulation-shorts-engine/recovery/capture-diagnostics-g2-v1/build_g2_image.py'
paths = {str(publisher): 'publisher', str(backup): 'pinnedBackup', str(g2): 'g2ImportDependency'}
hashes = {name: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path, name in paths.items()}
denied = []
executed = set()
calls = []


def audit(event, args):
    if (event.startswith('socket.') or event in {'subprocess.Popen', 'urllib.Request'}
            or event in {'os.system', 'os.exec', 'os.posix_spawn', 'os.fork', 'os.forkpty'}
            or event.startswith('os.spawn')):
        denied.append(event)
        raise RuntimeError('ISOLATION_EXTERNAL_OPERATION_FORBIDDEN')
    if event == 'exec':
        filename = str(Path(args[0].co_filename).resolve())
        if filename in paths:
            executed.add(paths[filename])


def profile(frame, event, arg):
    if event != 'call':
        return
    filename = frame.f_code.co_filename
    if filename not in paths:
        return
    name = frame.f_code.co_name
    if filename == str(publisher) and name in {
            'preflight', 'comparison', 'publish', 'remote', 'export', 'docker', 'old_tag', 'absent'}:
        denied.append('publisher.' + name)
        raise RuntimeError('ISOLATION_NON_REVIEW_ENTRY_FORBIDDEN')
    if filename == str(g2) and name == 'registry':
        denied.append('g2.registry')
        raise RuntimeError('ISOLATION_REGISTRY_FORBIDDEN')
    if name in {'review_d9_exception', 'safe_evidence_bytes'}:
        calls.append({'module': paths[filename], 'function': name})


sys.addaudithook(audit)
import runpy

sys.setprofile(profile)
sys.argv = [str(publisher), 'review_d9_exception']
try:
    runpy.run_path(str(publisher), run_name='__main__')
finally:
    sys.setprofile(None)
    with audit_path.open('x', encoding='utf-8') as handle:
        json.dump({
            'schema': 'WORLD_ENGINE_D9_REVIEW_EXECUTION_ISOLATION_V1',
            'scope': 'ACTUAL_UNCHANGED_PYTHON_REVIEW_CLI_WITH_SYNTHETIC_RECEIPTS_ONLY',
            'deniedExternalAttempts': denied,
            'externalAttempts': len(denied),
            'executedSourceModules': sorted(executed),
            'executedSourceSHA256': hashes,
            'observedFunctionCalls': calls,
            'realPinnedBackupUsed': any(row['module'] == 'pinnedBackup' for row in calls),
            'dockerExecuted': False,
            'registryWrites': 0,
        }, handle, sort_keys=True, indent=2)
        handle.write('\n')
