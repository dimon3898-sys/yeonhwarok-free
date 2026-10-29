"""New synthetic four-file packaging contracts; no Docker, browser or old suites."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('surface_package_under_test', HERE / 'package_candidate.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def put(root, name, raw):
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return target


class PackagingContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='surface-package-contract-')
        self.root = Path(self.tmp.name)
        self.parent = self.root / 'synthetic-parent'; self.parent.mkdir()
        self.context = self.root / 'context'
        old_profile = ("const stripped=['--disable-vulkan-surface'];\n" + p.OLD_FRAGMENT + '\n').encode()
        new_profile = old_profile.decode().replace(p.OLD_FRAGMENT, p.NEW_FRAGMENT).encode()
        self.candidate = put(self.root, 'candidate.mjs', new_profile)
        put(self.parent, p.PROFILE, old_profile)
        generated = b'{"syntheticGeneratedSource":true}\n'
        put(self.parent, p.GENERATED, generated)
        rows = [{'path': p.PROFILE, 'sha256': p.digest(old_profile), 'bytes': len(old_profile)},
                {'path': p.GENERATED, 'sha256': p.digest(generated), 'bytes': len(generated)}]
        rows += [{'path': 'world-simulation-shorts-engine/recovery/synthetic/file-%03d.py' % i,
                  'sha256': 'b' * 64, 'bytes': i} for i in range(351)]
        self.runtime = {'schema': 'WORLD_ENGINE_HANDOFF_RUNTIME_SOURCES_V1', 'files': rows,
                        'externalFiles': [{'path': '/opt/synthetic-external', 'sha256': 'd' * 64, 'bytes': 2}]}
        runtime_raw = p.wire(self.runtime)
        put(self.parent, p.RUNTIME, runtime_raw)
        bootstrap = ("IMAGE = '" + p.FROZEN_STARTUP_IMAGE + "'\nSOURCE_SHA = '" + p.digest(runtime_raw) + "'\n").encode()
        put(self.parent, p.BOOTSTRAP, bootstrap)
        self.worker = b'# synthetic worker must not change\n'
        put(self.parent, p.STARTUP.rsplit('/', 1)[0] + '/worker.py', self.worker)
        self.startup = {'schema': 'WORLD_ENGINE_STUDIO_COLD_START_FILES_V2',
                        'baseImageDigest': p.FROZEN_STARTUP_IMAGE,
                        'runtimeManifestSHA256': p.digest(runtime_raw),
                        'files': {'bootstrap.py': {'bytes': len(bootstrap), 'sha256': p.digest(bootstrap)},
                                  'worker.py': {'bytes': len(self.worker), 'sha256': p.digest(self.worker)}}}
        startup_raw = p.wire(self.startup)
        put(self.parent, p.STARTUP, startup_raw)
        self.pins = {'runtime': p.digest(runtime_raw), 'startup': p.digest(startup_raw),
                     'oldProfile': p.digest(old_profile), 'newProfile': p.digest(new_profile),
                     'oldBytes': len(old_profile), 'newBytes': len(new_profile),
                     'generated': p.digest(generated), 'startupImage': p.FROZEN_STARTUP_IMAGE}
        self.config = {'Entrypoint': p.expected_entrypoint(self.pins['runtime'], self.pins['startup']),
                       'Cmd': None, 'User': '0', 'Env': ['TEST_ONLY=1'], 'WorkingDir': '/opt/synthetic',
                       'ExposedPorts': {'8080/tcp': {}}, 'Labels': {'synthetic': 'true'}}

    def tearDown(self):
        self.tmp.cleanup()

    def stage(self):
        return p._stage(self.parent, self.candidate, self.context, self.config, pins=self.pins)

    def installed(self):
        result = self.stage()
        installed = self.root / 'synthetic-candidate'
        shutil.copytree(self.parent, installed)
        shutil.copytree(self.context / 'overlay', installed, dirs_exist_ok=True)
        config = copy.deepcopy(self.config); config['Entrypoint'] = result['entrypoint']
        return result, installed, config

    def test_01_exact_overlay_and_pin_connections(self):
        original = {str(x.relative_to(self.parent)): x.read_bytes() for x in self.parent.rglob('*') if x.is_file()}
        receipt, installed, config = self.installed()
        with patch.object(p, 'PRODUCTION_PINS', self.pins):
            result = p.verify(installed, self.context, self.config, config)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['overlayFilesVerified'], 4)
        self.assertEqual(receipt['unchangedSourceRows'], 352)
        self.assertEqual({str(x.relative_to(self.context / 'overlay')) for x in (self.context / 'overlay').rglob('*') if x.is_file()}, p.OVERLAY_FILES)
        self.assertEqual(original, {str(x.relative_to(self.parent)): x.read_bytes() for x in self.parent.rglob('*') if x.is_file()})
        self.assertEqual((installed / (p.STARTUP.rsplit('/', 1)[0] + '/worker.py')).read_bytes(), self.worker)
        startup = p.read_json(installed / p.STARTUP)
        self.assertEqual(startup['baseImageDigest'], p.FROZEN_STARTUP_IMAGE)
        self.assertEqual(startup['files']['worker.py'], self.startup['files']['worker.py'])
        runtime = p.read_json(installed / p.RUNTIME)
        self.assertEqual(runtime['externalFiles'], self.runtime['externalFiles'])
        self.assertEqual([r for r in runtime['files'] if r['path'] != p.PROFILE],
                         [r for r in self.runtime['files'] if r['path'] != p.PROFILE])
        dockerfile = (self.context / 'Dockerfile').read_text()
        self.assertEqual(len(dockerfile.splitlines()), 6)
        self.assertEqual(dockerfile.splitlines()[0], 'FROM ' + p.PARENT)
        self.assertNotIn('\nRUN ', dockerfile)
        copies = [line for line in dockerfile.splitlines() if line.startswith('COPY ')]
        self.assertEqual(len(copies), 4)
        for line, name in zip(copies, sorted(p.OVERLAY_FILES)):
            self.assertEqual(line, 'COPY --chown=0:0 --chmod=0644 '
                             + json.dumps(['overlay/' + name, str(p.REPO_ROOT / name)]))

    def test_02_wrong_parent_manifest_pin_blocks_before_context(self):
        wrong = dict(self.pins, runtime='0' * 64)
        with self.assertRaisesRegex(RuntimeError, 'PARENT_RUNTIME_PIN_MISMATCH'):
            p._stage(self.parent, self.candidate, self.context, self.config, pins=wrong)
        self.assertFalse(self.context.exists())

    def test_03_duplicate_353_paths_rejected(self):
        duplicate = copy.deepcopy(self.runtime)
        duplicate['files'][-1] = copy.deepcopy(duplicate['files'][-2])
        with self.assertRaisesRegex(RuntimeError, 'DUPLICATE_RUNTIME_PATH'):
            p.rows_by_path(duplicate)

    def test_04_extra_source_delta_rejected_even_with_candidate_test_pin(self):
        raw = self.candidate.read_bytes() + b'// unapproved extra change\n'
        self.candidate.write_bytes(raw)
        pins = dict(self.pins, newProfile=p.digest(raw), newBytes=len(raw))
        with self.assertRaisesRegex(RuntimeError, 'UNAPPROVED_PROFILE_DELTA'):
            p._stage(self.parent, self.candidate, self.context, self.config, pins=pins)
        self.assertFalse(self.context.exists())

    def test_05_wrong_entrypoint_and_existing_destination_fail_closed(self):
        config = copy.deepcopy(self.config); config['Entrypoint'][-1] = '/wrong-export'
        with self.assertRaisesRegex(RuntimeError, 'PARENT_IMAGE_CONFIG_MISMATCH'):
            p._stage(self.parent, self.candidate, self.context, config, pins=self.pins)
        self.context.mkdir()
        with self.assertRaisesRegex(RuntimeError, 'FRESH_CONTEXT_REQUIRED'):
            self.stage()

    def test_06_verifier_rejects_overlay_tamper_and_extra_files(self):
        receipt, installed, config = self.installed()
        put(self.context / 'overlay', 'unapproved-extra.txt', b'x')
        with patch.object(p, 'PRODUCTION_PINS', self.pins):
            with self.assertRaisesRegex(RuntimeError, 'OVERLAY_SCOPE_CHANGED'):
                p.verify(installed, self.context, self.config, config)
        (self.context / 'overlay/unapproved-extra.txt').unlink()
        (installed / p.PROFILE).write_bytes(b'wrong candidate profile')
        with patch.object(p, 'PRODUCTION_PINS', self.pins):
            with self.assertRaisesRegex(RuntimeError, 'INSTALLED_OVERLAY_MISMATCH'):
                p.verify(installed, self.context, self.config, config)

    def test_07_verifier_rejects_unrelated_image_configuration_change(self):
        receipt, installed, config = self.installed()
        config['User'] = '1000'
        with patch.object(p, 'PRODUCTION_PINS', self.pins):
            with self.assertRaisesRegex(RuntimeError, 'UNRELATED_IMAGE_CONFIG_CHANGED'):
                p.verify(installed, self.context, self.config, config)

    def test_08_cli_production_path_cannot_use_synthetic_pin_seam(self):
        with self.assertRaisesRegex(RuntimeError, 'INSTALLED_PARENT_ROOT_REQUIRED'):
            p.stage(self.parent, self.candidate, self.context, self.config)
        self.assertFalse(self.context.exists())

    def test_09_generated_context_modes_ignore_restrictive_umask(self):
        old_umask = os.umask(0o077)
        try:
            self.stage()
        finally:
            os.umask(old_umask)
        for item in [self.context, *self.context.rglob('*')]:
            self.assertEqual(stat.S_IMODE(item.stat().st_mode), 0o755 if item.is_dir() else 0o644)

    def test_10_verifier_rejects_extra_dockerfile_instruction(self):
        receipt, installed, config = self.installed()
        file = self.context / 'Dockerfile'
        file.write_text(file.read_text() + 'RUN echo unapproved-extra-step\n')
        with patch.object(p, 'PRODUCTION_PINS', self.pins):
            with self.assertRaisesRegex(RuntimeError, 'DOCKERFILE_SCOPE_CHANGED'):
                p.verify(installed, self.context, self.config, config)


if __name__ == '__main__':
    unittest.main(verbosity=2)
