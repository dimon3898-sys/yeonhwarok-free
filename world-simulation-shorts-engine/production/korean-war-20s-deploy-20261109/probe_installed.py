"""Read-only installed closure and startup checks. Never start a service/GPU."""
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import sys


def need(ok, code):
    if not ok:
        raise RuntimeError(code)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


request = json.load(sys.stdin)
root, plan = Path(request['root']), request['plan']
need(root.is_absolute() and not root.is_symlink(), 'INSTALLED_ROOT')
checked = 0
for row in request['closure']['files']:
    relative = Path(row['path'])
    need(not relative.is_absolute() and '..' not in relative.parts, 'INSTALLED_PATH')
    file = root / relative
    info = file.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022,
         'INSTALLED_FILE_TYPE_OWNER_MODE')
    current = file.parent
    while current != root.parent:
        parent = current.lstat()
        need(stat.S_ISDIR(parent.st_mode) and parent.st_uid == 0 and not parent.st_mode & 0o022,
             'INSTALLED_PARENT_TYPE_OWNER_MODE')
        current = current.parent
    raw = file.read_bytes()
    need(len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256'],
         'INSTALLED_BYTES_MISMATCH')
    checked += 1
startup = root / 'world-simulation-shorts-engine/recovery/studio-cold-start-v2'
source = root / 'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json'
module = load('_installed_final_bootstrap', startup / 'bootstrap.py')
module.verify_startup(startup / 'STARTUP_MANIFEST.json', plan['startupManifestSHA256'])
child = load('_installed_final_child', startup / 'worker.py')
child.bootstrap(startup / 'STARTUP_MANIFEST.json', plan['startupManifestSHA256'])
_, contract = module.source_contract(source, plan['runtimeManifestSHA256'])
need(contract.expected_sha256 == module.SOURCE_SHA == plan['runtimeManifestSHA256'],
     'INSTALLED_RUNTIME_MANIFEST_BINDING')
for row in plan.get('precreatedDirectories', []):
    info = Path(row['path']).lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == row['uid'] and info.st_gid == row['gid']
         and stat.S_IMODE(info.st_mode) == int(row['mode'], 8), 'PRIVATE_DIRECTORY_INSTALLATION')
print(json.dumps({'status': 'PASS', 'scope': 'FINAL_INSTALLED_CLOSURE_AND_STARTUP_HANDOFF',
                  'filesChecked': checked, 'privateRawAssetsInImage': False,
                  'oldPASSReruns': 0, 'gpuStarts': 0, 'renderedFrames': 0}, sort_keys=True))
