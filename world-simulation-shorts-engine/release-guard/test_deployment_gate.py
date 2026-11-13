"""New deployment-gate tests; configuration fixtures never touch gCube."""
import copy
import json
from pathlib import Path
import sys
import control

out = Path(sys.argv[1])
approval = json.loads((out / 'RELEASE_APPROVAL.json').read_bytes())
config = {'imageTag': approval['imageReference'], 'digest': approval['digest'], 'observedStatus': 'Stopped',
          'environmentChanges': {name: approval['digest'] for name in ('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST', 'WORLD_ENGINE_DEPLOYMENT_IMAGE_DIGEST')}}
result = control.deployment(approval, config)
cases = [{'case': 'matching_published_digest', 'result': 'PASS'}]
for field in ('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST', 'WORLD_ENGINE_DEPLOYMENT_IMAGE_DIGEST'):
    wrong = copy.deepcopy(config); wrong['environmentChanges'][field] = 'sha256:' + '0' * 64
    try:
        control.deployment(approval, wrong)
    except RuntimeError as error:
        assert str(error) == 'DEPLOYMENT_DIGEST_MISMATCH'
    else:
        raise AssertionError('WRONG_DIGEST_ACCEPTED')
    cases.append({'case': field + '_mismatch', 'result': 'EXPECTED_FAIL'})
control.write(out / 'DEPLOYMENT_GATE_TESTS.json', {'status': 'PASS', 'cases': cases, 'syntheticConfigurationOnly': True, 'gCubeChanged': False, 'GPUExecutions': 0, 'oldPassReruns': 0})
control.write(out / 'EXPECTED_DEPLOYMENT_CONFIG.json', {**config, 'configurationOnly': True, 'settingsSavePerformed': False, 'GPUStartAuthorized': False})
print(json.dumps({'status': 'PASS', 'newDeploymentCases': len(cases), 'gCubeChanged': False}))
