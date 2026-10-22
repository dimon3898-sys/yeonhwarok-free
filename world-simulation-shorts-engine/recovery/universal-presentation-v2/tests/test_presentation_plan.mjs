import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {validatePresentation,boundsFromKeyframe,reprojectFlowPresentation,assertMovingProjectionAdmission,projectBounds,unprojectBounds} from '../presentation_plan.mjs';
import {compileFlowIntent,compileFlowPlan,compileFlowRoute,evaluateFlowFrame} from '../../../web/map_infographic_v1/flow_core_v2.mjs';

const scene={timing:{fps:30,total_frames:90},routes:[{id:'route'}],locations:[{id:'location'}],time_steps:[{id:'state0'},{id:'state1'}]};
const keys=()=>({camera:{mode:'KEYFRAMES',keyframes:[{frame:0,center:[0,0],zoom:.8},{frame:30,center:[.2,.1],zoom:.6},{frame:89,center:[0,0],zoom:1}]}});
const camera={cameraLocked:false,settle:{locked:false}},modelCamera={cameraLocked:true,settle:{locked:true}};
const sourceGeometry={type:'LineString',coordinates:[[0,0],[1,1]]},project=p=>[400+p[0]*100,900-p[1]*100];
const source={source_type:'SYNTHETIC_TEST',source_reference:'https://example.org/fictional-fixture',verification_status:'SYNTHETIC_TEST'};
const intent=compileFlowIntent({data_mode:'SYNTHETIC_TEST',route_geometry:sourceGeometry,route_source:source,direction:'FORWARD',start_anchor:[0,0],end_anchor:[1,1],object_role:'AIRCRAFT',object_graphic:{width_px:46,height_px:28,polygons:[{points:[[0,-.5],[.5,.5],[-.5,.5]],color:[1,1,1,1]}]}});
const primitive=compileFlowRoute(intent,{project});
function admission(extra={}){return assertMovingProjectionAdmission({primitive,controls:{objectVisible:true,objectPosition:[450,850],departurePulse:{active:false},arrivalPulse:{active:false}},camera,modelCamera,safeArea:[100,100,980,1820],sourceBounds:[-20,-30,20,30],currentBounds:[-10,-20,10,20],project,sourceGeometry,...extra});}

test('explicit camera accepts zoom-out followed by closest approved endpoint',()=>assert.equal(validatePresentation(keys(),{scene}).camera.keyframes.length,3));
test('zoom never silently exceeds protected closest viewport',()=>{const x=keys();x.camera.keyframes[0].zoom=1.1;assert.throws(()=>validatePresentation(x,{scene}),/RANGE_INVALID/);});
test('final endpoint admission is explicit',()=>{const x=keys();x.camera.keyframes[2].zoom=.5;assert.throws(()=>validatePresentation(x,{scene}),/FINAL_ENDPOINT_CLOSEST/);});
test('complete integer-frame keyframe coverage required',()=>{const x=keys();x.camera.keyframes[0].frame=1;assert.throws(()=>validatePresentation(x,{scene}),/COMPLETE_KEYFRAME/);});
test('camera unknown fields reject hidden unused effects',()=>{const x=keys();x.camera.orbit=1;assert.throws(()=>validatePresentation(x,{scene}),/UNKNOWN_FIELD/);});
test('source route reference required for follow',()=>assert.throws(()=>validatePresentation({camera:{mode:'ROUTE_FOLLOW',routeId:'invented'}},{scene}),/SUPPLIED_ROUTE/));
test('bounded route follow retains requested source route',()=>{const x=validatePresentation({camera:{mode:'ROUTE_FOLLOW',routeId:'route'}},{scene});assert.equal(x.camera.routeId,'route');assert.equal(x.camera.zoom,.75);});
test('state palette colors require actual state IDs',()=>assert.throws(()=>validatePresentation({...keys(),territoryColors:{invented:[1,0,0,.3]}},{scene}),/STATE_COLOR_BINDING/));
test('state palette survives without source fact mutation',()=>{const x=keys();x.territoryColors={state0:[1,0,0,.32],state1:[0,0,1,.35]};assert.deepEqual(validatePresentation(x,{scene}).territoryColors,x.territoryColors);});
test('highlight must reference supplied geographic location',()=>assert.throws(()=>validatePresentation({...keys(),highlights:[{id:'h',locationId:'missing',startFrame:0,endFrame:20}]},{scene}),/LOCATION_REQUIRED/));
test('highlight time is bounded and cannot collapse to one frame',()=>assert.throws(()=>validatePresentation({...keys(),highlights:[{id:'h',locationId:'location',startFrame:10,endFrame:11}]},{scene}),/TIMING_INVALID/));
test('no dissolve feature is accepted as metadata',()=>assert.throws(()=>validatePresentation({...keys(),transitions:[{type:'DISSOLVE',frame:90}]},{scene}),/CUT_REQUIRED/));
test('bbox zoom preserves uniform source aspect',()=>assert.deepEqual(boundsFromKeyframe({center:[1,2],zoom:.5},[-1,-2,1,2]),[-1,-2,3,6]));
test('coordinate projection round trip preserves supplied geography',()=>{const b=[-18,-30,20,33],p=[3,-7];const round=unprojectBounds(b,projectBounds(b,p));assert.ok(Math.hypot(round[0]-p[0],round[1]-p[1])<1e-12);});
test('moving projection does not forge old Event admission',()=>{const x=admission();assert.equal(x.oldEventAdmissionClaimed,false);assert.equal(x.actualCameraLocked,false);});
test('old camera locked state cannot masquerade as current movement',()=>assert.throws(()=>admission({camera:modelCamera}),/ACTUAL_MOVING_CAMERA/));
test('source coverage checked against current viewport',()=>assert.throws(()=>admission({currentBounds:[-21,-20,10,20]}),/SOURCE_COVERAGE/));
test('stale projected route is rejected',()=>assert.throws(()=>admission({project:p=>[p[0],p[1]]}),/PROJECTION_BINDING/));
test('whole route footprint is required, no clipping hidden',()=>assert.throws(()=>admission({safeArea:[450,100,980,1820]}),/ROUTE_FULL_FOOTPRINT/));
test('actual current marker reservation is retained',()=>assert.deepEqual(admission({protectedGraphics:[{kind:'MARKER',box:[300,700,350,750]}]}).protectedReservations,[{kind:'MARKER',box:[300,700,350,750]}]));
test('invalid protected marker box blocks movement',()=>assert.throws(()=>admission({protectedGraphics:[{kind:'MARKER',box:[0,0,30,30]}]}),/PROTECTED_RESERVATION/));
test('current line reveal is recomputed rather than copied from model projection',()=>{
 const model={headingLookAheadPixels:12,objectFraction:.4,directionalFraction:.5,routeFraction:.7,departurePulse:{active:false},arrivalPulse:{active:false},eventControls:{readiness:{admitted:true}},routeReveal:{path:[[999,999]],roi:[999,999,1000,1000]}};
 const before=JSON.stringify(model),controls=reprojectFlowPresentation({modelControls:model,primitive,flowIntent:intent});
 assert.notDeepEqual(controls.routeReveal.path,model.routeReveal.path);assert.deepEqual(controls.routeReveal.path[0],primitive.screenCoordinates[0]);assert.equal(controls.eventControls.readinessScope,'MODEL_FIXED_V5_ONLY_NOT_CURRENT_MOVING_CAMERA');assert.equal(JSON.stringify(model),before);
});
test('moving source anchors remain authored and geometric fractions remain unchanged',()=>{
 const model={headingLookAheadPixels:12,objectFraction:.4,directionalFraction:.5,routeFraction:.7,departurePulse:{active:false},arrivalPulse:{active:false},eventControls:{}},before=JSON.stringify(primitive);
 const controls=reprojectFlowPresentation({modelControls:model,primitive,flowIntent:intent});assert.equal(controls.objectFraction,.4);assert.equal(controls.routeFraction,.7);assert.deepEqual(controls.departurePulse.anchor,primitive.screenCoordinates[0]);assert.deepEqual(controls.arrivalPulse.anchor,primitive.screenCoordinates.at(-1));assert.equal(JSON.stringify(primitive),before);
});
