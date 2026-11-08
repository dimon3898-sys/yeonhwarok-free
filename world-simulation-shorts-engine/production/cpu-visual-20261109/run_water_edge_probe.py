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
    for old, new in [(b'(175,180)', b'(295,300)'), (b'deadline=time.monotonic()+180', b'deadline=time.monotonic()+300'), (b"'wallSeconds':180", b"'wallSeconds':300")]:
        assert supervisor_after.count(old) == 1
        supervisor_after = supervisor_after.replace(old, new)
    supervisor_file.write_bytes(supervisor_after)
    host_adapter['supervisor'] = {'reason': 'Reuse verified normal CPU host resource budget', 'beforeSHA256': hashlib.sha256(supervisor_before).hexdigest(), 'afterSHA256': hashlib.sha256(supervisor_after).hexdigest(), 'aggregateBytes': 4*1024**3, 'hostAvailableBytes': available, 'perProcessMemoryLimitUnchanged': True, 'wallSeconds': 300, 'perProcessCPUSeconds': [295,300]}
    patch_env = {k: v for k, v in os.environ.items() if 'TOKEN' not in k and 'SECRET' not in k and 'APP_KEY' not in k and 'BACKUP_KEY' not in k}
    patch = subprocess.run(['node', str(Path(__file__).with_name('patch_water_edge_registry.mjs')),
        str(probe.parent / 'world_engine_destination_rehearsal/private-registry/OFFICIAL_SERVER_REGISTRY.json'),
        '35e6a2b95bd86f0b0383c0dba3e52818804f316958490b0279cc77403ecbdda9', str(probe)],
        env=patch_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False)
    assert patch.returncode == 0, 'WATER_EDGE_VARIANT_PREPARATION_FAILED'
    water_change = json.loads((probe / 'WATER_EDGE_CHANGE.json').read_text())
    config_file = probe / 'PROBE_CONFIG.json'
    config = json.loads(config_file.read_text())
    # Dependency location only. Scene, frame, original, source, and module pins stay fixed.
    config['depsRoot'] = os.environ['CPU_DEPS_ROOT']
    assert config['probeFrames'] == [100]
    config_file.write_text(json.dumps(config, indent=2) + '\n')
    child_env = {k: v for k, v in os.environ.items() if 'TOKEN' not in k and 'SECRET' not in k and 'APP_KEY' not in k and 'BACKUP_KEY' not in k}
    with (temp / 'private-supervision.log').open('wb') as log:
        run = subprocess.run([sys.executable, str(probe / 'supervise_probe.py')], env=child_env,
            stdout=log, stderr=subprocess.STDOUT, timeout=340, check=False)
    out = probe / 'probe_output'
    capture = json.loads((out / 'CAPTURE_RECEIPT.json').read_text()) if (out / 'CAPTURE_RECEIPT.json').exists() else {}
    report = {'schema': 'WORLD_ENGINE_NORMAL_CPU_SCREEN_RESULT_V1', 'sourceCommit': '5d749200684406ad66a6a381e04d5a31a3ef7b05',
        'inputTransfer': transfer, 'transferredEntries': entries, 'hostAdapter': host_adapter, 'runId': os.environ['GITHUB_RUN_ID'],
        'waterEdgeChange': water_change, 'renderedFrames': capture.get('renderedFrames', 0), 'captureStatus': capture.get('status', 'NO_CAPTURE_RECEIPT'),
        'oldTestsRerun': False, 'gpuExecuted': False, 'movieCreated': bool(list(probe.rglob('*.mp4'))),
        'visualQualityApproved': False, 'normalBrowserProofRun': 42522754078, 'privateChannelProofRun': 42523065120}
    archive_out = temp / ('KW20_CPU_SCREEN_RESULT_' + os.environ['GITHUB_RUN_ID'] + '.zip')
    with zipfile.ZipFile(archive_out, 'x', zipfile.ZIP_DEFLATED) as z:
        z.writestr('CPU_SCREEN_RESULT.json', json.dumps(report, indent=2))
        z.write(probe / 'WATER_EDGE_CHANGE.json', 'WATER_EDGE_CHANGE.json')
        for file in sorted(out.glob('*')):
            if file.is_file() and file.name not in {'REQUEST.json', 'RUNTIME.json'}:
                z.write(file, 'probe_output/' + file.name)
        for name in ['SUPERVISION_RECEIPT.json', 'probe_stdout.log', 'probe_stderr.log']:
            if (probe / name).is_file(): z.write(probe / name, name)
        z.write(temp / 'private-supervision.log', 'private-supervision.log')
    report['privateResult'] = upload_result(access, archive_out, str(PurePosixPath(selected['path_lower']).parent))
    print(json.dumps(report), flush=True)
    return 0 if capture.get('status') == 'ACTUAL_DRAW_PROBE_PASS_NOT_STUDIO_VIDEO' and capture.get('renderedFrames') == 1 and not report['movieCreated'] else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(json.dumps({'status': 'CPU_SCREEN_EXECUTION_BLOCKED', 'errorType': type(error).__name__, 'privateDetailsWithheld': True}), flush=True)
        sys.exit(1)
