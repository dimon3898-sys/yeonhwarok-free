"""New OCI/BUILD producer-consumer schema tests only; no image operations."""
import argparse
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parent/'label-packaging-v1'
EVIDENCE=HERE/'evidence'
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
consumer=load('new_oci_build_consumer',PACKAGE/'backup_build_evidence.py')
producer=load('new_oci_build_producer',PACKAGE/'produce_image_results.py')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def wire(value):return json.dumps(value,sort_keys=True).encode()

class NewOciBuildSchemas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='new-oci-build-contract-')
        cls.root=Path(cls.temp.name);cls.summaries=cls.root/'summaries';cls.summaries.mkdir()
        expected=json.loads((PACKAGE/'evidence/CONTEXT_PLAN.json').read_text())
        cls.inspect=cls.root/'synthetic-inspect.json';cls.expected=cls.root/'synthetic-expected.json'
        cls.inspect.write_text(json.dumps([{'Id':'sha256:'+'a'*64,'Config':{'Entrypoint':expected['entrypoint'],'Cmd':None,'User':'0'}}]))
        cls.expected.write_text(json.dumps({'entrypoint':expected['entrypoint']}))
        argv=['produce_image_results.py','--inspect',str(cls.inspect),'--expected',str(cls.expected),
              '--oci-out',str(cls.summaries/'OCI_RESULT.json'),'--build-out',str(cls.summaries/'BUILD_RESULT.json')]
        forbidden=AssertionError('REAL_NETWORK_OR_EXTERNAL_PROCESS_FORBIDDEN')
        with mock.patch.object(sys,'argv',argv),mock.patch('subprocess.check_output',side_effect=forbidden), \
             mock.patch('subprocess.run',side_effect=forbidden),mock.patch('subprocess.Popen',side_effect=forbidden), \
             mock.patch('socket.create_connection',side_effect=forbidden):
            producer.main()
        cls.raw={name:(cls.summaries/name).read_bytes() for name in ['OCI_RESULT.json','BUILD_RESULT.json']}
        cls.values={name:json.loads(raw) for name,raw in cls.raw.items()}
        EVIDENCE.mkdir(parents=True,exist_ok=True)
        receipt={'schema':'WORLD_ENGINE_SYNTHETIC_OCI_BUILD_PRODUCER_CONTRACT_V1',
                 'producerSHA256':sha((PACKAGE/'produce_image_results.py').read_bytes()),
                 'source':'Actual producer.main with synthetic inspect and pinned declared entrypoint',
                 'syntheticImageId':'sha256:'+'a'*64,'actualImageInspected':False,'imageBuilds':0,
                 'outputs':{name:{'value':cls.values[name],'bytes':len(raw),'sha256':sha(raw)} for name,raw in cls.raw.items()}}
        (EVIDENCE/'PRODUCER_CONTRACT_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def candidate(self,name,**updates):
        value=dict(self.values[name]);value.update(updates);return value

    def rejected(self,name,value):
        with self.assertRaisesRegex(RuntimeError,'EVIDENCE_(FIELDS|VALUE)_INVALID'):
            consumer.safe_evidence_bytes(name,wire(value))

    def test_01_actual_producer_oci_accepted_unchanged(self):
        result=consumer.safe_evidence_bytes('OCI_RESULT.json',self.raw['OCI_RESULT.json'])
        self.assertEqual(result,self.values['OCI_RESULT.json']);self.assertEqual(len(result),8)

    def test_02_actual_producer_build_stays_identity_only(self):
        result=consumer.safe_evidence_bytes('BUILD_RESULT.json',self.raw['BUILD_RESULT.json'])
        self.assertEqual(result,self.values['BUILD_RESULT.json']);self.assertEqual(len(result),7)
        self.assertEqual(result['status'],'IDENTITY_ONLY');self.assertNotEqual(result['status'],'PASS')

    def test_03_actual_pair_collected_without_claiming_image_build(self):
        index,payloads=consumer.collect_evidence(self.summaries)
        self.assertEqual(payloads,self.raw);self.assertEqual(index['status'],'PREPARED_NOT_REMOTE_BACKED_UP')
        self.assertEqual(index['totalBytes'],sum(map(len,self.raw.values())))
        for row in index['files']:
            self.assertEqual(row['sha256'],sha(self.raw[row['name']]))
        self.assertEqual(json.loads(payloads['BUILD_RESULT.json'])['status'],'IDENTITY_ONLY')
        output=self.summaries/'SAFE_INDEX.json'
        with mock.patch.object(sys,'argv',['backup_build_evidence.py','--evidence',str(self.summaries),'--index',str(output)]):consumer.main()
        self.assertEqual(json.loads(output.read_text()),index)

    def test_04_oci_missing_fields_rejected(self):
        for key in self.values['OCI_RESULT.json']:
            with self.subTest(key=key):
                value=self.candidate('OCI_RESULT.json');del value[key];self.rejected('OCI_RESULT.json',value)

    def test_05_oci_extra_private_fields_rejected(self):
        for key in ['stderr','environment','token','prompt','imageBuilt']:
            with self.subTest(key=key):self.rejected('OCI_RESULT.json',self.candidate('OCI_RESULT.json',**{key:'SYNTHETIC_NOT_FOR_EXPORT'}))

    def test_06_oci_schema_exact(self):
        for value in [None,1,'WORLD_ENGINE_LABEL355_BUILD_RESULT_V1','WORLD_ENGINE_LABEL355_OCI_RESULT_V2']:
            with self.subTest(value=value):self.rejected('OCI_RESULT.json',self.candidate('OCI_RESULT.json',schema=value))

    def test_07_oci_status_exact(self):
        for value in [None,True,'IDENTITY_ONLY','BLOCKED','SUCCESS']:
            with self.subTest(value=value):self.rejected('OCI_RESULT.json',self.candidate('OCI_RESULT.json',status=value))

    def bad_image_ids(self,name):
        for value in [None,True,123,[],{},'a'*64,'sha256:'+'a'*63,'sha256:'+'a'*65,'sha256:'+'A'*64,'sha256:'+'a'*64+'\n']:
            with self.subTest(value=value):self.rejected(name,self.candidate(name,imageId=value))

    def test_08_oci_image_id_strict(self):self.bad_image_ids('OCI_RESULT.json')

    def match_flag(self,key):
        for value in [False,1,0,'true',None,[],{}]:
            with self.subTest(value=value):self.rejected('OCI_RESULT.json',self.candidate('OCI_RESULT.json',**{key:value}))

    def test_09_oci_entrypoint_true_boolean(self):self.match_flag('entrypointMatch')
    def test_10_oci_cmd_true_boolean(self):self.match_flag('cmdUnchanged')
    def test_11_oci_user_true_boolean(self):self.match_flag('userUnchanged')

    def test_12_oci_scope_exact(self):
        for value in ['BUILD_PASS','INSTALLED_FILES_AND_UID1000_ONLY_OCI_HOST_CHECK_SEPARATE',None,[]]:
            with self.subTest(value=value):self.rejected('OCI_RESULT.json',self.candidate('OCI_RESULT.json',scope=value))

    def false_gpu(self,name):
        for value in [True,0,1,'false',None,[],{}]:
            with self.subTest(value=value):self.rejected(name,self.candidate(name,gpuExecuted=value))

    def test_13_oci_gpu_false_boolean(self):self.false_gpu('OCI_RESULT.json')

    def test_14_build_missing_fields_rejected(self):
        for key in self.values['BUILD_RESULT.json']:
            with self.subTest(key=key):
                value=self.candidate('BUILD_RESULT.json');del value[key];self.rejected('BUILD_RESULT.json',value)

    def test_15_build_extra_fields_cannot_add_pass_or_private_data(self):
        for key in ['stderr','environment','token','prompt','buildSucceeded','installedFilesVerified']:
            with self.subTest(key=key):self.rejected('BUILD_RESULT.json',self.candidate('BUILD_RESULT.json',**{key:'SYNTHETIC_NOT_FOR_EXPORT'}))

    def test_16_build_schema_exact(self):
        for value in [None,True,'WORLD_ENGINE_LABEL355_OCI_RESULT_V1','WORLD_ENGINE_LABEL355_BUILD_RESULT_V2']:
            with self.subTest(value=value):self.rejected('BUILD_RESULT.json',self.candidate('BUILD_RESULT.json',schema=value))

    def test_17_build_pass_promotion_rejected(self):
        for value in ['PASS','BUILD_PASS','SUCCESS','BLOCKED',None,True]:
            with self.subTest(value=value):self.rejected('BUILD_RESULT.json',self.candidate('BUILD_RESULT.json',status=value))

    def test_18_build_image_id_strict(self):self.bad_image_ids('BUILD_RESULT.json')

    def test_19_build_parent_digest_exact(self):
        for value in ['sha256:'+'b'*64,'9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da',None,True]:
            with self.subTest(value=value):self.rejected('BUILD_RESULT.json',self.candidate('BUILD_RESULT.json',parentDigest=value))

    def test_20_build_rows_exact_integer(self):
        for value in [355.0,'355',True,False,None,354,356,[],{}]:
            with self.subTest(value=value):self.rejected('BUILD_RESULT.json',self.candidate('BUILD_RESULT.json',expectedSourceRows=value))

    def test_21_build_scope_not_build_pass(self):
        for value in ['ACTUAL_CANDIDATE_OCI_CONFIG_ONLY','BUILD_PASS','INSTALLED_VALIDATION',None,[]]:
            with self.subTest(value=value):self.rejected('BUILD_RESULT.json',self.candidate('BUILD_RESULT.json',scope=value))

    def test_22_build_gpu_false_boolean(self):self.false_gpu('BUILD_RESULT.json')

    def test_23_filename_schema_swaps_rejected(self):
        self.rejected('BUILD_RESULT.json',self.values['OCI_RESULT.json'])
        self.rejected('OCI_RESULT.json',self.values['BUILD_RESULT.json'])

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--cases');args=parser.parse_args()
    names=unittest.defaultTestLoader.getTestCaseNames(NewOciBuildSchemas)
    if args.cases:names=[n for n in names if n[5:7] in set(args.cases.split(','))]
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(NewOciBuildSchemas(n) for n in names))
    print(json.dumps({'schema':'WORLD_ENGINE_NEW_OCI_BUILD_SCHEMA_TEST_RESULT_V1','status':'PASS' if result.wasSuccessful() else 'BLOCKED',
        'cases':len(names),'passed':len(names)-len(result.failures)-len(result.errors),'oldPASSReexecutions':0,
        'actualImageBuilds':0,'dockerCommands':0,'actionsDispatched':0,'gpuRuns':0,'scope':'SYNTHETIC_PRODUCER_CONSUMER_CONTRACT_ONLY'}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
