import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {HERE,validateGates,validateStyle,validateLayoutProfile,parseCaptureArguments} from '../capture_recovery.mjs';

const clone=x=>structuredClone(x);
function fixture(){
 const asset={path:path.relative(path.resolve(HERE,'../../..'),path.join(HERE,'assets/terrain/test.png')),
  url:'/recovery-assets/test.png',sha256:'1'.repeat(64),bytes:100,bounds:[90,-6,126,46],dimensions:[2160,3120],
  pixelSpacing:[1/60,1/60],CRS:'EPSG:4326',classification:'BAKED HILLSHADE',sourceOriginalSHA256:'2'.repeat(64)};
 return{totalFrames:180,sourceStyle:{schema:'WORLD_ENGINE_G2_MAP_STYLE_RECEIPT_V1',styleId:'NE1_SOURCE_NATIVE_COVERAGE',terrainAsset:asset},
  runtimePayload:{nativePlan:{assets:{terrain:{...asset,file:asset.path}}},cameraSchedule:Array.from({length:180},(_,frame)=>({frame,flatBounds:[93,-3,123,43]}))}};
}
test('full capture cannot start until all three required gates pass',()=>{
 const gates={baselineCommit:'3913ad8e90885c769cdccc91f396072d83e356f2',historicalG3:'BLOCKED',paidGpuExecuted:false,phaseA:{status:'PASS'},phaseB:{status:'PASS'},phaseC:{status:'PASS'}};
 assert.equal(validateGates(gates),true);
 for(const name of ['phaseA','phaseB','phaseC']){const invalid=clone(gates);invalid[name].status='FAIL';assert.throws(()=>validateGates(invalid),new RegExp(name.toUpperCase()));}
 assert.throws(()=>validateGates({...gates,baselineCommit:'NOT_THE_BASELINE'}),/BASELINE/);
});
test('bounded technical probe requires phases A and B and does not imply phase D permission',()=>{
 const gates={baselineCommit:'3913ad8e90885c769cdccc91f396072d83e356f2',historicalG3:'BLOCKED',paidGpuExecuted:false,phaseA:{status:'PASS'},phaseB:{status:'PASS'},phaseC:{status:'NOT_STARTED'}};
 assert.equal(validateGates(gates,{fullCapture:false}),true);assert.throws(()=>validateGates(gates),/PHASEC/);
});
test('truthful wide source covers every camera with a genuine native gutter',()=>{
 const value=validateStyle(fixture());assert.equal(value.minimumSourceGutterPixels,180);assert.equal(value.allActualCameraViewportsCovered,true);
});
test('a moved or zoomed camera cannot exit source coverage unnoticed',()=>{
 const invalid=fixture();invalid.runtimePayload.cameraSchedule[179].flatBounds=[89,-3,123,43];assert.throws(()=>validateStyle(invalid),/COMPLETE_VIEWPORT/);
 const noGutter=fixture();noGutter.runtimePayload.cameraSchedule[90].flatBounds=[90,-3,123,43];assert.throws(()=>validateStyle(noGutter),/COMPLETE_VIEWPORT/);
});
test('false dimensions, CRS and changed plan bindings are rejected',()=>{
 const invalid=fixture();invalid.sourceStyle.terrainAsset.dimensions[0]++;assert.throws(()=>validateStyle(invalid),/PIXEL_ALIGNMENT/);
 const wrongCRS=fixture();wrongCRS.sourceStyle.terrainAsset.CRS='EPSG:3857';assert.throws(()=>validateStyle(wrongCRS),/TRUTHFUL_NE1/);
 const changedPlan=fixture();changedPlan.runtimePayload.nativePlan.assets.terrain.sha256='3'.repeat(64);assert.throws(()=>validateStyle(changedPlan),/PLAN_STYLE_BINDING/);
});
test('overzoom and antimeridian or polar out-of-range source coverage fail explicitly',()=>{
 const tiny=fixture();tiny.runtimePayload.cameraSchedule[0].flatBounds=[100,10,110,20];assert.throws(()=>validateStyle(tiny),/PIXEL_BUDGET/);
 for(const b of [[170,-6,-170,46],[90,-91,126,46],[90,-6,181,46]]){const invalid=fixture();invalid.sourceStyle.terrainAsset.bounds=b;assert.throws(()=>validateStyle(invalid),/GEOGRAPHIC_SOURCE_BOUNDS/);}
});
test('asset URLs cannot point to overlays, external hosts or paths outside the preserved or new explicit terrain asset roots',()=>{
 for(const [key,value]of [['url','https://example.invalid/frame.png'],['path','../original/terrain.png'],['path','world-simulation-shorts-engine/web/flat_assets/existing.png']]){
  const invalid=fixture();invalid.sourceStyle.terrainAsset[key]=value;assert.throws(()=>validateStyle(invalid),/PATH_REQUIRED|ASSET_ROUTE/);
 }
});
test('worker compatibility arguments are exact and duplicate/unknown switches fail',()=>{
 const args=['--plan=/private/plan.json','--expected-sha256='+'1'.repeat(64),'--output-root=/new/output','--cache-root=/private/cache'];
 assert.equal(parseCaptureArguments(args).planFile,'/private/plan.json');assert.throws(()=>parseCaptureArguments([...args,'--plan=/changed']),/ARGUMENT_INVALID/);
 assert.throws(()=>parseCaptureArguments([...args,'--gpu=auto']),/ARGUMENT_INVALID/);assert.throws(()=>parseCaptureArguments(args.slice(1)),/ARGUMENT_MISSING/);
});

test('paid/historical authorization cannot be introduced by a gatefile',()=>{
 const gates={baselineCommit:'3913ad8e90885c769cdccc91f396072d83e356f2',historicalG3:'BLOCKED',paidGpuExecuted:false,phaseA:{status:'PASS'},phaseB:{status:'PASS'},phaseC:{status:'PASS'}};
 for(const key of ['historicalG3','paidGpuExecuted']){const changed=clone(gates);changed[key]=key==='historicalG3'?'PASS':true;assert.throws(()=>validateGates(changed),/NONHISTORICAL_FREE/);}
});
test('preserved source assets can be reused without copy or mutation',()=>{
 const fixtureValue=fixture(),asset=fixtureValue.sourceStyle.terrainAsset;
 asset.path=path.relative(path.resolve(HERE,'../../..'),path.resolve(HERE,'../g2-renderer-recovery-v1/assets/terrain/test.png'));
 fixtureValue.runtimePayload.nativePlan.assets.terrain.file=asset.path;
 assert.equal(validateStyle(fixtureValue).assetRoot,path.resolve(HERE,'../g2-renderer-recovery-v1/assets/terrain'));
});

test('only the explicit bounded opt-in layout profile is accepted for this lane',()=>{
 const value={runtimePayload:{nativePlan:{scale:{information:{location:true}},layout:{measured:{location:{gap:18}},locationPlacement:{schema:'WORLD_ENGINE_LOCATION_PLACEMENT_POLICY_V1',mode:'BOUNDED_GAP_SEARCH',maxGap:216,step:16}}}}};
 assert.equal(validateLayoutProfile(value).maxGap,216);
 for(const key of ['maxGap','step','schema']){const invalid=clone(value);invalid.runtimePayload.nativePlan.layout.locationPlacement[key]='wrong';assert.throws(()=>validateLayoutProfile(invalid),/EXPLICIT_GENERIC_LAYOUT/);}
 const silent=clone(value);silent.runtimePayload.nativePlan.scale.information.location=false;assert.throws(()=>validateLayoutProfile(silent),/ADMISSION_MUST_REMAIN/);
 const unknown=clone(value);unknown.runtimePayload.nativePlan.layout.locationPlacement.skipCollisions=true;assert.throws(()=>validateLayoutProfile(unknown),/EXPLICIT_GENERIC_LAYOUT/);
});
