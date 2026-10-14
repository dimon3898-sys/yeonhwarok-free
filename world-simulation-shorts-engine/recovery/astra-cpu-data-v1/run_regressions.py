"""Focused existing CPU regressions, once per final CPU checkpoint."""
import json
import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
ENGINE=ROOT.parents[1]
CASES=[('flat_terrain_cache',['/usr/bin/python3','-B','-m','unittest','discover','-s','tests','-p','test_flat_terrain_cache.py','-v']),
       ('production_visual_cache',['/usr/bin/python3','-B','-m','unittest','discover','-s','tests','-p','test_production_visual_cache.py','-v']),
       ('frontier_cpu',['node','recovery/moving-frontier-glow-fix-v1/test_control_frontier_glow.mjs'])]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reparse-recorded',action='store_true',
                        help='Correct result formatting from unchanged saved logs and exit codes; do not rerun tests')
    args=parser.parse_args()
    evidence=ROOT/'evidence'
    evidence.mkdir(exist_ok=True)
    previous=json.loads((evidence/'EXISTING_REGRESSIONS.json').read_bytes()) if args.reparse_recorded else None
    records=[]
    for name,command in CASES:
        try:
            if previous is not None:
                old=next(item for item in previous['cases'] if item['name']==name and item['command']==command)
                log=(evidence/(name+'.log')).read_text()
                exit_code=old['exitCode']
            else:
                result=subprocess.run(command,cwd=ENGINE,capture_output=True,text=True,timeout=60)
                log=result.stdout+result.stderr
                exit_code=result.returncode
            match=re.search(r'Ran (\d+) tests?',log) or re.search(r'(?:#|ℹ) tests (\d+)',log)
            count=int(match.group(1)) if match else 0
            record={'name':name,'command':command,'exitCode':exit_code,'testsRun':count,
                    'status':'PASS' if exit_code==0 and count>0 else 'FAIL'}
        except subprocess.TimeoutExpired:
            log='BLOCKED: command exceeded 60-second deadline\n'
            record={'name':name,'command':command,'testsRun':0,'status':'BLOCKED','exitCode':None}
        if previous is None:(evidence/(name+'.log')).write_text(log)
        records.append(record)
    report={'schema':'ASTRA_EXISTING_CPU_REGRESSIONS_V1','cases':records,
            'recordedLogsReparsedWithoutRerun':previous is not None,
            'gpuTestsExecuted':False,'vendorNetworkRequestsExecuted':False}
    (evidence/'EXISTING_REGRESSIONS.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
    return 0 if all(r['status']=='PASS' for r in records) else 1


if __name__=='__main__':sys.exit(main())
