/** CPU assertions for signature + capture admission contracts; no GPU/browser is started. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {captureSignature,assertAstraFrame} from '../capture_astra.mjs';
import {originalEncodingArgs} from '../../rtx-gpu-package-v1/hardware_render.mjs';
const h=value=>value.repeat(64);
const plan={sourceSignature:h('1'),activationSha256:h('2'),bundleManifestSha256:h('3'),profile:{profileId:'ASTRA_GPU_ACTIVATION_V1'}};
const admission={probe:{profile_fingerprint:h('4'),browser_version:'CPU_TEST_ONLY'},allocation:{model:'NOT_GPU_EVIDENCE',driver_version:'0'}};
const bindings={plan,admission,stagingReceiptSha256:h('5'),extensionManifestSha256:h('6')};
function captured(frame=12) {return {raw_rgba_sha256:h('7'),diagnostic:{frame,
 gpu:{glError:0,factoryCount:1,nativeDrawCount:1},protection:{sourceUnchanged:true,nativeVisualCoreUnchanged:true,
 sourceGeometryUnchanged:true,displayedNativeForeground:false},surveyAdmissionPreserved:true,nativeEndpointGuardActive:true,
 territory:{geometryUnchanged:true,continuousComplementaryOwnership:true,routeVisuals:false,arrowVisuals:false,standaloneFrontLine:false},
 frontierLight:{realControlBoundaryDerived:true,standaloneDecorativeLine:false},presentation:{cornerSamplesInside:true},
 units:{safeAreaViolations:[],criticalCollisions:[],noText:true,nationalFlags:true},cameraLocked:false,
 terrain:{astra:{selected:true,drawPasses:3,actualMaterialFactorySelected:true,sourceMaterialBeforeTerritory:true,combinedOutputTexture:true,
 actualNativeCoverage:true,gpuUploadExecuted:true,testOnly:false,selectedSourceRoles:['surfaceTexture','terrain','bathymetry']}}}};}
test('ASTRA signature deterministic and distinct from prior source-only capture',()=>{
 const first=captureSignature(bindings);assert.match(first,/^[a-f0-9]{64}$/);assert.equal(first,captureSignature(bindings));
 for(const key of ['sourceSignature','activationSha256','bundleManifestSha256'])
  assert.notEqual(first,captureSignature({...bindings,plan:{...plan,[key]:h('a')}}));
 assert.notEqual(first,captureSignature({...bindings,extensionManifestSha256:h('b')}));
 assert.notEqual(first,captureSignature({...bindings,stagingReceiptSha256:h('c')}));
 assert.notEqual(first,captureSignature({...bindings,admission:{...admission,allocation:{...admission.allocation,driver_version:'1'}}}));
});
test('ASTRA signature rejects missing bundle or extension hash',()=>{
 assert.throws(()=>captureSignature({...bindings,extensionManifestSha256:undefined}));
 assert.throws(()=>captureSignature({...bindings,plan:{...plan,bundleManifestSha256:'invalid'}}));
});
test('actual capture contract requires original protected fields and new material selection',()=>{
 assertAstraFrame(captured(),12);for(const key of ['actualMaterialFactorySelected','sourceMaterialBeforeTerritory',
 'combinedOutputTexture','actualNativeCoverage','gpuUploadExecuted']){
  const value=captured();value.diagnostic.terrain.astra[key]=false;assert.throws(()=>assertAstraFrame(value,12));
 }
 const value=captured();value.diagnostic.terrain.astra.testOnly=true;assert.throws(()=>assertAstraFrame(value,12));
});
test('missing source and existing graphic corruption cannot pass capture',()=>{
 const value=captured();value.diagnostic.terrain.astra.selectedSourceRoles=['terrain','surfaceTexture'];
 assert.throws(()=>assertAstraFrame(value,12));
 const corrupt=captured();corrupt.diagnostic.units.criticalCollisions=[1];assert.throws(()=>assertAstraFrame(corrupt,12));
 const wrong=captured();wrong.diagnostic.territory.arrowVisuals=true;assert.throws(()=>assertAstraFrame(wrong,12));
});
test('approved encoding contract reused for 150 silent frames',()=>{
 const args=originalEncodingArgs('/fixture/frames','/fixture/output.mp4');
 assert.equal(args[args.indexOf('-frames:v')+1],'150');assert.ok(args.includes('-an'));
 assert.equal(args[args.indexOf('-framerate')+1],'30');assert.equal(args[args.indexOf('-crf')+1],'16');
});
