/** Isolated candidate validator. Never authorizes production, rendering, or builds. */
import {readFile, realpath, lstat} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';

export const SCHEMA='WORLD_ENGINE_DERIVED_SOURCE_CANDIDATE_V1';
const encBytes={RGB8:3,MASK8:1,F32LE:4};
const classes={OPTICAL_RGB:'OPTICAL_RGB_NOT_BAKED',BAKED_BASEMAP_RGB:'BAKED_BASEMAP_NOT_OPTICAL',DSM:'REAL_DSM_METRES',VALIDITY_MASK:'SOURCE_VALIDITY',KNOWN_LAND_MASK:'KNOWN_LAND',KNOWN_WATER_MASK:'KNOWN_WATER',UNKNOWN_MASK:'UNKNOWN_CLASSIFICATION',SELECTION_MASK:'SOURCE_SELECTION',DSM_USE_MASK:'COMPLETE_DSM_NEIGHBORHOOD'};
const deny=code=>{throw Object.assign(new Error(code),{code});};
const check=(value,code)=>{if(!value)deny(code);};
const plain=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const keys=(v,allowed,code)=>{check(plain(v),code);check(Object.keys(v).every(k=>allowed.includes(k)),code+'_UNKNOWN_FIELD');};
const hex=v=>typeof v==='string'&&/^[0-9a-f]{64}$/.test(v);
const digest=b=>createHash('sha256').update(b).digest('hex');
const ident=v=>typeof v==='string'&&/^[a-zA-Z][a-zA-Z0-9_.-]{0,79}$/.test(v);
const eq=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const secureUrl=s=>{try{const u=new URL(s);return u.protocol==='https:'&&!u.username&&!u.password&&!u.hash;}catch{return false;}};
const sameGrid=(a,b)=>a.crs===b.crs&&eq(a.dimensions,b.dimensions)&&eq(a.bounds,b.bounds);
const lookup=(m,id,code)=>{check(m.has(id),code);return m.get(id);};
const positive=v=>Number.isInteger(v)&&v>0;

function validateProvenance(p){
 keys(p,['acquisitionReceiptSha256','upstreamManifestSha256','resampling','colorMapping'],'PROVENANCE');
 check(hex(p.acquisitionReceiptSha256)&&hex(p.upstreamManifestSha256),'BOUND_UPSTREAM_AND_DERIVATION_HASHES_REQUIRED');
 check(['NONE','NEAREST','BILINEAR','AREA_MEAN_VALID_ONLY'].includes(p.resampling),'UNSUPPORTED_RESAMPLING');
 check(typeof p.colorMapping==='string'&&p.colorMapping.length>0&&p.colorMapping.length<=500,'EXPLICIT_COLOR_MAPPING_REQUIRED');
}
function validateUpstreamManifest(m){
 keys(m,['schema','completeness','sources'],'UPSTREAM_MANIFEST');
 check(m.schema==='WORLD_ENGINE_DERIVED_SOURCE_INPUT_MANIFEST_V1'&&m.completeness==='ALL_DECLARED_UPSTREAM_INPUTS','COMPLETE_UPSTREAM_MANIFEST_REQUIRED');
 check(Array.isArray(m.sources)&&m.sources.length>0&&m.sources.length<=512,'UPSTREAM_SOURCES_REQUIRED');
 const ids=new Set();
 for(const p of m.sources){
  keys(p,['id','sourceUrl','license','attribution','sourceHashScope','sourceWholeFileSha256','rangeReceipts','grid','processingMethod'],'UPSTREAM_SOURCE');
  check(ident(p.id)&&!ids.has(p.id),'UPSTREAM_SOURCE_ID_INVALID');ids.add(p.id);
  check(secureUrl(p.sourceUrl),'SOURCE_HTTPS_URL_REQUIRED');
  check(typeof p.license==='string'&&p.license.trim()&&typeof p.attribution==='string'&&p.attribution.trim(),'SOURCE_CREDIT_REQUIRED');
  check(['WHOLE_FILE','BYTE_RANGES'].includes(p.sourceHashScope),'SOURCE_HASH_SCOPE_REQUIRED');
  if(p.sourceHashScope==='WHOLE_FILE')check(hex(p.sourceWholeFileSha256),'WHOLE_SOURCE_HASH_REQUIRED');
  else{
   check(p.sourceWholeFileSha256===null,'PARTIAL_HASH_MUST_NOT_CLAIM_WHOLE_SOURCE');
   check(Array.isArray(p.rangeReceipts)&&p.rangeReceipts.length>0&&p.rangeReceipts.length<=8192,'RANGE_RECEIPTS_REQUIRED');
   for(const r of p.rangeReceipts){keys(r,['offset','bytes','sha256'],'RANGE_RECEIPT');check(Number.isSafeInteger(r.offset)&&r.offset>=0&&positive(r.bytes)&&hex(r.sha256),'INVALID_RANGE_RECEIPT');}
  }
  keys(p.grid,['kind','crs','bounds','dimensions','pixelInterpretation'],'UPSTREAM_GRID');
  const g=p.grid;check(typeof g.crs==='string'&&g.crs.trim()&&Array.isArray(g.bounds)&&g.bounds.length===4&&g.bounds.every(Number.isFinite)&&g.bounds[0]<g.bounds[2]&&g.bounds[1]<g.bounds[3],'UPSTREAM_CRS_GRID_REQUIRED');
  check(['RASTER','VECTOR'].includes(g.kind),'UPSTREAM_GRID_KIND_REQUIRED');
  if(g.kind==='RASTER')check(Array.isArray(g.dimensions)&&g.dimensions.length===2&&g.dimensions.every(positive)&&['AREA','POINT'].includes(g.pixelInterpretation),'UPSTREAM_RASTER_GRID_REQUIRED');
  else check(g.dimensions===null&&g.pixelInterpretation===null,'VECTOR_GRID_MUST_NOT_INVENT_PIXELS');
  check(['EXACT_SOURCE_DECODE','COG_WINDOW_RESAMPLE','MASK_DERIVATION','GEOGRAPHIC_MASKED_COMPOSITION'].includes(p.processingMethod),'UPSTREAM_PROCESSING_METHOD_REQUIRED');
 }
 return m.sources.length;
}

/** Structural validation only. Returns a fresh index; never mutates the manifest. */
export function validateCandidateManifest(manifest){
 keys(manifest,['schema','purpose','assets','receipts','products','layers','qualification'],'MANIFEST');
 check(manifest.schema===SCHEMA&&manifest.purpose==='QUALIFICATION_ONLY','CANDIDATE_ONLY_SCHEMA_REQUIRED');
 keys(manifest.qualification,['state','missingChecks'],'QUALIFICATION');
 check(manifest.qualification.state==='PENDING'&&Array.isArray(manifest.qualification.missingChecks)&&manifest.qualification.missingChecks.length>0,'QUALIFICATION_MUST_REMAIN_PENDING');
 check(manifest.qualification.missingChecks.every(s=>typeof s==='string'&&s.trim()),'MISSING_CHECKS_INVALID');
 check(Array.isArray(manifest.assets)&&manifest.assets.length>0&&manifest.assets.length<=64,'ASSETS_REQUIRED');
 const assets=new Map();
 for(const a of manifest.assets){
  keys(a,['id','file','sha256','bytes','encoding','dimensions','bounds','crs'],'ASSET');
  check(ident(a.id)&&!assets.has(a.id),'DUPLICATE_OR_INVALID_ASSET_ID');
  check(typeof a.file==='string'&&a.file.length>0&&!path.isAbsolute(a.file)&&!a.file.split(/[\\/]/).some(x=>x==='..'||x==='.'||!x)&&!a.file.includes('\\'),'SAFE_RELATIVE_ASSET_PATH_REQUIRED');
  check(hex(a.sha256)&&positive(a.bytes),'ASSET_HASH_AND_SIZE_REQUIRED');
  check(Object.hasOwn(encBytes,a.encoding),'RAW_ASSET_ENCODING_REQUIRED');
  check(Array.isArray(a.dimensions)&&a.dimensions.length===2&&a.dimensions.every(v=>positive(v)&&v<=4096),'ATLAS_MAX_4096');
  check(a.bytes===a.dimensions[0]*a.dimensions[1]*encBytes[a.encoding],'ASSET_DECLARED_BYTE_SIZE_MISMATCH');
  check(a.crs==='EPSG:4326'&&Array.isArray(a.bounds)&&a.bounds.length===4&&a.bounds.every(Number.isFinite)&&a.bounds[0]<a.bounds[2]&&a.bounds[1]<a.bounds[3]&&a.bounds[0]>=-180&&a.bounds[2]<=180&&a.bounds[1]>=-90&&a.bounds[3]<=90,'REGISTERED_PIXEL_EDGE_BOUNDS_REQUIRED');
  assets.set(a.id,a);
 }
 check(Array.isArray(manifest.receipts)&&manifest.receipts.length>0&&manifest.receipts.length<=64,'RECEIPTS_REQUIRED');
 const receipts=new Map();
 for(const r of manifest.receipts){
  keys(r,['file','sha256','bytes'],'RECEIPT');check(hex(r.sha256)&&!receipts.has(r.sha256)&&positive(r.bytes)&&r.bytes<=2*1024**2,'INVALID_RECEIPT_DESCRIPTOR');
  check(typeof r.file==='string'&&r.file.length>0&&!path.isAbsolute(r.file)&&!r.file.split(/[\\/]/).some(x=>x==='..'||x==='.'||!x)&&!r.file.includes('\\'),'SAFE_RELATIVE_RECEIPT_PATH_REQUIRED');receipts.set(r.sha256,r);
 }
 check(Array.isArray(manifest.products)&&manifest.products.length>0&&manifest.products.length<=64,'PRODUCTS_REQUIRED');
 const products=new Map();
 for(const p of manifest.products){
  keys(p,['id','kind','classification','assetId','provenance'],'PRODUCT');
  check(ident(p.id)&&!products.has(p.id),'DUPLICATE_OR_INVALID_PRODUCT_ID');
  check(Object.hasOwn(classes,p.kind)&&p.classification===classes[p.kind],'TRUTHFUL_SOURCE_CLASSIFICATION_REQUIRED');
  const a=lookup(assets,p.assetId,'PRODUCT_ASSET_MISSING');
  check(a.encoding===(p.kind==='DSM'?'F32LE':['OPTICAL_RGB','BAKED_BASEMAP_RGB'].includes(p.kind)?'RGB8':'MASK8'),'PRODUCT_ENCODING_MISMATCH');
  validateProvenance(p.provenance);check(receipts.has(p.provenance.acquisitionReceiptSha256),'PROVENANCE_RECEIPT_NOT_BOUND');check(receipts.has(p.provenance.upstreamManifestSha256),'UPSTREAM_MANIFEST_NOT_BOUND');products.set(p.id,p);
 }
 check(Array.isArray(manifest.layers)&&manifest.layers.length>0&&manifest.layers.length<=2,'AT_MOST_TWO_LAYERS');
 const roles=new Set();
 for(const l of manifest.layers){
  keys(l,['role','rgbAssetId','opticalProductId','baselineProductId','baselineValidityProductId','opticalValidityProductId','knownLandMaskProductId','knownWaterMaskProductId','unknownMaskProductId','selectionProductId','composition','waterPolicy','invalidOpticalLandPolicy','height'],'LAYER');
  check(['overview','regional'].includes(l.role)&&!roles.has(l.role),'UNIQUE_LAYER_ROLE_REQUIRED');roles.add(l.role);
  check(l.composition==='EXACT_MASK_SELECT_REAL_RGB'&&l.waterPolicy==='PRESERVE_REAL_BASEMAP'&&l.invalidOpticalLandPolicy==='PRESERVE_BASEMAP_AND_BLOCK_ADMISSION','EXPLICIT_NO_INPAINTING_COMPOSITION_REQUIRED');
  const out=lookup(assets,l.rgbAssetId,'LAYER_RGB_MISSING');check(out.encoding==='RGB8','LAYER_RGB8_REQUIRED');
  for(const [field,kind] of [['opticalProductId','OPTICAL_RGB'],['baselineProductId','BAKED_BASEMAP_RGB'],['baselineValidityProductId','VALIDITY_MASK'],['opticalValidityProductId','VALIDITY_MASK'],['knownLandMaskProductId','KNOWN_LAND_MASK'],['knownWaterMaskProductId','KNOWN_WATER_MASK'],['unknownMaskProductId','UNKNOWN_MASK'],['selectionProductId','SELECTION_MASK']]){
   const p=lookup(products,l[field],'LAYER_PRODUCT_MISSING');check(p.kind===kind,'LAYER_PRODUCT_KIND_MISMATCH');check(sameGrid(out,assets.get(p.assetId)),'LAYER_GRIDS_MUST_MATCH');
  }
  if(l.height!==undefined){
   const h=l.height;keys(h,['dsmProductId','validityProductId','useMaskProductId','invalidPayload','unit','scale','offset','neighborhoodRadiusSamples','neighborhoodContract','outsidePolicy'],'HEIGHT');
   check(h.invalidPayload==='NAN'&&h.unit==='m'&&h.scale===1&&h.offset===0&&h.outsidePolicy==='NO_DEM_KEEP_BASELINE_LIGHTING','NO_FAKE_ZERO_HEIGHT_POLICY_REQUIRED');
   check(h.neighborhoodContract==='DECLARED_SQUARE_PENDING_RUNTIME_BINDING','RUNTIME_NEIGHBORHOOD_NOT_CERTIFIED');
   check(Number.isInteger(h.neighborhoodRadiusSamples)&&h.neighborhoodRadiusSamples>=1&&h.neighborhoodRadiusSamples<=64,'EXPLICIT_DERIVATIVE_NEIGHBORHOOD_REQUIRED');
   for(const [field,kind] of [['dsmProductId','DSM'],['validityProductId','VALIDITY_MASK'],['useMaskProductId','DSM_USE_MASK']]){
    const p=lookup(products,h[field],'HEIGHT_PRODUCT_MISSING');check(p.kind===kind,'HEIGHT_PRODUCT_KIND_MISMATCH');check(sameGrid(out,assets.get(p.assetId)),'HEIGHT_GRIDS_MUST_MATCH');
   }
  }
 }
 check(roles.has('overview'),'OVERVIEW_LAYER_REQUIRED');
 return{assets,products,receipts};
}

async function readAsset(root,a){
 const target=path.resolve(root,a.file);check(target.startsWith(root+path.sep),'ASSET_OUTSIDE_ROOT');
 const components=a.file.split('/');let prefix=root;
 for(const component of components){prefix=path.join(prefix,component);const stat=await lstat(prefix);check(!stat.isSymbolicLink(),'ASSET_SYMLINK_FORBIDDEN');}
 check(await realpath(target)===target,'ASSET_REALPATH_MISMATCH');const stat=await lstat(target);check(stat.isFile()&&stat.size===a.bytes,'ASSET_ACTUAL_SIZE_MISMATCH');
 const data=await readFile(target);check(data.length===a.bytes&&digest(data)===a.sha256,'ASSET_ACTUAL_HASH_MISMATCH');return data;
}

/** Check local derivative bytes. Authenticity/scientific qualification remains pending. */
export async function verifyCandidateFiles(manifest,{root,maxTotalBytes=512*1024**2}={}){
 const {assets,products,receipts}=validateCandidateManifest(manifest);
 check(typeof root==='string'&&path.isAbsolute(root),'ABSOLUTE_CANDIDATE_ROOT_REQUIRED');
 const requested=path.resolve(root),canonical=await realpath(root);check(requested===canonical&&!(await lstat(root)).isSymbolicLink(),'ROOT_SYMLINK_FORBIDDEN');
 check(Number.isSafeInteger(maxTotalBytes)&&maxTotalBytes>0&&maxTotalBytes<=512*1024**2,'MAX_CANDIDATE_BYTES_INVALID');
 check([...assets.values(),...receipts.values()].reduce((s,a)=>s+a.bytes,0)<=maxTotalBytes,'CANDIDATE_BYTE_BUDGET_EXCEEDED');
 const receiptData=new Map();for(const r of receipts.values()){const raw=await readAsset(canonical,r);let parsed;try{parsed=JSON.parse(raw.toString('utf8'));}catch{deny('RECEIPT_JSON_INVALID');}receiptData.set(r.sha256,parsed);}
 for(const p of products.values()){const r=receiptData.get(p.provenance.acquisitionReceiptSha256),v=p.provenance;
  check(r.schema==='WORLD_ENGINE_LOCAL_DERIVATION_RECEIPT_V1'&&r.productKind===p.kind&&r.derivedArtifactSha256===assets.get(p.assetId).sha256,'DERIVATION_RECEIPT_PRODUCT_MISMATCH');
  check(receiptData.has(v.upstreamManifestSha256),'UPSTREAM_MANIFEST_NOT_BOUND');validateUpstreamManifest(receiptData.get(v.upstreamManifestSha256));
  for(const k of ['upstreamManifestSha256','resampling','colorMapping'])check(eq(r[k],v[k]),'DERIVATION_RECEIPT_PROVENANCE_MISMATCH');
 }
 const data=new Map();for(const a of assets.values())data.set(a.id,await readAsset(canonical,a));
 for(const a of assets.values())if(a.encoding==='MASK8')check(data.get(a.id).every(v=>v===0||v===1),'MASK_MUST_BE_BINARY_0_1');
 const bytesFor=id=>data.get(products.get(id).assetId),reports=[];
 for(const l of manifest.layers){
  const a=assets.get(l.rgbAssetId),out=data.get(l.rgbAssetId),optical=bytesFor(l.opticalProductId),base=bytesFor(l.baselineProductId),baseValid=bytesFor(l.baselineValidityProductId),valid=bytesFor(l.opticalValidityProductId),land=bytesFor(l.knownLandMaskProductId),water=bytesFor(l.knownWaterMaskProductId),unknown=bytesFor(l.unknownMaskProductId),select=bytesFor(l.selectionProductId);
  let opticalPixels=0,invalidOpticalKnownLandPixels=0,knownLandPixels=0,knownWaterPixels=0,unknownPixels=0;
  for(let i=0;i<select.length;i++){
   check(land[i]+water[i]+unknown[i]===1,'CLASSIFICATION_MASKS_MUST_PARTITION');
   check(baseValid[i]===1,'BASEMAP_MUST_HAVE_VALID_COMPLETE_COVERAGE');
   check(select[i]===Number(valid[i]===1&&land[i]===1),'SELECTION_MUST_EQUAL_VALID_OPTICAL_AND_LAND');
   if(select[i])opticalPixels++;if(land[i]&&!valid[i])invalidOpticalKnownLandPixels++;knownLandPixels+=land[i];knownWaterPixels+=water[i];unknownPixels+=unknown[i];
   const source=select[i]?optical:base;for(let c=0;c<3;c++)check(out[i*3+c]===source[i*3+c],'COMPOSITE_IS_NOT_EXACT_REAL_SOURCE_SELECTION');
  }
  let height=null;
  if(l.height){
   const h=l.height,raw=bytesFor(h.dsmProductId),validH=bytesFor(h.validityProductId),use=bytesFor(h.useMaskProductId),[w,he]=a.dimensions,r=h.neighborhoodRadiusSamples;
   let usable=0,measuredZero=0;
   for(let i=0;i<validH.length;i++){const value=raw.readFloatLE(i*4);check(validH[i]?Number.isFinite(value):Number.isNaN(value),'DSM_INVALID_VALUES_MUST_REMAIN_NAN');if(validH[i]&&value===0)measuredZero++;}
   const stride=w+1,invalidPrefix=new Uint32Array((w+1)*(he+1));
   for(let y=0;y<he;y++){let row=0;for(let x=0;x<w;x++){row+=1-validH[y*w+x];invalidPrefix[(y+1)*stride+x+1]=invalidPrefix[y*stride+x+1]+row;}}
   for(let y=0;y<he;y++)for(let x=0;x<w;x++){
    const i=y*w+x;if(!use[i])continue;check(land[i]===1,'DSM_USE_REQUIRES_KNOWN_LAND_MASK');
    check(x>=r&&y>=r&&x<w-r&&y<he-r,'DSM_USE_NEIGHBORHOOD_OUTSIDE_GRID');
    const x0=x-r,y0=y-r,x1=x+r+1,y1=y+r+1;
    check(invalidPrefix[y1*stride+x1]-invalidPrefix[y0*stride+x1]-invalidPrefix[y1*stride+x0]+invalidPrefix[y0*stride+x0]===0,'DSM_USE_HAS_INCOMPLETE_NEIGHBORHOOD');usable++;
   }
   height={usablePixels:usable,measuredZeroPixels:measuredZero,invalidPixels:validH.length-validH.reduce((s,v)=>s+v,0),outsidePolicy:h.outsidePolicy};
  }
  reports.push({role:l.role,dimensions:[...a.dimensions],opticalPixels,invalidOpticalKnownLandPixels,knownLandPixels,knownWaterPixels,unknownPixels,height});
 }
 return{schema:'WORLD_ENGINE_DERIVED_SOURCE_CANDIDATE_CHECK_V1',status:'QUALIFICATION_REQUIRED',structuralAndByteChecks:'PASSED',productionAdmitted:false,renderAllowed:false,imageBuildAllowed:false,checkedAssetCount:assets.size,layers:reports,remainingChecks:[...manifest.qualification.missingChecks],provenanceScope:'Hashes verify supplied derivative files; upstream-list completeness and acquisition receipt authenticity, resampling correctness, source validity semantics, shoreline accuracy, visual quality, and renderer integration are not certified by this validator.'};
}
