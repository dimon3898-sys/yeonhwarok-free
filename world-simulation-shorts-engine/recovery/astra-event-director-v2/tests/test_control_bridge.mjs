import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {createQualifiedControlBridge,assertControlConsumerIdentity} from '../control_bridge.mjs';
const sha=x=>createHash('sha256').update(x).digest('hex'),clone=x=>structuredClone(x),bytes=x=>Buffer.from(JSON.stringify(x));
const [timelineBytes,profileBytes,catalogBytes]=await Promise.all(['CONTROL_TIMELINE','HISTORY_EVENT_PROFILE_V2','HISTORY_SOURCE_CATALOG']
 .map(x=>readFile(new URL('../fixtures/'+x+'.json',import.meta.url))));
const timeline=JSON.parse(timelineBytes),profile=JSON.parse(profileBytes),catalog=JSON.parse(catalogBytes);
function options(){return {timelineBytes,profileBytes,catalogBytes,expectedTimelineSHA256:sha(timelineBytes),
 expectedProfileSHA256:sha(profileBytes),expectedCatalogSHA256:sha(catalogBytes),sourcePlanSHA256:profile.sourcePlanSHA256,
 purpose:'QUALIFIED_SOURCE_REVIEW'};}
function consumers(state){return {state,area:{field:state,globalFrame:state.globalFrame,ownerDrawCount:0},
 front:{field:state,globalFrame:state.globalFrame,ownerDrawCount:0},terrain:{field:state,globalFrame:state.globalFrame,ownerDrawCount:0}};}
test('actual qualified timeline evaluates absolute global clock without fabricating ownership',async()=>{
 const bridge=await createQualifiedControlBridge(options());
 for(const frame of [0,150,600,865,964,965,1099,1500,2399]){
  const state=bridge.evaluateControlState(frame),evidence=assertControlConsumerIdentity(consumers(state));
  assert.equal(state.globalFrame,frame);assert.equal(state.stateId,null);assert.deepEqual(state.ownerMasks,[]);
  assert.equal(state.sharedFront,null);assert.equal(state.interpolationProgress,null);assert.equal(state.renderAllowed,false);
  assert.equal(evidence.ownerDrawCount,0);assert.equal(evidence.historicalMorphVerified,false);
 }
 assert.equal(bridge.evidence.scalarControlCompiled,false);assert.equal(bridge.evidence.boundedFrameCacheEntries,1);
});
test('immutable private frame identity rejects cloned, synthetic, stale and independently evaluated fields',async()=>{
 const bridge=await createQualifiedControlBridge(options()),state=bridge.evaluateControlState(900);
 assert.equal(bridge.evaluateControlState(900),state);assert.ok(Object.isFrozen(state));assert.ok(Object.isFrozen(state.sourceHashes));
 assert.throws(()=>assertControlConsumerIdentity(consumers(clone(state))),/ACTUAL_EVALUATED_FRAME_REQUIRED/);
 const wrong=consumers(state);wrong.front.field=clone(state);
 assert.throws(()=>assertControlConsumerIdentity(wrong),/SHARE_EXACT_FRAME_IDENTITY/);
 const stale=consumers(state);stale.terrain.globalFrame=901;
 assert.throws(()=>assertControlConsumerIdentity(stale),/SHARE_EXACT_FRAME_IDENTITY/);
 const fake=clone(state);fake.synthetic=true;
 assert.throws(()=>assertControlConsumerIdentity(consumers(fake)),/ACTUAL_EVALUATED_FRAME_REQUIRED/);
 const drawn=consumers(state);drawn.front.ownerDrawCount=1;
 assert.throws(()=>assertControlConsumerIdentity(drawn),/DRAW_BLOCKED_WITHOUT_OWNER_FIELD/);
});
test('same-byte SHA and explicit review admission are mandatory',async()=>{
 await assert.rejects(createQualifiedControlBridge({...options(),purpose:'PRODUCTION'}),/SOURCE_REVIEW_ONLY/);
 await assert.rejects(createQualifiedControlBridge({...options(),timelineBytes:Buffer.concat([timelineBytes,Buffer.from(' ')])}),/ACTUAL_SOURCE_SHA_MISMATCH/);
 await assert.rejects(createQualifiedControlBridge({...options(),expectedProfileSHA256:'0'.repeat(64)}),/ACTUAL_SOURCE_SHA_MISMATCH/);
 await assert.rejects(createQualifiedControlBridge({...options(),sourcePlanSHA256:'0'.repeat(64)}),/QUALIFIED_SOURCE_BINDING_REQUIRED/);
});
test('approved-looking JSON cannot enable a full owner field or previous-state fallback',async()=>{
 let t=clone(timeline);t.ownerFields=[{approved:true,mask:'invented'}];let b=bytes(t);
 await assert.rejects(createQualifiedControlBridge({...options(),timelineBytes:b,expectedTimelineSHA256:sha(b)}),/FULL_OWNER_SOURCE_ADAPTER_REQUIRED/);
 t=clone(timeline);t.states[0].controlStartState='PREVIOUS';b=bytes(t);
 await assert.rejects(createQualifiedControlBridge({...options(),timelineBytes:b,expectedTimelineSHA256:sha(b)}),/SOURCE_CHAPTER_CHANGED/);
 t=clone(timeline);t.states[0].sharedFront={geometry:'fake'};b=bytes(t);
 await assert.rejects(createQualifiedControlBridge({...options(),timelineBytes:b,expectedTimelineSHA256:sha(b)}),/UNKNOWN_OWNER_MUST_REMAIN_NULL/);
});
test('source observations retain provenance and cannot be promoted to owner geometry',async()=>{
 const bridge=await createQualifiedControlBridge(options()),observed=timeline.sourceObservations.find(x=>x.truthKind==='observed'),
  state=bridge.evaluateControlState(observed.startFrame);
 assert.deepEqual(state.qualifiedSourceObservation,observed);assert.equal(state.truthKind,'unknown');assert.equal(state.asOfDate,null);
 let t=clone(timeline);t.sourceObservations[0].sourceIds=['invented'];let b=bytes(t);
 await assert.rejects(createQualifiedControlBridge({...options(),timelineBytes:b,expectedTimelineSHA256:sha(b)}),/SOURCE_OBSERVATION_CHANGED/);
});
test('out of range frames and use after disposal are fail closed',async()=>{
 const bridge=await createQualifiedControlBridge(options());
 for(const frame of [-1,2400,.1,NaN])assert.throws(()=>bridge.evaluateControlState(frame),/GLOBAL_FRAME_OUT_OF_RANGE/);
 bridge.dispose();assert.throws(()=>bridge.evaluateControlState(0),/BRIDGE_DISPOSED/);
});
