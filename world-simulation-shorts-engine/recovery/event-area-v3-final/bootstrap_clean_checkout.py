#!/usr/bin/env python3
"""Verify actual remote provenance, hydrate canonical Git LFS, install frozen dependencies."""
import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

FINAL = Path(__file__).resolve().parent
REMOTE = 'https://github.com/dimon3898-sys/yeonhwarok-free.git'
BRANCH = 'development/event-tsunami-wave-polish-v3-20261013'
REVISION = 'a6ef67fa16143dc2bd53b334d583c05cf1476bed'
BASE = 'world-simulation-shorts-engine/recovery/event-tsunami-wave-polish-v3'


def digest(file):
    with file.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkout', required=True)
    args = parser.parse_args()
    checkout = Path(args.checkout).resolve()
    report = {'schema': 1, 'status': 'STARTED', 'checkout': str(checkout),
              'remote': REMOTE, 'branch': BRANCH, 'revision': REVISION,
              'clone_method': 'REMOTE_GIT_CLONE', 'source_or_asset_copies': False,
              'git_alternates': [], 'shared_system_toolchain': True,
              'fresh_operating_system': False, 'bootstrap_started_at': datetime.now(timezone.utc).isoformat(), 'logs': []}

    def command(argv, env=None):
        result = subprocess.run(argv, cwd=checkout, env=env, capture_output=True, text=True)
        report['logs'].append({'command': argv, 'exit_code': result.returncode,
                               'stdout': result.stdout, 'stderr': result.stderr})
        if result.returncode:
            raise RuntimeError('CHECKOUT_SETUP_COMMAND_FAILED ' + str(argv) + ' ' + result.stderr[-1500:])
        return result.stdout.strip()

    try:
        assert command(['git', 'rev-parse', 'HEAD']) == REVISION
        assert command(['git', 'config', '--get', 'remote.origin.url']) == REMOTE
        assert not (checkout / '.git/objects/info/alternates').exists()
        report['git_status_before_setup'] = command(['git', 'status', '--porcelain'])
        assert report['git_status_before_setup'] == ''
        inventory = json.loads((checkout / BASE / 'manifests/HASH_MANIFEST.json').read_text())
        dependency = json.loads((checkout / BASE / 'manifests/DEPENDENCY_MANIFEST.json').read_text())
        wanted = {row['path']: row for row in inventory['required_files']}
        # Find pointer files in this remote checkout rather than assuming local assets exist.
        lfs = []
        for name in wanted:
            with (checkout / name).open('rb') as stream:
                if stream.read(128).startswith(b'version https://git-lfs.github.com/spec/v1'):
                    lfs.append(name)
        command(['git', 'lfs', 'install', '--local'])
        pull = ['git', 'lfs', 'pull', '--include=' + ','.join(lfs), '--exclude=']
        command(pull)
        report['lfs_pull'] = {'status': 'PASS', 'command': pull, 'remote_source_only': True}
        report['lfs_objects'] = []
        for name in lfs:
            file = checkout / name
            expected = wanted[name]
            assert file.stat().st_size == expected['bytes'] and digest(file) == expected['sha256'], name
            report['lfs_objects'].append({**expected, 'source': 'REMOTE_GIT_LFS', 'status': 'PASS'})
        lock = checkout / 'cinematic-world-map/package-lock.json'
        before = digest(lock)
        assert not (checkout / 'cinematic-world-map/node_modules').exists()
        cache = checkout / '.git/area-final-npm-cache'
        assert not cache.exists()
        command(dependency['setup'], {**os.environ, 'npm_config_cache': str(cache), 'PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD': '1'})
        packages = [{'name': name, 'version': json.loads((checkout / 'cinematic-world-map/node_modules' / name / 'package.json').read_text())['version']}
                    for name in ['three', 'playwright', 'playwright-core']]
        assert packages == [{'name': 'three', 'version': '0.170.0'}, {'name': 'playwright', 'version': '1.62.1'}, {'name': 'playwright-core', 'version': '1.62.1'}]
        assert digest(lock) == before
        report['npm_ci'] = {'status': 'PASS', 'command': dependency['setup'], 'fresh_install': True,
                            'fresh_cache': True, 'cache': str(cache), 'packages': packages,
                            'package_lock_sha256_before': before, 'package_lock_sha256_after': before}
        report['toolchain'] = {'node': command(['node', '-p', 'process.versions.node']),
                               'python': command(['/usr/bin/python3', '-c', 'import platform;print(platform.python_version())']),
                               'chromium': command(['/usr/bin/chromium', '--version']).split()[1],
                               'ffmpeg': command(['ffmpeg', '-version']).splitlines()[0].split()[2].split('-')[0]}
        assert report['toolchain'] == {'node': '24.19.0', 'python': '3.13.5', 'chromium': '154.0.8037.57', 'ffmpeg': '7.1.5'}
        report['raster_dependencies'] = json.loads(command(['/usr/bin/python3', '-B', '-c',
            'import json,numpy,PIL;from osgeo import gdal;print(json.dumps({"GDAL":gdal.__version__,"numpy":numpy.__version__,"Pillow":PIL.__version__}))']))
        assert report['raster_dependencies'] == {'GDAL': '3.10.3', 'numpy': '2.2.4', 'Pillow': '11.1.0'}
        report['git_status_before_reproduction'] = command(['git', 'status', '--porcelain'])
        assert report['git_status_before_reproduction'] == ''
        report['git_status_after_setup'] = report['git_status_before_reproduction']
        report['clone'] = {'command': ['git', 'clone', '--depth', '1', '--single-branch', '--branch', BRANCH,
                                     '--filter=blob:none', '--no-checkout', REMOTE, str(checkout)],
                           'environment_overrides': {'GIT_LFS_SKIP_SMUDGE': '1'}, 'shallow': True,
                           'local_objects_reused': False, 'source_asset_hardlinks_or_symlink_reuse': False,
                           'selected_production_inputs': len(inventory['required_files']) + 2,
                           'additional_checkout_infrastructure': 2, 'sparse': True}
        report['status'] = 'PASS'
    except Exception as error:
        report['status'] = 'FAIL'
        report['error'] = str(error)
        raise
    finally:
        report['bootstrap_finished_at'] = datetime.now(timezone.utc).isoformat()
        (FINAL / 'evidence/CLEAN_CHECKOUT_SETUP.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'revision': REVISION, 'remote_lfs_objects': len(lfs), 'fresh_npm': True}))


if __name__ == '__main__':
    main()
