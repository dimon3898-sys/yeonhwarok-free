"""NEW installed-verifier code cases using tiny synthetic sources, never an image."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent
SCRIPT=HERE.parent/'label-packaging-v1/verify_installed_355.py'
SPEC=importlib.util.spec_from_file_location('new_installed355',SCRIPT)
verify=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(verify)
MANIFEST='world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json'
STARTUP='world-simulation-shorts-engine/recovery/studio-cold-start-v2/STARTUP_MANIFEST.json'
BOOTSTRAP='world-simulation-shorts-engine/recovery/studio-cold-start-v2/bootstrap.py'
WORKER='world-simulation-shorts-engine/recovery/studio-cold-start-v2/worker.py'
sha=lambda raw:hashlib.sha256(raw).hexdigest()

class Installed355Cases(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='new-installed355-')
        self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name);self.root=self.home/'synthetic-root';self.root.mkdir()
        self.expected=self.home/'expected.json';self.out=self.home/'result.json'
        self.rows=[]
        for index in range(355):
            name='world-simulation-shorts-engine/synthetic/source%03d.txt'%index
            file=self.root/name;file.parent.mkdir(parents=True,exist_ok=True)
            raw=('synthetic-%03d'%index).encode();file.write_bytes(raw)
            self.rows.append({'path':name,'bytes':len(raw),'sha256':sha(raw)})
        self.source_manifest={'schema':'WORLD_ENGINE_HANDOFF_RUNTIME_SOURCES_V1','files':self.rows}
        self.write_manifest()
        self.write_bootstrap()
        self.worker=b'# synthetic worker; never executed\n';(self.root/WORKER).write_bytes(self.worker)
        self.write_startup()

    def write_manifest(self):
        p=self.root/MANIFEST;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(self.source_manifest,sort_keys=True)+'\n')
        self.runtime_sha=sha(p.read_bytes())

    def write_bootstrap(self,source_sha=None):
        p=self.root/BOOTSTRAP;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text("# synthetic; never executed\nSOURCE_SHA = '"+(source_sha or self.runtime_sha)+"'\n")

    def write_startup(self):
        bootstrap=(self.root/BOOTSTRAP).read_bytes()
        self.startup={'schema':'WORLD_ENGINE_STUDIO_COLD_START_FILES_V2',
                      'runtimeManifestSHA256':self.runtime_sha,
                      'baseImageDigest':'sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da',
                      'files':{'bootstrap.py':{'sha256':sha(bootstrap),'bytes':len(bootstrap)},
                               'worker.py':{'sha256':sha(self.worker),'bytes':len(self.worker)}}}
        self.refresh_expected()

    def refresh_expected(self):
        p=self.root/STARTUP;p.write_text(json.dumps(self.startup,sort_keys=True)+'\n')
        self.expected_data={'runtimeSourceRows':355,'runtimeManifestSHA256':self.runtime_sha,
                            'startupManifestSHA256':sha(p.read_bytes())}
        self.expected.write_text(json.dumps(self.expected_data)+'\n')

    def invoke(self,root=None,out=None):
        argv=[str(SCRIPT),'--root',str(root or self.root),'--expected',str(self.expected),'--out',str(out or self.out)]
        with mock.patch.object(sys,'argv',argv):verify.main()

    def rejected(self,pattern,root=None):
        with self.assertRaisesRegex((RuntimeError,PermissionError,ValueError),pattern):self.invoke(root)
        self.assertFalse(self.out.exists(),'a rejection must not produce PASS evidence')

    def test_01_synthetic355_normal_actual_uid1000(self):
        self.assertEqual(verify.os.geteuid(),1000)
        self.invoke();result=json.loads(self.out.read_text())
        self.assertEqual(result['status'],'PASS');self.assertEqual(result['installedFilesVerified'],355)
        self.assertEqual(result['uid'],1000);self.assertFalse(result['gpuExecuted'])

    def test_02_expected_count_rejected(self):
        self.expected_data['runtimeSourceRows']=354;self.expected.write_text(json.dumps(self.expected_data))
        self.rejected('EXPECTED_ROWS')

    def test_03_manifest_hash_rejected(self):
        self.expected_data['runtimeManifestSHA256']='0'*64;self.expected.write_text(json.dumps(self.expected_data))
        self.rejected('MANIFEST_SHA')

    def test_04_source_hash_rejected(self):
        (self.root/self.rows[0]['path']).write_bytes(b'changed synthetic bytes')
        self.rejected('SOURCE_HASH')

    def test_05_duplicate_source_path_rejected(self):
        self.source_manifest['files'][1]=dict(self.rows[0]);self.write_manifest();self.write_bootstrap();self.write_startup()
        self.rejected('MANIFEST_355_UNIQUE')

    def test_06_parent_traversal_rejected(self):
        self.source_manifest['files'][0]['path']='../private-synthetic'
        self.write_manifest();self.write_bootstrap();self.write_startup();self.rejected('PATH_TRAVERSAL')

    def test_07_source_symlink_rejected(self):
        p=self.root/self.rows[0]['path'];p.unlink();p.symlink_to(self.root/self.rows[1]['path'])
        self.rejected('SYMLINK')

    def test_08_source_read_permission_denied_is_not_pass(self):
        original=verify.read
        def denied(p):
            if p==self.root/self.rows[0]['path']:raise PermissionError('SYNTHETIC_READ_DENIED')
            return original(p)
        with mock.patch.object(verify,'read',side_effect=denied):self.rejected('SYNTHETIC_READ_DENIED')

    def test_09_uid_other_than1000_rejected(self):
        with mock.patch.object(verify.os,'geteuid',return_value=0):self.rejected('UID1000_REQUIRED')

    def test_10_bootstrap_byte_hash_rejected(self):
        (self.root/BOOTSTRAP).write_bytes(b'# changed synthetic bootstrap\n')
        self.rejected('BOOTSTRAP_SHA')

    def test_11_stale_bootstrap_source_pin_rejected(self):
        self.write_bootstrap('0'*64);self.write_startup()
        self.rejected('BOOTSTRAP_SOURCE_PIN')

    def test_12_missing_startup_worker_rejected(self):
        (self.root/WORKER).unlink();self.rejected('WORKER')

    def test_13_startup_worker_hash_rejected(self):
        (self.root/WORKER).write_bytes(b'# changed synthetic worker\n');self.rejected('WORKER_SHA')

    def test_14_manifest_symlink_rejected(self):
        p=self.root/MANIFEST;other=self.home/'manifest-copy.json';other.write_bytes(p.read_bytes());p.unlink();p.symlink_to(other)
        self.rejected('SYMLINK')

    def test_15_startup_symlink_rejected(self):
        p=self.root/STARTUP;other=self.home/'startup-copy.json';other.write_bytes(p.read_bytes());p.unlink();p.symlink_to(other)
        self.rejected('SYMLINK')

    def test_16_root_symlink_rejected(self):
        link=self.home/'root-link';link.symlink_to(self.root,target_is_directory=True)
        self.rejected('SYMLINK',root=link)

    def test_17_startup_link_hash_rejected(self):
        self.startup['runtimeManifestSHA256']='0'*64;self.refresh_expected();self.rejected('STARTUP_LINK')

    def test_18_startup_manifest_hash_rejected(self):
        self.expected_data['startupManifestSHA256']='0'*64;self.expected.write_text(json.dumps(self.expected_data))
        self.rejected('STARTUP_SHA')

    def test_19_new_chain_reads_both_bootstrap_and_worker(self):
        original=verify.read;seen=[]
        def tracked(p):seen.append(p);return original(p)
        with mock.patch.object(verify,'read',side_effect=tracked):self.invoke()
        self.assertIn(self.root/BOOTSTRAP,seen);self.assertIn(self.root/WORKER,seen)
        self.assertEqual(json.loads(self.out.read_text())['installedFilesVerified'],355)

    def test_20_new_read_bound_rejects_oversized_before_read(self):
        oversized=self.home/'oversized.txt';oversized.write_bytes(b'x'*33)
        with mock.patch.object(verify,'MAX_SOURCE_BYTES',32):
            with self.assertRaisesRegex(RuntimeError,'BOUNDED_REGULAR_SOURCE_REQUIRED'):verify.read(oversized)

    def test_21_new_manifest_row_rejects_boolean_size(self):
        p=self.root/self.rows[0]['path'];p.write_bytes(b'x');self.rows[0].update(bytes=True,sha256=sha(b'x'))
        self.write_manifest();self.write_bootstrap();self.write_startup();self.rejected('MANIFEST_ROW')

    def test_22_new_worker_symlink_rejected(self):
        p=self.root/WORKER;p.unlink();target=self.home/'synthetic-worker.py';target.write_bytes(self.worker);p.symlink_to(target)
        self.rejected('WORKER_MISSING_OR_SYMLINK')

    def test_23_new_startup_row_rejects_boolean_size(self):
        self.startup['files']['worker.py']['bytes']=True;self.refresh_expected();self.rejected('STARTUP_FILE_ROW')

    def test_24_new_source_ancestor_symlink_rejected(self):
        directory=self.root/'world-simulation-shorts-engine';(directory/'alias').symlink_to(directory/'synthetic',target_is_directory=True)
        self.rows[0]['path']='world-simulation-shorts-engine/alias/source000.txt'
        self.write_manifest();self.write_bootstrap();self.write_startup();self.rejected('SYMLINK')

    def reject_output(self,target):
        expected_before=self.expected.read_bytes()
        source=self.root/self.rows[0]['path'];source_before=source.read_bytes()
        with self.assertRaisesRegex((RuntimeError,OSError),'OUTPUT|SYMLINK'):
            self.invoke(out=target)
        self.assertEqual(self.expected.read_bytes(),expected_before)
        self.assertEqual(source.read_bytes(),source_before)

    def test_25_output_cannot_overwrite_expected(self):
        self.reject_output(self.expected)

    def test_26_output_cannot_overwrite_verified_source(self):
        self.reject_output(self.root/self.rows[0]['path'])

    def test_27_output_cannot_be_inside_verified_root(self):
        target=self.root/'untracked-result.json';self.reject_output(target);self.assertFalse(target.exists())

    def test_28_output_cannot_be_verified_root_directory(self):
        self.reject_output(self.root)

    def test_29_output_cannot_overwrite_existing_regular_file(self):
        target=self.home/'existing-result.json';before=b'SYNTHETIC_EXISTING_EVIDENCE';target.write_bytes(before)
        self.reject_output(target);self.assertEqual(target.read_bytes(),before)

    def test_30_output_symlink_cannot_clobber_target(self):
        target=self.home/'existing-evidence.json';before=b'SYNTHETIC_EVIDENCE_TARGET';target.write_bytes(before)
        link=self.home/'result-link';link.symlink_to(target)
        self.reject_output(link);self.assertEqual(target.read_bytes(),before)

    def test_31_new_fresh_external_output_preserves_verified_inputs(self):
        target=self.home/'fresh-external-result.json';before=self.expected.read_bytes()
        self.invoke(out=target)
        self.assertEqual(self.expected.read_bytes(),before)
        self.assertEqual(json.loads(target.read_text())['installedFilesVerified'],355)

if __name__=='__main__':
    # Optional explicit names allow only newly failed cases to be rerun.
    unittest.main(verbosity=2)
