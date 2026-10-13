#!/usr/bin/env python3
"""Scan only the new Candidate and SHA-bound new material modules, read-only."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
ENGINE=ROOT.parents[1]
WORK=ENGINE.parents[1]/'.onboarding/map-visual-secret-scan'
SCANNER=Path('/workspace/.onboarding/event-v1-tools/gitleaks')
CONFIG=Path('/workspace/.onboarding/reference-reproduction-secret-scan/trusted-default.toml')
MODULES=['map_visual_gpu_adapter_v3.mjs','reference_terrain_material_v3.mjs','reference_ocean_material_v3.mjs',
 'reference_control_frontier_light_v3.mjs','world_engine_unit_overlay_v3.mjs']
def sha(file):return hashlib.sha256(file.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--phase',required=True,choices=['IMPLEMENTATION','PRE_RENDER','CANDIDATE','FINAL_REPORT']);a=p.parse_args()
 WORK.mkdir(parents=True,exist_ok=True);(WORK/'empty.ignore').write_text('')
 modules=WORK/'modules';modules.mkdir(exist_ok=True);bindings=[]
 for file in [*(ENGINE/'web/map_infographic_v1'/name for name in MODULES),ENGINE/'tests/reference_ocean_material_v3.test.mjs']:
  saved=modules/file.name;shutil.copyfile(file,saved)
  assert sha(saved)==sha(file);bindings.append({'path':str(file.relative_to(ENGINE)),'sha256':sha(file),'bytes':file.stat().st_size})
 reports=[]
 for label,folder in [('candidate',ROOT),('modules',modules)]:
  report=WORK/(a.phase.lower()+'-'+label+'.json')
  command=[str(SCANNER),'dir',str(folder),'--config',str(CONFIG),'--gitleaks-ignore-path',str(WORK/'empty.ignore'),
   '--ignore-gitleaks-allow','--redact=100','--report-format','json','--report-path',str(report),'--no-banner']
  result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  findings=json.loads(report.read_text()) if report.exists() else None
  if result.returncode or findings is None or len(findings):raise RuntimeError('SECRET_SCAN_FAILED '+label+' exit '+str(result.returncode))
  reports.append({'scope':label,'findings':len(findings),'reportSha256':sha(report)})
 value={'status':'PASS','phase':a.phase,'scanner':'gitleaks8.24.3','scannerSHA256':sha(SCANNER),
  'configSHA256':sha(CONFIG),'emptyIgnoreUsed':True,'inlineAllowIgnored':True,'scope':'Only NEW Candidate folder and bound NEW modules/tests',
  'reports':reports,'moduleBindings':bindings,'findings':0,'credentialsPublic':False}
 out=ROOT/'evidence'/('SECRET_SCAN_'+a.phase+'.json');out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(value,indent=2)+'\n')
 print(json.dumps({'status':'PASS','phase':a.phase,'findings':0}))
if __name__=='__main__':main()
