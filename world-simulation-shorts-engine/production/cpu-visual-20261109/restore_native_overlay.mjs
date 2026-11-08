/** Apply the same preserved V8 edits to the reviewed NVIDIA source overlay. */
import {cp,readFile,writeFile} from 'node:fs/promises';import path from 'node:path';import {createHash} from 'node:crypto';
import {restoreRuntime,restorePlan} from './restore_viewport_features.mjs';
const [source,target]=process.argv.slice(2);if(!source||!target)throw Error('SOURCE_AND_NEW_TARGET_REQUIRED');
await cp(source,target,{recursive:true,errorOnExist:true,force:false});
const hash=x=>createHash('sha256').update(x).digest('hex'),root='world-simulation-shorts-engine/recovery/',changes=[];
for(const [relative,restore] of [
 ['official-candidate-v1/presentation_runtime.mjs',restoreRuntime],
 ['official-candidate-v1/presentation_runtime_nvidia.generated.mjs',restoreRuntime],
 ['codex-to-gcube-handoff-v1/presentation_runtime_vulkan.generated.mjs',restoreRuntime],
 ['official-candidate-v1/presentation_plan.mjs',restorePlan]]){
 const file=path.join(target,root,relative),before=await readFile(file,'utf8'),after=restore(before);await writeFile(file,after);
 changes.push({path:root+relative,beforeSHA256:hash(before),afterSHA256:hash(after)});
}
const name=root+'codex-to-gcube-handoff-v1/backend/capture_nvidia.mjs',file=path.join(target,name),before=await readFile(file,'utf8'),old='f39a24ced64da5aae5bb2520183a96713301a15e2f7f55515a2c84da288cae11';
if(before.split(old).length!==2)throw Error('PARENT_RUNTIME_PIN_ANCHOR');
const after=before.replace(old,'c766de85267f7ae30e3b76af9fef4168a786baafa93c03bdbdc39da476e4cf49');await writeFile(file,after);changes.push({path:name,beforeSHA256:hash(before),afterSHA256:hash(after)});
console.log(JSON.stringify({schema:'WORLD_ENGINE_NATIVE_V8_RESTORATION_V1',status:'PREPARED_INACTIVE',changes,paidExecution:false,oldTestsRerun:false,existingV8ImplementationReused:true}));
