/** Opt-in CPU-only single-layer binary snapshot. No renderer or PNG policy changes. */
import path from 'node:path';
import {createHash} from 'node:crypto';
import {readPinnedServerFile} from './candidate_asset_snapshot.mjs';
export const BINARY_LAYER_LIMIT_BYTES=71000064;
export const BINARY_REQUEST_SCHEMA='WORLD_ENGINE_BINARY_LAYER_PREPARATION_V3';
const check=(v,c)=>{if(!v)throw Error(c);};
const sha=b=>createHash('sha256').update(b).digest('hex');
const freeze=v=>{if(v&&typeof v==='object'){Object.values(v).forEach(freeze);Object.freeze(v);}return v;};
export async function prepareRegisteredBinaryLayerV3({request,registry}={}){
 const input=Object.freeze({schema:request?.schema,registrationId:request?.registrationId,layerId:request?.layerId,camera:freeze(structuredClone(request?.camera))});
 check(request&&Object.keys(request).sort().join(',')==='camera,layerId,registrationId,schema'&&input.schema===BINARY_REQUEST_SCHEMA&&[input.registrationId,input.layerId].every(s=>typeof s==='string'&&/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(s)),'BINARY_REQUEST_INVALID');
 check(registry instanceof Map&&registry.has(input.registrationId),'BINARY_SERVER_REGISTRATION_REQUIRED');
 const camera={projection:'REGIONAL_EQUIRECTANGULAR',projectionMode:null,updateMethod:'updateCamera',width:1080,height:1920};
 check(input.camera&&Object.keys(input.camera).length===5&&Object.entries(camera).every(([k,v])=>input.camera[k]===v),'BINARY_CONTROLLED_CAMERA_REQUIRED');
 const registration=freeze(structuredClone(registry.get(input.registrationId)));
 check(registration&&Object.keys(registration).sort().join(',')==='descriptor,root','BINARY_REGISTRATION_INVALID');
 const receiptBytes=await readPinnedServerFile(registration.root,registration.descriptor.localFile,registration.descriptor);
 const receipt=JSON.parse(receiptBytes.toString('utf8'));
 check(receipt.schema==='WORLD_ENGINE_BINARY_LAYER_DESCRIPTORS_V3'&&receipt.renderAllowed===false&&receipt.productionAdmitted===false&&Array.isArray(receipt.layers),'BINARY_DESCRIPTOR_INVALID');
 check(receipt.binaryLayerLimitBytes===BINARY_LAYER_LIMIT_BYTES&&receipt.camera&&Object.keys(receipt.camera).length===5&&Object.entries(camera).every(([k,v])=>receipt.camera[k]===v),'BINARY_DESCRIPTOR_CAMERA_OR_CAP_MISMATCH');
 const readReceipt=async pin=>{check(pin&&typeof pin.sourcePath==='string'&&path.isAbsolute(pin.sourcePath)&&path.normalize(pin.sourcePath)===pin.sourcePath,'BINARY_RECEIPT_PIN_REQUIRED');return JSON.parse((await readPinnedServerFile(path.dirname(pin.sourcePath),path.basename(pin.sourcePath),pin)).toString('utf8'));};
 const range=await readReceipt(receipt.sourceRangeReceipt),eligibility=await readReceipt(receipt.eligibilityReceipt);
 check(range.schema==='PRESERVED_SOURCE_ELEVATION_RANGE_V1'&&range.productionAdmitted===false&&Number.isFinite(range.minimumMetres)&&Number.isFinite(range.maximumMetres)&&range.minimumMetres<=range.maximumMetres&&Math.max(Math.abs(range.minimumMetres),Math.abs(range.maximumMetres))<=1000000&&Array.isArray(range.atlasRows),'BINARY_SOURCE_RANGE_INVALID');
 const matches=receipt.layers.filter(l=>l.id===input.layerId);check(matches.length===1,'BINARY_LAYER_NOT_UNIQUE');
 const layer=matches[0];check(layer.eligibilityStatus==='FULL_DERIVATIVE_FOOTPRINT_CPU_BOUND_NOT_GPU_QUALIFIED','BINARY_ELIGIBILITY_STATUS_INVALID');
 const roles=['height','validity','terrainEligibility'];let total=0;
 for(const role of roles){const a=layer.assets?.[role];check(a&&Number.isInteger(a.width)&&a.width>0&&a.width<=4096&&Number.isInteger(a.height)&&a.height>0&&a.height<=4096,'BINARY_DIMENSIONS_INVALID');check(a.format===(role==='height'?'FLOAT32_LE':'UINT8_BINARY')&&a.bytes===a.width*a.height*(role==='height'?4:1),'BINARY_ENCODING_INVALID');check(a.rowOrder==='NORTH_TO_SOUTH'&&a.grid&&Array.isArray(a.grid.firstSampleCenter)&&a.grid.firstSampleCenter.length===2&&a.grid.firstSampleCenter.every(Number.isFinite)&&Array.isArray(a.grid.pixelSpacingDegrees)&&a.grid.pixelSpacingDegrees.length===2&&a.grid.pixelSpacingDegrees.every(x=>Number.isFinite(x)&&x>0),'BINARY_GRID_INVALID');check(typeof a.sourcePath==='string'&&path.isAbsolute(a.sourcePath)&&path.normalize(a.sourcePath)===a.sourcePath,'BINARY_SOURCE_PATH_INVALID');total+=a.bytes;}
 check(total<=BINARY_LAYER_LIMIT_BYTES,'BINARY_LAYER_LIMIT');
 const h=layer.assets.height,v=layer.assets.validity;check(h.width===v.width&&h.height===v.height&&JSON.stringify(h.grid)===JSON.stringify(v.grid),'BINARY_VALIDITY_GRID_MISMATCH');
 const e=layer.assets.terrainEligibility;check(e.width===h.width&&e.height===h.height&&JSON.stringify(e.grid)===JSON.stringify(h.grid),'BINARY_ELIGIBILITY_HEIGHT_GRID_MISMATCH');
 const rangeRow=range.atlasRows.filter(r=>r.heightSha256===h.sha256);check(rangeRow.length===1,'BINARY_HEIGHT_NOT_RANGE_BOUND');
 // Receipt schema and full-envelope binding validated below before any large binary read.
 validateEligibilityReceipt(eligibility,receipt,layer);
 const buffers=new Map();
 for(const role of roles){const a=layer.assets[role],b=await readPinnedServerFile(path.dirname(a.sourcePath),path.basename(a.sourcePath),a);buffers.set(role,b);}
 const heights=buffers.get('height'),valid=buffers.get('validity'),eligible=buffers.get('terrainEligibility');
 let validCount=0;
 for(let i=0;i<valid.length;i++){check(valid[i]===0||valid[i]===1,'BINARY_VALIDITY_NOT_BINARY');const x=heights.readFloatLE(4*i);check(valid[i]===1?Number.isFinite(x):Number.isNaN(x),'BINARY_HEIGHT_VALIDITY_MISMATCH');if(valid[i]===1)check(x>=range.minimumMetres&&x<=range.maximumMetres,'BINARY_HEIGHT_OUTSIDE_SOURCE_RANGE');validCount+=valid[i];}
 for(const x of eligible)check(x===0||x===1,'BINARY_ELIGIBILITY_NOT_BINARY');
 const descriptors=Object.fromEntries(roles.map(role=>{const{sourcePath,...a}=layer.assets[role];return[role,{...a,assetKey:'sha256/'+a.sha256}];}));
 const identity={schema:input.schema,registrationId:input.registrationId,layerId:input.layerId,descriptorSha256:sha(receiptBytes),sourceRangeReceiptSha256:receipt.sourceRangeReceipt.sha256,eligibilityReceiptSha256:receipt.eligibilityReceipt.sha256,camera,sourceRangeMetres:[range.minimumMetres,range.maximumMetres],assets:descriptors};
 const result={status:'CPU_BINARY_SNAPSHOT_ONLY',dataIdentity:freeze(identity),sourceQualificationSHA256:sha(Buffer.from(JSON.stringify(identity))),snapshotBytes:total,binaryLayerLimitBytes:BINARY_LAYER_LIMIT_BYTES,pngLimitBytesUnchanged:67108864,validHeightSamples:validCount,eligibilityStatus:layer.eligibilityStatus,executingCodeIdentity:'UNVERIFIED',cacheReuseAllowed:false,renderAllowed:false,productionAdmitted:false,imageBuildAllowed:false,browserUploadQualified:false,allLayerResidencyClaimed:false};
 Object.defineProperty(result,'binarySnapshot',{enumerable:false,value:Object.freeze({read(role){check(buffers.has(role),'BINARY_ROLE_NOT_REGISTERED');return Buffer.from(buffers.get(role));}})});
 return Object.freeze(result);
}

function validateEligibilityReceipt(eligibility,receipt,layer){
 check(eligibility.algorithm==='DERIVATIVE_RADIUS3_PROVIDER_MARGIN_CLOSED_ENDPOINT_NEXTAFTER'&&eligibility.closedEndpointCoverage===true&&eligibility.endpointRule==='OUTWARD_NEXTAFTER_EACH_ENVELOPE_BOUND_BEFORE_CELL_INTERSECTION','BINARY_CLOSED_ENDPOINT_REQUIRED');
 check(eligibility.schema==='LAND_DERIVATIVE_ELIGIBILITY_V3'&&eligibility.status==='FULL_DERIVATIVE_FOOTPRINT_CPU_BOUND_NOT_GPU_QUALIFIED'&&eligibility.maskAnchor==='FLOOR_OF_HEIGHT_SAMPLE_COORDINATE'&&eligibility.radius===3&&eligibility.maskEncoding==='UINT8_0_OR_1'&&eligibility.geometricRadiusBoundFrames===600&&eligibility.nativeLandGroundTruthClaim===false&&eligibility.sourceUnknownOrWaterConvertedToLand===false,'BINARY_FOOTPRINT_CONTRACT_INVALID');
 const camera={projection:'REGIONAL_EQUIRECTANGULAR',updateMethod:'updateCamera',width:1080,height:1920,rotationAllowed:false,updateSimilarityAllowed:false};
 check(eligibility.camera&&Object.keys(eligibility.camera).length===6&&Object.entries(camera).every(([k,v])=>eligibility.camera[k]===v),'BINARY_ELIGIBILITY_CAMERA_MISMATCH');
 check(eligibility.elevationRangeContractSha256===receipt.sourceRangeReceipt.sha256,'BINARY_RANGE_RECEIPT_UNBOUND');
 const matches=eligibility.rows?.filter(r=>r.id===layer.eligibilityReceiptLayerId);check(matches?.length===1,'BINARY_ELIGIBILITY_ROW_REQUIRED');
 const r=matches[0],h=layer.assets.height,v=layer.assets.validity,e=layer.assets.terrainEligibility;
 check(r.heightSha256===h.sha256&&r.heightValidSha256===v.sha256&&r.sha256===e.sha256&&r.bytes===e.bytes&&r.dimensions[0]===h.width&&r.dimensions[1]===h.height&&(h.grid.bounds===undefined||JSON.stringify(r.bounds)===JSON.stringify(h.grid.bounds)),'BINARY_ELIGIBILITY_ASSETS_UNBOUND');
 check(Array.isArray(r.bounds)&&r.bounds.length===4&&r.bounds.every(Number.isFinite)&&(h.grid.crs===undefined||h.grid.crs==='EPSG:4326'),'BINARY_BOUND_GRID_INVALID');
 const[west,south,east,north]=r.bounds,spacing=[(east-west)/h.width,(north-south)/h.height],first=[west+spacing[0]/2,north-spacing[1]/2];
 check(spacing.every(x=>x>0)&&spacing.every((x,i)=>Math.abs(x-h.grid.pixelSpacingDegrees[i])<1e-12)&&first.every((x,i)=>Math.abs(x-h.grid.firstSampleCenter[i])<1e-10),'BINARY_BOUND_GRID_MISMATCH');
}
