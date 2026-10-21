/** Real Area CPU plan/evaluation; GPU handoff is a labeled mock, not draw proof. */
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {registerHooks} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {normalizeProductionVisualProfile} from '../../universal-production-v3/production_visual_profile.mjs';
const ROOT=fileURLToPath(new URL('..',import.meta.url)),web=path.resolve(ROOT,'../../web/map_infographic_v1'),
 sha=x=>createHash('sha256').update(x).digest('hex'),clone=x=>structuredClone(x),
 mockGPU='data:text/javascript,'+encodeURIComponent(`export function createProductionAreaPass(){return{
 draw(input){globalThis.__directorMockPartialInput=input;return {areas:[],fronts:input.controls.fronts,backend:'CPU_GPU_HANDOFF_MOCK',drawCount:1};},
 dispose(){globalThis.__directorMockPartialDisposed=true;}};}`),
 hook=registerHooks({resolve(specifier,context,next){
  if(specifier.startsWith('/modules/'))return{url:new URL('file://'+path.join(web,specifier.slice(9))).href,shortCircuit:true};
  if(specifier==='/production-v3/production_area_pass.mjs')return{url:mockGPU,shortCircuit:true};
  if(specifier==='/front-v4/front_visual.mjs')return{url:new URL('../../verified-front-data-v4-recovery/front_visual.mjs',import.meta.url).href,shortCircuit:true};
  return next(specifier,context);
 }});
let api;try{api=await import('../partial_front_pass.mjs');}finally{hook.deregister();}
const p=JSON.parse(await readFile(new URL('../fixtures/HISTORY_EVENT_PROFILE_V2.json',import.meta.url))),
 geoBytes=await readFile(new URL('../source-review/CMH_APPLEMAN_1950_06_28_PARTIAL_FRONT.geojson',import.meta.url)),
 geo=JSON.parse(geoBytes),frontId='source-qualified-roi-front',sourceFile='source-review/CMH_APPLEMAN_1950_06_28_PARTIAL_FRONT.geojson',
 geometry={type:'MultiLineString',coordinates:geo.features.map(x=>clone(x.geometry.coordinates))},
 front={frontId,geometry,sourceFile,geoJsonSha256:sha(geoBytes),mapDate:'1950-06-28',
  source:{reference:'https://www.govinfo.gov/content/pkg/GOVPUB-D114-PURL-gpo93269/pdf/GOVPUB-D114-PURL-gpo93269.pdf; Map I PDF49',
   documentSha256:'942197804b46d5a9007b22083b569669844d3e72225fe203c2edc2878f7be8ad',
   rasterSha256:geo.metadata.sourceMapSHA256,cartographicAccuracy:'UNKNOWN_NOT_CERTIFIED',classification:'OBSERVED_ROK_FRONT'},
  sourceLabel:'1950.06.28 근사 부분전선',runtimeAdmission:'QUALIFIED_SOURCE_REVIEW_ONLY',
  fullControlPolygon:false,renderConsumer:'DIRECTOR_ADDITIONAL_PARTIAL_FRONT'};
function profile(){const profile=clone(p),row=profile.sourceSchedule.find(x=>x.startFrame===200);
 Object.assign(row,{stateId:frontId,kind:'OBSERVED_PARTIAL_FRONT',truthKind:'observed',sourceDate:front.mapDate,sourceIds:[frontId]});return profile;}
function input(){return{canvas:{},profile:profile(),fronts:[clone(front)],origin:p.locations[0].anchor,
 productionVisualProfile:normalizeProductionVisualProfile()};}
function drawInput(stateId=frontId,globalFrame=300){return{stateId,globalFrame,project:point=>point,
 safeArea:[48,72,1032,1848],protectedGraphics:[{kind:'TEXT',box:[50,80,250,150]}],
 boundarySegments:[{a:[0,0],b:[1,1],radiusPx:3}]};}

test('actual Map I traced edge chunks remain exact; source is not mislabeled UN or an ownership polygon',()=>{
 const original=JSON.stringify(front),compiled=api.compileQualifiedPartialFronts(input()),selected=compiled.fronts[0];
 assert.equal(JSON.stringify(front),original);assert.equal(selected.sourceGeometryBinding,JSON.stringify(geometry));
 assert.deepEqual(selected.sourceChunks.map(x=>x.geometry.coordinates),geometry.coordinates);
 assert.equal(selected.front.source.classification,'OBSERVED_ROK_FRONT');
 assert.equal(selected.front.fullControlPolygon,false);assert.equal(selected.sourceRecord.verification_status,'VERIFIED');
});
test('original Area CPU evaluation and labeled mock GPU handoff contain only the observed front',()=>{
 const owner=api.createQualifiedPartialFrontPass(input()),d=drawInput(),result=owner.draw(d);
 assert.equal(result.globalFrame,300);assert.equal(result.controls.frame,300);assert.equal(result.sourceDate,'1950-06-28');
 assert.deepEqual(result.controls.areas,[]);assert.equal(result.controls.fronts.length,geometry.coordinates.length);
 assert.equal(result.graphics.backend,'CPU_GPU_HANDOFF_MOCK');assert.equal(result.sourceAreaDrawCount,0);
 assert.equal(result.fullControlGeometryDrawn,false);assert.equal(result.coordinatesInterpolated,false);
 assert.equal(result.sourceQualifier,front.sourceLabel);assert.equal(result.geoJsonSha256,sha(geoBytes));
 assert.equal(result.sourceSide,'OBSERVED_ROK_FRONT');assert.equal(result.nvidiaHardwareVerified,false);
 const handed=globalThis.__directorMockPartialInput;assert.equal(handed.protectedGraphics,d.protectedGraphics);
 assert.deepEqual(handed.boundarySegments,[]);assert.equal(handed.project,d.project);owner.dispose();
 assert.equal(globalThis.__directorMockPartialDisposed,true);
});
test('unselected state gets no source geometry and stale selected frame fails',()=>{
 const owner=api.createQualifiedPartialFrontPass(input());
 assert.equal(owner.draw(drawInput(null,700)),null);
 assert.throws(()=>owner.draw(drawInput(frontId,700)),/FRAME_SOURCE_MISMATCH/);
 assert.throws(()=>owner.draw(drawInput(null,300)),/ACTIVE_STATE_OMITTED/);
 assert.throws(()=>owner.draw(drawInput(frontId,2400)),/GLOBAL_FRAME_REQUIRED/);
 owner.dispose();assert.throws(()=>owner.draw(drawInput()),/PASS_DISPOSED/);
});
test('unreviewed proof, absent byte hash and false full-control claims are rejected',()=>{
 for(const mutation of [x=>{x.fronts[0].runtimeAdmission='APPROVED';},x=>{x.fronts[0].geoJsonSha256=null;},
  x=>{x.fronts[0].fullControlPolygon=true;},x=>{x.fronts[0].source.cartographicAccuracy='EXACT';},
  x=>{x.fronts[0].sourceFile='../outside';}]){
  const args=input();mutation(args);assert.throws(()=>api.compileQualifiedPartialFronts(args),/PARTIAL_FRONT_PROOF_REQUIRED/);
 }
});
test('source clock/date mismatch and unknown state cannot be promoted to observed fronts',()=>{
 let args=input();args.profile.sourceSchedule.find(x=>x.startFrame===200).sourceDate='1950-06-29';
 assert.throws(()=>api.compileQualifiedPartialFronts(args),/ACTUAL_SOURCE_SCHEDULE_REQUIRED/);
 args=input();args.profile.sourceSchedule.find(x=>x.startFrame===200).truthKind='unknown';
 assert.throws(()=>api.compileQualifiedPartialFronts(args),/ACTUAL_SOURCE_SCHEDULE_REQUIRED/);
});
test('closed or fabricated polygon geometry is rejected by the unchanged source-line and Area owners',()=>{
 let args=input();args.fronts[0].geometry={type:'Polygon',coordinates:[[[0,0],[1,0],[1,1],[0,0]]]};
 assert.throws(()=>api.compileQualifiedPartialFronts(args),/OPEN_LINE_GEOMETRY_REQUIRED/);
 args=input();args.fronts[0].geometry={type:'LineString',coordinates:[[0,0],[1,1],[0,0]]};
 assert.throws(()=>api.compileQualifiedPartialFronts(args),/CLOSED_BOUNDARY_NOT_ADMITTED/);
});
