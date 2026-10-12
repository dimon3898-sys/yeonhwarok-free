// The review grades below are explicit inspection findings, never inferred from survey certificates.
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {selectVisualDetailExtent,createEventDetailFramingRequest} from '../../web/map_infographic_v1/visual_detail_admission_v1.mjs';
import {compileCameraDetailApproach,assessCameraDetailMotion} from '../../web/map_infographic_v1/camera_detail_approach_adapter_v1.mjs';
import {compileEventIntent} from '../../web/map_infographic_v1/event_contract_v1.mjs';
import {compileEventPlan} from '../../web/map_infographic_v1/event_timeline_v1.mjs';
import {savedCandidateInputs,json,sha} from './visual_runtime.mjs';
const {root,fixture,candidates}=await savedCandidateInputs();
const probes=await json(path.join(root,'evidence/static-probes-r2/REPORT.json'));
const review=await json(path.join(root,'evidence/VISUAL_STATIC_REVIEW.json'));
const evidenceByCandidate={};
for(const row of probes.candidates){
 const observed=review.candidates[row.candidate.id],capture=row.event??row.native;
 assert.ok(capture,'Actual native candidate PNG required');
 const bytes=await readFile(path.join(root,'evidence/static-probes-r2',capture.file));
 assert.equal(sha(bytes),capture.sha256);
 const d=capture.diagnostic,ev=d.event;
 const audit=(await json(path.join(root,'../suez-detail-data-admission-v1/evidence/DETAIL_QUALITY_AUDIT.json'))).candidates.find(c=>c.candidateId===row.candidate.id);
 const hidden=d.hiddenGeographicLabels.map(item=>({role:item.role,reason:item.reason,
  originalAnchorPreserved:item.anchorPreserved,stylePreserved:item.stylePreserved}));
 evidenceByCandidate[row.candidate.id]={evidenceKind:'ACTUAL_NATIVE_RENDER',
  render:{verified:true,width:1080,height:1920,sha256:capture.sha256,byteLength:bytes.length,
   candidateBounds:row.candidate.bounds,geometryBinding:row.candidate.geometryBinding},
  visual:observed.visual,semantic:review.semanticIntegrity,
  protection:{cameraV5:true,eventV2:true,rendererVisual:true,geometry:true,marker:true},
  layout:{verified:Boolean(row.event),candidateBounds:row.candidate.bounds,geometryBinding:row.candidate.geometryBinding,
   metricBounds:ev.placement?.roi??null,protectedGraphics:ev.protectedGraphics.map(item=>({kind:item.kind,bounds:item.box})),
   hiddenGeographicLabels:hidden},
  quality:{gisAbsoluteAccuracyCertified:false,coastAlignmentMeasured:false,nativeTexelToScreenPixelRatio:audit.currentRegisteredTerrainRatio},
  warnings:observed.warnings??[]};
 if(row.event){assert.equal(capture.protected_changed_pixels,0);assert.equal(capture.marker_changed_pixels,0);assert.equal(capture.outside_roi_changed_pixels,0);}
}
const selection=selectVisualDetailExtent({candidates,eventGeometry:fixture.intent.line.geometry,evidenceByCandidate});
assert.equal(selection.status,'VISUAL_DETAIL_ADMITTED');
const current=candidates[0],request=createEventDetailFramingRequest({eventGeometry:fixture.intent.line.geometry,
 eventAnchor:current.eventAnchor,safeArea:current.safeArea,protectedGraphics:evidenceByCandidate[current.id].layout.protectedGraphics,
 currentCameraState:{bounds:current.bounds,output:current.output},desiredScreenCoverageRange:current.desiredScreenCoverageRange,
 evidenceByCandidate,detailAdmission:selection});
const eventPlan=compileEventPlan(compileEventIntent(fixture.intent),fixture.timeline);
const adapter=compileCameraDetailApproach({currentCamera:{flatBounds:current.bounds},framingRequest:request,
 eventPlan,eventGeometry:fixture.intent.line.geometry,safeArea:current.safeArea});
const motion=assessCameraDetailMotion(adapter);assert.equal(motion.status,'PASS');
for(const [name,value] of [['VISUAL_ADMISSION.json',selection],['fixtures/DETAIL_REQUEST.json',request],
 ['fixtures/DETAIL_ADAPTER_PLAN.json',adapter],['evidence/MOTION_CONTINUITY.json',motion]])
 await writeFile(path.join(root,name),JSON.stringify(value,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({selected:selection.selectedCandidate.id,status:selection.status,
 coverage:selection.selectedCandidate.axisCoverage,projectedLength:selection.selectedCandidate.projectedLengthPixels,
 totalFrames:adapter.totalFrames,lockFrame:adapter.detailLockFrame,motion:motion.status}));
