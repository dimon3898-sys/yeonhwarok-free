/** Offline geometry preparation inside the existing formal compiler. No renderer. */
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
export function compileContinuousTerritory(transitions){
 const result=spawnSync(process.env.WORLD_ENGINE_PYTHON??'python3',[fileURLToPath(new URL('./continuous_territory.py',import.meta.url))],{input:JSON.stringify({transitions}),encoding:'utf8',maxBuffer:128*1024*1024,timeout:180000});
 if(result.error||result.status!==0)throw Error('CONTINUOUS_COMPILE_FAILED: '+(result.error?.message??result.stderr).slice(-2000));
 return JSON.parse(result.stdout);
}
