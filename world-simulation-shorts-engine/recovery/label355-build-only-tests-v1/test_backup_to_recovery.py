"""New remote-backup control tests. Every Git/process/network operation is mocked."""
from contextlib import contextmanager, redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / 'label-packaging-v1/backup_to_recovery.py'
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location('new_remote_backup', SCRIPT)
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)
PREFIX = 'world-simulation-shorts-engine/recovery/label-image-build-v1/evidence/actions-'
MAX_BYTES = 5 * 1024 * 1024
ORIGIN = 'https://github.com/dimon3898-sys/yeonhwarok-free.git'

def sha(data): return hashlib.sha256(data).hexdigest()

class RemoteBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='new-remote-backup-')
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.evidence = self.workspace / 'safe-evidence'
        self.evidence.mkdir()
        self.old_cwd = Path.cwd()
        os.chdir(self.workspace)
        self.addCleanup(os.chdir, self.old_cwd)
        self.destination = PREFIX + '42'
        self.data = (json.dumps({'status':'PASS','parentDigest':'sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da',
            'compressedLayerBytes':10,'freeBytes':10**12,'estimatedRequiredBytes':8589934632,
            'costGate':'CURRENT_ATTESTED','scope':'BUILD_PREFLIGHT_ONLY',
            'storageDriver':'overlay2','layerCount':1,'capacityEstimateBasis':'4x compressed bytes +8GiB reserve',
            'localDaemonEndpoint':'unix:///var/run/docker.sock'}, sort_keys=True)+'\n').encode()
        self.payloads = {'PREFLIGHT.json': self.data}
        for name, data in self.payloads.items(): (self.evidence/name).write_bytes(data)
        self.index = {'schema':'WORLD_ENGINE_LABEL355_SAFE_EVIDENCE_INDEX_V1',
            'files':[{'name':name,'bytes':len(data),'sha256':sha(data)} for name,data in self.payloads.items()],
            'totalBytes':sum(map(len,self.payloads.values())), 'status':'PREPARED_NOT_REMOTE_BACKED_UP'}
        self.write_index()
        self.calls = []
        self.env = {'GITHUB_RUN_ATTEMPT':'1','GITHUB_RUN_ID':'42',
            'GITHUB_REPOSITORY':'dimon3898-sys/yeonhwarok-free',
            'WORLD_ENGINE_LABEL355_BACKUP_APPROVED':'true'}
        self.fetch_hook = None
        self.push_denied = False
        self.dirty = False
        self.origin = ORIGIN

    def write_index(self):
        (self.evidence/'SAFE_INDEX.json').write_text(json.dumps(self.index)+'\n')

    def fake_run(self, *cmd):
        self.calls.append(tuple(cmd))
        if cmd[:3] == ('git','status','--porcelain'): return ' M synthetic.txt' if self.dirty else ''
        if cmd[:3] == ('git','remote','get-url'): return self.origin
        if cmd[:3] == ('git','rev-parse','--show-toplevel'): return str(self.workspace)
        if cmd[:2] == ('git','fetch') and self.fetch_hook:
            hook,self.fetch_hook=self.fetch_hook,None
            hook()
        if cmd[:2] == ('git','push') and self.push_denied: raise RuntimeError('SYNTHETIC_PUSH_DENIED')
        return ''

    def fake_output(self, cmd, *args, **kwargs):
        self.calls.append(tuple(cmd))
        if cmd[:2] == ['git','show']:
            name=cmd[2].rsplit('/',1)[-1]
            return (Path(self.destination)/name).read_bytes()
        raise AssertionError('REAL_EXTERNAL_PROCESS_FORBIDDEN')

    def invoke(self):
        argv=['backup_to_recovery.py','--evidence',str(self.evidence),'--destination',self.destination]
        with mock.patch.dict(os.environ,self.env,clear=True), mock.patch.object(sys,'argv',argv), \
             mock.patch.object(backup,'run',self.fake_run), \
             mock.patch('subprocess.check_output',self.fake_output), \
             mock.patch('subprocess.run',side_effect=AssertionError('REAL_PROCESS_FORBIDDEN')), \
             mock.patch('socket.socket',side_effect=AssertionError('NETWORK_FORBIDDEN')), redirect_stdout(io.StringIO()):
            backup.main()

    def blocked_before_git(self):
        with self.assertRaises(Exception): self.invoke()
        self.assertEqual(self.calls,[])
        self.assertFalse(Path(self.destination).exists())

    def test_01_approval_required(self):
        self.env['WORLD_ENGINE_LABEL355_BACKUP_APPROVED']='false';self.blocked_before_git()

    def test_02_retry_forbidden(self):
        self.env['GITHUB_RUN_ATTEMPT']='2';self.blocked_before_git()

    def test_03_wrong_repository(self):
        self.env['GITHUB_REPOSITORY']='synthetic/elsewhere';self.blocked_before_git()

    def test_04_mocked_normal_backup_exact_bytes(self):
        self.invoke()
        self.assertEqual((Path(self.destination)/'PREFLIGHT.json').read_bytes(),self.data)
        self.assertEqual(len([c for c in self.calls if c[:2]==('git','push')]),1)
        self.assertFalse(any('--force' in c or '--force-with-lease' in c for c in self.calls))

    def test_05_hash_mismatch_blocks(self):
        self.index['files'][0]['sha256']='0'*64;self.write_index();self.blocked_before_git()

    def test_06_permission_denied_blocks(self):
        original=Path.read_text
        def denied(path,*args,**kwargs):
            if path==self.evidence/'SAFE_INDEX.json': raise PermissionError('synthetic denied')
            return original(path,*args,**kwargs)
        # read_bytes-based fixed versions are covered too.
        original_bytes=Path.read_bytes
        def denied_bytes(path,*args,**kwargs):
            if path==self.evidence/'SAFE_INDEX.json': raise PermissionError('synthetic denied')
            return original_bytes(path,*args,**kwargs)
        original_open=Path.open
        def denied_open(path,*args,**kwargs):
            if path==self.evidence/'SAFE_INDEX.json':raise PermissionError('synthetic denied')
            return original_open(path,*args,**kwargs)
        with mock.patch.object(Path,'read_text',denied),mock.patch.object(Path,'read_bytes',denied_bytes),mock.patch.object(Path,'open',denied_open):
            self.blocked_before_git()

    def test_07_forged_total_blocks(self):
        self.index['totalBytes']=1;self.write_index();self.blocked_before_git()

    def test_08_oversized_payload_with_forged_total_blocks(self):
        raw=b'x'*(MAX_BYTES+1);(self.evidence/'PREFLIGHT.json').write_bytes(raw)
        self.index['files'][0].update(bytes=len(raw),sha256=sha(raw));self.index['totalBytes']=0
        self.write_index();self.blocked_before_git()

    def test_09_duplicate_index_rows_block(self):
        self.index['files'].append(dict(self.index['files'][0]));self.index['totalBytes']*=2
        self.write_index();self.blocked_before_git()

    def test_10_wrong_index_schema_blocks(self):
        self.index['schema']='SYNTHETIC_UNKNOWN';self.write_index();self.blocked_before_git()

    def test_11_destination_traversal_blocks(self):
        self.destination=PREFIX+'42/../synthetic-escape';self.blocked_before_git()

    def test_12_run_id_destination_mismatch_blocks(self):
        self.destination=PREFIX+'99';self.blocked_before_git()

    def test_13_symlink_index_blocks(self):
        index=self.evidence/'SAFE_INDEX.json';other=self.workspace/'synthetic-index.json'
        other.write_bytes(index.read_bytes());index.unlink();index.symlink_to(other)
        self.blocked_before_git()

    def test_14_validated_bytes_frozen_before_git(self):
        self.fetch_hook=lambda:(self.evidence/'PREFLIGHT.json').write_bytes(b'SYNTHETIC_CHANGED_AFTER_VALIDATION')
        self.invoke();self.assertEqual((Path(self.destination)/'PREFLIGHT.json').read_bytes(),self.data)

    def test_15_remote_push_denial_no_retry(self):
        self.push_denied=True
        with self.assertRaisesRegex(RuntimeError,'SYNTHETIC_PUSH_DENIED'): self.invoke()
        self.assertEqual(len([c for c in self.calls if c[:2]==('git','push')]),1)
        self.assertFalse(any(c[:2]==('git','show') for c in self.calls))

    def test_16_dirty_worktree_blocks_checkout(self):
        self.dirty=True
        with self.assertRaisesRegex(RuntimeError,'DIRTY_WORKTREE'): self.invoke()
        self.assertFalse(any(c[:2] in [('git','checkout'),('git','push')] for c in self.calls))

    def test_17_wrong_origin_blocks_before_fetch(self):
        self.origin='https://github.com/synthetic/unapproved.git'
        with self.assertRaises(Exception): self.invoke()
        self.assertFalse(any(c[:2] in [('git','fetch'),('git','push')] for c in self.calls))

    def test_18_remote_readback_requires_fresh_fetch(self):
        self.invoke();push=next(i for i,c in enumerate(self.calls) if c[:2]==('git','push'))
        show=next(i for i,c in enumerate(self.calls) if c[:2]==('git','show'))
        self.assertTrue(any(c[:2]==('git','fetch') for c in self.calls[push+1:show]))

    def test_19_oversized_index_blocks(self):
        (self.evidence/'SAFE_INDEX.json').write_text(' '*65537);self.blocked_before_git()

    def test_20_allowed_filename_cannot_carry_raw_private_text(self):
        raw=b'SYNTHETIC_PRIVATE_STDERR_NOT_FOR_EXPORT';(self.evidence/'PREFLIGHT.json').write_bytes(raw)
        self.index['files'][0].update(bytes=len(raw),sha256=sha(raw));self.index['totalBytes']=len(raw)
        self.write_index();self.blocked_before_git()

    def test_21_existing_destination_blocks(self):
        Path(self.destination).mkdir(parents=True)
        with self.assertRaisesRegex(RuntimeError,'DESTINATION_ALREADY_EXISTS'): self.invoke()
        self.assertEqual(self.calls,[])

    def test_22_index_metadata_integer_types_required(self):
        self.index['totalBytes']=float(self.index['totalBytes'])
        self.index['files'][0]['bytes']=float(self.index['files'][0]['bytes'])
        self.write_index();self.blocked_before_git()

    def test_23_destination_parent_symlink_blocks(self):
        ancestor=Path(PREFIX).parent
        ancestor.parent.mkdir(parents=True)
        target=self.workspace/'synthetic-target';target.mkdir();ancestor.symlink_to(target,target_is_directory=True)
        self.blocked_before_git()

    def test_24_push_denial_retains_local_evidence(self):
        self.push_denied=True
        with self.assertRaisesRegex(RuntimeError,'SYNTHETIC_PUSH_DENIED'): self.invoke()
        self.assertEqual((Path(self.destination)/'PREFLIGHT.json').read_bytes(),self.data)
        self.assertEqual(len([c for c in self.calls if c[:2]==('git','push')]),1)

    def test_25_readback_mismatch_blocks_without_retry(self):
        def wrong_output(cmd,*args,**kwargs):
            self.calls.append(tuple(cmd));return b'SYNTHETIC_REMOTE_MISMATCH'
        self.fake_output=wrong_output
        with self.assertRaisesRegex(RuntimeError,'REMOTE_READBACK_MISMATCH'): self.invoke()
        self.assertEqual(len([c for c in self.calls if c[:2]==('git','push')]),1)
        self.assertEqual((Path(self.destination)/'PREFLIGHT.json').read_bytes(),self.data)

    def test_26_incomplete_cost_summary_blocks(self):
        value=json.loads(self.data);del value['costGate'];raw=json.dumps(value).encode()
        (self.evidence/'PREFLIGHT.json').write_bytes(raw)
        self.index['files'][0].update(bytes=len(raw),sha256=sha(raw));self.index['totalBytes']=len(raw)
        self.write_index();self.blocked_before_git()

    def test_27_index_size_rejected_before_read(self):
        index=self.evidence/'SAFE_INDEX.json';index.write_bytes(b'x'*65537)
        original_open=Path.open
        def guarded(path,*args,**kwargs):
            if path==index:raise AssertionError('OVERSIZED_INDEX_MUST_NOT_BE_READ')
            return original_open(path,*args,**kwargs)
        with mock.patch.object(Path,'open',guarded):
            with self.assertRaisesRegex(RuntimeError,'INDEX_SIZE_LIMIT'):self.invoke()
        self.assertEqual(self.calls,[])

if __name__=='__main__':
    unittest.main(verbosity=2)
