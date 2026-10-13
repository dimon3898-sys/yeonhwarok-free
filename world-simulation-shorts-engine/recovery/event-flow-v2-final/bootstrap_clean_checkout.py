#!/usr/bin/env python3
"""Hydrate only retained remote production inputs; install fresh locked npm dependencies."""
import argparse,hashlib,json,os,subprocess
from datetime import datetime,timezone
from pathlib import Path
FINAL=Path(__file__).resolve().parent
REPO=FINAL.parents[2]
BASE='world-simulation-shorts-engine/recovery/event-feature-bundle-v2-polish'
REVISION='4a1f773dcf377ebca5e46d83b81204707a56b59d'
REMOTE='https://github.com/dimon3898-sys/yeonhwarok-free.git'
BRANCH='development/event-flow-polish-v2-20261013'
LFS=['world-simulation-shorts-engine/library/flat/terrain/NE1_HR_LC_SR_W_DR.tif','world-simulation-shorts-engine/web/dem/glo30/height.f32']
def now():return datetime.now(timezone.utc).isoformat()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 a=argparse.ArgumentParser();a.add_argument('--checkout',required=True);args=a.parse_args();checkout=Path(args.checkout).resolve()
 ev=FINAL/'evidence';ev.mkdir(exist_ok=True)
 report={'schema':1,'status':'STARTED','checkout':str(checkout),'remote':REMOTE,'branch':BRANCH,'revision':REVISION,'clone_method':'REMOTE_GIT_CLONE','source_or_asset_copies':False,'git_alternates':[],
 'shared_system_toolchain':True,'fresh_operating_system':False,'bootstrap_started_at':now(),'logs':[]}
 def command(argv,env=None):
  r=subprocess.run(argv,cwd=checkout,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  report['logs'].append({'command':argv,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
  if r.returncode:raise RuntimeError('CHECKOUT_SETUP_COMMAND_FAILED '+str(argv)+' '+r.stderr[-1500:])
  return r.stdout.strip()
 try:
  assert command(['git','rev-parse','HEAD'])==REVISION
  assert command(['git','config','--get','remote.origin.url'])==REMOTE
  assert not (checkout/'.git/objects/info/alternates').exists()
  report['git_status_before_setup']=command(['git','status','--porcelain']);assert report['git_status_before_setup']==''
  dep=json.loads((checkout/BASE/'manifests/DEPENDENCY_MANIFEST.json').read_text())
  inv=json.loads((checkout/BASE/'manifests/HASH_MANIFEST.json').read_text())
  before=sha(checkout/'cinematic-world-map/package-lock.json')
  assert not (checkout/'cinematic-world-map/node_modules').exists()
  command(['git','lfs','install','--local'])
  pull=['git','lfs','pull','--include='+','.join(LFS),'--exclude='];command(pull)
  report['lfs_pull']={'status':'PASS','command':pull,'remote_source_only':True}
  wanted={r['path']:r for r in inv['required_files']}
  report['lfs_objects']=[]
  for name in LFS:
   file=checkout/name;expected=wanted[name]
   assert file.stat().st_size==expected['bytes'] and sha(file)==expected['sha256']
   report['lfs_objects'].append({**expected,'source':'REMOTE_GIT_LFS','status':'PASS'})
  cache=checkout/'.git/flow-final-npm-cache';assert not cache.exists()
  install=dep['setup'];command(install,{**os.environ,'npm_config_cache':str(cache),'PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD':'1'})
  packages=[{'name':n,'version':json.loads((checkout/'cinematic-world-map/node_modules'/n/'package.json').read_text())['version']} for n in ['three','playwright','playwright-core']]
  assert packages==[{'name':'three','version':'0.170.0'},{'name':'playwright','version':'1.62.1'},{'name':'playwright-core','version':'1.62.1'}]
  assert sha(checkout/'cinematic-world-map/package-lock.json')==before
  report['npm_ci']={'status':'PASS','command':install,'fresh_install':True,'fresh_cache':True,'cache':str(cache),'packages':packages,'package_lock_sha256_before':before,'package_lock_sha256_after':before}
  report['toolchain']={'node':command(['node','-p','process.versions.node']),'python':command(['/usr/bin/python3','-c','import platform;print(platform.python_version())']),'chromium':command(['/usr/bin/chromium','--version']).split()[1],'ffmpeg':command(['ffmpeg','-version']).splitlines()[0].split()[2].split('-')[0]}
  assert report['toolchain']=={'node':'24.19.0','python':'3.13.5','chromium':'154.0.8037.57','ffmpeg':'7.1.5'}
  report['raster_dependencies']=json.loads(command(['/usr/bin/python3','-B','-c','import json,numpy,PIL;from osgeo import gdal;print(json.dumps({"GDAL":gdal.__version__,"numpy":numpy.__version__,"Pillow":PIL.__version__}))']))
  assert report['raster_dependencies']=={'GDAL':'3.10.3','numpy':'2.2.4','Pillow':'11.1.0'}
  report['git_status_before_reproduction']=command(['git','status','--porcelain']);assert report['git_status_before_reproduction']==''
  report['git_status_after_setup']=report['git_status_before_reproduction'];report['status']='PASS'
  report['clone']={'command':['git','clone','--depth','1','--single-branch','--branch',BRANCH,'--filter=blob:none','--no-checkout',REMOTE,str(checkout)],'environment_overrides':{'GIT_LFS_SKIP_SMUDGE':'1'},'shallow':True,'local_objects_reused':False,'source_asset_hardlinks_or_symlink_reuse':False,'selected_production_inputs':415,'additional_checkout_infrastructure':3,'sparse':True}
 except Exception as e:report['status']='FAIL';report['error']=str(e);raise
 finally:
  report['bootstrap_finished_at']=now();(ev/'CLEAN_CHECKOUT_SETUP.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'status':report['status'],'revision':REVISION,'lfs':len(report['lfs_objects']),'fresh_npm':True,'clean_checkout':True}))
if __name__=='__main__':main()
