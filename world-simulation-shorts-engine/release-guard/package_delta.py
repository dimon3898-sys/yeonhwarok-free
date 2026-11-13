"""Stage only explicitly sealed runtime delta; common gate owns publication."""
import hashlib
import json
from pathlib import Path
import sys

planfile, context = map(Path, sys.argv[1:])
root = Path(__file__).resolve().parents[2]
plan = json.loads(planfile.read_bytes())
context.mkdir(exist_ok=False)
for row in plan['files']:
    raw = (root / row['path']).read_bytes()
    assert len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256']
    p = context / 'overlay' / row['path']; p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(raw); p.chmod(0o644)
installed = '/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
prefix = installed + '/world-simulation-shorts-engine/recovery/'
entry = ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '-I', '-B', prefix + 'studio-cold-start-v2/bootstrap.py',
         '--startup-manifest', prefix + 'studio-cold-start-v2/STARTUP_MANIFEST.json', '--startup-manifest-sha256', plan['startupManifestSHA256'],
         '--source-manifest', prefix + 'codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json', '--source-manifest-sha256', plan['runtimeManifestSHA256'], '--export-root', '/world-storage']
(context / 'Dockerfile').write_text('FROM ' + plan['parentImage'] + '\nCOPY --chown=0:0 ' + json.dumps(['overlay/', installed + '/']) + '\nENTRYPOINT ' + json.dumps(entry) + '\n')
print(json.dumps({'status': 'STAGED_EXACT_DELTA', 'files': len(plan['files']), 'GPUExecutions': 0}))
