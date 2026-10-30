"""New D9 workflow controls only; no runner, Docker, network, or old suite."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock
import yaml

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
WORKFLOW=REPO/'.github/workflows/world-engine-label355-build-only-DRAFT.yml'
PUBLISHER=HERE.parent/'label355-publication-v1/publish_label355_once.py'
BASELINE=HERE/'evidence/BASELINE_SAFE_WORKFLOW.yml.txt'
PIN='e163de2602a486196ec75683ddf0609bdcffb2ed'
SOURCE='af9347963b4405dac66cdbe0ad6c6898c3d42ea0'
PARENT='sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da'
PREFIX='world-simulation-shorts-engine/recovery/label-packaging-v1/'

def parse(file):return yaml.load(file.read_text(),Loader=yaml.BaseLoader)
def require(ok,code):
    if not ok:raise RuntimeError(code)

def inline_python(script):
    match=re.search(r"python3(?: -B)? - <<'PY'\n(.*?)\nPY(?:\n|$)",script,re.S)
    if not match:raise AssertionError('NEW_SAFE_CONFIG_INLINE_PYTHON_REQUIRED')
    return match.group(1)

class NewD9Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow=parse(WORKFLOW);cls.base=parse(BASELINE)
        cls.job=cls.workflow['jobs']['candidate-build'];cls.steps=cls.job['steps']
        cls.byid={row['id']:row for row in cls.steps if 'id' in row}
        cls.env=cls.job['env'];cls.safe_python=inline_python(cls.byid['safe_config']['run'])

    def test_01_runtime_and_extra_helper_checkouts_are_separate_fixed_sources(self):
        original=self.base['jobs']['candidate-build']['steps'][0]
        self.assertEqual(self.steps[0],original)
        self.assertEqual(self.steps[0]['with']['ref'],SOURCE)
        helpers=next(s for s in self.steps if s.get('uses')=='actions/checkout@v4' and s['with'].get('ref')==PIN)
        self.assertEqual(helpers['with']['path'],'label355-safe-evidence')
        self.assertEqual(helpers['with']['persist-credentials'],'false')
        self.assertEqual(set(helpers['with']['sparse-checkout'].splitlines()),
                         {PREFIX+'image_config_safe.py',PREFIX+'backup_build_evidence.py'})
        self.assertEqual(self.env['SAFE_IMAGE_CONFIG'],'label355-safe-evidence/'+PREFIX+'image_config_safe.py')
        self.assertEqual(self.env['SAFE_BACKUP'],'label355-safe-evidence/'+PREFIX+'backup_build_evidence.py')

    def test_02_no_runtime_context_or_existing_build_policy_changes(self):
        base=self.base['jobs']['candidate-build'];ids={s['id']:s for s in base['steps'] if 'id' in s}
        for name in ['pull','build_space','build','context','installed','oci']:
            self.assertEqual(self.byid[name],ids[name])
        for key in ['on','permissions','concurrency','defaults']:
            self.assertEqual(self.workflow[key],self.base[key])
        self.assertEqual(self.job['if'],base['if'])
        for key in ['PARENT','PKG','VERIFIER','PREFLIGHT','ROOT','TAG']:
            self.assertEqual(self.env[key],base['env'][key])

    def test_03_new_order_and_explicit_fail_closed_publish_dependencies(self):
        ids=[s.get('id') for s in self.steps]
        self.assertEqual(sorted(['oci','installed','safe_config','comparison','publish'],key=ids.index),
                         ['oci','installed','safe_config','comparison','publish'])
        for gate in ['installed','safe_config','comparison']:
            self.assertIn("steps."+gate+".outcome == 'success'",self.byid['publish']['if'])
        for step in ['installed','safe_config','comparison','publish']:
            self.assertNotIn('always()',self.byid[step].get('if',''))
            self.assertNotEqual(self.byid[step].get('continue-on-error'),'true')

    def test_04_final_backup_uses_pinned_schema_and_creates_index_only_once(self):
        final=self.byid['evidence'];self.assertIn('always()',final['if'])
        self.assertIn('"$SAFE_BACKUP"',final['run'])
        self.assertNotIn('SAFE_INDEX.json',self.byid['safe_config']['run'])
        self.assertEqual(sum('SAFE_INDEX.json"' in s.get('run','') and '--index' in s.get('run','') for s in self.steps),1)
        artifact=next(s for s in self.steps if s.get('uses')=='actions/upload-artifact@v4')
        self.assertNotIn('label355-oci.json',artifact['with']['path'])
        self.assertNotIn('repodigests',artifact['with']['path'])
        self.assertNotIn('label355-oci.json',final['run'])

    def comparison(self,current):
        tree=ast.parse(PUBLISHER.read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='comparison')
        old=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='OLD_ID' for t in n.targets))
        writes=[];ns={'read':lambda _: {'imageId':current},'write':lambda name,value:writes.append((name,value)),
                     'need':require,'BUILT':Path('/synthetic-evidence'),'OLD_ID':old,'SOURCE':SOURCE}
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(PUBLISHER),'exec'),ns)
        return old,writes,ns['comparison']

    def test_05_exact_d9_mismatch_writes_evidence_then_stops(self):
        old,writes,call=self.comparison('sha256:'+'b'*64)
        with self.assertRaisesRegex(RuntimeError,'BLOCKED_IMAGE_ID_MISMATCH_CAUSE_UNVERIFIED'):call()
        self.assertEqual(writes[0][0],'IMAGE_ID_COMPARISON.json');self.assertIs(writes[0][1]['imageIDsEqual'],False)

    def test_06_exact_d9_equal_id_control_does_not_bypass_other_gates(self):
        tree=ast.parse(PUBLISHER.read_text());old=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='OLD_ID' for t in n.targets))
        _,writes,call=self.comparison(old);call();self.assertIs(writes[0][1]['imageIDsEqual'],True)
        self.assertIn("steps.installed.outcome == 'success'",self.byid['publish']['if'])

    def test_07_changed_inline_syntax_contains_no_raw_export_or_build_commands(self):
        ast.parse(self.safe_python)
        self.assertNotIn('os.environ.items',self.safe_python)
        self.assertNotIn('print(raw',self.safe_python)
        self.assertNotIn('json.dump(inspect',self.safe_python)
        self.assertIn('label355-oci.json',self.safe_python)
        self.assertNotIn('docker build',self.byid['safe_config']['run'])
        self.assertNotIn('docker push',self.byid['safe_config']['run'])

    def execute_new_inline(self, mutation=None, failure=None):
        calls=[];validated=[]
        with tempfile.TemporaryDirectory(prefix='new-d9-inline-') as temp:
            root=Path(temp);evidence=root/'label355-evidence';evidence.mkdir()
            publication=root/'label355-publication';publication.mkdir()
            image='sha256:'+'a'*64;parent_ref='ghcr.io/dimon3898-sys/world-simulation-shorts-engine@'+PARENT
            documents={
                evidence/'PREFLIGHT.json':{'status':'PASS','parentDigest':PARENT},
                evidence/'BUILD_RESULT.json':{'status':'IDENTITY_ONLY','imageId':image},
                evidence/'OCI_RESULT.json':{'status':'PASS','imageId':image},
                evidence/'INSTALLED_RESULT.json':{'status':'PASS','installedFilesVerified':355},
                publication/'GHCR_PREFLIGHT.json':{'status':'PASS','existingG2TagDigest':PARENT},
                root/'context-verify.json':{'status':'PASS','parentImage':parent_ref},
                root/'label355-parent-repodigests.json':[parent_ref],
            }
            if mutation:mutation(documents,root,evidence,publication)
            for file,value in documents.items():file.write_text(json.dumps(value))
            # It represents sensitive raw inspect and stays outside artifact dirs.
            raw=root/'label355-oci.json';raw.write_text('SYNTHETIC_RAW_INSPECT_NOT_FOR_EXPORT')
            environment={'RUNNER_TEMP':str(root),'PARENT':parent_ref,
                         'SAFE_BACKUP':self.env['SAFE_BACKUP'],'SAFE_IMAGE_CONFIG':self.env['SAFE_IMAGE_CONFIG']}

            def validate(name,value):
                validated.append(name)
                if failure=='schema' and name=='IMAGE_CONFIG_SAFE.json':raise RuntimeError('SYNTHETIC_SAFE_SCHEMA_FAILED')
                return json.loads(value)
            backup=types.SimpleNamespace(safe_evidence_bytes=validate)
            spec=types.SimpleNamespace(loader=types.SimpleNamespace(exec_module=lambda _:None))
            def generate(command,**kwargs):
                calls.append((command,kwargs))
                self.assertIs(kwargs['check'],True)
                self.assertEqual(command[:3],['python3','-B',environment['SAFE_IMAGE_CONFIG']])
                self.assertEqual(command[command.index('--inspect')+1],str(raw))
                self.assertEqual(command[command.index('--verified-parent-digest')+1],PARENT)
                self.assertEqual(command[command.index('--image-id')+1],image)
                if failure=='generator':raise subprocess.CalledProcessError(2,command)
                target=Path(command[command.index('--out')+1])
                self.assertEqual(target,evidence/'IMAGE_CONFIG_SAFE.json')
                target.write_text(json.dumps({'imageId':'sha256:'+'c'*64 if failure=='captured-id' else image}))
                return subprocess.CompletedProcess(command,0)
            blocked=AssertionError('REAL_PROCESS_OR_NETWORK_FORBIDDEN')
            try:
                with mock.patch.dict(os.environ,environment,clear=True), \
                     mock.patch('importlib.util.spec_from_file_location',return_value=spec), \
                     mock.patch('importlib.util.module_from_spec',return_value=backup), \
                     mock.patch('subprocess.run',side_effect=generate), \
                     mock.patch('subprocess.check_output',side_effect=blocked), \
                     mock.patch('subprocess.Popen',side_effect=blocked), \
                     mock.patch('socket.create_connection',side_effect=blocked):
                    exec(compile(self.safe_python,'<new-safe-config-inline>','exec'),{})
            except BaseException as error:
                error.generator_calls=calls;error.validated_names=validated
                raise
            self.assertFalse((evidence/'SAFE_INDEX.json').exists())
            self.assertFalse(any('Env' in name or 'inspect' in name for name in [x.name for x in evidence.iterdir()]))
            return calls,validated

    def test_08_new_inline_binds_all_provenance_before_pinned_generation(self):
        calls,validated=self.execute_new_inline()
        self.assertEqual(len(calls),1)
        self.assertEqual(validated,['PREFLIGHT.json','BUILD_RESULT.json','OCI_RESULT.json','INSTALLED_RESULT.json','IMAGE_CONFIG_SAFE.json'])

    def test_09_new_inline_rejects_parent_provenance_before_generator(self):
        mutations=[
            ('SAFE_CONFIG_PARENT_PROVENANCE',lambda d,r,e,p:d[e/'PREFLIGHT.json'].update(parentDigest='sha256:'+'d'*64)),
            ('SAFE_CONFIG_PARENT_PROVENANCE',lambda d,r,e,p:d[p/'GHCR_PREFLIGHT.json'].update(existingG2TagDigest='sha256:'+'d'*64)),
            ('SAFE_CONFIG_PARENT_PROVENANCE',lambda d,r,e,p:d[p/'GHCR_PREFLIGHT.json'].update(status='BLOCKED')),
            ('SAFE_CONFIG_CONTEXT_PARENT',lambda d,r,e,p:d[r/'context-verify.json'].update(parentImage='synthetic-wrong-parent')),
            ('SAFE_CONFIG_CONTEXT_PARENT',lambda d,r,e,p:d[r/'context-verify.json'].update(status='BLOCKED')),
            ('SAFE_CONFIG_PULLED_PARENT',lambda d,r,e,p:d.__setitem__(r/'label355-parent-repodigests.json',[])),
        ]
        for reason,change in mutations:
            with self.subTest(reason=reason):
                with self.assertRaisesRegex(RuntimeError,reason) as found:self.execute_new_inline(change)
                self.assertEqual(found.exception.generator_calls,[])

    def test_10_new_inline_candidate_id_binding_before_and_after_generation(self):
        def changed(d,r,e,p):d[e/'OCI_RESULT.json']['imageId']='sha256:'+'c'*64
        with self.assertRaisesRegex(RuntimeError,'SAFE_CONFIG_CANDIDATE_ID') as found:self.execute_new_inline(changed)
        self.assertEqual(found.exception.generator_calls,[])
        with self.assertRaisesRegex(RuntimeError,'SAFE_CONFIG_RECEIPT_ID') as found:self.execute_new_inline(failure='captured-id')
        self.assertEqual(len(found.exception.generator_calls),1)

    def test_11_new_inline_generator_or_schema_failure_propagates(self):
        with self.assertRaises(subprocess.CalledProcessError) as found:self.execute_new_inline(failure='generator')
        self.assertEqual(len(found.exception.generator_calls),1)
        self.assertNotIn('IMAGE_CONFIG_SAFE.json',found.exception.validated_names)
        with self.assertRaisesRegex(RuntimeError,'SYNTHETIC_SAFE_SCHEMA_FAILED') as found:self.execute_new_inline(failure='schema')
        self.assertEqual(len(found.exception.generator_calls),1)

    def test_12_failed_verification_or_d9_never_reaches_publish_but_preserves_evidence_path(self):
        expr=self.byid['publish']['if']
        clauses=re.findall(r"steps\.([A-Za-z0-9_]+)\.outcome == 'success'",expr)
        self.assertEqual(set(clauses),{'installed','safe_config','comparison'})
        for failed in ['installed','safe_config','comparison']:
            with self.subTest(failed=failed):
                outcomes={name:'success' for name in clauses};outcomes[failed]='failure'
                # GitHub adds success() to a step if without status functions.
                eligible=not any(v=='failure' for v in outcomes.values()) and all(outcomes[name]=='success' for name in clauses)
                self.assertFalse(eligible)
                self.assertEqual(self.byid['evidence']['if'],'always() && !cancelled()')
                self.assertIn('"$SAFE_BACKUP"',self.byid['evidence']['run'])
        self.assertNotIn('if',self.byid['comparison'])

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NewD9Controls))
    report={'schema':'WORLD_ENGINE_NEW_D9_WORKFLOW_CONTROL_TESTS_V1','status':'PASS' if result.wasSuccessful() else 'FAIL',
            'newCases':result.testsRun,'passed':result.testsRun-len(result.failures)-len(result.errors),
            'oldPASSSuiteRuns':0,'realDockerCommands':0,'realNetworkRequests':0,'actionsExecuted':0,'imageBuilds':0,'ghcrWrites':0,'gpuRuns':0}
    evidence=HERE/'evidence';evidence.mkdir(parents=True,exist_ok=True)
    (evidence/'FOCUSED_CONTROL_RESULT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
    raise SystemExit(0 if result.wasSuccessful() else 1)
