"""New packaged CLI wire-to-remote-consumer connection only; old9/11 skipped."""
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import traceback
from unittest import mock

HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parent/'label-packaging-v1'
EVIDENCE=HERE/'evidence'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
producer=load('handoff_image_config_safe',PACKAGE/'image_config_safe.py')
consumer=load('actual_remote_backup_contract',PACKAGE/'backup_build_evidence.py')
report={'schema':'WORLD_ENGINE_IMAGE_CONFIG_NEW_CLI_CONNECTION_V1','status':'NOT_RUN',
    'case':'packaged_main_serialized_bytes_to_actual_remote_validator_collector_index',
    'producerSHA256':hashlib.sha256((PACKAGE/'image_config_safe.py').read_bytes()).hexdigest(),
    'consumerSHA256':hashlib.sha256((PACKAGE/'backup_build_evidence.py').read_bytes()).hexdigest(),
    'oldGenerator9Reexecuted':False,'oldMirrorContract11Reexecuted':False,
    'allOtherOldPASSReexecuted':False,'imageBuilds':0,'dockerCommands':0,
    'actionsExecuted':0,'ghcrWrites':0,'gpuRuns':0,'collectorReached':False,'indexReached':False,
    'inputKind':'TINY_SYNTHETIC_INSPECT_NOT_AN_ACTUAL_IMAGE'}
try:
    with tempfile.TemporaryDirectory(prefix='new-image-config-wire-') as temp:
        root=Path(temp);summaries=root/'summaries';summaries.mkdir();source=root/'inspect.json'
        image='sha256:'+'a'*64
        source.write_text(json.dumps([{'Id':image,'Config':{'Entrypoint':['/usr/bin/tini'],'Cmd':None,'User':'0',
            'Env':['SYNTHETIC_PRIVATE_NOT_FOR_EXPORT']},'RootFS':{'Type':'layers','Layers':['sha256:'+'b'*64]},
            'Os':'linux','Architecture':'amd64','History':[]}]))
        output=summaries/'IMAGE_CONFIG_SAFE.json'
        argv=['image_config_safe.py','--inspect',str(source),'--image-id',image,
              '--verified-parent-digest',producer.PARENT,'--out',str(output)]
        forbidden=AssertionError('EXTERNAL_PROCESS_OR_NETWORK_FORBIDDEN')
        with mock.patch.object(sys,'argv',argv),mock.patch('subprocess.check_output',side_effect=forbidden), \
             mock.patch('subprocess.run',side_effect=forbidden),mock.patch('subprocess.Popen',side_effect=forbidden), \
             mock.patch('socket.create_connection',side_effect=forbidden):producer.main()
        raw=output.read_bytes();report.update(producerCliOutputWritten=True,wireBytes=len(raw),
            wireSHA256=hashlib.sha256(raw).hexdigest(),lastTwoBytesHex=raw[-2:].hex(),
            syntheticPrivateSentinelExcluded=b'SYNTHETIC_PRIVATE_NOT_FOR_EXPORT' not in raw)
        # This is the newly exercised boundary: consume exact CLI file bytes.
        value=consumer.safe_evidence_bytes('IMAGE_CONFIG_SAFE.json',raw)
        assert value['status']=='CAPTURED_NOT_COMPARED'
        report['collectorReached']=True;index,payloads=consumer.collect_evidence(summaries)
        assert payloads['IMAGE_CONFIG_SAFE.json']==raw
        report['indexReached']=True
        with mock.patch.object(sys,'argv',['backup_build_evidence.py','--evidence',str(summaries),
             '--index',str(summaries/'SAFE_INDEX.json')]):consumer.main()
        assert json.loads((summaries/'SAFE_INDEX.json').read_bytes())==index
        report['status']='PASS'
except Exception as error:
    report.update(status='FAIL',errorType=type(error).__name__,error=str(error),
                  stoppedAt='FIRST_NEW_CLI_SERIALIZED_BYTES_TO_REMOTE_VALIDATOR')
    traceback.print_exc()
finally:
    (EVIDENCE/'NEW_CONNECTION_RESULT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
raise SystemExit(0 if report['status']=='PASS' else 1)
