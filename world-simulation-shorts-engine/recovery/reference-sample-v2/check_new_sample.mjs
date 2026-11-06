import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {presentationAreaViewport,presentationMapTheme,validatePresentation} from '../universal-presentation-v2/presentation_plan.mjs';
import {analyzePresentationPrompt} from '../universal-presentation-v2/presentation_prompt.mjs';
import {prepareNvidiaRuntimeRequest,verifyNvidiaPreparedRuntimeRequest} from '../codex-to-gcube-handoff-v1/backend/capture_nvidia.mjs';
const here=path.dirname(fileURLToPath(import.meta.url)),output=process.argv[2],privateRoot=process.argv[3];
assert(path.isAbsolute(output)&&path.isAbsolute(privateRoot));await mkdir(output,{mode:0o700});
const write=(name,value)=>writeFile(path.join(output,name),JSON.stringify(value,null,2)+'\n',{flag:'wx'});
const hash=b=>createHash('sha256').update(b).digest('hex');
const oldPreset={mapStyle:{preset:'COUNTRY_FOCUS_V1'}},newPreset={mapStyle:{preset:'REFERENCE_FOCUS_V2'}};
const polygon=ring=>({type:'Polygon',coordinates:[ring]}),square=(x0,y0,x1,y1)=>[[x0,y0],[x1,y0],[x1,y1],[x0,y1],[x0,y0]];
const view=(geometry,presentation=newPreset)=>presentationAreaViewport({geometry,project:p=>p,safeArea:[10,10,90,90],presentation,width:100,height:100});
let checks=0;
assert.throws(()=>view(polygon(square(-20,20,50,70)),oldPreset),/FOOTPRINT_OUTSIDE_SAFE/);checks++;
assert.equal(view(polygon(square(-20,20,50,70))).clipped,true);checks++;
assert.equal(view(polygon(square(-20,-20,120,120))).clipped,true);checks++;
assert.throws(()=>view(polygon(square(110,110,120,120))),/OUTSIDE_VIEWPORT/);checks++;
assert.throws(()=>view({type:'Polygon',coordinates:[square(-30,-30,130,130),square(-10,-10,110,110)]}),/OUTSIDE_VIEWPORT/);checks++;
const theme={primaryWidth:3,glowGain:.1};assert.equal(presentationMapTheme(oldPreset,theme),theme);assert.equal(presentationMapTheme(newPreset,theme).primaryWidth,4);assert.equal(theme.primaryWidth,3);checks++;
const raw=await readFile(path.join(here,'REFERENCE_SAMPLE_10S_V2.json')),input=JSON.parse(raw);
const original=JSON.parse(await readFile(path.join(here,'../reference-label-quality-v1/QUALITY_LABELS_10S.json')));
for(let i=0;i<2;i++)assert.deepEqual(input.data.scenes[i].facts,original.data.scenes[i].facts);checks++;
assert.equal(input.presentation.labels.items[0].pin,'NONE');
assert(input.presentation.labels.items.every(x=>x.pin!=='HERO'));
const end=input.presentation.sceneOverrides['namibia-coast-overview'];assert.equal(end.labels.items.at(-1).endFrame,150);assert.equal(end.labels.items.at(-1).exitFrames,1);checks++;
const analysis=await analyzePresentationPrompt(input,{allowTenSecondStudioSample:true});await write('ANALYSIS.json',analysis);
assert.equal(analysis.status,'PASS',JSON.stringify(analysis.issues));assert.equal(analysis.totalFrames,300);assert.equal(analysis.renderRequests.length,2);
const request={schema:'WORLD_ENGINE_PRESENTATION_RUNTIME_REQUEST_V2',durationSeconds:10,totalFrames:300,sourceInputSHA256:analysis.inputSHA256,transitions:analysis.transitionPlan,
 segments:analysis.renderRequests.map(r=>({sceneId:r.sceneId,startFrame:r.startFrame,endFrame:r.endFrame,scene:r.scene,region:r.region,presentation:r.presentation,inputTrace:r.inputTrace}))};
const prepared=await prepareNvidiaRuntimeRequest({request,cacheRoot:path.join(privateRoot,'sample-sources'),privateWorkspaceRoot:privateRoot,publicExportRoot:output});
const verified=await verifyNvidiaPreparedRuntimeRequest({prepared,privateWorkspaceRoot:privateRoot,publicExportRoot:output});
const first=prepared.segments[0],second=prepared.segments[1];assert.deepEqual(first.presentationPlan.cpuFrameBounds[149],second.presentationPlan.cpuFrameBounds[0]);
for(const segment of prepared.segments){
 const p=segment.presentation,scene=segment.scene;
 assert.throws(()=>validatePresentation({...p,mapStyle:{...p.mapStyle,lineAccentFrames:[20,10]}},{scene}),/LINE_ACCENT/);
 for(const bounds of segment.presentationPlan.cpuFrameBounds)assert(bounds.every(Number.isFinite));
}
await write('PREPARED.json',prepared);
await write('CHECK_RESULT.json',{schema:'WORLD_ENGINE_REFERENCE_SAMPLE_CHECK_V2',status:'PASS',newChecks:checks,actualPrepareVerify:verified,
 inputSHA256:hash(raw),sourceGeometryUnchanged:true,frameCount:300,cameraSeam:'PASS',sourceCoverage:'ACTUAL_SOURCE_FILES_VERIFIED',
 zoomScaleRatio:1/.35,sourcePixelSpacingDegrees:1/60,sourceScope:'REGIONAL_NOT_STREET_DETAIL',oldPassSuitesRerun:0,gpuStarts:0,imageBuilds:0,visualQuality:'PENDING_CPU_PREVIEW_REVIEW'});
console.log('NEW_SAMPLE_PREPARED_PASS');
