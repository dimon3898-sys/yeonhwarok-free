"""Focused packaging/security contract checks. No image build, network or GPU."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


package = load('_test_reconciliation_manifest', HERE / 'package_manifest.py')
ci = load('_test_reconciliation_ci', HERE / 'ci_package.py')


class PackageContractTests(unittest.TestCase):
    def fixture(self, root):
        names = {'bootstrap.py', 'studio_entry.py', 'studio_controller.py', 'runtime_bridge.py',
            'package_manifest.py', 'native_capabilities.py'}
        for name in names:
            (root / name).write_text('# isolated CPU packaging fixture\n')
        (root / 'Dockerfile').write_bytes((HERE / 'Dockerfile').read_bytes())
        manifest = {'schema': package.SCHEMA, 'sourceBaseCommit': package.BASE_COMMIT,
            'baseOperatingImageDigest': package.BASE_IMAGE,
            'previousManifestSHA256': package.PREVIOUS_MANIFEST_SHA,
            'files': {name: package.sha((root / name).read_bytes()) for name in names},
            'registeredCandidateImageDigest': None, 'gpuVerified': False,
            'existingSourceChanged': False}
        (root / 'RECONCILIATION_FILES.json').write_text(json.dumps(manifest))
        return manifest

    def test_parent_27_plus_55_verified_without_relabeling_gpu(self):
        proof = package._verify_parent()
        self.assertEqual(proof['files'], 27)
        self.assertEqual(proof['parentFiles'], 55)
        self.assertEqual(proof['manifestSHA256'], package.PREVIOUS_MANIFEST_SHA)
        self.assertFalse(proof['gpuVerified'])

    def test_payload_contains_only_manifested_runtime_and_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = self.fixture(root)
            (root / 'SECRET_DO_NOT_PACKAGE.txt').write_text('test-only ordinary value')
            (root / 'reports').mkdir()
            (root / 'reports' / 'diagnostic.json').write_text('{}')
            with patch.object(ci, 'location', return_value=root):
                result = ci.payload_context(root=root)
            self.assertEqual({p.name for p in (result / 'reconciliation').iterdir()},
                {*manifest['files'], 'RECONCILIATION_FILES.json'})
            self.assertFalse((result / 'reconciliation/reports').exists())

    def test_payload_rejects_modified_source_before_build(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.fixture(root)
            (root / 'runtime_bridge.py').write_text('changed')
            with patch.object(ci, 'location', return_value=root), \
                    self.assertRaisesRegex(RuntimeError, 'REGULAR_SHA_SOURCE_REQUIRED'):
                ci.payload_context(root=root)

    def test_payload_rejects_symlink_source_without_following_it(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.fixture(root)
            original = root / 'runtime_bridge.py'
            original.unlink()
            original.symlink_to(root / 'studio_entry.py')
            with patch.object(ci, 'location', return_value=root), \
                    self.assertRaisesRegex(RuntimeError, 'REGULAR_SHA_SOURCE_REQUIRED'):
                ci.payload_context(root=root)

    def test_manifest_path_traversal_rejected_before_copy(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            value = self.fixture(root)
            value['files']['../escape.py'] = 'a' * 64
            (root / 'RECONCILIATION_FILES.json').write_text(json.dumps(value))
            with self.assertRaisesRegex(RuntimeError, 'PACKAGE_PATH_INVALID'):
                ci._manifest(root)

    def test_new_manifest_binds_added_flat_sources_and_parent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'new.py').write_text('CPU fixture only')
            with patch.object(package, 'HERE', root), patch.object(package, 'MANIFEST', root / 'RECONCILIATION_FILES.json'):
                package.build_manifest()
                proof = package.verify_sources()
                self.assertEqual(proof['files'], 1)
                self.assertEqual(proof['parentFiles'], 82)
                (root / 'unmanifested.py').write_text('must fail')
                with self.assertRaisesRegex(RuntimeError, 'UNMANIFESTED_RUNTIME_SOURCE'):
                    package.verify_sources()

    def test_frozen_source_protection_fails_on_old_renderer_change(self):
        with patch.object(ci.ci, 'run', return_value=types.SimpleNamespace(stdout='world-simulation-shorts-engine/web/map_infographic_v1/map_runtime.mjs\n')):
            with self.assertRaisesRegex(RuntimeError, 'PROTECTED_SOURCE_CHANGED'):
                ci.source_protection()

    def test_frozen_source_protection_allows_only_new_scope(self):
        output = ci.ci.NAMESPACE + '/runtime_bridge.py\n' + ci.ci.WORKFLOW + '\n'
        with patch.object(ci.ci, 'run', return_value=types.SimpleNamespace(stdout=output)):
            self.assertEqual(ci.source_protection()['protectedChanged'], 0)

    def test_cpu_container_cannot_access_network_or_gpu(self):
        command = ci.container('CPU_ONLY_FIXTURE')
        self.assertIn('--network=none', command)
        self.assertIn('--restart=no', command)
        self.assertNotIn('--gpus', command)
        self.assertFalse(any('/dev/nvidia' in value for value in command))
        probe = ci.startup_probe_code()
        compile(probe, '<bounded-container-probe>', 'exec')
        self.assertIn('STUDIO_OWNER_CONFIGURATION_REQUIRED', probe)
        self.assertIn('guard_native_selection', probe)
        self.assertIn('import studio_entry,runtime_bridge,native_capabilities', probe)

    def test_new_image_only_and_original_healthcheck_inherited(self):
        text = (HERE / 'Dockerfile').read_text()
        self.assertIn('FROM ' + ci.ci.BASE, text)
        self.assertNotIn('HEALTHCHECK', '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('#')))
        self.assertIn('test ! -e ' + ci.ci.DEST, text)
        self.assertIn('COPY reconciliation/', text)
        self.assertRegex(ci.ci.TAG.pattern, re.escape('reconcile-v1-'))
        self.assertNotEqual(ci.ci.BASE_DIGEST, package.old.BASE_IMAGE)


if __name__ == '__main__':
    unittest.main()
