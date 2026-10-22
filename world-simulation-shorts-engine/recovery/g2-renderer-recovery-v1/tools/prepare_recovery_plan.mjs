/** Data-only source swap using the existing Scale compiler. No runtime copy. */
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {compileScalePlan} from '../../../web/map_infographic_v1/scale_contract.mjs';
const HERE=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),REPO=path.resolve(HERE,'../../..');
const SOURCE_SHA='b47bdddd1336b07f498c50eba5d70699ec57dd726a7ea0a85d2dca243236c9eb';
const clone=x=>structuredClone(x),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),sha=b=>createHash('sha256').update(b).digest('hex');
const fail=code=>{throw Error(code);};
export async function prepareRecoveryNative({native,receipt,assetRoot=REPO}){
 if(receipt?.schema!=='WORLD_ENGINE_G2_MAP_STYLE_RECEIPT_V1'||receipt.styleId!=='NE1_SOURCE_NATIVE_COVERAGE'||receipt.sourceOriginal?.sha256!==SOURCE_SHA)fail('RECOVERY_PINNED_MAP_STYLE_REQUIRED');
 if(!native?.nativePlan||native.nativePlan.scale?.name!=='REGIONAL'||!Array.isArray(native.cameraSchedule)||!Array.isArray(native.sourceBindings)||receipt.frameCount!==native.cameraSchedule.length)fail('RECOVERY_REGIONAL_NATIVE_AND_SCHEDULE_REQUIRED');
 const a=receipt.terrainAsset,s=receipt.sourceOriginal;
 if(a?.CRS!=='EPSG:4326'||a.classification!=='BAKED HILLSHADE'||a.sourceOriginalSHA256!==SOURCE_SHA||!same(a.pixelSpacing,[1/60,1/60])||a.NoData!==null)fail('RECOVERY_NATIVE_SOURCE_DESCRIPTOR_REQUIRED');
 const window=receipt.cropSourcePixelBox;
 if(!Array.isArray(window)||window.length!==4||window.some(v=>!Number.isSafeInteger(v))||window[0]<0||window[1]<0||window[2]>21600||window[3]>10800||window[0]>=window[2]||window[1]>=window[3]
  ||!same(a.dimensions,[window[2]-window[0],window[3]-window[1]])||!same(a.bounds,[-180+window[0]/60,90-window[3]/60,-180+window[2]/60,90-window[1]/60]))fail('RECOVERY_NATIVE_WINDOW_GEOGRAPHIC_BINDING_REQUIRED');
 const prefix='world-simulation-shorts-engine/recovery/g2-renderer-recovery-v1/assets/terrain/';
 if(typeof a.path!=='string'||!a.path.startsWith(prefix)||a.path.includes('..')||a.url!=='/recovery-assets/'+path.basename(a.path))fail('RECOVERY_ASSET_SCOPE_REQUIRED');
 const bytes=await readFile(path.resolve(assetRoot,a.path));
 if(sha(bytes)!==a.sha256||bytes.length!==a.bytes||bytes.subarray(0,8).toString('hex')!=='89504e470d0a1a0a'||!same([bytes.readUInt32BE(16),bytes.readUInt32BE(20)],a.dimensions))fail('RECOVERY_SOURCE_PNG_HASH_OR_DIMENSION_MISMATCH');
 const envelope=[Infinity,Infinity,-Infinity,-Infinity];
 for(const row of native.cameraSchedule){
  const b=row.flatBounds;
  if(!Array.isArray(b)||b.length!==4||b.some(x=>!Number.isFinite(x))||b[0]>=b[2]||b[1]>=b[3])fail('RECOVERY_ACTUAL_CAMERA_BOUNDS_REQUIRED');
  if(b[0]<a.bounds[0]+a.pixelSpacing[0]||b[1]<a.bounds[1]+a.pixelSpacing[1]||b[2]>a.bounds[2]-a.pixelSpacing[0]||b[3]>a.bounds[3]-a.pixelSpacing[1])fail('RECOVERY_COMPLETE_SOURCE_VIEWPORT_REQUIRED');
  if(Math.max(1080*a.pixelSpacing[0]/(b[2]-b[0]),1920*a.pixelSpacing[1]/(b[3]-b[1]))>1)fail('RECOVERY_NATIVE_PIXEL_BUDGET_EXCEEDED');
  envelope[0]=Math.min(envelope[0],b[0]);envelope[1]=Math.min(envelope[1],b[1]);envelope[2]=Math.max(envelope[2],b[2]);envelope[3]=Math.max(envelope[3],b[3]);
 }
 if(!same(envelope,receipt.cameraEnvelope))fail('RECOVERY_RECEIPT_CAMERA_ENVELOPE_MISMATCH');
 const before=JSON.stringify(native),base=clone(native.nativePlan);
 base.assets.terrain={file:a.path,url:a.url,bounds:clone(a.bounds),dimensions:clone(a.dimensions),pixelSpacing:clone(a.pixelSpacing),
  sha256:a.sha256,classification:a.classification,license:'Public Domain',
  source:{name:'Natural Earth I with shaded relief, water and drainages',sha256:SOURCE_SHA,url:s.url,license:'Public Domain',crs:s.CRS,version:s.version,
   resolution:clone(s.dimensions),geographicExtent:clone(s.bounds),pixelSpacing:clone(s.pixelSpacing)},
  lodPreparation:{method:'EXACT_NATIVE_PIXEL_WINDOW_NO_RESAMPLE_OR_RECOLOR',cropSourcePixelBox:clone(receipt.cropSourcePixelBox),gutterSourcePixels:receipt.nativeWindowPolicy.gutterSourcePixels}};
 const plan=compileScalePlan(base,'REGIONAL',{allCountries:base.geometries});
 for(const key of ['anchor','framing','geometries','layout','primary','secondary','text','theme'])if(!same(plan[key],native.nativePlan[key]))fail('RECOVERY_APPROVED_NATIVE_DESIGN_OR_GEOMETRY_CHANGED');
 if(plan.scale.lod.rasterCoverage!=='FULL_REGIONAL_CROP'||Math.max(...plan.scale.lod.projectedPixelsPerNativeRgbTexel)>1)fail('RECOVERY_SCALE_SOURCE_METADATA_NOT_READY');
 const bindings=native.sourceBindings.map(row=>row.role==='terrain'?{role:'terrain',path:a.path,sha256:a.sha256,bytes:a.bytes}:clone(row));
 if(bindings.filter(row=>row.role==='terrain').length!==1)fail('RECOVERY_ONE_TERRAIN_BINDING_REQUIRED');
 const result={...clone(native),nativePlan:plan,sourceBindings:bindings,sourceStyle:clone(receipt),
  evidence:{...clone(native.evidence??{}),sourceRasterExtent:clone(a.bounds),rasterOutsideSupport:'FAIL_PREFLIGHT_NO_UNSUPPORTED_SOURCE_FALLBACK',
   recoveryStyleId:receipt.styleId,recoveryDataOnly:true,approvedCameraUnchanged:true,approvedGeometryUnchanged:true,
   originalSourceSHA256:SOURCE_SHA,actualAssetSHA256:a.sha256,sourceProjectedPixelsPerNativeTexel:plan.scale.lod.projectedPixelsPerNativeRgbTexel}};
 if(JSON.stringify(native)!==before||!same(result.cameraPlan,native.cameraPlan)||!same(result.cameraSchedule,native.cameraSchedule))fail('RECOVERY_ORIGINAL_NATIVE_INPUT_MUTATED');
 return result;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const args={};for(const value of process.argv.slice(2)){const m=/^--(native|receipt|output)=(.+)$/.exec(value);if(!m||args[m[1]])fail('RECOVERY_PREPARE_ARGUMENT_INVALID');args[m[1]]=m[2];}
 if(!args.native||!args.receipt||!args.output)fail('RECOVERY_PREPARE_INPUT_REQUIRED');
 const native=JSON.parse(await readFile(args.native)),receipt=JSON.parse(await readFile(args.receipt));
 const result=await prepareRecoveryNative({native,receipt});await writeFile(args.output,JSON.stringify(result)+'\n',{flag:'wx',mode:0o600});
 console.log(JSON.stringify({status:'PREPARED_DATA_ONLY',output:args.output,sha256:sha(await readFile(args.output)),sourceAssetSHA256:receipt.terrainAsset.sha256,cameraUnchanged:true}));
}
