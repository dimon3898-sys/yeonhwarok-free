"""Only newly connected CLI output/remote-wire guards; existing9+11 skipped."""
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent;PACKAGE=HERE.parent/'label-packaging-v1';EVIDENCE=HERE/'evidence'
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,file);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
producer=load('new_safe_cli_output_guard',PACKAGE/'image_config_safe.py')
consumer=load('new_safe_remote_wire_guard',PACKAGE/'backup_build_evidence.py')

class NewTransportGuards(unittest.TestCase):
    def test_01_existing_cli_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory(prefix='new-cli-exclusive-') as temp:
            root=Path(temp);inspect=root/'inspect.json';output=root/'IMAGE_CONFIG_SAFE.json';image='sha256:'+'a'*64
            inspect.write_text(json.dumps([{'Id':image,'Config':{'Entrypoint':[],'Cmd':None,'User':'0'},
                'RootFS':{'Type':'layers','Layers':['sha256:'+'b'*64]},'Os':'linux','Architecture':'amd64'}]))
            original=b'SYNTHETIC_EXISTING_EVIDENCE_DO_NOT_OVERWRITE';output.write_bytes(original)
            argv=['image_config_safe.py','--inspect',str(inspect),'--image-id',image,
                  '--verified-parent-digest',producer.PARENT,'--out',str(output)]
            denied=AssertionError('PROCESS_OR_NETWORK_FORBIDDEN')
            with mock.patch.object(sys,'argv',argv),mock.patch('subprocess.run',side_effect=denied), \
                 mock.patch('subprocess.check_output',side_effect=denied),mock.patch('socket.create_connection',side_effect=denied):
                with self.assertRaises(FileExistsError):producer.main()
            self.assertEqual(output.read_bytes(),original)

    def test_02_actual_emitted_wire_raw_size_cap_at_remote_boundary(self):
        # Reuse emitted-byte fixture by hash; never rerun the passed CLI case.
        raw=(EVIDENCE/'SYNTHETIC_IMAGE_CONFIG_SAFE.json').read_bytes()
        prior=json.loads((EVIDENCE/'NEW_CONNECTION_RESULT.json').read_text())
        self.assertEqual(hashlib.sha256(raw).hexdigest(),prior['wireSHA256'])
        padded=raw+b' '*(131073-len(raw));self.assertEqual(len(padded),131073)
        self.assertEqual(json.loads(padded),json.loads(raw))
        with self.assertRaisesRegex(RuntimeError,'EVIDENCE_VALUE_INVALID'):
            consumer.safe_evidence_bytes('IMAGE_CONFIG_SAFE.json',padded)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NewTransportGuards))
    report={'schema':'WORLD_ENGINE_NEW_IMAGE_CONFIG_TRANSPORT_GUARDS_V1','status':'PASS' if result.wasSuccessful() else 'FAIL',
        'newCases':result.testsRun,'passed':result.testsRun-len(result.failures)-len(result.errors),'old9And11Reexecuted':False,
        'actualImageInspected':False,'imageBuilds':0,'ghcrWrites':0,'actionsExecuted':0,'gpuRuns':0}
    (EVIDENCE/'TRANSPORT_GUARD_RESULT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
    raise SystemExit(0 if result.wasSuccessful() else 1)
