/** Server-only CPU preparation. This module cannot admit or execute rendering. */
import {readFile,realpath,lstat} from 'node:fs/promises';
import path from 'node:path';import {createHash} from 'node:crypto';
import {verifyPartialOpticalCandidate} from './partial_optical_candidate.mjs';
const SHA=/^[a-f0-9]{64}$/;const digest=b=>createHash('sha256').update(b).digest('hex');
const assert=(v,c)=>{if(!v)throw Object.assign(new Error(c),{code:c});};
const exact=(v,k)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===k.length&&k.every(x=>Object.hasOwn(v,x));
export const ROUTE_MODE='PREPARE_PARTIAL_OPTICAL_BMNG_CPU_ONLY';
const ALGORITHM='partial-route-v1:strict+partial-validation;server-pinned-generation;hash-addressed-local-assets;mixed-optical-bmng;no-height;no-runtime';
/** registration comes ONLY from server configuration, never request body. */
export async function preparePartialRoute(registration,request){
 assert(exact(request,['mode','segment'])&&request.mode===ROUTE_MODE&&Number.isInteger(request.segment)&&request.segment>=1&&request.segment<=4,'EXPLICIT_CPU_ROUTE_REQUEST_REQUIRED');
 assert(exact(registration,['root','generationIndexSha256','originalGenerationIndexSha256']),'SERVER_REGISTRATION_REQUIRED');
 assert(typeof registration.root==='string'&&!registration.root.includes('://')&&path.isAbsolute(registration.root)&&SHA.test(registration.generationIndexSha256)&&SHA.test(registration.originalGenerationIndexSha256),'SERVER_LOCAL_PIN_REQUIRED');
 const root=await realpath(registration.root);
 const readLocal=async(file,expected)=>{
  assert(typeof file==='string'&&path.basename(file)===file&&!file.includes('..')&&!file.includes('\\'),'SAFE_SERVER_ASSET_PATH_REQUIRED');
  const p=path.join(root,file),s=await lstat(p);assert(s.isFile()&&!s.isSymbolicLink(),'SERVER_ASSET_REGULAR_FILE_REQUIRED');
  const b=await readFile(p);if(expected)assert(digest(b)===expected.sha256&&b.length===expected.bytes,'SERVER_ASSET_HASH_MISMATCH');return b;
 };
 const indexRaw=await readLocal('PARTIAL_GENERATION_INDEX.json');assert(digest(indexRaw)===registration.generationIndexSha256,'SERVER_GENERATION_PIN_MISMATCH');const index=JSON.parse(indexRaw);
 assert(index.schema==='WORLD_ENGINE_PARTIAL_OPTICAL_GENERATION_INDEX_V1'&&index.productionAdmitted===false&&index.originalGenerationIndexSha256===registration.originalGenerationIndexSha256,'SERVER_ORIGINAL_GENERATION_PIN_MISMATCH');
 const name=`segment${request.segment}_partial_wrapper.json`,originalName=`segment${request.segment}_manifest.json`;
 assert(index.files[name]&&index.files[originalName],'SERVER_WRAPPER_NOT_REGISTERED');
 const wrapperRaw=await readLocal(name,index.files[name]),wrapper=JSON.parse(wrapperRaw);
 const verified=await verifyPartialOpticalCandidate(wrapper,{root});
 assert(wrapper.candidate.layers.every(l=>l.height===undefined),'ELEVATION_NOT_PERMITTED_IN_PARTIAL_ROUTE');
 const originalRaw=await readLocal(originalName,index.files[originalName]);
 const policyDescriptor=wrapper.candidate.receipts.find(r=>r.sha256===wrapper.partialPolicyReceiptSha256);
 const policy=JSON.parse(await readLocal(policyDescriptor.file,policyDescriptor));
 // Recheck all admitted local bytes while building the server map. No external URL is accepted or emitted.
 const serverAssets={},keys=new Map();
 for(const a of wrapper.candidate.assets){
  assert(index.files[a.file]?.sha256===a.sha256&&index.files[a.file]?.bytes===a.bytes,'ASSET_NOT_IN_PINNED_GENERATION');await readLocal(a.file,a);
  const key='sha256/'+a.sha256;keys.set(a.id,key);
  // Same bytes may have different grids. Grid is kept per layer binding, not deduplicated into byte identity.
  serverAssets[key]={sha256:a.sha256,bytes:a.bytes,localFile:a.file};
 }
 for(const r of wrapper.candidate.receipts){assert(index.files[r.file]?.sha256===r.sha256&&index.files[r.file]?.bytes===r.bytes,'RECEIPT_NOT_IN_PINNED_GENERATION');await readLocal(r.file,r);}
 const m=wrapper.candidate,products=new Map(m.products.map(p=>[p.id,p])),assets=new Map(m.assets.map(a=>[a.id,a]));
 const productAsset=id=>{const p=products.get(id),a=assets.get(p.assetId);return{assetKey:keys.get(a.id),encoding:a.encoding,dimensions:a.dimensions,bounds:a.bounds,crs:a.crs,productKind:p.kind,classification:p.classification,derivationReceiptSha256:p.provenance.acquisitionReceiptSha256,upstreamManifestSha256:p.provenance.upstreamManifestSha256};};
 const layers=m.layers.map(l=>{const a=assets.get(l.rgbAssetId),f=policy.layerFallbacks.find(f=>f.role===l.role);return{role:l.role,composite:{assetKey:keys.get(a.id),encoding:a.encoding,dimensions:a.dimensions,bounds:a.bounds,crs:a.crs},optical:productAsset(l.opticalProductId),baseline:productAsset(l.baselineProductId),opticalValidity:productAsset(l.opticalValidityProductId),knownLand:productAsset(l.knownLandMaskProductId),knownWater:productAsset(l.knownWaterMaskProductId),unknown:productAsset(l.unknownMaskProductId),opticalSelection:productAsset(l.selectionProductId),invalidKnownLandFallback:productAsset(f.maskProductId),declaredFallbackPixels:f.declaredPixelCount};});
 const moduleDigests={};for(const file of ['partial_route_adapter.mjs','partial_optical_candidate.mjs','derived_source_manifest.mjs'])moduleDigests[file]=digest(await readFile(new URL('./'+file,import.meta.url)));
 const identity={algorithm:ALGORITHM,moduleDigests,generationIndexSha256:registration.generationIndexSha256,originalGenerationIndexSha256:registration.originalGenerationIndexSha256,originalManifestSha256:digest(originalRaw),wrapperSha256:digest(wrapperRaw),sourceEvidenceSha256:policy.sourceGapEvidenceSha256,policyReceiptSha256:wrapper.partialPolicyReceiptSha256,segment:request.segment};
 return{schema:'WORLD_ENGINE_PARTIAL_ROUTE_PREPARATION_V1',status:'CPU_PREPARATION_ONLY',cacheIdentity:digest(Buffer.from(JSON.stringify(identity))),identity,serverAssetRoot:root,serverAssets,layers,material:{kind:'MIXED_MODERN_OPTICAL_REAL_BMNG',composition:'EXACT_MASK_SELECT_REAL_RGB',opticalTreatment:'OPTICAL_NOT_BAKED_RELIEF',baselineTreatment:'REAL_BMNG_WITH_BAKED_RELIEF',lighting:'UNQUALIFIED_NO_RUNTIME_TREATMENT',disclosure:verified.disclosure,fullOpticalCoverageClaim:false,sourceGridInvalidOpticalKnownLandPixels:verified.sourceGridInvalidOpticalKnownLandPixels,waterAndUnknownDistinct:true},height:null,demEnabled:false,productionAdmitted:false,renderAllowed:false,imageBuildAllowed:false,remainingChecks:verified.remainingChecks};
}
