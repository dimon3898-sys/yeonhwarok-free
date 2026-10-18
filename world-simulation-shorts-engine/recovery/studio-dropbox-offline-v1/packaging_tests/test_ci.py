"""Packaging safety regressions only; no Docker, provider or GPU calls."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('_offline_packaging_cpu_tests', HERE / 'ci.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='offline-ci-cpu-')
        self.root = Path(self.scratch.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'tests').mkdir()
        for name in ('offline_entry.py', 'offline_manifest.py', 'tests/test_fixture.py'):
            (self.source / name).write_text('# SYNTHETIC CPU PACKAGING FIXTURE\n')
        (self.source / 'Dockerfile').write_text('FROM synthetic-fixture-only\n')
        (self.source / '.dockerignore').write_text('**\n!extension/**\n')
        self.manifest = {'schema': 'SYNTHETIC_PACKAGING_FIXTURE',
                         'files': {name: self.digest(self.source / name)
                                   for name in ('offline_entry.py', 'offline_manifest.py')},
                         'testFiles': {'tests/test_fixture.py': self.digest(self.source / 'tests/test_fixture.py')}}
        self.write_manifest()
        self.path_patch = patch.object(package, 'HERE', self.source)
        self.path_patch.start()
        self.env_patch = patch.dict(os.environ, {
            'GITHUB_SHA': 'b' * 40, 'RUNNER_TEMP': str(self.root),
            **{name: '' for name in (*package.SECRET_NAMES, 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_TOKEN')},
        })
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()
        self.path_patch.stop()
        self.scratch.cleanup()

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def write_manifest(self):
        (self.source / package.MANIFEST).write_text(json.dumps(self.manifest))

    def test_staging_is_explicit_and_definition_immutable(self):
        (self.source / 'UNLISTED_CREDENTIAL_FIXTURE').write_text('SYNTHETIC_EXCLUDED_INPUT')
        before = (self.source / package.MANIFEST).read_bytes()
        context = package.payload_context()
        names = {p.relative_to(context / 'extension').as_posix()
                 for p in (context / 'extension').rglob('*') if p.is_file()}
        self.assertEqual(names, {'offline_entry.py', 'offline_manifest.py',
                                 'tests/test_fixture.py', package.MANIFEST})
        generated = json.loads((context / 'extension' / package.MANIFEST).read_bytes())
        self.assertEqual(generated['sourceCommit'], 'b' * 40)
        self.assertEqual(generated['definitionManifestSha256'], hashlib.sha256(before).hexdigest())
        self.assertEqual((self.source / package.MANIFEST).read_bytes(), before)

    def test_stale_manifest_hash_rejected(self):
        (self.source / 'offline_entry.py').write_text('# CHANGED SYNTHETIC SOURCE\n')
        with self.assertRaisesRegex(RuntimeError, 'OFFLINE_MANIFESTED_REGULAR_SOURCE_REQUIRED'):
            package.payload_context()

    def test_symlink_source_rejected(self):
        path = self.source / 'offline_entry.py'
        path.unlink()
        path.symlink_to(self.source / 'offline_manifest.py')
        with self.assertRaisesRegex(RuntimeError, 'OFFLINE_MANIFESTED_REGULAR_SOURCE_REQUIRED'):
            package.payload_context()

    def test_manifest_escape_rejected(self):
        self.manifest['files']['../outside.py'] = 'a' * 64
        self.write_manifest()
        with self.assertRaisesRegex(RuntimeError, 'OFFLINE_MANIFESTED_REGULAR_SOURCE_REQUIRED'):
            package.payload_context()

    def test_runtime_and_test_name_overlap_rejected(self):
        self.manifest['testFiles']['offline_entry.py'] = self.manifest['files']['offline_entry.py']
        self.write_manifest()
        with self.assertRaisesRegex(RuntimeError, 'OFFLINE_EXPLICIT_RUNTIME_AND_TESTS_REQUIRED'):
            package.payload_context()

    def test_source_commit_required(self):
        with patch.dict(os.environ, {'GITHUB_SHA': 'not-a-git-commit'}):
            with self.assertRaisesRegex(RuntimeError, 'OFFLINE_SOURCE_COMMIT_REQUIRED'):
                package.generated_manifest()

    def test_missing_offline_secrets_never_launch_probe(self):
        value = {}
        with patch.object(package.ci, 'state', return_value=value), \
             patch.object(package.ci, 'save'), \
             patch.object(package.ci, 'run', side_effect=AssertionError('NO CPU CONTAINER SHOULD START')), \
             patch('builtins.print'):
            package.external()
        report = value['externalDurability']
        self.assertEqual(report['status'], 'BLOCKED')
        self.assertEqual(report['reasonCode'], 'OFFLINE_EXTERNAL_SECRETS_NOT_BOUND')
        self.assertFalse(value['actualExternalBackupVerified'])
        self.assertFalse(value['actualOfflineTokenRefreshVerified'])

    def test_all_oauth_values_redacted_from_evidence(self):
        values = {name: 'SYNTHETIC_PRIVATE_FIXTURE_' + str(index)
                  for index, name in enumerate(package.SECRET_NAMES)}
        with patch.dict(os.environ, values):
            output = package.bounded('|'.join(values.values()))
        self.assertNotIn('SYNTHETIC_PRIVATE_FIXTURE', output)
        self.assertEqual(output.count('[REDACTED]'), len(values))

    def image_row(self):
        return {'Os': 'linux', 'Architecture': 'amd64', 'Id': 'sha256:' + 'a' * 64,
                'Size': 123, 'Config': {
                    'Entrypoint': ['/usr/bin/tini', '-g', '--', package.VENV_PYTHON, '-B',
                                   package.ci.DEST + '/offline_entry.py', 'bootstrap'],
                    'Labels': {'world-engine.studio-dropbox-offline.parent-digest': package.ci.BASE_DIGEST,
                               'world-engine.studio-dropbox-offline.source-revision': 'b' * 40},
                    'Healthcheck': {'Test': ['CMD', '/parent-health', 'http://127.0.0.1:8080/healthz']},
                    'Env': []}}

    def test_image_config_preserves_provenance_and_health(self):
        with patch.object(package.ci, 'run', return_value=SimpleNamespace(stdout=json.dumps([self.image_row()]))):
            result = package.inspect_image('synthetic-local-image')
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['platform'], 'linux/amd64')
        self.assertFalse(result['secretEnvironmentPresent'])

    def test_image_baked_secret_rejected(self):
        for name in package.SECRET_NAMES:
            with self.subTest(name=name):
                row = self.image_row()
                row['Config']['Env'] = [name + '=SYNTHETIC_FORBIDDEN_INPUT']
                with patch.object(package.ci, 'run', return_value=SimpleNamespace(stdout=json.dumps([row]))):
                    with self.assertRaisesRegex(RuntimeError, 'OFFLINE_IMAGE_SECRET_ENV_FORBIDDEN'):
                        package.inspect_image('synthetic-local-image')

    def test_docker_configuration_is_additive_without_installs(self):
        docker = (HERE / 'Dockerfile').read_text()
        self.assertIn('FROM ' + package.ci.BASE, docker)
        self.assertIn('offline_entry.py", "bootstrap"', docker)
        self.assertNotIn('pip install', docker)
        self.assertNotIn('apt-get', docker)
        self.assertNotIn('rm -', docker)
        self.assertNotIn('HEALTHCHECK ', docker)

    def test_inherited_helper_is_sha_pinned(self):
        self.assertEqual(self.digest(package.FROZEN_CI),
                         '93f588a9f1df0763814d42c8842495fd7733dcd3bbb97304c16a264d4cc6b393')


if __name__ == '__main__':
    unittest.main()
