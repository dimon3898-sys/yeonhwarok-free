"""Reuse the complete secure bootstrap; select only the isolated overnight entry."""
from pathlib import Path
import hashlib
import importlib.util

HERE = Path(__file__).resolve().parent
_source = HERE.parent / 'universal-integration-completion-v2/bootstrap.py'
_manifest = HERE.parent / 'universal-integration-completion-v2/COMPLETION_FILES.json'
import json
_manifest_raw = _manifest.read_bytes()
if hashlib.sha256(_manifest_raw).hexdigest() != '99caa40a2c7566982f5c5502ce4d5ce95e35367dc5809c8e7013ca4e83c7b3e9':
    raise RuntimeError('OVERNIGHT_PRESERVED_MANIFEST_CHANGED')
_expected = json.loads(_manifest_raw)['files']['bootstrap.py']
if hashlib.sha256(_source.read_bytes()).hexdigest() != _expected:
    raise RuntimeError('OVERNIGHT_PRESERVED_BOOTSTRAP_CHANGED')
_spec = importlib.util.spec_from_file_location('_overnight_preserved_secure_bootstrap', _source)
_owner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_owner)
_owner.HERE = HERE
main = _owner.main

if __name__ == '__main__':
    raise SystemExit(main())
