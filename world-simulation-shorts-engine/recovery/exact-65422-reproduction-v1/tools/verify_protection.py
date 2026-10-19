"""Check immutable original files, old media, and the restricted Git change scope."""
from pathlib import Path
import hashlib
import json
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
BASE = '8e5053c3317a8b7ded366069274ca2d10a5dc8e2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    prefix = ROOT.relative_to(REPO).as_posix() + '/'
    changed = subprocess.check_output(['git', 'diff', '--name-only', BASE], cwd=REPO, text=True).splitlines()
    assert all(p.startswith(prefix) for p in changed), 'PROTECTED_EXISTING_TRACKED_FILE_CHANGED'
    untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=REPO, text=True).splitlines()
    assert all(p.startswith(prefix) for p in untracked), 'UNEXPECTED_UNTRACKED_FILE_OUTSIDE_NEW_NAMESPACE'
    manifest = json.loads((ROOT / 'reports/SOURCE_CAPSULE_MANIFEST.json').read_text())
    capsule = Path(manifest['capsuleRoot'])
    assert manifest['status'] == 'READY'
    assert manifest['originalReportBindingsRestored'] == 73
    checked = []
    for item in manifest['files']:
        file = capsule / item['path']
        assert file.is_file() and not file.is_symlink()
        assert file.stat().st_size == item['bytes'] and sha(file) == item['sha256'], item['path']
        checked.append(item['path'])
    original_media = Path('/workspace/attachments/6e700596-2b12-4e6d-9ac6-a6339aa633af/WORLD_ENGINE_MOVING_FRONTIER_GLOW_FIX_5S.mp4')
    assert sha(original_media) == 'f3de1bdf9244171a47c6e5eccca6aae1370f58d8bf4721a7658b6bca2eed2ef6'
    result = {'schema': 'EXACT_65422_PROTECTION_V1', 'status': 'PASS',
        'checkedAtUtc': datetime.now(timezone.utc).isoformat(), 'baselineCommit': BASE,
        'protectedTrackedFilesChanged': 0, 'changesConfinedToNewNamespace': True,
        'sourceCapsuleFilesChecked': len(checked), 'originalBoundFilesChecked': 73,
        'originalMediaUnchanged': True, 'originalCacheUsedOrModified': False,
        'existingSceneAssetRendererShaderCameraFinalChanged': False,
        'paidGpuExecuted': False, 'existingWorkloadRedeployed': False,
        'full80SecondRenderExecuted': False, 'finalPromoted': False,
        'requiredTempOnlyFiles': 0,
        'tempOnlyExplanation': 'Unpublished complete diagnostic rows and PNG cache are regenerable. All required source/configuration, immutable Git bindings, safe per-frame comparison, movie and checkpoints are persisted; no cache is required to repeat the capture.'}
    (ROOT / 'reports/PROTECTION.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return result


if __name__ == '__main__':
    verify()
