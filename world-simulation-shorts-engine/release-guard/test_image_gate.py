"""New gate fault injection against actual immutable image bytes; no rendering."""
import argparse
import json
from pathlib import Path
import tempfile
import control

def rejected(call, expected):
    try:
        call()
    except RuntimeError as error:
        assert str(error) == expected, (str(error), expected)
    else:
        raise AssertionError('EXPECTED_GATE_REJECTION_MISSING')

def main(image, out, repo):
    admission = control.verify(image, out, reuse=False)
    root = control.POLICY['installedRepoRoot']
    workerpath = 'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/controller/nvidia_worker.py'
    cases = [{'case': 'normal_image', 'result': 'PASS'}]
    with tempfile.TemporaryDirectory(prefix='release-mutations-') as folder:
        folder = Path(folder); folder.chmod(0o755)
        missing = folder / 'missing-worker'; missing.mkdir(mode=0o755)
        rejected(lambda: control.verify(image, out, mounts=[(str(missing), root + '/' + str(Path(workerpath).parent))]), 'REQUIRED_WORKER_MISSING')
        cases.append({'case': 'missing_worker', 'result': 'EXPECTED_FAIL', 'code': 'REQUIRED_WORKER_MISSING'})
        source = (repo / workerpath).read_text()
        start = source.index('def _read_frame_evidence(')
        end = source.index('def _validate_capture(', start)
        old = folder / 'old_worker.py'
        old.write_text((source[:start] + source[end:]).replace("frames = _read_frame_evidence(directory, receipt.get('frameEvidence'), total_frames)", "frames = directory.json('FRAME_EVIDENCE.json')")); old.chmod(0o444)
        rejected(lambda: control.verify(image, out, mounts=[(str(old), root + '/' + workerpath)]), 'BOUNDED_READER_MISSING')
        cases.append({'case': 'old_generic_reader', 'result': 'EXPECTED_FAIL', 'code': 'BOUNDED_READER_MISSING'})
        wrong = folder / 'wrong-manifest.json'; wrong.write_text('{}\n'); wrong.chmod(0o444)
        # Bind source is host-owned UID1001 on hosted runner, read-only to UID1000.
        target = root + '/world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json'
        rejected(lambda: control.verify(image, out, mounts=[(str(wrong), target)]), 'SOURCE_MANIFEST_MISMATCH')
        cases.append({'case': 'wrong_source_manifest', 'result': 'EXPECTED_FAIL', 'code': 'SOURCE_MANIFEST_MISMATCH'})
    control.write(Path(out) / 'NEW_GATE_CASES.json', {'status': 'PASS', 'cases': cases, 'normalAdmission': admission,
                 'GPUExecutions': 0, 'rendererExecutions': 0, 'oldPassReruns': 0})

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--image', required=True); p.add_argument('--evidence', type=Path, required=True); p.add_argument('--repo', type=Path, required=True)
    a = p.parse_args(); main(a.image, a.evidence, a.repo)
