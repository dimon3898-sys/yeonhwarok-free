"""Focused CPU orchestration tests. All hardware calls are explicit mocks.

Synthetic reports do not assert that NVIDIA, Dropbox or GPU pixels were tested.
"""
from __future__ import annotations
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location('_test_astra_launch', HERE / 'launch_astra.py')
launch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launch)

class TestError(RuntimeError):
    __test__ = False
    def __init__(self, code):
        self.code=code
        super().__init__(code)

class LaunchMonitorTests(unittest.TestCase):
    def setUp(self):
        self.allocation={'uuid':'CPU_TEST_ONLY', 'model':'CPU_TEST_ONLY', 'driver_version':'0',
                         'memory_total_mib':16384,'memory_free_mib':15000}
        self.gpu=SimpleNamespace(LauncherError=TestError,ENGINE_ROOT=HERE.parents[1],MIB=1024**2,
            RESERVED_MEMORY_BYTES=2*1024**3,query_allocation=mock.Mock(return_value=self.allocation),
            _stop_render=mock.Mock())
        self.admission=SimpleNamespace(test_only=False,private_report={'allocation':self.allocation},
            safe_report={'vramBudgetBytes':8*1024**3},environ={'CPU_TEST_ONLY':'1'},
            admission_file=Path('/private/SYNTHETIC_ADMISSION.json'),output_root=Path('/private/SYNTHETIC_OUTPUT'))
        self.config=SimpleNamespace(validate=mock.Mock(return_value=8*1024**3),render_timeout_seconds=3600)
        self.process=SimpleNamespace(poll=mock.Mock(side_effect=[None,0,0]),returncode=0,pid=123456)

    def run_fake(self, clock=None):
        with mock.patch.object(launch.subprocess,'Popen',return_value=self.process) as spawn, \
             mock.patch.object(launch.time,'sleep'), \
             mock.patch.object(launch.time,'monotonic',side_effect=clock or [0,0,0]):
            result=launch.render_astra(self.gpu,self.admission,self.config)
        return result,spawn

    def test_fixed_new_capture_with_native_admission_and_original_limits(self):
        before=signal.getsignal(signal.SIGHUP)
        result,spawn=self.run_fake()
        self.assertEqual(result,0)
        argv=spawn.call_args.args[0]
        self.assertEqual(argv[0],'node')
        self.assertEqual(Path(argv[1]).name,'capture_astra.mjs')
        self.assertEqual(argv[2:],['--admission-file','/private/SYNTHETIC_ADMISSION.json',
                                  '--output-root','/private/SYNTHETIC_OUTPUT'])
        self.assertTrue(spawn.call_args.kwargs['start_new_session'])
        self.assertEqual(spawn.call_args.kwargs['env'],{'CPU_TEST_ONLY':'1'})
        self.gpu.query_allocation.assert_called_once_with(self.admission.environ,launch.subprocess.run)
        self.assertEqual(signal.getsignal(signal.SIGHUP),before)

    def test_admission_test_seam_cannot_dispatch_production_capture(self):
        self.admission.test_only=True
        with mock.patch.object(launch.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(TestError,'^TEST_ADMISSION_NOT_EXECUTABLE$'):
                launch.render_astra(self.gpu,self.admission,self.config)
            spawn.assert_not_called()

    def test_physical_allocation_change_stops_capture(self):
        self.gpu.query_allocation.return_value={**self.allocation,'uuid':'DIFFERENT_TEST_UUID'}
        self.process.poll=mock.Mock(return_value=None)
        with self.assertRaisesRegex(TestError,'^GPU_ALLOCATION_CHANGED_DURING_RENDER$'):
            self.run_fake()
        self.gpu._stop_render.assert_called_once_with(self.process)

    def test_vram_growth_preserves_native_failure_policy(self):
        self.gpu.query_allocation.return_value={**self.allocation,'memory_free_mib':2000}
        self.process.poll=mock.Mock(return_value=None)
        with self.assertRaisesRegex(TestError,'^GPU_RENDER_VRAM_BUDGET_EXCEEDED$'):
            self.run_fake()
        self.gpu._stop_render.assert_called_once_with(self.process)

    def test_deadline_stops_job_and_restores_signal_handlers(self):
        self.process.poll=mock.Mock(return_value=None)
        self.config.render_timeout_seconds=1
        with self.assertRaisesRegex(TestError,'^GPU_RENDER_DEADLINE_EXCEEDED$'):
            self.run_fake([0,2])
        self.gpu.query_allocation.assert_not_called()
        self.gpu._stop_render.assert_called_once_with(self.process)

    def test_nonzero_native_exit_is_never_success(self):
        self.process=SimpleNamespace(poll=mock.Mock(return_value=2),returncode=2)
        with self.assertRaisesRegex(TestError,'^GPU_RENDER_PROCESS_FAILED$'):
            self.run_fake()

    def test_diagnostic_mode_blocks_before_preparation_or_gpu(self):
        with mock.patch.dict(os.environ,{'WORLD_ENGINE_STARTUP_MODE':'diagnostic'}), \
             mock.patch.object(launch.prepare_activation,'verify_extension') as verify, \
             mock.patch.object(launch.base,'_publish') as publish:
            self.assertEqual(launch.main(['--render-astra-65422']),2)
            verify.assert_not_called()
            self.assertEqual(publish.call_args.args[0]['errorCode'],'DIAGNOSTIC_RENDER_FORBIDDEN')

    def test_explicit_render_flag_required(self):
        with mock.patch.object(launch.prepare_activation,'verify_extension') as verify, \
             mock.patch.object(launch.base,'_publish'):
            self.assertEqual(launch.main([]),2)
            verify.assert_not_called()

    def test_export_after_capture_and_receipt_before_locator(self):
        calls=[]
        @contextlib.contextmanager
        def guard(root):
            self.assertEqual(root,launch.base.storage.PRIVATE_BASE)
            calls.append('guard');yield;calls.append('unlock')
        gpu=SimpleNamespace(capture_guard=guard,
            admit_gpu=lambda config:(calls.append('admit') or SimpleNamespace(test_only=False)))
        result={'directory':'capture-'+'b'*12+'-'+'c'*24}
        report={'status':'EXPORTED','captures':1,'files':7,'results':[result],
                'mountedViewReadbackVerified':True,'privateDataAllowed':False,
                'remotePersistenceVerified':False,'externalDownloadVerified':False}
        session=SimpleNamespace(export_results=lambda:(calls.append('export') or report))
        with mock.patch.object(launch,'render_astra',side_effect=lambda *args:calls.append('render')), \
             mock.patch.object(launch,'_capture_receipt',side_effect=lambda *a:calls.append('receipt')), \
             mock.patch.object(launch.base,'_emit_export_location',side_effect=lambda *a,**kw:(calls.append('locator') or True)):
            self.assertEqual(launch._render_and_export(gpu,None,session,{}),0)
        self.assertEqual(calls,['guard','admit','render','export','receipt','locator','unlock'])

    def test_existing_common_gpu_guard_blocks_before_admission(self):
        spec=importlib.util.spec_from_file_location('_cpu_only_native_gpu_guard',
            HERE.parent/'rtx-gpu-package-v1'/'gpu_launcher.py')
        native=importlib.util.module_from_spec(spec);sys.modules[spec.name]=native;spec.loader.exec_module(native)
        with tempfile.TemporaryDirectory(prefix='test-only-astra-common-lock-',dir='/workspace') as area:
            root=Path(area)/'private';root.mkdir(mode=0o700)
            gpu=SimpleNamespace(capture_guard=native.capture_guard,admit_gpu=mock.Mock())
            with mock.patch.object(launch.base.storage,'PRIVATE_BASE',root),native.capture_guard(root):
                with self.assertRaisesRegex(native.LauncherError,'^GPU_CAPTURE_ALREADY_RUNNING$'):
                    launch._render_and_export(gpu,None,None,{})
            gpu.admit_gpu.assert_not_called()

    def test_missing_public_export_has_no_success_locator(self):
        gpu=SimpleNamespace(capture_guard=lambda root:contextlib.nullcontext(),
            admit_gpu=lambda config:SimpleNamespace(test_only=False))
        session=SimpleNamespace(export_results=lambda:{'status':'NO_PUBLIC_RESULTS'})
        with mock.patch.object(launch,'render_astra'),mock.patch.object(launch,'_capture_receipt') as receipt, \
             mock.patch.object(launch.base,'_emit_export_location') as emit:
            with self.assertRaises(launch.base.storage.StorageError):
                launch._render_and_export(gpu,None,session,{})
            receipt.assert_not_called();emit.assert_not_called()


@unittest.skipUnless(os.geteuid()==1000 and os.getegid()==1000,'requires original private UID/GID 1000 contract')
class AstRaReceiptTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='test-only-astra-receipt-',dir='/workspace')
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        private=self.root/'private';private.mkdir(mode=0o700)
        self.shared=self.root/'shared';self.shared.mkdir(mode=0o700)
        self.session=launch.base.storage.StorageSession.create(SimpleNamespace(pw_uid=1000,pw_gid=1000),
            base=private,export_root=self.shared)
        self.session.preflight()
        self.capture_id='a'*64
        self.capture=self.session.private_root/'captures'/self.capture_id
        self.public=self.capture/'public-review';self.public.mkdir(parents=True,mode=0o700)
        (self.session.private_root/'captures').chmod(0o700);self.capture.chmod(0o700)
        media={'WORLD_ENGINE_RTX_GPU_65422_5S_SILENT.mp4':b'\0\0\0\x18ftypisom'+b'CPU_ONLY'*16}
        media.update({name:b'\x89PNG\r\n\x1a\n'+b'CPU_ONLY'*16 for name in
            ['01_START.png','02_ADVANCE.png','03_TRACKING.png','04_CONTINUOUS_CONTROL.png','05_END.png']})
        for name,data in media.items():(self.public/name).write_bytes(data)
        (self.public/'SHA256SUMS').write_text(''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n'
                                                   for name,data in sorted(media.items())))
        self.activation={'activationSha256':'b'*64,'bundleManifestSha256':'c'*64,'profileId':'ASTRA_TEST_ONLY'}
        self.report={'schema':'RTX_GPU_HARDWARE_CAPTURE_V1','status':'CAPTURE_TECHNICAL_PASS',
            'signature':self.capture_id,'sourceVerification':{'status':'PASS'},'astraApplied':True,
            **self.activation,'astraProfileId':self.activation['profileId'],
            'runtimeSourceSignature':'d'*64,'extensionManifestSha256':'e'*64,'frames':[{}]*150}
        self.write_report()
        self.export=self.session.export_results()
        self.result=self.export['results'][0]
        self.unit=self.shared/self.session.export_name/self.result['directory']

    def write_report(self):
        target=self.capture/'REPORT.json';target.write_text(json.dumps(self.report));target.chmod(0o600)

    def test_ast_ra_receipt_outside_exact_public_allowlist_readback_verified(self):
        receipt=launch._capture_receipt(self.session,self.result,self.activation,test_only=True)
        self.assertEqual(receipt['captureId'],self.capture_id)
        self.assertTrue(receipt['testOnly']);self.assertFalse(receipt['gpuRenderingVerified'])
        self.assertFalse(receipt['externalDownloadVerified']);self.assertFalse(receipt['remotePersistenceVerified'])
        self.assertEqual(json.loads((self.unit/'ASTRA_COMPLETE.json').read_text()),receipt)
        self.assertEqual(len(list((self.unit/'public-review').iterdir())),7)
        self.assertFalse((self.unit/'public-review'/'ASTRA_COMPLETE.json').exists())

    def test_old_success_report_without_ast_ra_application_rejected(self):
        self.report.pop('astraApplied');self.write_report()
        with self.assertRaises(launch.base.storage.StorageError):
            launch._capture_receipt(self.session,self.result,self.activation,test_only=True)
        self.assertFalse((self.unit/'ASTRA_COMPLETE.json').exists())

    def test_profile_mismatch_has_no_ast_ra_receipt(self):
        wrong={**self.activation,'activationSha256':'f'*64}
        with self.assertRaises(launch.base.storage.StorageError):
            launch._capture_receipt(self.session,self.result,wrong,test_only=True)
        self.assertFalse((self.unit/'ASTRA_COMPLETE.json').exists())

    def test_shared_receipt_fifo_fails_without_blocking(self):
        receipt=self.unit/'EXPORT_COMPLETE.json';receipt.unlink();os.mkfifo(receipt)
        with self.assertRaises(launch.base.storage.StorageError):
            launch._capture_receipt(self.session,self.result,self.activation,test_only=True)

    def test_existing_receipt_never_overwritten(self):
        launch._capture_receipt(self.session,self.result,self.activation,test_only=True)
        before=(self.unit/'ASTRA_COMPLETE.json').read_bytes()
        with self.assertRaises(launch.base.storage.StorageError):
            launch._capture_receipt(self.session,self.result,self.activation,test_only=True)
        self.assertEqual(before,(self.unit/'ASTRA_COMPLETE.json').read_bytes())

if __name__=='__main__':unittest.main()
