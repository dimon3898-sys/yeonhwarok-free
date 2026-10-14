#!/usr/bin/env python3
"""Scan exactly one new Candidate folder; no legacy-tree or renderer mutation."""
import argparse,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
WORK=ROOT.parents[3]/'.onboarding/moving-frontier-glow-secret-scan'
SCANNER=Path('/workspace/.onboarding/event-v1-tools/gitleaks')
CONFIG=Path('/workspace/.onboarding/reference-reproduction-secret-scan/trusted-default.toml')
def sha(file):return hashlib.sha256(file.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--phase',required=True,choices=['IMPLEMENTATION','PRE_RENDER','CANDIDATE','FINAL_REPORT']);a=p.parse_args()
 version=subprocess.check_output([str(SCANNER),'version'],text=True).strip()
 if version!='8.24.3':raise RuntimeError('PINNED_GITLEAKS_VERSION_REQUIRED')
 WORK.mkdir(parents=True,exist_ok=True);ignore=WORK/'empty.ignore';ignore.write_text('')
 report=WORK/(a.phase.lower()+'.json')
 command=[str(SCANNER),'dir',str(ROOT),'--config',str(CONFIG),'--gitleaks-ignore-path',str(ignore),
  '--ignore-gitleaks-allow','--redact=100','--report-format','json','--report-path',str(report),'--no-banner']
 result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 findings=json.loads(report.read_text()) if report.exists() else None
 if result.returncode or findings is None or len(findings):raise RuntimeError('SECRET_SCAN_FAILED_NEW_CANDIDATE_ONLY exit '+str(result.returncode))
 value={'schema':'MOVING_FRONTIER_GLOW_SECRET_SCAN_V1','status':'PASS','phase':a.phase,
  'scanner':'gitleaks8.24.3','scannerSHA256':sha(SCANNER),'configSHA256':sha(CONFIG),
  'emptyIgnoreUsed':True,'inlineAllowIgnored':True,'scope':'EXACT_ONE_NEW_CANDIDATE_FOLDER_NO_NEW_ENGINE_MODULES',
  'reportSHA256':sha(report),'findings':0,'credentialsPublic':False,'previousSourcesScannedOrModified':False}
 out=ROOT/'evidence'/('SECRET_SCAN_'+a.phase+'.json');out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(value,indent=2)+'\n')
 print(json.dumps({'status':'PASS','phase':a.phase,'findings':0,'scope':'ONE_NEW_CANDIDATE_FOLDER'}))
if __name__=='__main__':main()
