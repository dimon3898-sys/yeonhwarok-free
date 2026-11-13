#!/usr/bin/env python3
"""Runner-local publication interlock. Delegate read/build calls unchanged."""
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import control

def main():
    name = Path(sys.argv[0]).name
    settings = json.loads((HERE / 'INSTALLATION.json').read_bytes())
    real = settings.get(name) or '/usr/bin/' + name
    args = sys.argv[1:]
    evidence = Path(settings['evidence'])
    if name == 'skopeo':
        if 'copy' in args and any(s.startswith('docker://') for s in args[-1:]):
            raise RuntimeError('OCI_DIRECT_PUBLISH_BLOCKED_USE_COMMON_DOCKER_GATE')
        return subprocess.call([real, *args])
    # Docker global switches precede the subcommand. Remote daemon publication
    # is deliberately unsupported; the probe must inspect the pushed daemon.
    rest = list(args)
    while rest and rest[0].startswith('-'):
        flag = rest.pop(0)
        if flag in ('--host', '-H', '--config', '--context'):
            value = rest.pop(0)
        elif '=' in flag:
            flag, value = flag.split('=', 1)
        else:
            continue
        if flag in ('--context',) or flag in ('--host', '-H') and value != 'unix:///var/run/docker.sock':
            raise RuntimeError('REMOTE_DAEMON_PUBLISH_ROUTE_NOT_ADMITTED')
    direct_output = any('type=registry' in value or 'push=true' in value for value in rest)
    if rest[:2] == ['manifest', 'push'] or rest[:3] == ['buildx', 'imagetools', 'create'] or '--push' in rest or direct_output:
        raise RuntimeError('DIRECT_BUILD_PUBLISH_BLOCKED_LOAD_THEN_GATED_PUSH')
    push = rest[:1] == ['push'] or rest[:2] == ['image', 'push']
    if not push:
        return subprocess.call([real, *args])
    control.need(os.environ.get('DOCKER_HOST', 'unix:///var/run/docker.sock') == 'unix:///var/run/docker.sock', 'REMOTE_DOCKER_HOST_NOT_ADMITTED')
    image = rest[-1]
    control.need(image.startswith(control.POLICY['imageRepository'] + ':') and not any(x in rest for x in ('--all-tags', '-a')), 'EXACT_FORMAL_IMAGE_TAG_REQUIRED')
    admitted = control.verify(image, evidence, real)
    control.need(control.inspect_image(image, real)['Id'] == admitted['imageId'], 'IMAGE_CHANGED_BEFORE_PUSH')
    result = subprocess.call([real, *args])
    if result:
        return result
    control.promote(image, evidence, real)
    return 0

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        code = str(error) if isinstance(error, RuntimeError) else 'PUBLICATION_INTERLOCK_' + type(error).__name__.upper()
        try:
            settings = json.loads((HERE / 'INSTALLATION.json').read_bytes())
            control.write(Path(settings['evidence']) / 'PUBLICATION_BLOCKED.json', {'status': 'FAIL', 'code': code, 'deploymentApproved': False, 'GPUExecutions': 0})
        finally:
            print(code, file=sys.stderr)
        raise SystemExit(1)
