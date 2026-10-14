/** Only a new frontier material profile; every other saved scene input is exact. */
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {validateControlFrontierLightProfile} from '../../web/map_infographic_v1/reference_control_frontier_light_v3.mjs';
const root=path.dirname(fileURLToPath(import.meta.url)),parent=path.join(root,'../map-engine-unit-bundle-v1');
const oldBytes=await readFile(path.join(parent,'fixtures/SCENE_PLAN.json'));
const old=JSON.parse(oldBytes),scene=structuredClone(old);
scene.frontierProfile={...old.frontierProfile,profileName:'MOVING_FRONTIER_GLOW_FIX_V1',
 centerColor:[1,.985,.94],centerWidthPixels:2.5,centerAlpha:1,
 haloColor:[1,.70,.25],haloSigmaPixels:3.5,haloSupportPixels:10,haloAlpha:.35,
 velocityWindowFrames:12,settledStrength:.08};
validateControlFrontierLightProfile(scene.frontierProfile);
const withoutGlow=s=>{const copy=structuredClone(s);delete copy.frontierProfile;return copy;};
assert.deepEqual(withoutGlow(scene),withoutGlow(old),'GLOW_ONLY_SCENE_CHANGE_REQUIRED');
for(const name of ['luminanceAnchor','minimumLightingFactor','reliefLightingEnabled'])
 assert.equal(scene.frontierProfile[name],old.frontierProfile[name],'TERRAIN_RELIEF_LIGHTING_IS_LOCKED');
const off=structuredClone(scene),core=structuredClone(scene);
off.frontierProfile={...scene.frontierProfile,profileName:'PRIVATE_GLOW_OFF_RELIEF_UNCHANGED',centerAlpha:0,haloAlpha:0};
core.frontierProfile={...scene.frontierProfile,profileName:'PRIVATE_CORE_ONLY_RELIEF_UNCHANGED',haloAlpha:0};
const save=async(name,value)=>writeFile(path.join(root,'fixtures',name),JSON.stringify(value,null,2)+'\n');
await save('SCENE_PLAN.json',scene);await save('SCENE_GLOW_OFF.json',off);await save('SCENE_CORE_ONLY.json',core);
const runtime=JSON.parse(await readFile(path.join(parent,'fixtures/RUNTIME_FIXTURE.json')));
runtime.videoFilename='WORLD_ENGINE_MOVING_FRONTIER_GLOW_FIX_5S.mp4';
await save('RUNTIME_FIXTURE.json',runtime);
const record={status:'PASS',parentSceneSha256:createHash('sha256').update(oldBytes).digest('hex'),
 parentCommit:'8e2b994755330907ceed9b9bfcc922e9b113138d',sourceCoreChanged:false,
 changesOnly:'FRONTIER_PROFILE',parentFrontierProfile:old.frontierProfile,newFrontierProfile:scene.frontierProfile,
 unchanged:['ALL_OTHER_SCENE_FIELDS','CONTROL_SPEED_GEOMETRY_TIMELINE','CAMERA','TERRAIN_OCEAN_GOLD_LIGHT','NATIONAL_ICONS','PROJECTION','PLANNER','FINAL_SOURCE'],
 ablations:'PRIVATE alpha0 and haloAlpha0 reuse same source pass and preserve reliefLightingEnabled/minimumLightingFactor/luminanceAnchor',
 privateStopTest:true,publicFalseStopAtOutputEnd:false,newRequiredAssets:[],requiredTempOnlyFiles:0};
await writeFile(path.join(root,'evidence/FIXTURE_BUILD.json'),JSON.stringify(record,null,2)+'\n');
console.log(JSON.stringify({status:'PASS',scope:'FRONTIER_PROFILE_ONLY',newEngine:false,newAssets:0}));
