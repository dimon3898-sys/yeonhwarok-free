/** Explicit partial optical display candidate. Never relaxes the strict validator. */
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {verifyCandidateFiles,validateCandidateManifest} from './derived_source_manifest.mjs';
export const PARTIAL_SCHEMA='WORLD_ENGINE_PARTIAL_OPTICAL_BMNG_CANDIDATE_V1';
const check=(v,code)=>{if(!v)throw Object.assign(new Error(code),{code});};
const exactKeys=(v,keys)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
export async function verifyPartialOpticalCandidate(envelope,{root,...options}){
 check(exactKeys(envelope,['schema','candidate','partialPolicyReceiptSha256'])&&envelope.schema===PARTIAL_SCHEMA,'EXPLICIT_PARTIAL_WRAPPER_REQUIRED');
 const m=envelope.candidate;
 // Retain every strict schema, mask, source evidence, hash and composition check.
 const base=await verifyCandidateFiles(m,{root,...options});
 const {assets,products,receipts}=validateCandidateManifest(m);
 const readBound=async r=>{check(r,'PARTIAL_RECEIPT_NOT_BOUND');const b=await readFile(path.join(root,r.file));check(b.length===r.bytes&&createHash('sha256').update(b).digest('hex')===r.sha256,'PARTIAL_BOUND_FILE_CHANGED');return b;};
 const receipt=async hash=>JSON.parse((await readBound(receipts.get(hash))).toString('utf8'));
 const policy=await receipt(envelope.partialPolicyReceiptSha256);
 check(exactKeys(policy,['schema','mode','disclosure','sourceGapEvidenceSha256','declaredSourceInvalidKnownLandPixels','baselineSourceId','layerFallbacks']),'PARTIAL_POLICY_FIELDS_REQUIRED');
 check(policy.schema==='WORLD_ENGINE_PARTIAL_OPTICAL_POLICY_V1'&&policy.mode==='EXPLICIT_PARTIAL_OPTICAL_REAL_BMNG_FALLBACK','PARTIAL_MODE_REQUIRED');
 check(policy.disclosure==='Partial modern optical imagery. Missing optical known-land, known water, and unknown classification use real BMNG context. This is not complete optical coverage or historical imagery.','PARTIAL_DISCLOSURE_REQUIRED');
 check(policy.baselineSourceId==='NASA_BMNG_KOREA_500M_NE10M_V2','REAL_BMNG_IDENTITY_REQUIRED');
 const evidence=await receipt(policy.sourceGapEvidenceSha256);
 check(evidence.schema==='WORLD_ENGINE_SOURCE_EVIDENCE_INDEX_V1'&&evidence.authenticity==='PENDING'&&evidence.productionAdmitted===false,'PARTIAL_SOURCE_EVIDENCE_REQUIRED');
 check(Number.isSafeInteger(policy.declaredSourceInvalidKnownLandPixels)&&policy.declaredSourceInvalidKnownLandPixels>=0&&policy.declaredSourceInvalidKnownLandPixels===evidence.sourceInvalidKnownLand,'SOURCE_GRID_GAP_COUNT_MISMATCH');
 check(evidence.baselineCatalog?.id===policy.baselineSourceId&&evidence.baselineMaterialization?.derivedPngSha256===evidence.baselineCatalog.sha256&&evidence.baselineMaterialization?.sourceOriginalSha256===evidence.baselineCatalog.sourceOriginal?.sha256,'BMNG_DERIVATION_EVIDENCE_REQUIRED');
 check(Array.isArray(policy.layerFallbacks)&&policy.layerFallbacks.length===m.layers.length,'ALL_LAYER_FALLBACKS_REQUIRED');
 const seen=new Set(),results=[];
 for(const l of m.layers){
  const entries=policy.layerFallbacks.filter(x=>x.role===l.role);check(entries.length===1,'UNIQUE_LAYER_FALLBACK_REQUIRED');const f=entries[0];
  check(exactKeys(f,['role','maskProductId','declaredPixelCount'])&&Number.isSafeInteger(f.declaredPixelCount)&&f.declaredPixelCount>=0,'FALLBACK_DECLARATION_REQUIRED');
  check(!seen.has(f.maskProductId),'FALLBACK_MASK_REUSE_FORBIDDEN');seen.add(f.maskProductId);
  const product=products.get(f.maskProductId);check(product?.kind==='VALIDITY_MASK','FALLBACK_MASK_PRODUCT_REQUIRED');
  const mask=assets.get(product.assetId),grid=assets.get(l.rgbAssetId);
  check(JSON.stringify(mask.bounds)===JSON.stringify(grid.bounds)&&JSON.stringify(mask.dimensions)===JSON.stringify(grid.dimensions)&&mask.crs===grid.crs,'FALLBACK_MASK_GRID_MISMATCH');
  // All participating products, including the fallback mask, must bind this same evidence generation.
  for(const id of [l.opticalProductId,l.baselineProductId,l.baselineValidityProductId,l.opticalValidityProductId,l.knownLandMaskProductId,l.knownWaterMaskProductId,l.unknownMaskProductId,l.selectionProductId,f.maskProductId]){
   const r=await receipt(products.get(id).provenance.acquisitionReceiptSha256);check(r.sourceEvidenceSha256===policy.sourceGapEvidenceSha256,'PARTIAL_PRODUCT_EVIDENCE_MISMATCH');
  }
  const upstream=await receipt(products.get(l.baselineProductId).provenance.upstreamManifestSha256);
  check(upstream.sources.length===1&&upstream.sources[0].sourceHashScope==='WHOLE_FILE'&&upstream.sources[0].sourceWholeFileSha256===evidence.baselineCatalog.sourceOriginal.sha256&&upstream.sources[0].sourceUrl===evidence.baselineCatalog.sourceOriginal.url,'BMNG_UPSTREAM_IDENTITY_MISMATCH');
  const bytes=async id=>readBound(assets.get(products.get(id).assetId));
  const [fallback,land,valid]=await Promise.all([bytes(f.maskProductId),bytes(l.knownLandMaskProductId),bytes(l.opticalValidityProductId)]);let count=0;
  for(let i=0;i<fallback.length;i++){const expected=Number(land[i]===1&&valid[i]===0);check(fallback[i]===expected,'FALLBACK_MASK_MUST_EQUAL_INVALID_OPTICAL_KNOWN_LAND');count+=expected;}
  check(count===f.declaredPixelCount,'ATLAS_FALLBACK_COUNT_MISMATCH');
  results.push({role:l.role,invalidOpticalKnownLandFallbackPixels:count,fullOpticalCoverageClaim:false});
 }
 return{...base,schema:'WORLD_ENGINE_PARTIAL_OPTICAL_CANDIDATE_CHECK_V1',mode:policy.mode,disclosure:policy.disclosure,fullOpticalCoverageClaim:false,sourceGridInvalidOpticalKnownLandPixels:policy.declaredSourceInvalidKnownLandPixels,sourceGapEvidenceSha256:policy.sourceGapEvidenceSha256,partialFallbackLayers:results,productionAdmitted:false,renderAllowed:false,imageBuildAllowed:false};
}
