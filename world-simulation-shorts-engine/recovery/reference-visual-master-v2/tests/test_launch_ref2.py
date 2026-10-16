"""New reference V2 fixed selectors exercise inherited dispatch without GPU execution."""
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('_test_ref2_launch',HERE/'launch_ref2.py')
ref2=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref2)

class ReferenceLaunchTests(unittest.TestCase):
    def test_fixed_new_capture_preserves_original_argument_contract(self):
        admission=SimpleNamespace(admission_file=Path('/private/admission.json'),output_root=Path('/private/output'))
        command=ref2.native_command(admission)
        self.assertEqual(command,['node',str(ref2.ENGINE_HERE/'capture_ref2.mjs'),
            '--admission-file','/private/admission.json','--output-root','/private/output'])
        self.assertNotIn('shell',command)

    def test_isolated_wrapper_selects_only_new_prepare_and_capture(self):
        original_bytes=ref2.ORIGINAL.read_bytes()
        with mock.patch.object(ref2.inherited,'main',return_value=2) as dispatch:
            self.assertEqual(ref2.main(['--render-65422']),2)
            dispatch.assert_called_once_with(['--render-65422'])
            self.assertIs(ref2.inherited._native_command,ref2.native_command)
            self.assertIs(ref2.inherited.prepare_activation,ref2.prepare_ref2)
        self.assertEqual(ref2.ORIGINAL.read_bytes(),original_bytes)
        self.assertEqual(Path(ref2.inherited.render_astra.__code__.co_filename).resolve(),ref2.ORIGINAL.resolve())
        self.assertEqual(Path(ref2.inherited._capture_receipt.__code__.co_filename).resolve(),ref2.ORIGINAL.resolve())

    def test_diagnostic_execution_stays_blocked_before_any_preparation(self):
        with mock.patch.dict(os.environ,{'WORLD_ENGINE_STARTUP_MODE':'diagnostic'}), \
             mock.patch.object(ref2.prepare_ref2,'verify_extension') as verify, \
             mock.patch.object(ref2.inherited.base,'_publish') as publish:
            self.assertEqual(ref2.main(['--render-65422']),2)
            verify.assert_not_called()
            self.assertEqual(publish.call_args.args[0]['errorCode'],'DIAGNOSTIC_RENDER_FORBIDDEN')

    def test_complete_dispatch_reuses_old_controller_with_new_profile_before_gpu(self):
        calls=[]
        prepared={'activationFile':'/private/ref2.json','activationSha256':'a'*64,
                  'bundleManifestSha256':'b'*64,'profileId':'REFERENCE_VISUAL_MASTER_V2_F'}
        session=SimpleNamespace(private_root=Path('/private/output'))
        selected=SimpleNamespace(bootstrap=lambda:SimpleNamespace(prepare_environment=lambda account:calls.append('bootstrap')),
            account=lambda:'CPU_ONLY_ACCOUNT',source=lambda:calls.append('source'),
            dependencies=lambda:(calls.append('dependencies') or {'status':'PASS'}))
        gpu=SimpleNamespace(LauncherConfig=lambda **kwargs:SimpleNamespace(**kwargs))
        native=SimpleNamespace(account=lambda:'CPU_ONLY_ACCOUNT',gpu=lambda:(calls.append('gpu_module') or gpu))
        with mock.patch.dict(os.environ,{'WORLD_ENGINE_STARTUP_MODE':'normal'}), \
             mock.patch.object(ref2.prepare_ref2,'verify_extension',side_effect=lambda:calls.append('extension')), \
             mock.patch.object(ref2.prepare_ref2,'prepare_activation',side_effect=lambda root:(calls.append('new_profile') or prepared)), \
             mock.patch.object(ref2.inherited.base.startup,'NativeOperations',return_value=native), \
             mock.patch.object(ref2.inherited.base.storage.StorageSession,'create',return_value=session), \
             mock.patch.object(ref2.inherited.base,'StorageOperations',return_value=selected), \
             mock.patch.object(ref2.inherited,'_render_and_export',side_effect=lambda *args:(calls.append('inherited_guard_admit_render_export') or 0)):
            self.assertEqual(ref2.main(['--render-65422']),0)
            self.assertEqual(os.environ['WORLD_ENGINE_ASTRA_ACTIVATION_SHA256'],prepared['activationSha256'])
        self.assertEqual(calls,['extension','bootstrap','source','dependencies','new_profile','gpu_module',
                                'inherited_guard_admit_render_export'])

if __name__=='__main__':unittest.main()
