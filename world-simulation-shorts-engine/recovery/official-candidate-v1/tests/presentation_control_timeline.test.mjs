import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash,webcrypto} from 'node:crypto';
import {SOURCE_CONTROL_TIMELINE_SCHEMA,CONTROL_TIMELINE_MAX_BYTES,canonicalControlTimelineJSON,
 validateSourceControlTimeline,preloadSourceControlTimeline,controlTimelineStateDigest} from '../presentation_control_timeline.mjs';

// All geometry, dates, provenance assertions and receipt hashes in this file are SYNTHETIC UNIT FIXTURES.
// A mock positive admission exercises a contract, and is not an admission of historical/production data.
const hash=value=>createHash('sha256').update(value).digest('hex');
const sourceId='SYNTHETIC_UNIT_FIXTURE_NOT_HISTORICAL',sourceSHA256=hash(sourceId),origin='https://synthetic-unit.invalid';
const ring=(x,y,size=1)=>[[x,y],[x+size,y],[x+size,y+size],[x,y+size],[x,y]];
function fixture(){
 return {schema:SOURCE_CONTROL_TIMELINE_SCHEMA,totalFrames:4,fps:30,crs:'EPSG:4326',sourceId,sourceSHA256,
  admission:{sourceType:'OFFICIAL_RETROSPECTIVE_STRATEGIC_MAP',georeferencing:'DERIVED_GRATICULE',originalCRS:'UNKNOWN',
   dailyObserved:false,transitionKind:'SOURCE_AUTHORED_VISUAL_TRANSITION',productionReady:true,
   sourceQualificationReceiptSHA256:hash('SYNTHETIC_MOCK_QUALIFICATION_RECEIPT_NOT_PRODUCTION')},
  frames:Array.from({length:4},(_,frame)=>({frame,sourceFrame:10+frame/2,sourceDateLabel:'SYNTHETIC_SOURCE_LABEL_'+(frame<2?'A':'B'),
   areas:[{id:'ACTOR_A_chunk0',ownerId:'ACTOR_A',geometry:{type:'Polygon',coordinates:[ring(frame/10,0)]}},
    {id:'ACTOR_B_chunk0',ownerId:'ACTOR_B',geometry:{type:'MultiPolygon',coordinates:[[ring(3,0)],
     [ring(6,0,2),ring(6.5,.5,.5)]]}}],
   fronts:[{id:'SUPPLIED_FRONT_chunk0',geometry:{type:'LineString',coordinates:[[1,0],[1.1,.4],[1,1]]}}]}))};
}
async function packageFixture(input=fixture(),firstFrame=1,lastFrame=2){
 const bytes=new TextEncoder().encode(JSON.stringify(input)),sha256=hash(bytes);
 const ref={schema:'WORLD_ENGINE_SOURCE_CONTROL_TIMELINE_REF_V1',url:'/qualified-control/'+sha256+'.json',sha256,
  bytes:bytes.length,firstFrame,lastFrame,totalFrames:input.totalFrames,ownerIds:['ACTOR_A','ACTOR_B'],sourceId:input.sourceId,
  sourceSHA256:input.sourceSHA256,admissionSHA256:hash(canonicalControlTimelineJSON(input.admission)),
  firstStateSHA256:await controlTimelineStateDigest(input.frames[firstFrame],{crypto:webcrypto}),
  lastStateSHA256:await controlTimelineStateDigest(input.frames[lastFrame],{crypto:webcrypto})};
 return {input,bytes,ref};
}
function options(bytes,extra={}){
 return {origin,crypto:webcrypto,fetch:async()=>new Response(bytes,{status:200}),...extra};
}

test('pinned dense frames preserve source offset, fractional source frame, parts, holes and ownership without interpolation',async()=>{
 const data=await packageFixture(),snapshot=structuredClone(data.input);let request;
 const timeline=await preloadSourceControlTimeline(data.ref,options(data.bytes,{fetch:async(url,init)=>{
  request={url,init};return new Response(data.bytes,{status:200});}}));
 const first=timeline.evaluate(0),last=timeline.evaluate(1);
 assert.deepEqual(request,{url:origin+data.ref.url,init:{method:'GET',credentials:'same-origin',redirect:'error',cache:'no-store'}});
 assert.equal(timeline.totalFrames,2);assert.equal(first.frame,0);assert.equal(first.absoluteFrame,1);assert.equal(first.sourceFrame,10.5);
 assert.equal(last.absoluteFrame,2);assert.equal(first.timeLabel,'SYNTHETIC_SOURCE_LABEL_A');
 assert.equal(first.dailyObserved,false);assert.equal(first.interpolation,'NONE_RUNTIME_SOURCE_AUTHORED_STATES');
 assert.deepEqual(first.areas.map(area=>[area.id,area.ownerId,area.alpha,area.coverage]),[
  ['ACTOR_A_chunk0','ACTOR_A',1,1],['ACTOR_B_chunk0','ACTOR_B',1,1]]);
 assert.deepEqual(first.areas.map(area=>area.geometry),data.input.frames[1].areas.map(area=>area.geometry));
 assert.equal(first.areas[1].geometry.coordinates.length,2);assert.equal(first.areas[1].geometry.coordinates[1].length,2);
 assert.equal(first.fronts[0].linePrimitive,null);assert.deepEqual(data.input,snapshot);
 assert(Object.isFrozen(first.areas[0].geometry));assert.equal(timeline.validation.geometryValidatedFirstFrame,1);
 assert.equal(timeline.validation.geometryValidatedLastFrame,2);assert.equal(timeline.validation.geometryCacheHits,1);
});

test('fronts reuse the existing line primitive against the current projection on every evaluation',async()=>{
 const {bytes,ref,input}=await packageFixture(),timeline=await preloadSourceControlTimeline(ref,options(bytes));
 const first=timeline.evaluate(0,{project:([x,y])=>[x*10,y*20]}),next=timeline.evaluate(0,{project:([x,y])=>[x*30+7,y*40]});
 assert.deepEqual(first.fronts[0].linePrimitive.screenCoordinates,input.frames[1].fronts[0].geometry.coordinates.map(([x,y])=>[x*10,y*20]));
 assert.deepEqual(next.fronts[0].linePrimitive.screenCoordinates,input.frames[1].fronts[0].geometry.coordinates.map(([x,y])=>[x*30+7,y*40]));
 assert.equal(first.fronts[0].linePrimitive.version,'GEOGRAPHIC_LINE_REVEAL_V1');
 assert.equal(first.fronts[0].lineReveal.complete,true);assert.notDeepEqual(first.fronts[0].linePrimitive,next.fronts[0].linePrimitive);
 for(const frame of [-1,.5,2,NaN])assert.throws(()=>timeline.evaluate(frame),/CONTROL_TIMELINE_FRAME_OUT_OF_RANGE/);
 assert.throws(()=>timeline.evaluate(0,{project:{}}),/AREA_EXISTING_PROJECTION_REQUIRED/);
});

test('each immutable drawn geographic geometry exposes its canonical SHA256 and actual coordinate count, hashed once',async()=>{
 const {bytes,ref,input}=await packageFixture();let calls=0;
 const crypto={subtle:{digest:async(...args)=>{calls++;return webcrypto.subtle.digest(...args);}}};
 const timeline=await preloadSourceControlTimeline(ref,options(bytes,{crypto}));
 // Dataset + admission + first/last states + four distinct area/front geometries, despite six items across two frames.
 assert.equal(calls,8);assert.equal(timeline.validation.distinctGeometrySHA256Count,4);
 for(let localFrame=0;localFrame<2;localFrame++){
  const controls=timeline.evaluate(localFrame,{project:point=>point}),source=input.frames[ref.firstFrame+localFrame];
  for(const kind of ['areas','fronts'])for(let index=0;index<controls[kind].length;index++){
   const item=controls[kind][index];assert.equal(item.geometrySHA256,hash(canonicalControlTimelineJSON(source[kind][index].geometry)));
   assert.equal(item.geometryCoordinateCount,kind==='fronts'?3:index===0?5:15);
  }
 }
 assert.equal(calls,8,'evaluating already loaded geometry must not hash or fetch again');
});

test('dense grid, source ordering, date labels, IDs and basic coordinates fail closed',()=>{
 for(const [change,error] of [
  [d=>d.frames.pop(),/DENSE_FRAME_GRID/],
  [d=>d.frames[1].frame=0,/DENSE_FRAME_GRID/],
  [d=>d.frames[1].sourceFrame=9,/SOURCE_FRAME_ORDER/],
  [d=>d.frames[0].sourceDateLabel='',/SOURCE_DATE_LABEL/],
  [d=>d.frames[0].areas.push(structuredClone(d.frames[0].areas[0])),/DUPLICATE_AREA_ID/],
  [d=>d.frames[0].fronts.push(structuredClone(d.frames[0].fronts[0])),/DUPLICATE_FRONT_ID/],
  [d=>d.frames[0].areas[0].geometry.coordinates[0][1]=[181,0],/GEOGRAPHIC_POINT_REQUIRED/],
  [d=>d.fps=25,/FRAME_GRID/],
  [d=>d.crs='UNKNOWN',/OUTPUT_CRS/]]){
  const data=fixture();change(data);assert.throws(()=>validateSourceControlTimeline(data,{firstFrame:1,lastFrame:2}),error);
 }
});

test('source admission and truthful retrospective/vector metadata are mandatory, with no daily front inference fallback',()=>{
 for(const [key,value,error] of [
  ['productionReady',false,/SOURCE_NOT_ADMITTED/],['dailyObserved',true,/SOURCE_TRUTH_CONTRACT/],
  ['originalCRS','EPSG:4326',/SOURCE_TRUTH_CONTRACT/],['georeferencing','ASSUMED',/SOURCE_TRUTH_CONTRACT/],
  ['transitionKind','INVENTED_LINEAR_DAILY_FRONT',/SOURCE_TRUTH_CONTRACT/],
  ['sourceQualificationReceiptSHA256','not-a-receipt',/QUALIFICATION_RECEIPT_SHA256/]]){
  const data=fixture();data.admission[key]=value;assert.throws(()=>validateSourceControlTimeline(data),error);
 }
 const data=fixture();delete data.admission;assert.throws(()=>validateSourceControlTimeline(data),/ADMISSION_REQUIRED/);
});

test('actual source, admission, owner and endpoint pins must match the fetched content',async()=>{
 const {bytes,ref}=await packageFixture();
 for(const [key,value,error] of [
  ['sourceId','DIFFERENT_SOURCE',/SOURCE_REFERENCE_MISMATCH/],['sourceSHA256',hash('other'),/SOURCE_REFERENCE_MISMATCH/],
  ['admissionSHA256',hash('other'),/ADMISSION_SHA256_MISMATCH/],
  ['firstStateSHA256',hash('other'),/ENDPOINT_STATE_SHA256_MISMATCH/],
  ['lastStateSHA256',hash('other'),/ENDPOINT_STATE_SHA256_MISMATCH/],
  ['ownerIds',['ACTOR_A'],/OWNER_REFERENCE_MISMATCH/]])
  await assert.rejects(()=>preloadSourceControlTimeline({...ref,[key]:value},options(bytes)),error);
});

test('raw bytes and streamed size are verified before parsing and rejected without retries',async()=>{
 const {bytes,ref}=await packageFixture();
 const corrupt=new Uint8Array(bytes);corrupt[0]=91;
 await assert.rejects(()=>preloadSourceControlTimeline(ref,options(corrupt)),/CONTENT_SHA256_MISMATCH/);
 await assert.rejects(()=>preloadSourceControlTimeline(ref,options(bytes.slice(1))),/BYTE_LENGTH_MISMATCH/);
 let requests=0,cancelled=false;
 const stream=new ReadableStream({start(controller){controller.enqueue(bytes);controller.enqueue(new Uint8Array([0]));},cancel(){cancelled=true;}});
 await assert.rejects(()=>preloadSourceControlTimeline(ref,options(bytes,{fetch:async()=>{requests++;return new Response(stream);}})),/BYTE_LIMIT/);
 assert.equal(requests,1);assert.equal(cancelled,true);
 await assert.rejects(()=>preloadSourceControlTimeline(ref,options(bytes,{fetch:async()=>new Response(bytes,
  {headers:{'content-length':String(CONTROL_TIMELINE_MAX_BYTES+1)}})})),/BYTE_LIMIT/);
 await assert.rejects(()=>preloadSourceControlTimeline({...ref,bytes:CONTROL_TIMELINE_MAX_BYTES+1},options(bytes)),/REFERENCE_BYTE_LIMIT/);
});

test('same-origin content-addressed path, HTTP success and no redirects are enforced',async()=>{
 const {bytes,ref}=await packageFixture();
 await assert.rejects(()=>preloadSourceControlTimeline({...ref,url:'https://other.invalid/data.json'},options(bytes)),/REGISTERED_RELATIVE_URL/);
 await assert.rejects(()=>preloadSourceControlTimeline(ref,options(bytes,{origin:origin+'/path'})),/SAME_ORIGIN_REQUIRED/);
 await assert.rejects(()=>preloadSourceControlTimeline(ref,options(bytes,{fetch:async()=>new Response('missing',{status:404})})),/FETCH_FAILED/);
 await assert.rejects(()=>preloadSourceControlTimeline(ref,options(bytes,{fetch:async()=>({ok:true,redirected:true})})),/REDIRECT_FORBIDDEN/);
});

test('existing 4096 area vertex and 129 front vertex capacities remain hard failures',()=>{
 const data=fixture(),parts=Array.from({length:1025},(_,i)=>{
  const x=(i%50)/10,y=Math.floor(i/50)/10;return [[[x,y],[x+.01,y],[x,y+.01],[x,y]]];});
 data.frames[1].areas[0].geometry={type:'MultiPolygon',coordinates:parts};
 assert.throws(()=>validateSourceControlTimeline(data,{firstFrame:1,lastFrame:1}),/AREA_GEOMETRY_CAPACITY_EXCEEDED/);
 const lineData=fixture();lineData.frames[1].fronts[0].geometry.coordinates=Array.from({length:130},(_,i)=>[i/100,0]);
 assert.throws(()=>validateSourceControlTimeline(lineData,{firstFrame:1,lastFrame:1}),/AREA_LINE_CAPACITY_EXCEEDED/);
});

test('explicit admitted SOURCE_NATIVE_8192 profile enables the bounded native vector capacity and records actual vertices',()=>{
 const data=fixture(),parts=Array.from({length:1025},(_,i)=>{
  const x=(i%50)/10,y=Math.floor(i/50)/10;return [[[x,y],[x+.01,y],[x,y+.01],[x,y]]];});
 data.frames[1].areas[0].geometry={type:'MultiPolygon',coordinates:parts};
 data.admission.capacityProfile='SOURCE_NATIVE_8192';
 const result=validateSourceControlTimeline(data,{firstFrame:1,lastFrame:1});
 assert.equal(result.validation.maxCoordinatesPerArea,8192);assert.equal(result.validation.maxObservedAreaCoordinates,4100);
 assert.equal(result.validation.geometryCapacityProfile,'SOURCE_NATIVE_8192');
 assert.equal(result.validation.triangleCapacity,16384);assert.equal(result.validation.triangleValidation,'EXISTING_AREA_OVERLAY_PASS_AT_DRAW_PENDING');
 data.admission.capacityProfile='UNBOUNDED';assert.throws(()=>validateSourceControlTimeline(data),/CAPACITY_PROFILE_INVALID/);
 data.admission.capacityProfile='SOURCE_NATIVE_8192';
 data.frames[1].areas[0].geometry.coordinates=Array.from({length:2049},(_,i)=>parts[i%parts.length]);
 assert.throws(()=>validateSourceControlTimeline(data,{firstFrame:1,lastFrame:1}),/AREA_GEOMETRY_CAPACITY_EXCEEDED/);
});

test('topology validation is explicit for the selected range; unselected geometry is never exposed as validated',()=>{
 const data=fixture();data.frames[0].areas[0].geometry.coordinates=[[[0,0],[1,1],[1,0],[0,1],[0,0]]];
 const result=validateSourceControlTimeline(data,{firstFrame:1,lastFrame:2});
 assert.deepEqual(result.frames.map(frame=>frame.frame),[1,2]);
 assert.equal(result.geometryValidatedFirstFrame,1);assert.equal(result.geometryValidatedLastFrame,2);
 assert.throws(()=>validateSourceControlTimeline(data),/AREA_RING_SELF_INTERSECTION/);
});

test('state identity ignores dates and object key insertion order but preserves source paint order and owner identity',async()=>{
 const frame=fixture().frames[0],clone=structuredClone(frame),original=await controlTimelineStateDigest(frame,{crypto:webcrypto});
 clone.frame=999;clone.sourceFrame=1000;clone.sourceDateLabel='DIFFERENT_SYNTHETIC_LABEL';
 clone.areas=clone.areas.map(area=>({geometry:area.geometry,ownerId:area.ownerId,id:area.id}));
 assert.equal(await controlTimelineStateDigest(clone,{crypto:webcrypto}),original);
 clone.areas.reverse();assert.notEqual(await controlTimelineStateDigest(clone,{crypto:webcrypto}),original);
 clone.areas.reverse();clone.areas[0].ownerId='ACTOR_B';assert.notEqual(await controlTimelineStateDigest(clone,{crypto:webcrypto}),original);
});
