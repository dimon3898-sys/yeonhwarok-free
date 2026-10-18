"""One fixed working-directory correction for the frozen CPU proof invocation."""
from __future__ import annotations

IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:6d2e87fc8fb7f10edc2ebb7f77b5d666e329904b9c37f7f060b289f943bdd9d0'
DEST = '/opt/world-engine-studio-dropbox-offline'
PYTHON = '/opt/world-engine-studio-durability-venv/bin/python'
PROBE = '/tmp/world-engine-offline-external-proof'


def bootstrap_code():
    return ('import os,runpy,sys;os.mkdir(' + repr(PROBE) + ',0o700);'
            'sys.argv=[' + repr(DEST + '/offline_entry.py')
            + ',"cli","external-check","--private-work-root",' + repr(PROBE) + '];'
            'runpy.run_path(' + repr(DEST + '/offline_entry.py') + ',run_name="__main__")')


def adapt(command):
    if not isinstance(command, (list, tuple)) or list(command[:2]) != ['docker', 'run'] or IMAGE not in command:
        return command
    result = list(command)
    index = result.index(IMAGE)
    tail = result[index + 1:]
    if tail != ['-B', '-c', bootstrap_code()]:
        if any(isinstance(part, str) and PROBE in part for part in tail):
            raise RuntimeError('STARTUP_FROZEN_BOOTSTRAP_CHANGED')
        return command
    required = {'--user=1000:1000', '--read-only', '--cap-drop=ALL',
                '--security-opt=no-new-privileges', '--restart=no', '--entrypoint=' + PYTHON}
    if (result.count(IMAGE) != 1 or not required <= set(result[:index])
            or any(part == '-w' or part.startswith(('--workdir', '--gpus', '--privileged', '--device'))
                   for part in result[:index])
            or any(part in {'-u', '--user', '--entrypoint', '--network', '--cap-add', '--read-only=false'}
                   or part.startswith(('--network=', '--cap-add=')) for part in result[:index])
            or [part for part in result[:index] if part.startswith('--user=')] != ['--user=1000:1000']
            or [part for part in result[:index] if part.startswith('--entrypoint=')] != ['--entrypoint=' + PYTHON]):
        raise RuntimeError('STARTUP_FROZEN_SECURITY_OPTIONS_REQUIRED')
    return result[:index] + ['--workdir=' + DEST] + result[index:]
