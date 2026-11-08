"""Run the previously blocked official one-frame probe on a normal CPU host.

The private bundle supplies the unchanged, pinned renderer and source data.
No movie, NVIDIA assertion bypass, or new scene renderer is implemented here.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import urllib.request
import zipfile
from private_transfer import download_exact, token


def restore(archive):
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read('TRANSFER_MANIFEST.json'))
        rows = manifest['files']
        names = [r['name'] for r in rows]
        assert len(names) == len(set(names))
        assert set(z.namelist()) == set(names) | {'TRANSFER_MANIFEST.json'}
        assert sum(r['bytes'] for r in rows) < 2 * 1024**3
        for row in rows:
            name = PurePosixPath(row['name'])
            assert not name.is_absolute() and '..' not in name.parts
            assert name.parts[:2] == ('workspace', 'shared')
            info = z.getinfo(str(name))
            assert info.file_size == row['bytes']
            assert not stat.S_ISLNK(info.external_attr >> 16)
            raw = z.read(info)
            assert hashlib.sha256(raw).hexdigest() == row['sha256']
            target = Path('/') / str(name)
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with target.open('xb') as output:
                output.write(raw)
            target.chmod(0o600)
    probes = [Path('/') / PurePosixPath(r['name']).parent for r in rows
              if PurePosixPath(r['name']).name == 'PROBE_CONFIG.json']
    assert len(probes) == 1
    return len(rows), probes[0]


def upload_result(access, filename, remote_parent):
    raw = filename.read_bytes()
    assert len(raw) < 140 * 1024**2
    request = urllib.request.Request('https://content.dropboxapi.com/2/files/upload', data=raw,
        headers={'Authorization': 'Bearer ' + access, 'Content-Type': 'application/octet-stream',
            'Dropbox-API-Arg': json.dumps({'path': remote_parent + '/' + filename.name,
                'mode': 'add', 'autorename': False, 'mute': True, 'strict_conflict': True})})
    with urllib.request.urlopen(request, timeout=180) as response:
        receipt = json.load(response)
    assert receipt['size'] == len(raw)
    return {'file': filename.name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def main():
    temp = Path(os.environ['RUNNER_TEMP'])
    archive = temp / 'private-input.zip'
    access = token()
    selected = {}
    transfer = download_exact(access, sys.argv[1], sys.argv[2], archive, selected)
    entries, probe = restore(archive)
    capture_source = probe / 'closure/world-simulation-shorts-engine/recovery/universal-presentation-v2/capture_presentation.mjs'
    before = capture_source.read_bytes()
    assert hashlib.sha256(before).hexdigest() == '39e698d181346e57852640a7cf62282629af0500290f982cb3c59cb122b7624c'
    old = b"executablePath:'/usr/bin/chromium'"
    assert before.count(old) == 1
    # Use the already verified normal Chrome installation; retain sandbox and all flags.
    after = before.replace(old, b"executablePath:'/usr/bin/google-chrome'")
    capture_source.write_bytes(after)
    host_adapter = {'scope': 'BROWSER_EXECUTABLE_LOCATION_ONLY', 'beforeSHA256': hashlib.sha256(before).hexdigest(),
                    'afterSHA256': hashlib.sha256(after).hexdigest(), 'sandboxAndFlagsUnchanged': True}
    supervisor_file = probe / 'supervise_probe.py'
    supervisor_before = supervisor_file.read_bytes()
    assert hashlib.sha256(supervisor_before).hexdigest() == 'f35ccd0c6515ffdda8de69b1f530612c9d284887e198684a70b27141f6b0fa22'
    memory = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    available = int(memory['MemAvailable'].strip().split()[0]) * 1024
    assert available >= 6 * 1024**3, 'NORMAL_HOST_MEMORY_UNAVAILABLE'
    limit_old = b'memory_exceeded=total>2*1024**3'
    receipt_old = b"'aggregateRSSMonitorBytes':2*1024**3"
    assert supervisor_before.count(limit_old) == 1 and supervisor_before.count(receipt_old) == 1
    supervisor_after = supervisor_before.replace(limit_old, b'memory_exceeded=total>4*1024**3').replace(receipt_old, b"'aggregateRSSMonitorBytes':4*1024**3")
    supervisor_file.write_bytes(supervisor_after)
    host_adapter['supervisor'] = {'reason': 'Run 42523576309 owned RSS 2200928256 exceeded old 2147483648 byte CPU probe budget', 'beforeSHA256': hashlib.sha256(supervisor_before).hexdigest(), 'afterSHA256': hashlib.sha256(supervisor_after).hexdigest(), 'oldAggregateBytes': 2*1024**3, 'aggregateBytes': 4*1024**3, 'hostAvailableBytes': available, 'perProcessAndTimeLimitsUnchanged': True}
    child_env = {k: v for k, v in os.environ.items() if 'TOKEN' not in k and 'SECRET' not in k and 'APP_KEY' not in k and 'BACKUP_KEY' not in k}
    setup = subprocess.run(['node', str(Path(__file__).with_name('prepare_frame_cases.mjs')), str(probe), str(probe.parent / 'world_engine_destination_rehearsal')], env=child_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=240, check=False)
    if setup.returncode:
        (temp / 'private-case-preparation.log').write_bytes(setup.stdout + setup.stderr)
        raise RuntimeError('EXISTING_FRAME_CASE_PREPARATION_FAILED')
    cases = json.loads((probe / 'FRAME_CASES.json').read_text())
    assert len(cases) == 4
    report = {'schema': 'WORLD_ENGINE_FOUR_SCENE_CPU_SCREEN_V1', 'sourceCommit': '5d749200684406ad66a6a381e04d5a31a3ef7b05',
        'inputTransfer': transfer, 'transferredEntries': entries, 'hostAdapter': host_adapter, 'runId': os.environ['GITHUB_RUN_ID'],
        'renderedFrames': 0, 'cases': [], 'oldTestsRerun': False, 'gpuExecuted': False,
        'visualQualityApproved': False, 'preservedOneFrameRun': 42524272844}
    archive_out = temp / ('KW20_CPU_SCREEN_RESULT_' + os.environ['GITHUB_RUN_ID'] + '.zip')
    with zipfile.ZipFile(archive_out, 'x', zipfile.ZIP_DEFLATED) as z:
        for case in cases:
            config = case['config']
            assert config['probeFrames'] == [0, 75, 149]
            (probe / 'PROBE_CONFIG.json').write_text(json.dumps(config, indent=2) + '\n')
            with (temp / 'private-supervision.log').open('wb') as log:
                run = subprocess.run([sys.executable, str(probe / 'supervise_probe.py')], env=child_env,
                    stdout=log, stderr=subprocess.STDOUT, timeout=220, check=False)
            out = Path(config['outputRoot'])
            capture = json.loads((out / 'CAPTURE_RECEIPT.json').read_text()) if (out / 'CAPTURE_RECEIPT.json').exists() else {}
            result = {'name': case['name'], 'globalOffset': case['globalOffset'], 'probeFrames': config['probeFrames'],
                'renderedFrames': capture.get('renderedFrames', 0), 'captureStatus': capture.get('status', 'NO_CAPTURE_RECEIPT')}
            report['cases'].append(result)
            report['renderedFrames'] += result['renderedFrames']
            for file in sorted(out.glob('*')):
                if file.is_file() and file.name not in {'REQUEST.json', 'RUNTIME.json'}:
                    z.write(file, case['name'] + '/' + file.name)
            for name in ['SUPERVISION_RECEIPT.json', 'probe_stdout.log', 'probe_stderr.log']:
                if (probe / name).is_file(): z.write(probe / name, case['name'] + '/' + name)
            z.write(temp / 'private-supervision.log', case['name'] + '/private-supervision.log')
            if result['captureStatus'] != 'ACTUAL_DRAW_PROBE_PASS_NOT_STUDIO_VIDEO' or result['renderedFrames'] != 3:
                break
        report['movieCreated'] = bool(list(probe.rglob('*.mp4')))
        z.writestr('CPU_SCREEN_RESULT.json', json.dumps(report, indent=2))
    report['privateResult'] = upload_result(access, archive_out, str(PurePosixPath(selected['path_lower']).parent))
    print(json.dumps(report), flush=True)
    return 0 if report['renderedFrames'] == 12 and len(report['cases']) == 4 and not report['movieCreated'] else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(json.dumps({'status': 'CPU_SCREEN_EXECUTION_BLOCKED', 'errorType': type(error).__name__, 'privateDetailsWithheld': True}), flush=True)
        sys.exit(1)
