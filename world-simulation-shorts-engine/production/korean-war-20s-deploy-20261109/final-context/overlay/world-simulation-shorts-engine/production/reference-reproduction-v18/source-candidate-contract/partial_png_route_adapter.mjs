/** Separate CPU image-file binding; never certifies browser upload or rendering. */
import {readFile,realpath,lstat} from 'node:fs/promises';import path from 'node:path';import {createHash} from 'node:crypto';
import {preparePartialRoute,ROUTE_MODE} from './partial_route_adapter.mjs';
const hash=b=>createHash('sha256').update(b).digest('hex'),check=(v,c)=>{if(!v)throw Object.assign(new Error(c),{code:c});};
const exact=(v,k)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===k.length&&k.every(x=>Object.hasOwn(v,x));
export const PNG_ROUTE_MODE='PREPARE_PARTIAL_OPTICAL_BMNG_PNG_CPU_ONLY';
export async function preparePartialPngRoute(registration,request){
 check(exact(request,['mode','segment'])&&request.mode===PNG_ROUTE_MODE,'EXPLICIT_PNG_CPU_ROUTE_REQUIRED');
 check(exact(registration,['partial','png'])&&exact(registration.png,['root','generationIndexSha256']),'SERVER_PNG_REGISTRATION_REQUIRED');
 const pin=registration.png;check(typeof pin.root==='string'&&path.isAbsolute(pin.root)&&!pin.root.includes('://')&&/^[a-f0-9]{64}$/.test(pin.generationIndexSha256),'SERVER_LOCAL_PNG_PIN_REQUIRED');
 const prepared=await preparePartialRoute(registration.partial,{mode:ROUTE_MODE,segment:request.segment}),root=await realpath(pin.root);
 const read=async(name,r)=>{check(typeof name==='string'&&path.basename(name)===name&&!name.includes('..')&&!name.includes('\\'),'SAFE_PNG_PATH_REQUIRED');const file=path.join(root,name),s=await lstat(file);check(s.isFile()&&!s.isSymbolicLink(),'PNG_REGULAR_FILE_REQUIRED');const b=await readFile(file);if(r)check(b.length===r.bytes&&hash(b)===r.sha256,'PNG_BOUND_BYTES_MISMATCH');return b;};
 const indexBytes=await read('PNG_GENERATION_INDEX.json');check(hash(indexBytes)===pin.generationIndexSha256,'PNG_GENERATION_PIN_MISMATCH');const index=JSON.parse(indexBytes);
 check(index.schema==='WORLD_ENGINE_COMPOSITE_PNG_GENERATION_V1'&&index.productionAdmitted===false&&index.sourceGenerationIndexSha256===registration.partial.generationIndexSha256,'PNG_SOURCE_GENERATION_MISMATCH');
 const receiptDescriptor=index.files?.['PNG_DERIVATION_RECEIPT.json'];check(receiptDescriptor,'PNG_RECEIPT_NOT_BOUND');
 const receiptBytes=await read('PNG_DERIVATION_RECEIPT.json',receiptDescriptor),receipt=JSON.parse(receiptBytes);
 check(receipt.schema==='WORLD_ENGINE_EXACT_RGB8_PNG_DERIVATION_V1'&&receipt.sourceGenerationIndexSha256===registration.partial.generationIndexSha256&&receipt.originalGenerationIndexSha256===registration.partial.originalGenerationIndexSha256,'PNG_DERIVATION_SOURCE_MISMATCH');
 for(const k of ['productionAdmitted','renderAllowed','imageBuildAllowed'])check(receipt[k]===false,'PNG_ADMISSION_CLAIM_FORBIDDEN');
 const policy=receipt.decoderPolicy;
 check(policy&&policy.bitDepth===8&&policy.colorType==='RGB_OPAQUE'&&policy.iccProfile===false&&policy.gammaChunk===false&&policy.srgbChunk===false&&policy.alpha===false&&JSON.stringify(policy.allowedChunks)==='["IHDR","IDAT","IEND"]','PNG_DECODER_POLICY_UNSUPPORTED');
 check(policy.colorConversion==='No CPU color conversion. Browser/Canvas/WebGL color-management equivalence is unverified; absence of ICC/gAMA is not a runtime certification.'&&policy.premultiplication==='Not applicable to opaque RGB source; runtime upload must not alter bytes','PNG_BROWSER_POLICY_CLAIM_FORBIDDEN');
 check(Array.isArray(receipt.composites),'PNG_COMPOSITE_RECEIPTS_REQUIRED');
 const serverImages={},images=[];
 for(const layer of prepared.layers){
  const matches=receipt.composites.filter(r=>r.segment===request.segment&&r.role===layer.role);check(matches.length===1,'UNIQUE_COMPOSITE_PNG_REQUIRED');const r=matches[0];
  const raw=prepared.serverAssets[layer.composite.assetKey];
  check(r.sourceSha256===raw.sha256&&r.sourceBytes===raw.bytes&&r.sourceFile===raw.localFile&&r.sourceWrapperSha256===prepared.identity.wrapperSha256&&r.encoding==='RGB8'&&r.cpuDecodedRgbSha256===raw.sha256&&r.exactCpuRoundTrip===true,'PNG_RAW_DERIVATION_MISMATCH');
  check(JSON.stringify(r.dimensions)===JSON.stringify(layer.composite.dimensions)&&JSON.stringify(r.bounds)===JSON.stringify(layer.composite.bounds)&&r.crs===layer.composite.crs,'PNG_GRID_MISMATCH');
  const d=index.files[r.pngFile];check(d&&d.sha256===r.pngSha256&&d.bytes===r.pngBytes,'PNG_IMAGE_NOT_BOUND');const png=await read(r.pngFile,d);
  check(png.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])),'PNG_SIGNATURE_INVALID');
  let offset=8,ihdr=null,chunks=[];
  while(offset<png.length){check(offset+12<=png.length,'PNG_CHUNK_TRUNCATED');const n=png.readUInt32BE(offset),kind=png.toString('ascii',offset+4,offset+8);check(n<=png.length-offset-12,'PNG_CHUNK_TRUNCATED');check(['IHDR','IDAT','IEND'].includes(kind),'PNG_METADATA_CHUNK_FORBIDDEN');if(kind==='IHDR'){check(!ihdr&&n===13,'PNG_IHDR_INVALID');ihdr=png.subarray(offset+8,offset+21);}chunks.push(kind);offset+=n+12;}
  check(ihdr&&chunks[0]==='IHDR'&&chunks.at(-1)==='IEND'&&chunks.includes('IDAT')&&JSON.stringify(chunks)===JSON.stringify(r.pngChunks),'PNG_CHUNK_POLICY_MISMATCH');
  check(ihdr.readUInt32BE(0)===r.dimensions[0]&&ihdr.readUInt32BE(4)===r.dimensions[1]&&ihdr[8]===8&&ihdr[9]===2&&ihdr[10]===0&&ihdr[11]===0&&ihdr[12]===0,'PNG_RGB8_DIMENSIONS_REQUIRED');
  const key='sha256/'+r.pngSha256;serverImages[key]={localFile:r.pngFile,sha256:r.pngSha256,bytes:r.pngBytes,mimeType:'image/png'};
  images.push({role:layer.role,imageKey:key,rawAssetKey:layer.composite.assetKey,dimensions:r.dimensions,bounds:r.bounds,crs:r.crs,derivationReceiptSha256:receiptDescriptor.sha256,decoderPolicy:policy});
 }
 const identity={algorithm:'partial-png-route-v1:pinned-index;exact-raw-link;rgb8-metadata-checked;browser-upload-unqualified',adapterSha256:hash(await readFile(new URL(import.meta.url))),partialRouteCacheIdentity:prepared.cacheIdentity,pngGenerationIndexSha256:pin.generationIndexSha256,pngDerivationReceiptSha256:receiptDescriptor.sha256,decoderPolicySha256:hash(Buffer.from(JSON.stringify(policy))),images:images.map(i=>({role:i.role,imageKey:i.imageKey,rawAssetKey:i.rawAssetKey,dimensions:i.dimensions,bounds:i.bounds,crs:i.crs}))};
 return{...prepared,schema:'WORLD_ENGINE_PARTIAL_PNG_ROUTE_PREPARATION_V1',cacheIdentity:hash(Buffer.from(JSON.stringify(identity))),pngIdentity:identity,serverImageRoot:root,serverImages,images,browserUploadQualified:false,materialQualified:false,lodQualified:false,sourceSelectionMasksStillRequired:true,asfLightingMasksStillRequired:true,productionAdmitted:false,renderAllowed:false,imageBuildAllowed:false};
}
