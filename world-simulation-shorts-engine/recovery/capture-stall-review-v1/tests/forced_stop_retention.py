"""New end-to-end recorder -> storage helper -> SIGKILL -> readback contract.

Runs as UID1000, with local independent directories. No browser, GPU or encode.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
HANDOFF = HERE.parent.parent / 'codex-to-gcube-handoff-v1'
sys.path.insert(0, str(HANDOFF / 'controller'))
from capture_diagnostics_safe import ActiveCheckpointMirror

def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()

def run(output, node):
    assert os.getuid() == 1000, 'UID1000_REQUIRED'
    output.mkdir(mode=0o700)
    result = {'schema': 'WORLD_ENGINE_FORCED_STOP_RETENTION_V1', 'status': 'RUNNING',
        'uid': os.getuid(), 'gpuExecutions': 0, 'oldPassReruns': 0, 'cases': [],
        'scope': 'LOCAL_UID1000_RECORDER_MIRROR_SIGKILL_READBACK_NOT_GCUBE_MOUNT'}
    with tempfile.TemporaryDirectory(prefix='we-forced-stop-') as temporary:
        root = Path(temporary)
        script = root / 'record.mjs'
        script.write_text("""
import {createRecorder,classifyException} from RECORDER_URL;
const [outputRoot,runId,operation,mode]=process.argv.slice(2);
const recorder=createRecorder({outputRoot,runId,durationSeconds:10,totalFrames:300});
await recorder.event({operationId:'PNG',phase:'END',frameIndex:0});
await recorder.completeFrame(1);
await recorder.event({operationId:operation,phase:'START',frameIndex:1});
if(mode==='failure')await recorder.fail(classifyException(new Error('UP2_FRAME_GL_ERROR'),operation,'CAPTURE_ADAPTER',1,recorder.snapshot()));
setInterval(()=>{},1000);
""".replace('RECORDER_URL', json.dumps((HANDOFF / 'backend/capture_operation_diagnostics.mjs').as_uri())))
        for index, (operation, mode) in enumerate([
            ('DRAW', 'stall'), ('READBACK', 'stall'), ('PNG', 'stall'),
            ('ENCODER_DRAIN', 'stall'), ('PROGRESS', 'stall'), ('READBACK', 'failure')]):
            job = root / 'private' / 'handoff-gpu-jobs' / ('studio-' + f'{index + 1:032x}')
            capture = job / 'capture'
            capture.mkdir(parents=True, mode=0o700)
            job.chmod(0o700)
            exports = root / ('exports-' + str(index))
            exports.mkdir(mode=0o700)
            child = subprocess.Popen([node, str(script), str(capture), job.name, operation, mode],
                env={}, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            mirror = ActiveCheckpointMirror(job, exports)
            target = exports / ('capture-checkpoint-' + job.name) / 'CAPTURE_CHECKPOINT.json'
            try:
                limit = time.monotonic() + 5
                local = capture / 'CAPTURE_OPERATION_CHECKPOINT.json'
                while time.monotonic() < limit:
                    assert child.poll() is None, child.stderr.read().decode()
                    if local.exists():
                        value = json.loads(local.read_bytes())
                        if value['operationId'] == operation and value['operationPhase'] == ('FAIL' if mode == 'failure' else 'START'):
                            break
                    time.sleep(.01)
                else:
                    raise AssertionError('RECORDER_BOUNDARY_MISSING')
                while time.monotonic() < limit:
                    mirror.tick()
                    if target.exists() and mirror.status == 'ACTIVE_CHECKPOINT_MOUNTED_WRITE_CONFIRMED':
                        break
                    time.sleep(.01)
                else:
                    raise AssertionError('MIRROR_UNCONFIRMED:' + mirror.status)
                assert child.poll() is None
                child.kill()
                child.wait(timeout=1)
                assert child.returncode == -9
                mirror.close()
                shutil.rmtree(job)
                wire = target.read_bytes()
                envelope = json.loads(wire)
                assert hashlib.sha256(canonical(envelope['snapshot'])).hexdigest() == envelope['sha256']
                operations = envelope['snapshot']['operations']
                assert operations['operationId'] == operation and operations['frameIndex'] == 1
                assert operations['renderedFrames'] == 1
                if mode == 'stall':
                    assert operations['firstFailure'] is None
                else:
                    assert operations['firstFailure']['errorCode'] == 'UP2_FRAME_GL_ERROR'
                    assert operations['firstFailure']['frameIndex'] == 1
                assert envelope['snapshot']['renderRecoveryPass'] is False
                assert target.stat().st_uid == 1000 and target.stat().st_mode & 0o777 == 0o600
                name = f'{operation}_{mode}.json'
                (output / name).write_bytes(wire)
                result['cases'].append({'operation': operation, 'mode': mode, 'status': 'PASS',
                    'childExit': -9, 'privateDirectoryRemoved': True, 'retainedSHA256': hashlib.sha256(wire).hexdigest(),
                    'snapshotSHA256': envelope['sha256'], 'bytes': len(wire), 'file': name})
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=1)
                child.stderr.close()
                mirror.close()
    result['status'] = 'LOCAL_FORCED_STOP_RETENTION_PASS'
    (output / 'RESULT.json').write_bytes(canonical(result))
    print(json.dumps(result))

if __name__ == '__main__':
    run(Path(sys.argv[1]).resolve(), sys.argv[2])
