from pathlib import Path
import sys,importlib.util,json
root=Path(sys.argv[2]).resolve()
folder=Path(sys.argv[1]).resolve()/'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/controller'
sys.path.insert(0,str(folder));import nvidia_backend as backend
keys=['WORLD_ENGINE_OFFICIAL_CANDIDATE_REGISTRY_FILE','WORLD_ENGINE_OFFICIAL_CANDIDATE_REGISTRY_SHA256']
sample={keys[0]:'/test-only/registry.json',keys[1]:'a'*64,'GITHUB_TOKEN':'TEST_SENTINEL','OWNER_CODE':'TEST_SENTINEL','DEBUG':'TEST_SENTINEL','PATH':'TEST_PATH'}
env=backend._runtime_environment(sample);assert all(env[k]==sample[k] for k in keys)
assert not any(k in env for k in ['GITHUB_TOKEN','OWNER_CODE','DEBUG'])
assert env['PATH']=='TEST_PATH'
result={'schema':'WORLD_ENGINE_NATIVE_ENVIRONMENT_TEST_V1','status':'PASS','newChecks':3,'checks':['SERVER_REGISTRY_PAIR_FORWARDED','OWNER_AND_GITHUB_SECRETS_EXCLUDED','EXISTING_RUNTIME_PATH_RETAINED'],'workerStarted':False,'gpuExecuted':False}
(root/'NATIVE_ENVIRONMENT_RESULT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
