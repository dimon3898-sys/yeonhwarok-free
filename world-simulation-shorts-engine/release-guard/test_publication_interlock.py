"""New publication interlock negative tests with a non-network Docker double."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='release-interlock-test-') as folder:
    root = Path(folder)
    for name in ('control.py', 'probe.py', 'command.py', 'REQUIRED_FIXES.json'):
        shutil.copyfile(HERE / name, root / name)
    fake = root / 'fake-docker'
    fake.write_text('''#!/usr/bin/env python3
import json,sys
from pathlib import Path
p=Path(__file__).parent
with (p/'invocations.jsonl').open('a') as f:f.write(json.dumps(sys.argv[1:])+'\\n')
if sys.argv[1:3]==['image','inspect']:
 print(json.dumps([{'Id':'sha256:'+'a'*64,'Config':{'Entrypoint':[]}}]))
elif sys.argv[1]=='run':
 print(json.dumps({'status':'FAIL','code':'REQUIRED_WORKER_MISSING'}));sys.exit(1)
else:raise RuntimeError('NETWORK_OR_PUSH_MUST_NOT_BE_CALLED')
''')
    fake.chmod(0o755)
    (root / 'command.py').chmod(0o755)
    (root / 'docker').symlink_to(root / 'command.py')
    (root / 'skopeo').symlink_to(root / 'command.py')
    (root / 'INSTALLATION.json').write_text(json.dumps({'docker': str(fake), 'skopeo': str(fake), 'evidence': str(root / 'evidence')}))
    cases = []
    for executable, args, code in [
        ('docker', ['push', 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine:test-only'], 'REQUIRED_WORKER_MISSING'),
        ('docker', ['buildx', 'build', '--push', '.'], 'DIRECT_BUILD_PUBLISH_BLOCKED_LOAD_THEN_GATED_PUSH'),
        ('skopeo', ['copy', 'dir:fixture', 'docker://fixture'], 'OCI_DIRECT_PUBLISH_BLOCKED_USE_COMMON_DOCKER_GATE')]:
        process = subprocess.run([str(root / executable), *args], text=True, capture_output=True, timeout=20)
        assert process.returncode == 1 and code in process.stderr, (process.returncode, process.stderr)
        cases.append({'case': executable + ' ' + ' '.join(args[:2]), 'code': code, 'result': 'EXPECTED_FAIL'})
    calls = [json.loads(row) for row in (root / 'invocations.jsonl').read_text().splitlines()]
    assert not any('push' in row or 'copy' in row for row in calls)
    out = HERE / 'evidence/PUBLICATION_INTERLOCK_TESTS.json';out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({'status':'PASS','newCases':cases,'actualRegistryWrites':0,'actualImageTests':False,'GPUExecutions':0,'oldPassReruns':0},indent=2)+'\n')
    print('PASS: rejected-image push, direct build-push, direct OCI publication all blocked before network mutation')
