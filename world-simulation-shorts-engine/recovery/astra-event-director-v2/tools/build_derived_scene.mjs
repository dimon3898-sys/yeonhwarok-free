/** New immutable derived artifacts over the fixed canonical source. No rendering. */
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {compileDerivedScene} from '../derive_scene.mjs';
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),args=process.argv.slice(2);
assert.equal(args.length,1,'CANONICAL_PLAN_FILE_REQUIRED');
const result=compileDerivedScene({sourceBytes:await readFile(args[0]),
 profileBytes:await readFile(path.join(ROOT,'fixtures/HISTORY_EVENT_PROFILE_V2.json')),
 catalogBytes:await readFile(path.join(ROOT,'fixtures/HISTORY_SOURCE_CATALOG.json')),
 frontProfileBytes:await readFile(path.join(ROOT,'../verified-front-data-v4-recovery/FRONT_PROFILE.json'))});
result.receipt.compilerSHA256=createHash('sha256').update(await readFile(path.join(ROOT,'derive_scene.mjs'))).digest('hex');
for(const[name,raw]of [['fixtures/DERIVED_SCENE.json',result.bytes],['fixtures/DERIVED_FRONT_PROFILE.json',result.frontBytes],
 ['reports/DERIVATION.json',Buffer.from(JSON.stringify(result.receipt,null,2)+'\n')]]){
 const file=path.join(ROOT,name),old=await readFile(file).catch(e=>{if(e.code!=='ENOENT')throw e;return null;});
 if(old)assert.deepEqual(old,raw,'REFUSE_DIFFERENT_EXISTING_DERIVED_ARTIFACT_'+name);
 else await writeFile(file,raw,{flag:'wx'});
}
console.log(JSON.stringify(result.receipt));
