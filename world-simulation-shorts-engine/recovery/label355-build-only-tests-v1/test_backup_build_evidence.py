"""New local safe-evidence preparer cases; no old suite, network or process."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent
TARGET=HERE.parent/'label-packaging-v1/backup_build_evidence.py'
spec=importlib.util.spec_from_file_location('focused_local_backup',TARGET)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def valid():
    return {'status':'PASS','parentDigest':'sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da',
            'compressedLayerBytes':1,'freeBytes':20*1024**3,'estimatedRequiredBytes':8*1024**3+4,
            'costGate':'CURRENT_ATTESTED','scope':'BUILD_PREFLIGHT_ONLY'}

class NewBackupLocal(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='new-label355-safe-evidence-')
        self.root=Path(self.temp.name);self.index=self.root/'SAFE_INDEX.json'
    def tearDown(self):self.temp.cleanup()
    def write(self,name,value):
        p=self.root/name;p.write_text(json.dumps(value)+'\n');return p
    def call(self,index=None):
        with mock.patch.object(sys,'argv',[str(TARGET),'--evidence',str(self.root),'--index',str(index or self.index)]):
            module.main()
    def test_01_normal_closed_summary_is_hashed_exactly(self):
        p=self.write('PREFLIGHT.json',valid());raw=p.read_bytes();self.call();v=json.loads(self.index.read_text())
        self.assertEqual(v['status'],'PREPARED_NOT_REMOTE_BACKED_UP')
        self.assertEqual(v['totalBytes'],len(raw));self.assertEqual(v['files'],[{'name':p.name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}])
    def test_02_unknown_private_files_are_never_read_or_indexed(self):
        self.write('PREFLIGHT.json',valid());p=self.root/'private-stderr.log';p.write_text('SYNTHETIC_NON_PUBLIC_NOT_FOR_EXPORT')
        original=Path.read_bytes
        def guarded(path,*args,**kwargs):
            if path==p:raise AssertionError('PRIVATE_READ_FORBIDDEN')
            return original(path,*args,**kwargs)
        with mock.patch.object(Path,'read_bytes',guarded):self.call()
        self.assertEqual([r['name'] for r in json.loads(self.index.read_text())['files']],['PREFLIGHT.json'])
    def test_03_empty_safe_set_is_blocked(self):
        with self.assertRaisesRegex(RuntimeError,'NO_SAFE_EVIDENCE'):self.call()
        self.assertFalse(self.index.exists())
    def test_04_size_over_limit_is_blocked_without_output(self):
        self.write('PREFLIGHT.json',valid())
        with mock.patch.object(module,'MAX_BYTES',16):
            with self.assertRaisesRegex(RuntimeError,'EVIDENCE_SIZE_LIMIT'):self.call()
        self.assertFalse(self.index.exists())
    def test_05_symlink_payload_is_skipped(self):
        outside=self.root/'not-exported';outside.write_text('SYNTHETIC_UNEXPORTED')
        (self.root/'PREFLIGHT.json').symlink_to(outside)
        with self.assertRaisesRegex(RuntimeError,'NO_SAFE_EVIDENCE'):self.call()
    def test_06_permission_denial_is_fail_closed(self):
        p=self.write('PREFLIGHT.json',valid());original=Path.open
        def denied(path,*args,**kwargs):
            if path==p:raise PermissionError('SYNTHETIC_READ_PERMISSION_DENIED')
            return original(path,*args,**kwargs)
        with mock.patch.object(Path,'open',denied):
            with self.assertRaises(PermissionError):self.call()
        self.assertFalse(self.index.exists())
    def test_07_index_must_not_overwrite_payload(self):
        p=self.write('PREFLIGHT.json',valid());raw=p.read_bytes()
        with self.assertRaisesRegex(RuntimeError,'INDEX_PATH_REQUIRED'):self.call(p)
        self.assertEqual(p.read_bytes(),raw)
    def test_08_existing_index_must_not_be_overwritten(self):
        self.write('PREFLIGHT.json',valid());self.index.write_text('SYNTHETIC_PRIOR_INDEX')
        with self.assertRaisesRegex(RuntimeError,'INDEX_ALREADY_EXISTS'):self.call()
        self.assertEqual(self.index.read_text(),'SYNTHETIC_PRIOR_INDEX')
    def test_09_oversized_payload_is_rejected_before_open(self):
        p=self.write('PREFLIGHT.json',valid());original=Path.open
        def no_payload_open(path,*args,**kwargs):
            if path==p:raise AssertionError('OVERSIZED_PAYLOAD_OPENED')
            return original(path,*args,**kwargs)
        with mock.patch.object(module,'MAX_BYTES',16),mock.patch.object(Path,'open',no_payload_open):
            with self.assertRaisesRegex(RuntimeError,'EVIDENCE_SIZE_LIMIT'):self.call()
    def test_10_allowed_filename_cannot_export_plaintext(self):
        (self.root/'PREFLIGHT.json').write_text('SYNTHETIC_PRIVATE_TEXT')
        with self.assertRaisesRegex(RuntimeError,'EVIDENCE_JSON_INVALID'):self.call()
        self.assertFalse(self.index.exists())
    def test_11_unknown_private_fields_are_rejected(self):
        v=valid();v['stderr']='SYNTHETIC_PRIVATE_NOT_FOR_EXPORT';self.write('PREFLIGHT.json',v)
        with self.assertRaisesRegex(RuntimeError,'EVIDENCE_FIELDS_INVALID'):self.call()
        self.assertFalse(self.index.exists())
    def test_12_symlink_evidence_root_is_rejected(self):
        self.write('PREFLIGHT.json',valid());link=self.root/'link';link.symlink_to(self.root,target_is_directory=True)
        with mock.patch.object(sys,'argv',[str(TARGET),'--evidence',str(link),'--index',str(link/'SAFE_INDEX.json')]):
            with self.assertRaisesRegex(RuntimeError,'EVIDENCE_SYMLINK_FORBIDDEN'):module.main()
    def test_13_shared_collector_accepts_actual_producer_shapes_without_writes(self):
        v=valid();v.update(storageDriver='vfs',layerCount=75,
                         capacityEstimateBasis='4x cumulative compressed prefixes +8GiB reserve',
                         localDaemonEndpoint='unix:///var/run/docker.sock')
        self.write('PREFLIGHT.json',v)
        installed={'schema':'WORLD_ENGINE_INSTALLED_LABEL355_VERIFICATION_V1','status':'PASS',
                   'installedFilesVerified':355,'uid':1000,'runtimeManifestSHA256':'1'*64,
                   'startupManifestSHA256':'2'*64,'scope':'INSTALLED_FILES_AND_UID1000_ONLY_OCI_HOST_CHECK_SEPARATE','gpuExecuted':False}
        self.write('INSTALLED_RESULT.json',installed)
        index,payloads=module.collect_evidence(self.root)
        self.assertFalse(self.index.exists());self.assertEqual(set(payloads),{'PREFLIGHT.json','INSTALLED_RESULT.json'})
        self.assertEqual(index['totalBytes'],sum(map(len,payloads.values())))
        for row in index['files']:
            self.assertEqual(row['sha256'],hashlib.sha256(payloads[row['name']]).hexdigest())
            self.assertEqual(row['bytes'],len(payloads[row['name']]))
    def test_14_exact_limit_acceptance_and_one_byte_over_rejection(self):
        p=self.write('PREFLIGHT.json',valid());length=len(p.read_bytes())
        with mock.patch.object(module,'MAX_BYTES',length):
            index,_=module.collect_evidence(self.root);self.assertEqual(index['totalBytes'],length)
        with mock.patch.object(module,'MAX_BYTES',length-1):
            with self.assertRaisesRegex(RuntimeError,'EVIDENCE_SIZE_LIMIT'):module.collect_evidence(self.root)
    def test_15_boolean_and_wrong_enum_payloads_are_not_safe_summaries(self):
        for changes in [{'freeBytes':True},{'costGate':'UNCONFIRMED'},{'scope':'SYNTHETIC_PRIVATE_NOT_FOR_EXPORT'},
                        {'parentDigest':'sha256:'+'0'*64},{'storageDriver':'remote-unreviewed'}]:
            v=valid();v.update(changes)
            with self.subTest(keys=list(changes)):
                with self.assertRaisesRegex(RuntimeError,'EVIDENCE_VALUE_INVALID'):
                    module.safe_evidence_bytes('PREFLIGHT.json',json.dumps(v).encode())
    def test_16_duplicate_json_keys_and_non_objects_are_rejected(self):
        for raw,error in [(b'{"status":"PASS","status":"PASS"}','EVIDENCE_DUPLICATE_JSON_KEY'),
                          (b'[]','EVIDENCE_JSON_INVALID'),(b'{"status":NaN}','EVIDENCE_JSON_INVALID')]:
            with self.subTest(error=error):
                with self.assertRaisesRegex(RuntimeError,error):module.safe_evidence_bytes('PREFLIGHT.json',raw)
    def test_17_unreviewed_oci_and_build_producers_remain_blocked(self):
        for name in ['OCI_RESULT.json','BUILD_RESULT.json']:
            with self.subTest(name=name):
                with self.assertRaisesRegex(RuntimeError,'UNREVIEWED_EVIDENCE_SCHEMA'):
                    module.safe_evidence_bytes(name,b'{"status":"PASS"}')
    def test_18_index_symlink_does_not_overwrite_source(self):
        p=self.write('PREFLIGHT.json',valid());raw=p.read_bytes();self.index.symlink_to(p)
        with self.assertRaisesRegex(RuntimeError,'EVIDENCE_SYMLINK_FORBIDDEN'):self.call()
        self.assertEqual(p.read_bytes(),raw)
    def test_19_index_write_permission_failure_retains_input(self):
        p=self.write('PREFLIGHT.json',valid());raw=p.read_bytes();original=Path.open
        def denied(path,*args,**kwargs):
            if path==self.index:raise PermissionError('SYNTHETIC_INDEX_WRITE_DENIED')
            return original(path,*args,**kwargs)
        with mock.patch.object(Path,'open',denied):
            with self.assertRaises(PermissionError):self.call()
        self.assertEqual(p.read_bytes(),raw);self.assertFalse(self.index.exists())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cases');a=p.parse_args()
    names=unittest.defaultTestLoader.getTestCaseNames(NewBackupLocal)
    if a.cases:names=[n for n in names if n[5:7] in set(a.cases.split(','))]
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(NewBackupLocal(n) for n in names))
    print(json.dumps({'schema':'WORLD_ENGINE_NEW_LOCAL_BACKUP_TEST_RESULT_V1','cases':len(names),'passed':len(names)-len(result.failures)-len(result.errors),'failures':[t._testMethodName for t,_ in result.failures+result.errors],'existingSuiteExecutions':0,'networkRequests':0,'processStarts':0}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
