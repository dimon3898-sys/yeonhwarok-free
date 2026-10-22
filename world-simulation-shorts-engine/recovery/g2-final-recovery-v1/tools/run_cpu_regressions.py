"""Run the requested preserved 101 tests, then new tests; stop at first failure."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
PREFIX = 'world-simulation-shorts-engine/recovery/'

def run(reuse_preserved_report=None):
    gates = json.loads((HERE / 'reports/GATES.json').read_text())
    if not all(gates.get(k, {}).get('status') == 'PASS' for k in ['phaseA', 'phaseB']):
        raise RuntimeError('G2_FINAL_PHASE_A_B_REQUIRED')
    old = PREFIX + 'universal-source-pipeline-v2/'
    prev = PREFIX + 'g2-renderer-recovery-v1/'
    current = PREFIX + 'g2-final-recovery-v1/'
    suites = [
        ('EXISTING_35', ['python','-B','-m','unittest','discover','-s',old+'tests','-p','test_*.py','-v'],35),
        ('EXISTING_NATIVE_8', ['node',old+'tests/test_native_preparation.mjs'],8),
        ('EXISTING_CAMERA_6', ['node',old+'tests/test_camera_numerics.mjs'],6),
        ('EXISTING_GEOMETRY_3', ['node',old+'tests/test_source_geometry_contract.mjs'],3),
        ('PRIOR_RECOVERY_37', ['python','-B','-m','unittest','discover','-s',prev+'tests','-p','test_*.py','-v'],37),
        ('PRIOR_CAPTURE_8', ['node',prev+'tests/test_capture_recovery.mjs'],8),
        ('PRIOR_PLAN_4', ['node',prev+'tests/test_prepare_recovery_plan.mjs'],4),
        ('FINAL_PYTHON', ['python','-B','-m','unittest','discover','-s',current+'tests','-p','test_*.py','-v'],None),
    ]
    suites += [('FINAL_JS_'+f.stem,['node',str(f.relative_to(REPO))],None)
               for f in sorted((HERE/'tests').glob('test_*.mjs'))]
    env = {**os.environ,'PYTHONDONTWRITEBYTECODE':'1',
           'G2_GENERIC_PROBE_ROOT':'/workspace/g2-recovery-generic-probes-20261022'}
    results = []
    report = {'schema':'WORLD_ENGINE_G2_FINAL_CPU_REGRESSIONS_V1','status':'IN_PROGRESS',
              'baselineCommit':'3913ad8e90885c769cdccc91f396072d83e356f2',
              'softwareOnly':True,'nvidiaVerified':False,'visualQualityApproved':False,
              'results':results}
    first = 0
    if reuse_preserved_report is not None:
        file = Path(reuse_preserved_report).resolve()
        if not file.is_relative_to(HERE/'reports') or file.is_symlink():
            raise ValueError('G2_FINAL_RESUME_REPORT_SCOPE_INVALID')
        raw = file.read_bytes()
        previous = json.loads(raw)['results'][:7]
        for row, (name, cmd, expected) in zip(previous, suites[:7]):
            if not (row['id']==name and row['command']==cmd and row['exitCode']==0
                    and row['tests']==expected and row['skipped']==0 and row['status']=='PASS'):
                raise ValueError('G2_FINAL_PRESERVED_RESULT_NOT_PASSED')
        if len(previous)!=7 or sum(r['tests'] for r in previous)!=101:
            raise ValueError('G2_FINAL_PRESERVED_101_REQUIRED')
        results.extend(previous)
        first=7
        report['preservedActualExecutionLog']={'path':str(file.relative_to(HERE)),
            'sha256':hashlib.sha256(raw).hexdigest(),
            'reason':'All 101 preserved tests already actually passed. The later new-test machine JSON summary was not recognized by the first reporting harness. Original logs retained; only additional suites are rerun.'}
    try:
        for name,cmd,expected in suites[first:]:
            started = time.monotonic()
            p = subprocess.run(cmd,cwd=REPO,env=env,text=True,capture_output=True,timeout=240)
            output = p.stdout + '\n' + p.stderr
            match = re.search(r'Ran (\d+) tests?',output) if cmd[0]=='python' else re.search(r'(?:ℹ|#) tests (\d+)',output)
            count = int(match[1]) if match else None
            skipped_match = re.search(r'skipped(?:=| )(\d+)',output)
            skipped = int(skipped_match[1]) if skipped_match else 0
            if count is None and cmd[0]=='node':
                # The extension's dependency-free test harness emits a strict
                # machine JSON summary rather than node:test's TAP summary.
                summaries=[]
                for line in p.stdout.splitlines():
                    try: value=json.loads(line)
                    except ValueError: continue
                    if isinstance(value,dict) and {'status','tests','skipped'}<=value.keys():
                        summaries.append(value)
                if len(summaries)==1:
                    value=summaries[0]
                    if value['status']=='PASS' and type(value['tests']) is int and value['tests']>0:
                        count=value['tests'];skipped=value['skipped']
            valid = p.returncode==0 and count is not None and skipped==0 and (expected is None or count==expected)
            row = {'id':name,'command':cmd,'elapsedSeconds':round(time.monotonic()-started,3),
                   'exitCode':p.returncode,'tests':count,'expected':expected,'skipped':skipped,
                   'status':'PASS' if valid else 'FAIL','stdout':p.stdout,'stderr':p.stderr}
            results.append(row)
            print(json.dumps({k:row[k] for k in ['id','exitCode','tests','skipped','status']}),flush=True)
            if not valid:
                raise RuntimeError('G2_FINAL_CPU_REGRESSION_FAILED_'+name)
        report.update(status='PASS',preservedTests=sum(r['tests'] for r in results[:7]),
                      additionalTests=sum(r['tests'] for r in results[7:]),allSkipped=0)
        assert report['preservedTests']==101
    except BaseException as error:
        report.update(status='FAIL',failure=str(error))
        raise
    finally:
        (HERE/'reports/CPU_REGRESSION_RESULTS.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--reuse-preserved-report')
    result=run(parser.parse_args().reuse_preserved_report)
    print(json.dumps({k:result[k] for k in ['status','preservedTests','additionalTests']}))
