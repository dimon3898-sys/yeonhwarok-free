"""Repeatable start for a private, persistent Codespaces/current-cloud workspace.

No hosting account is created; no billing or public-port configuration is changed.
The access code is created locally and is never printed.
"""
from __future__ import annotations
import argparse, hashlib, json, os, socket, subprocess, sys, time
from pathlib import Path
from urllib.request import urlopen

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
sys.path.insert(0, str(APP))
from deployment.security import ensure_access_file

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=7860)
    parser.add_argument('--internal-port', type=int, default=7861)
    parser.add_argument('--state-root', type=Path, default=APP/'deployment/runtime/mobile')
    args = parser.parse_args()
    state = args.state_root.resolve()
    if not state.is_relative_to(APP/'deployment/runtime'):
        raise SystemExit('State must be inside the new deployment/runtime directory.')
    state.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((APP/'data/production_rhythm_promotion_v001.json').read_text())
    mismatches = [name for name,digest in manifest['source_manifest'].items()
                  if hashlib.sha256((APP/name).read_bytes()).hexdigest()!=digest]
    if mismatches:
        raise SystemExit('Certified source mismatch: '+', '.join(mismatches))
    for exe in ['ffmpeg','ffprobe','node','chromium']:
        import shutil
        if not shutil.which(exe):
            raise SystemExit('Missing runtime dependency: '+exe)
    modules = REPO/'cinematic-world-map/node_modules'
    image_modules = Path('/opt/world-engine/cinematic-world-map/node_modules')
    if not modules.exists() and image_modules.is_dir():
        modules.symlink_to(image_modules, target_is_directory=True)
    if not (modules/'playwright').is_dir():
        raise SystemExit('Run frozen npm ci in cinematic-world-map before startup.')
    from engine.production import production_default_status
    from engine.assets import validate_assets
    import numpy, scipy, PIL, jsonschema
    if not production_default_status().get('active'):
        raise SystemExit('Production certificate/assets are incomplete; preserving the approved default.')
    if not validate_assets().get('passed'):
        raise SystemExit('Required preserved assets failed validation.')
    access = state/'owner-code.txt'
    ensure_access_file(access)
    pidfile = state/'server.pid'
    if pidfile.exists():
        try:
            pid = int(pidfile.read_text().strip())
            command = Path(f'/proc/{pid}/cmdline').read_bytes()
            if b'deployment.mobile_server' in command and str(state).encode() in command:
                with urlopen(f'http://127.0.0.1:{args.port}/', timeout=3) as response:
                    if response.status==200:
                        print(json.dumps({'status':'already_running','port':args.port,'access_file':str(access)}))
                        return 0
                raise SystemExit('Existing mobile server needs inspection; not starting a duplicate.')
        except (FileNotFoundError, ValueError, ProcessLookupError):
            pass
    for port in [args.port,args.internal_port]:
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1',port))==0:
                raise SystemExit(f'Port {port} belongs to an existing service; choose an unused pair.')
    command = [sys.executable,'-m','deployment.mobile_server','--state-root',str(state),
               '--access-file',str(access),'--host','0.0.0.0','--port',str(args.port),
               '--internal-port',str(args.internal_port)]
    name = os.environ.get('CODESPACE_NAME')
    domain = os.environ.get('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN')
    if name and domain:
        command += ['--public-origin',f'https://{name}-{args.port}.{domain}']
    logpath = state/'server.log'
    fd = os.open(logpath,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
    with os.fdopen(fd,'ab',buffering=0) as log:
        process = subprocess.Popen(command,cwd=APP,stdout=log,stderr=log,
                                   stdin=subprocess.DEVNULL,start_new_session=True)
    pidfile.write_text(str(process.pid)+'\n');pidfile.chmod(0o600)
    for _ in range(60):
        if process.poll() is not None:
            raise SystemExit('Server exited. Inspect the private runtime server.log.')
        try:
            with urlopen(f'http://127.0.0.1:{args.port}/',timeout=1) as response:
                if response.status==200:
                    print(json.dumps({'status':'started','port':args.port,'pid':process.pid,
                                      'access_file':str(access),'source_hashes_verified':len(manifest['source_manifest'])}))
                    return 0
        except OSError:
            time.sleep(.5)
    raise SystemExit('Server readiness timed out. Existing state was preserved.')

if __name__=='__main__':
    raise SystemExit(main())
