"""Compare every file captured before V3, without changing the originals."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--baseline', required=True)
p.add_argument('--output', default='outputs/v3_preservation_final.json')
a = p.parse_args()
project = Path(__file__).resolve().parents[1]
source = Path(a.baseline).resolve()
baseline = json.loads(source.read_text())
root = Path(baseline['root'])
destination = project / a.output
if destination.exists():
    raise FileExistsError(destination)
missing, changed = [], []
for relative, expected in baseline['files'].items():
    path = root / relative
    if not path.is_file():
        missing.append(relative)
    elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        changed.append(relative)
tracked = subprocess.check_output([
    'git', 'diff', '--name-status', 'HEAD', '--'], cwd=project.parent, text=True)
archive = Path(baseline['archive'])
assert archive.is_file()
result = {
    'baseline': str(source), 'baseline_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'original_project_files_checked': len(baseline['files']),
    'changed_original_files': changed, 'missing_original_files': missing,
    'tracked_repository_changes_before_v3_staging': tracked.splitlines(),
    'preserved_archive': str(archive), 'archive_bytes': archive.stat().st_size,
    'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
    'scope': 'All original project files in the pre-V3 snapshot; new V3 files excluded. '
             'Tracked repository diff is checked before staging the additive V3 commit.'}
with destination.open('x') as file:
    json.dump(result, file, indent=2)
print(json.dumps(result, indent=2))
assert not missing and not changed and not tracked
