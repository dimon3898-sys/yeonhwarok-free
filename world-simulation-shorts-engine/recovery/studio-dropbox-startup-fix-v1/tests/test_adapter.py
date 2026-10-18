"""Focused CPU regression for the immutable proof's missing import path.

No provider credential, Docker daemon, network connection, old source mutation,
or real backup is used here. The real Dropbox proof is a separate CI phase.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import adapter


EXPECTED_IMAGE = (
    'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@'
    'sha256:6d2e87fc8fb7f10edc2ebb7f77b5d666e329904b9c37f7f060b289f943bdd9d0'
)
EXPECTED_DEST = '/opt/world-engine-studio-dropbox-offline'
EXPECTED_PYTHON = '/opt/world-engine-studio-durability-venv/bin/python'


def original_bootstrap():
    # Independent reconstruction of the frozen helper's original generated code.
    probe = '/tmp/world-engine-offline-external-proof'
    entry = EXPECTED_DEST + '/offline_entry.py'
    return ('import os,runpy,sys;os.mkdir(' + repr(probe) + ',0o700);'
            'sys.argv=[' + repr(entry)
            + ',"cli","external-check","--private-work-root",' + repr(probe) + '];'
            'runpy.run_path(' + repr(entry) + ',run_name="__main__")')


def probe_command():
    # Paths describe disposable CI mounts; they contain no credential values.
    secret_root = '/run/world-engine-backup-secrets/'
    return ['docker', 'run', '--rm', '--name', 'studio-offline-external-' + 'a' * 32,
            '--user=1000:1000', '--read-only', '--memory=2g', '--cpus=2',
            '--pids-limit=256', '--restart=no', '--cap-drop=ALL',
            '--security-opt=no-new-privileges', '--tmpfs', '/tmp:rw,mode=1777',
            '--mount', 'type=bind,source=/tmp/disposable-proof-secrets,target='
            + secret_root.rstrip('/') + ',readonly',
            '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'HOME=/tmp',
            '--env', 'WORLD_ENGINE_STUDIO_BACKUP_MODE=dropbox-api',
            '--env', 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_AUTH_MODE=offline',
            '--env', 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_PREFIX=/WORLD_ENGINE_STUDIO_BACKUPS_V1',
            '--env', 'WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE=' + secret_root + 'backup-key',
            '--env', 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_KEY_FILE=' + secret_root + 'app-key',
            '--env', 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_SECRET_FILE=' + secret_root + 'app-secret',
            '--env', 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_REFRESH_TOKEN_FILE=' + secret_root + 'refresh-token',
            '--entrypoint=' + EXPECTED_PYTHON, EXPECTED_IMAGE, '-B', '-c', original_bootstrap()]


class AdapterTests(unittest.TestCase):
    def test_constants_pin_existing_image_and_entrypoint(self):
        self.assertEqual(adapter.IMAGE, EXPECTED_IMAGE)
        self.assertEqual(adapter.DEST, EXPECTED_DEST)
        self.assertEqual(adapter.PYTHON, EXPECTED_PYTHON)

    def test_bootstrap_matches_frozen_code_byte_for_byte(self):
        actual = adapter.bootstrap_code()
        expected = original_bootstrap()
        self.assertIsInstance(actual, str)
        self.assertEqual(actual, expected)
        self.assertEqual(hashlib.sha256(actual.encode()).digest(),
                         hashlib.sha256(expected.encode()).digest())

    def test_only_fixed_workdir_is_added_before_immutable_image(self):
        command = probe_command()
        saved = list(command)
        index = command.index(EXPECTED_IMAGE)
        expected = command[:index] + ['--workdir=' + EXPECTED_DEST] + command[index:]
        result = adapter.adapt(command)
        self.assertEqual(result, expected)
        self.assertEqual(command, saved)
        self.assertIsNot(result, command)
        self.assertEqual(result[result.index(EXPECTED_IMAGE) + 1:], command[index + 1:])

    def test_returned_mutable_command_does_not_alias_input(self):
        command = probe_command()
        saved = list(command)
        result = adapter.adapt(command)
        result[0] = 'DO_NOT_EXECUTE'
        self.assertEqual(command, saved)

    def test_unrelated_commands_are_unchanged(self):
        for command in (
            ['git', 'status', '--short'],
            ['docker', 'pull', EXPECTED_IMAGE],
            ['docker', 'image', 'inspect', EXPECTED_IMAGE],
            ['docker', 'stop', '--time=5', 'studio-offline-external-' + 'a' * 32],
            ['docker', 'run', '--rm', '--entrypoint=' + EXPECTED_PYTHON,
             EXPECTED_IMAGE, '-B', EXPECTED_DEST + '/offline_entry.py', 'cli', '--help'],
        ):
            with self.subTest(command=command[:3]):
                self.assertEqual(adapter.adapt(command), command)

    def test_mutable_tag_is_not_accepted_as_immutable_target(self):
        command = probe_command()
        command[command.index(EXPECTED_IMAGE)] = (
            'ghcr.io/dimon3898-sys/world-simulation-shorts-engine:existing-tag'
        )
        self.assertEqual(adapter.adapt(command), command)

    def test_missing_required_security_flag_is_rejected(self):
        for flag in ('--user=1000:1000', '--read-only', '--cap-drop=ALL',
                     '--security-opt=no-new-privileges', '--restart=no'):
            with self.subTest(flag=flag):
                command = probe_command()
                command.remove(flag)
                with self.assertRaises(RuntimeError):
                    adapter.adapt(command)

    def test_preexisting_workdir_is_rejected(self):
        for flags in (['--workdir=/tmp'], ['--workdir', '/tmp'], ['-w', '/tmp']):
            with self.subTest(flags=flags):
                command = probe_command()
                index = command.index(EXPECTED_IMAGE)
                command[index:index] = flags
                with self.assertRaises(RuntimeError):
                    adapter.adapt(command)

    def test_gpu_options_are_rejected_in_cpu_proof(self):
        for flags in (['--gpus=all'], ['--gpus', 'all']):
            with self.subTest(flags=flags):
                command = probe_command()
                index = command.index(EXPECTED_IMAGE)
                command[index:index] = flags
                with self.assertRaises(RuntimeError):
                    adapter.adapt(command)

    def test_changed_generated_source_is_rejected(self):
        for replacement in (original_bootstrap() + ';pass',
                            original_bootstrap().replace('external-check', 'restore')):
            with self.subTest(changed=True):
                command = probe_command()
                command[-1] = replacement
                with self.assertRaises(RuntimeError):
                    adapter.adapt(command)


class ImportPathReproductionTests(unittest.TestCase):
    def test_original_fails_then_fixed_workdir_imports_without_network(self):
        with tempfile.TemporaryDirectory(prefix='offline-import-path-fixture-') as temporary:
            root = Path(temporary)
            source, other = root / 'source', root / 'unrelated-working-directory'
            source.mkdir(mode=0o700)
            other.mkdir(mode=0o700)
            (source / 'offline_manifest.py').write_text('RESULT = "FIXTURE_IMPORT_OK"\n')
            (source / 'offline_entry.py').write_text(
                'from offline_manifest import RESULT\nprint(RESULT)\n'
            )
            code = ('import runpy;runpy.run_path('
                    + repr(str(source / 'offline_entry.py')) + ',run_name="__main__")')
            command = [sys.executable, '-B', '-c', code]
            environment = {'PATH': os.defpath, 'PYTHONNOUSERSITE': '1',
                           'PYTHONDONTWRITEBYTECODE': '1'}
            before = subprocess.run(command, cwd=other, env=environment,
                                    capture_output=True, text=True, timeout=15)
            after = subprocess.run(command, cwd=source, env=environment,
                                   capture_output=True, text=True, timeout=15)
            self.assertNotEqual(before.returncode, 0)
            self.assertIn("ModuleNotFoundError: No module named 'offline_manifest'", before.stderr)
            self.assertEqual(after.returncode, 0, after.stderr)
            self.assertEqual(after.stdout.strip(), 'FIXTURE_IMPORT_OK')
            self.assertEqual(after.stderr, '')


if __name__ == '__main__':
    unittest.main()
