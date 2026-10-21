import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {compileDerivedScene} from '../derive_scene.mjs';
import {evaluateProductionGeometryClock} from '../../universal-production-v3/production_visual_profile.mjs';
import {selectFrontSnapshot,normalizeFrontProfile} from '../../verified-front-data-v4-recovery/front_visual.mjs';
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),
 replay=JSON.parse(await readFile(path.join(ROOT,'reports/ORIGINAL_SOURCE_REPLAY.json'))),
 original={sourceBytes:await readFile(path.join(path.dirname(replay.preparedPath),'PLAN.json')),
  profileBytes:await readFile(path.join(ROOT,'fixtures/HISTORY_EVENT_PROFILE_V2.json')),
  catalogBytes:await readFile(path.join(ROOT,'fixtures/HISTORY_SOURCE_CATALOG.json')),
  frontProfileBytes:await readFile(path.join(ROOT,'../verified-front-data-v4-recovery/FRONT_PROFILE.json'))
 };
// The source owner is a sibling namespace, never a copied adapter.
const copyProfile=()=>JSON.parse(original.profileBytes),bytes=v=>Buffer.from(JSON.stringify(v)),
 hash=v=>createHash('sha256').update(v).digest('hex');
test('derived scene changes only declared narrative/source schedule/palette; old geometry and input bytes exact',()=>{
 const before=hash(original.sourceBytes),r=compileDerivedScene(original),p=JSON.parse(original.sourceBytes);
 assert.equal(hash(original.sourceBytes),before);assert.deepEqual(r.document.legacyScenePlan,p.legacyScenePlan);
 assert.deepEqual(r.document.scenes,p.scenes);assert.deepEqual(r.frontProfile.fronts,JSON.parse(original.frontProfileBytes).fronts);
 assert.notEqual(r.receipt.derivedSceneSHA256,r.receipt.sourcePlanSHA256);
 assert.equal(r.document.productionV3.eventChapters[10].title,'휴전 협상·전선 고착');
 assert.equal(r.receipt.fullControlGeometryAvailable,false);
});
test('actual original clock evaluator never selects BUSAN for later events or fills unknown gaps',()=>{
 const r=compileDerivedScene(original);
 for(let f=600;f<1400;f++)assert.equal(evaluateProductionGeometryClock(r.document,f).eventEnabled,false);
 for(let f=400;f<600;f++)assert.equal(evaluateProductionGeometryClock(r.document,f).sourceStateId,'BUSAN');
 assert.equal(evaluateProductionGeometryClock(r.document,1560).snapshotDate,'1951-01-04');
 const p=normalizeFrontProfile(r.frontProfile,{totalFrames:2400,eventChapters:r.document.productionV3.eventChapters});
 assert.equal(selectFrontSnapshot(p,1500).mapDate,'1950-12-31');
 assert.equal(selectFrontSnapshot(p,1560).sourceActiveFrame,false);
 assert.equal(selectFrontSnapshot(p,1650).mapDate,'1951-01-24');
});
test('palette is selected by input faction ID, not a built-in country branch',()=>{
 const p=copyProfile();p.factions={ALPHA:{color:'#123456'},BETA:{color:'#abcdef'}};
 p.presentation.heldCoreColorFactionId='ALPHA';
 const r=compileDerivedScene({...original,profileBytes:bytes(p)});
 assert.deepEqual(r.document.productionV3.visualBindings.areaStyles[0].color,[0x12/255,0x34/255,0x56/255]);
});
test('source byte mismatch and unknown kinds cannot fall back to old preset',()=>{
 assert.throws(()=>compileDerivedScene({...original,sourceBytes:Buffer.concat([original.sourceBytes,Buffer.from(' ')])}),/SOURCE_HASH_MISMATCH/);
 const p=copyProfile();p.sourceSchedule[4].kind='HOLD_PREVIOUS';
 assert.throws(()=>compileDerivedScene({...original,profileBytes:bytes(p)}),/UNSUPPORTED_SOURCE_STATE_KIND/);
});
test('chapter identity changes and an unqualified previous-state fallback are rejected',()=>{
 const p=copyProfile();p.chapters[3].eventId='ANOTHER_EVENT';
 assert.throws(()=>compileDerivedScene({...original,profileBytes:bytes(p)}));
 const q=copyProfile();q.sourceSchedule[4].stateId='BUSAN';
 assert.throws(()=>compileDerivedScene({...original,profileBytes:bytes(q)}),/UNKNOWN_CANNOT_REUSE_PREVIOUS_STATE/);
});
