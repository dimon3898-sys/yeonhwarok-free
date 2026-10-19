#!/usr/bin/env python3
"""Reproducible focused CPU checks; no Docker, GPU, video or external API."""
from pathlib import Path
import hashlib,json,os,re,subprocess,sys,time,tempfile,argparse
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

def run(only=None):
 rows=[]
 previous={}
 if only and (HERE/'reports/TEST_RESULTS.json').exists():
  previous={r['test']:r for r in json.loads((HERE/'reports/TEST_RESULTS.json').read_text())['suites']}
 temporary=tempfile.TemporaryDirectory(prefix='world-engine-unified-cpu-',dir=ROOT)
 commands=[('python',name,[sys.executable,'-B','-m','unittest','discover','-s',str(HERE/'tests'),'-p',name])
  for name in ['test_contract_v2.py','test_data_coverage.py','test_feature_decisions.py','test_quality_gate.py',
               'test_studio_entry.py','test_runtime_bridge.py','test_real_studio_path.py','test_execution_handoff.py']]
 commands += [('node',name,['node','--test','--test-reporter=tap',str(HERE/'tests'/name)]) for name in ['test_presentation.mjs','test_capture_binding.mjs']]
 for kind,name,command in commands:
  if only and name not in only:
   old=previous.get(name)
   if not old or old['status']!='PASS' or old['testSourceSHA256']!=hashlib.sha256((HERE/'tests'/name).read_bytes()).hexdigest():
    raise RuntimeError('UNVERIFIED_PREVIOUS_TEST_RESULT')
   rows.append({**old,'reusedUnchangedTestResult':True});continue
  at=time.monotonic();r=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
   timeout=180,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','TMPDIR':temporary.name},check=False)
  output=r.stdout.decode('utf-8','replace');match=re.search(r'Ran (\d+) tests?',output) if kind=='python' else re.search(r'# tests (\d+)',output)
  skipped=re.search(r'skipped=(\d+)',output) if kind=='python' else re.search(r'# skipped (\d+)',output)
  failed=re.search(r'failures=(\d+)',output) if kind=='python' else re.search(r'# fail (\d+)',output)
  row={'test':name,'exitCode':r.returncode,'executed':int(match.group(1)) if match else 0,
       'skipped':int(skipped.group(1)) if skipped else 0,'status':'PASS' if r.returncode==0 and match else 'FAIL',
       'elapsedSeconds':round(time.monotonic()-at,3),'outputSHA256':hashlib.sha256(r.stdout).hexdigest(),
       'testSourceSHA256':hashlib.sha256((HERE/'tests'/name).read_bytes()).hexdigest()}
  rows.append(row);print(json.dumps(row),flush=True)
  if row['status']=='FAIL':print(output[-8000:],file=sys.stderr)
 report={'schema':'WORLD_ENGINE_UNIFIED_INTEGRATION_CPU_TESTS_V1','status':'PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',
  'executed':sum(r['executed'] for r in rows),'skipped':sum(r['skipped'] for r in rows),'suites':rows,
  'scope':'Pure CPU contracts/evaluators, actual frozen backend, real localhost HTTP auth; explicit fake factories/backends used only in labelled tests.',
  'gpuExecuted':False,'swiftShaderDrawExecuted':False,'videoRendered':False,'paidOperations':0,
  'existingWholeTestSuitesRepeated':False,'outputVisualQuality':'NOT_VERIFIED'}
 temporary.cleanup()
 (HERE/'reports/TEST_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 return 0 if report['status']=='PASS' else 1
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--only',action='append');args=parser.parse_args();raise SystemExit(run(args.only))
