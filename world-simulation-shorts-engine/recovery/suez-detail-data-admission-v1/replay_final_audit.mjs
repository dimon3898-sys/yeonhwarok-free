// Recheck saved research against the final generic API; no renderer/camera execution.
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {generateDetailExtentCandidates,selectSafeDetailExtent} from '../../web/map_infographic_v1/detail_data_profile_v1.mjs';
const root=path.dirname(fileURLToPath(import.meta.url)),engine=path.resolve(root,'../..');
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const json=async name=>JSON.parse(await readFile(name,'utf8'));
const profileBytes=await readFile(path.join(root,'DETAIL_DATA_PROFILE.json'));
const profile=JSON.parse(profileBytes),audit=await json(path.join(root,'evidence/DETAIL_QUALITY_AUDIT.json'));
const fixtureBytes=await readFile(path.join(engine,'recovery/event-data/suez-full-canal-20261012/fixture.json'));
const fixture=JSON.parse(fixtureBytes),camera=await json(path.join(engine,'recovery/v5/inputs/camera-plan.json'));
const regional=await json(path.join(engine,'recovery/v4/equivalent-plans/REGIONAL-plan.json'));
const on=await json(path.join(engine,'recovery/event-v1-candidate-v2/evidence/on150/REPORT.json'));
assert.equal(hash(profileBytes),audit.profileSha256);
assert.equal(hash(Buffer.from(JSON.stringify(profile))),audit.canonicalProfileSha256);
assert.equal(hash(fixtureBytes),audit.requestedGeometrySourceHash);
assert.deepEqual(profile.eventGeometry.geometry,fixture.intent.line.geometry);
assert.equal(fixture.intent.line.geometry.coordinates.length,92);
const candidates=generateDetailExtentCandidates({eventGeometry:fixture.intent.line.geometry,
 eventAnchor:regional.anchor.coordinates,currentBounds:camera.intent.finalExtent,output:[1080,1920],
 safeArea:on.frames.at(-1).placement.safeArea,desiredScreenCoverageRange:audit.readabilityRequest.axisCoverage,linePaddingPixels:5.75});
assert.deepEqual(candidates.map(c=>c.bounds),audit.candidates.map(c=>c.bounds));
const outcome=selectSafeDetailExtent({candidates,profile});
assert.equal(outcome.status,'DETAIL_DATA_ADMISSION_BLOCKED');
assert.equal(outcome.safeDetailExtent,null);
assert.ok(outcome.audits.every(a=>a.status==='DATA_LIMITED'));
assert.ok(outcome.audits.every(a=>a.checks.find(c=>c.name==='HEIGHT_SOURCE_CONTRACT')?.status==='PASS'));
assert.ok(outcome.audits.every(a=>a.checks.find(c=>c.name==='PROFILE_EVIDENCE_MODE')?.status==='DATA_LIMITED'));
const record={schema:'FINAL_DETAIL_AUDIT_REPLAY_V1',status:'PASS',admissionDecision:outcome.status,
 replayedAtUtc:new Date().toISOString(),profileSha256:hash(profileBytes),canonicalProfileSha256:audit.canonicalProfileSha256,
 admissionModuleSha256:hash(await readFile(path.join(engine,'web/map_infographic_v1/detail_data_profile_v1.mjs'))),
 testSourceSha256:hash(await readFile(path.join(engine,'tests/detail_data_profile_v1.test.mjs'))),
 requestedGeometrySourceHash:hash(fixtureBytes),coordinateCount:92,segmentCount:91,
 candidatesRecomputedFromProtectedInputs:true,storedProposalBoundsIdentical:true,geometryUnchanged:true,
 allCandidateDecisions:outcome.audits.map(a=>({candidateId:a.candidate.id,status:a.status})),
 finalChecks:outcome.audits.map(a=>({candidateId:a.candidate.id,checks:a.checks,missingData:a.missingData,violations:a.violations})),
 safeDetailExtent:null,staticProofCreated:false,cameraAnimationStarted:false,eventAnimationStarted:false,
 evidenceTrustBoundary:'This pure API consumes trusted verification evidence. No new source payload or fresh native layout was verified here.'};
await writeFile(path.join(root,'evidence/FINAL_AUDIT_REPLAY.json'),JSON.stringify(record,null,2)+'\n');
// Refresh final check records while retaining provenance of the earlier safe blocked snapshot.
audit.finalReplayReference='evidence/FINAL_AUDIT_REPLAY.json';
audit.admissionModuleSha256=record.admissionModuleSha256;
audit.audits=outcome.audits;
audit.finalChecksReplayedAtUtc=record.replayedAtUtc;
await writeFile(path.join(root,'evidence/DETAIL_QUALITY_AUDIT.json'),JSON.stringify(audit,null,2)+'\n');
console.log(JSON.stringify({status:record.status,admissionDecision:record.admissionDecision,candidates:record.allCandidateDecisions}));
