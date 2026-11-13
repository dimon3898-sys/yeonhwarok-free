"""Check current-tree publication wiring; no old tests or image execution."""
import argparse
import json
from pathlib import Path
import re
import yaml

ACTION = './.world-engine-guard-control/.github/actions/world-engine-release-guard'

def audit(root):
    coverage = []
    for path in sorted((root / '.github/workflows').glob('*.y*ml')):
        value = yaml.safe_load(path.read_text())
        if not isinstance(value, dict):
            continue
        for name, job in value.get('jobs', {}).items():
            permissions = job.get('permissions', value.get('permissions', {}))
            steps = job.get('steps', [])
            package_write = permissions == 'write-all' or isinstance(permissions, dict) and permissions.get('packages') == 'write'
            publisher_secret = any('secrets.WORLD_ENGINE_SURFACE_GHCR_PUBLISHER_TOKEN' in json.dumps(step) for step in steps)
            if not package_write and not publisher_secret:
                continue
            assert len(steps) >= 2, 'UNGATED_PUBLISHER_JOB:' + str(path)
            checkout, guard = steps[:2]
            assert str(checkout.get('uses', '')).startswith('actions/checkout@'), 'GUARD_SOURCE_CHECKOUT_REQUIRED'
            assert checkout.get('with', {}).get('path') == '.world-engine-guard-control', 'GUARD_CHECKOUT_PATH_REQUIRED'
            assert checkout['with'].get('ref') == '${{ github.sha }}', 'GUARD_CURRENT_COMMIT_REQUIRED'
            assert guard.get('uses') == ACTION and not guard.get('if') and not guard.get('continue-on-error'), 'RELEASE_GUARD_BYPASSED'
            for step in steps:
                if 'build-push-action' in str(step.get('uses', '')):
                    assert step.get('with', {}).get('push') in (False, 'false', None), 'DIRECT_BUILDX_PUSH_FORBIDDEN'
                code = str(step.get('run', ''))
                assert not re.search(r'(?:sudo\s+docker|/(?:usr/)?(?:local/)?bin/docker)\s', code), 'ABSOLUTE_DOCKER_BYPASS_FORBIDDEN'
            coverage.append({'workflow': str(path.relative_to(root)), 'job': name, 'gate': ACTION})
    assert len(coverage) >= 47, 'PUBLISHER_COVERAGE_INCOMPLETE'
    return {'status': 'PASS', 'scope': 'CURRENT_TREE_ALL_FORMAL_PUBLISHER_JOBS_ANY_SCENE', 'jobs': coverage,
            'historicalBranchesModified': False, 'GPUExecutions': 0, 'oldPassReruns': 0}

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--repo', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); result = audit(a.repo)
    a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'publisherJobs': len(result['jobs']), 'GPUExecutions': 0}))
