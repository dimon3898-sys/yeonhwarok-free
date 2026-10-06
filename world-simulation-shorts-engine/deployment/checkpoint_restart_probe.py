"""Bounded deployment QA: stop only this gateway after cached Scenes complete.

Requires an already-approved <=20s audio-only test. Never starts a render and
never targets an existing legacy server or unfinished native Scene.
"""
import argparse, hashlib, json, os, signal, sys, time
from pathlib import Path
APP=Path(__file__).resolve().parents[1];sys.path.insert(0,str(APP))
from deployment.mobile_server import checked_state_root
from engine.storage import ProjectStore, read_json

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--state-root',required=True)
    parser.add_argument('--project',required=True)
    parser.add_argument('--version',required=True)
    args=parser.parse_args();root=checked_state_root(args.state_root)
    store=ProjectStore(root/'projects');plan=store.require_approved(args.project,args.version)
    if not 5<=plan['duration']<=20 or plan['options'].get('bgm') is not False:
        raise SystemExit('Only a short approved BGM-OFF audio-only regression is permitted.')
    folder=store.version_path(args.project,args.version)
    receipt=root/'qa'/(args.project+'_'+args.version+'_restart_point.json')
    receipt.parent.mkdir(exist_ok=True)
    if receipt.exists():raise SystemExit('Restart proof already exists; preserving it.')
    for _ in range(1200):
        state=store.status(args.project,args.version)
        manifest=folder/'renders/scene_results.json'
        if state['status']=='rendering' and manifest.exists():
            scenes=read_json(manifest)['scenes']
            if len(scenes)==len(plan['scenes']) and all(x.get('complete') and x.get('reused') for x in scenes):
                servers=[]
                for proc in Path('/proc').iterdir():
                    if not proc.name.isdigit():continue
                    try:
                        argv=(proc/'cmdline').read_bytes().decode().split('\0')
                        if not Path(argv[0]).name.startswith('python') or 'deployment.mobile_server' not in argv or '--worker-ticket' in argv:continue
                        value=argv[argv.index('--state-root')+1]
                        candidate=(Path(os.readlink(proc/'cwd'))/value).resolve()
                        if candidate==root:servers.append(int(proc.name))
                    except (OSError,ValueError,IndexError,UnicodeError):continue
                if len(servers)!=1:raise SystemExit('Cannot uniquely identify the owned QA gateway.')
                hashes=[{'scene_id':x['scene_id'],'sha256':hashlib.sha256(Path(x['movie']).read_bytes()).hexdigest()} for x in scenes]
                if any(a['sha256']!=b['video_sha256'] for a,b in zip(hashes,scenes)):raise SystemExit('Scene hash mismatch.')
                result={'project_id':args.project,'version':args.version,'job_id':state['job_id'],
                    'completed_scene_count':len(scenes),'all_scenes_reused':True,'scene_hashes_before_restart':hashes,
                    'stopped_owned_gateway_pid':servers[0],'checkpoint_preserved':True,'timestamp_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}
                with receipt.open('x') as f:json.dump(result,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
                receipt.chmod(0o600)
                print(json.dumps(result),flush=True)
                os.kill(servers[0],signal.SIGTERM)
                return
        if state['status'] in {'complete','failed','qc_failed'}:raise SystemExit('Missed checkpoint or job failed; no server was stopped.')
        time.sleep(.05)
    raise SystemExit('Bounded checkpoint wait expired; no server was stopped.')

if __name__=='__main__':main()
