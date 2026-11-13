"""Install the same fail-closed publication interlock in every image job."""
import json
import os
from pathlib import Path
import shutil

source = Path(__file__).resolve().parent
target = Path(os.environ['RUNNER_TEMP']) / 'world-engine-release-guard'
target.mkdir(exist_ok=False)
for path in source.iterdir():
    if path.is_file() and path.suffix in {'.py', '.json'}:
        shutil.copyfile(path, target / path.name)
evidence = Path(os.environ['RUNNER_TEMP']) / 'world-engine-release-evidence'
evidence.mkdir(exist_ok=True)
settings = {'docker': shutil.which('docker'), 'skopeo': shutil.which('skopeo'), 'evidence': str(evidence)}
assert settings['docker'], 'DOCKER_EXECUTABLE_REQUIRED'
(target / 'INSTALLATION.json').write_text(json.dumps(settings) + '\n')
binpath = target / 'bin'; binpath.mkdir()
(target / 'command.py').chmod(0o755)
for name in ('docker', 'skopeo'):
    (binpath / name).symlink_to(target / 'command.py')
with open(os.environ['GITHUB_PATH'], 'a') as stream:
    stream.write(str(binpath) + '\n')
with open(os.environ['GITHUB_ENV'], 'a') as stream:
    stream.write('WORLD_ENGINE_RELEASE_GUARD=' + str(target) + '\n')
    stream.write('WORLD_ENGINE_GUARD_EVIDENCE=' + str(evidence) + '\n')
print('COMMON_RELEASE_INTERLOCK_INSTALLED; every formal docker push requires actual-image admission')
