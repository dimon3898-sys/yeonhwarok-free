"""Four-file overlay on the incident image after new archived-ledger PASS."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parents[2]
REPO = ENGINE.parent
ROOT = '/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
PARENT = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:8f8b3a2bfe859dc78715b9e8955fc4a74ef74229b44b86ac4417915b166ea8a4'
sha = lambda raw: hashlib.sha256(raw).hexdigest()

def main(context, cpu_file):
    cpu = json.loads(cpu_file.read_bytes())
    assert cpu['status'] == 'PASS' and cpu['baselineError'] == 'JSON_SIZE_INVALID'
    assert cpu['rendererExecutions'] == cpu['GPUExecutions'] == cpu['oldPassReruns'] == 0
    scope = json.loads((HERE / 'SCOPE.json').read_bytes())
    context.mkdir(exist_ok=False)
    files = []
    for name in scope['liveFilesChanged']:
        p = REPO / name
        raw = p.read_bytes()
        dest = context / 'overlay' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        dest.chmod(0o644)
        files.append({'path': name, 'bytes': len(raw), 'sha256': sha(raw)})
    assert len(files) == 4
    assert files[0]['sha256'] == cpu['reusedWorkerSHA256'] == 'd5bf03d4b79d70411c02d542bbebd08d9df0463636f558f02ee271c259b6b3d9'
    prefix = ROOT + '/world-simulation-shorts-engine/recovery/'
    entry = ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '-I', '-B', prefix + 'studio-cold-start-v2/bootstrap.py',
             '--startup-manifest', prefix + 'studio-cold-start-v2/STARTUP_MANIFEST.json',
             '--startup-manifest-sha256', scope['startupManifestSHA256'],
             '--source-manifest', prefix + 'codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json',
             '--source-manifest-sha256', scope['runtimeManifestSHA256'], '--export-root', '/world-storage']
    (context / 'Dockerfile').write_text('FROM ' + PARENT + '\nCOPY --chown=0:0 ' + json.dumps(['overlay/', ROOT + '/']) + '\nENTRYPOINT ' + json.dumps(entry) + '\n')
    plan = {'parentImage': PARENT, 'root': ROOT, 'files': files, 'entrypoint': entry,
            'runtimeManifestSHA256': scope['runtimeManifestSHA256'], 'startupManifestSHA256': scope['startupManifestSHA256'],
            'reusedWorkerSHA256': cpu['reusedWorkerSHA256'], 'cpuResultSHA256': sha(cpu_file.read_bytes()),
            'renderersChanged': False, 'inputsChanged': False, 'GPUExecutions': 0}
    (context / 'CONTEXT.json').write_text(json.dumps(plan, indent=2) + '\n')
    shutil.copyfile(HERE / 'verify_installed.py', context / 'verify_installed.py')
    print(json.dumps({'overlayFiles': len(files), 'parentImage': PARENT, 'GPUExecutions': 0}))

if __name__ == '__main__':
    main(Path(sys.argv[1]), Path(sys.argv[2]))
