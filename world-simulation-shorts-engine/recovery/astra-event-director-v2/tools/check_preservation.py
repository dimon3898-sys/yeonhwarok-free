"""Verify immutable parent bytes; this tool cannot render, deploy, or admit GPU work."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ENGINE, REPO = ROOT.parents[1], ROOT.parents[2]


def verify():
    baseline = json.loads((ROOT / 'BASELINE.json').read_bytes())
    allowed = ROOT.relative_to(REPO).as_posix() + '/'
    changed = subprocess.check_output(
        ['git', 'diff', '--name-only', baseline['baselineCommit'], '--'], cwd=REPO, text=True
    ).splitlines()
    outside = [name for name in changed if not name.startswith(allowed)]
    manifest = ENGINE / 'recovery/story-director-16frames-v1/reports/SOURCE_ASSET_MANIFEST.json'
    parent = json.loads(manifest.read_bytes())
    replay = json.loads((ROOT / 'reports/ORIGINAL_SOURCE_REPLAY.json').read_bytes())
    verified, errors, generated = [], [], []
    for row in parent['files']:
        name = row['path']
        if name.startswith('@'):
            generated.append(name)
            continue
        relative = Path(name)
        # The existing manifest records completion sources from the repository
        # root and other engine owners relative to the engine directory.
        base = REPO if relative.parts[0] == ENGINE.name else ENGINE
        file = (base / relative).resolve()
        # The inherited closure also names the pinned sibling JavaScript
        # dependencies with ../cinematic-world-map/...; require repository scope.
        if relative.is_absolute():
            raise ValueError('PARENT_MANIFEST_REPOSITORY_SCOPE_REQUIRED')
        if not file.is_relative_to(REPO):
            if relative.name != 'PLAN.json' or row['sha256'] != replay['originalPlanSHA256']:
                raise ValueError('PARENT_MANIFEST_UNRECOGNIZED_GENERATED_INPUT')
            generated.append(name)
            file = Path(replay['preparedPath']).parent / 'PLAN.json'
        if not file.is_file() or file.is_symlink():
            errors.append({'path': name, 'error': 'MISSING_OR_SYMLINK'})
            continue
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
        if digest != row['sha256'] or file.stat().st_size != row['bytes']:
            errors.append({'path': name, 'error': 'PARENT_BYTES_CHANGED'})
        else:
            verified.append(name)
    return {
        'schema': 'ASTRA_V2_IMMUTABLE_PARENT_PRESERVATION_V1',
        'status': 'PASS' if not outside and not errors else 'FAIL',
        'baselineCommit': baseline['baselineCommit'],
        'parentManifestSHA256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
        'outsideNamespaceChanges': outside,
        'verifiedParentFiles': len(verified),
        'parentFileErrors': errors,
        'generatedInputAliasesCheckedBySeparateSourceReplay': generated,
        'sourceReplayEvidence': 'reports/ORIGINAL_SOURCE_REPLAY.json',
        'originalFinalOrCoreModificationAllowed': False,
        'hardwareVerified': False,
        'visualQualityApproved': False,
    }


if __name__ == '__main__':
    result = verify()
    (ROOT / 'reports/PRESERVATION.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
