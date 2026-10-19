"""Original secure root bootstrap; substitute only this isolated Studio entry."""
from pathlib import Path
import importlib.util
import os
import subprocess
import sys
HERE = Path(__file__).resolve().parent
PROXY = Path('/opt/world-engine-studio-https-proxy-fix') if HERE.is_relative_to('/opt') else HERE.parent / 'studio-https-proxy-fix-v1'
sys.path.insert(0, str(PROXY))
spec = importlib.util.spec_from_file_location('_completion_proxy_bootstrap_instance', PROXY / 'proxy_bootstrap.py')
parent = importlib.util.module_from_spec(spec); spec.loader.exec_module(parent)


def spawn(command, **kwargs):
    expected = ['/usr/bin/python3', '-B', str(parent.parent.root / 'https_server.py')]
    if command[:3] == expected:
        command = [*command[:2], str(HERE / 'studio_entry.py'), *command[3:]]
    return subprocess.Popen(command, **kwargs)


def main(argv=None):
    if os.geteuid() != 0:
        raise RuntimeError('STUDIO_ROOT_BOOTSTRAP_REQUIRED')
    spec = importlib.util.spec_from_file_location('_completion_boot_source', HERE / 'package_manifest.py')
    manifest = importlib.util.module_from_spec(spec); spec.loader.exec_module(manifest); manifest.verify_sources()
    parent.parent.manifest.verify_sources()
    config = parent.parent.bootstrap.prepare_configuration(os.environ)
    proof_spec = importlib.util.spec_from_file_location('_completion_boot_image_proof', HERE / 'image_proof.py')
    proof = importlib.util.module_from_spec(proof_spec); proof_spec.loader.exec_module(proof)
    proof.install(os.environ.get(proof.ENV), config, manifest.verify_sources()['manifestSHA256'],
                  parent.parent.bootstrap.original)
    environment = parent.parent.bootstrap.child_environment(os.environ, studio=True, config=config)
    environment.pop(proof.ENV, None)
    os.environ.pop(proof.ENV, None)
    for name in parent.parent.bootstrap.original.SECRET_ENV:
        os.environ.pop(name, None)
    return parent.parent.bootstrap.supervise(config, environment,
        sys.argv[1:] if argv is None else argv, spawn=spawn)


if __name__ == '__main__':
    raise SystemExit(main())
