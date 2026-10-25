/** Data-driven region/source admission. No renderer, shader, invented elevation or country exception. */
import {readFile,mkdir,lstat,realpath,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {assertPrivateWorkspace,assertQualifiedPrivatePath,ensureQualifiedPrivateDirectory} from './backend/private_workspace.mjs';
import {fitGeographicExtent,compileScalePlan} from '../../web/map_infographic_v1/scale_contract.mjs';
import {compileMinimumContextPlan,evaluateMinimumContextCameraFrame} from '../../web/map_infographic_v1/camera_director_v5.mjs';

export const REGION_SOURCE_VERSION='WORLD_ENGINE_REGION_SOURCE_V2';
export const HERE=path.dirname(fileURLToPath(import.meta.url));
export const REPO=path.resolve(HERE,'../../..');
const CATALOG=path.join(HERE,'../universal-presentation-v2/REGION_SOURCE_CATALOG.json'),run=promisify(execFile),clone=structuredClone;
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const plain=v=>v!==null&&typeof v==='object'&&!Array.isArray(v)&&[Object.prototype,null].includes(Object.getPrototypeOf(v));
const within=(p,r)=>p===r||p.startsWith(r+path.sep);
const issue=(status,code,field,reason,example)=>({status,code,field,reason,example});
const statusOf=rows=>['INVALID','CONFLICT','UNSUPPORTED','NEEDS_INPUT'].find(s=>rows.some(r=>r.status===s))??'PASS';
const check=(ok,code)=>{if(!ok)throw Error(code);};
export const canonicalJSON=value=>Array.isArray(value)?'['+value.map(canonicalJSON).join(',')+']':plain(value)?'{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonicalJSON(value[k])).join(',')+'}':JSON.stringify(value);
const contains=(a,b)=>a[0]<=b[0]&&a[1]<=b[1]&&a[2]>=b[2]&&a[3]>=b[3];
const unionBounds=(a,b)=>[Math.min(a[0],b[0]),Math.min(a[1],b[1]),Math.max(a[2],b[2]),Math.max(a[3],b[3])];
const finitePoint=v=>Array.isArray(v)&&v.length===2&&v.every(Number.isFinite)&&Math.abs(v[0])<=180&&Math.abs(v[1])<=90;

export function validateRegionRequest(value){
 const issues=[];
 if(!plain(value))return{status:'NEEDS_INPUT',issues:[issue('NEEDS_INPUT','REGION_OBJECT_REQUIRED','$.region','Supply a geographic center and bbox; place names do not supply coordinates.',{center:[138,37],bbox:[130,29,145,46],crs:'EPSG:4326'})]};
 for(const key of Object.keys(value))if(!['center','bbox','countryId','countryName','sourceId','crs','legacyProfileId'].includes(key))issues.push(issue('UNSUPPORTED','REGION_FIELD_UNSUPPORTED','$.region.'+key,'This regional provider does not consume this field.',{supportedFields:['center','bbox','countryId','countryName','sourceId','crs','legacyProfileId']}));
 if(value.legacyProfileId!==undefined&&typeof value.legacyProfileId!=='string')issues.push(issue('INVALID','LEGACY_PROFILE_ID_INVALID','$.region.legacyProfileId','Use a registered legacy profile identifier.',{legacyProfileId:'europe_germany'}));
 if(value.crs!==undefined&&value.crs!=='EPSG:4326')issues.push(issue('UNSUPPORTED','REGION_CRS_UNSUPPORTED','$.region.crs','The provider preserves EPSG:4326 coordinates; it does not guess a CRS transform.',{crs:'EPSG:4326'}));
 for(const key of ['sourceId','countryId','countryName'])if(value[key]!==undefined&&(typeof value[key]!=='string'||!value[key].trim()))issues.push(issue('INVALID','REGION_TEXT_FIELD_INVALID','$.region.'+key,'Use a nonempty string or omit this optional field.',{[key]:'See REGION_SOURCE_CATALOG.json'}));
 if(value.legacyProfileId!==undefined&&value.center===undefined&&value.bbox===undefined)return{status:statusOf(issues),issues,region:issues.length?undefined:clone(value)};
 if(!finitePoint(value.center))issues.push(issue(value.center===undefined?'NEEDS_INPUT':'INVALID','REGION_CENTER_REQUIRED','$.region.center','Use finite [longitude,latitude] in EPSG:4326.',{center:[138,37]}));
 const b=value.bbox;
 if(!Array.isArray(b)||b.length!==4||!b.every(Number.isFinite))issues.push(issue(b===undefined?'NEEDS_INPUT':'INVALID','REGION_BBOX_REQUIRED','$.region.bbox','Use [west,south,east,north].',{bbox:[130,29,145,46]}));
 else{
  if(b[0]>=b[2])issues.push(issue('UNSUPPORTED','REGION_ANTIMERIDIAN_OR_REVERSED_BOUNDS','$.region.bbox','This flat regional path requires unwrapped increasing west/east bounds; dateline split is not inferred.',{bbox:[130,29,145,46]}));
  if(b[1]>=b[3]||b[0]<-180||b[2]>180||b[1]<-90||b[3]>90)issues.push(issue('INVALID','REGION_BBOX_RANGE','$.region.bbox','Bounds must be nonempty and inside EPSG:4326.',{bbox:[130,29,145,46]}));
  if(b[1]<-85||b[3]>85)issues.push(issue('UNSUPPORTED','REGION_POLAR_PROJECTION_REQUIRED','$.region.bbox','The existing flat regional projection is not admitted beyond ±85 degrees.',{action:'Provide a supported regional extent; polar projection is not implemented here.'}));
  if(b[0]<b[2]&&b[1]<b[3]&&finitePoint(value.center)&&!(value.center[0]>=b[0]&&value.center[0]<=b[2]&&value.center[1]>=b[1]&&value.center[1]<=b[3]))issues.push(issue('CONFLICT','REGION_CENTER_OUTSIDE_BBOX','$.region.center','The requested center must lie inside its requested extent.',{center:[(b[0]+b[2])/2,(b[1]+b[3])/2]}));
 }
 return{status:statusOf(issues),issues,region:issues.length?undefined:{...clone(value),crs:'EPSG:4326',sourceId:value.sourceId??'AUTO'}};
}

async function safeFile(relative){
 check(typeof relative==='string'&&!path.isAbsolute(relative),'REGION_SERVER_RELATIVE_SOURCE_REQUIRED');
 const file=path.resolve(REPO,relative),real=await realpath(file);
 check(real===file&&within(real,REPO),'REGION_SOURCE_PATH_UNSAFE');
 const stat=await lstat(file);check(stat.isFile()&&!stat.isSymbolicLink(),'REGION_SOURCE_REGULAR_FILE_REQUIRED');
 return{file,raw:await readFile(file),stat};
}
export async function loadRegionSourceCatalog(){
 const raw=await readFile(CATALOG),data=JSON.parse(raw);check(data.schema==='WORLD_ENGINE_REGION_SOURCE_CATALOG_V2','REGION_CATALOG_SCHEMA_REQUIRED');
 return{data,sha256:hash(raw)};
}
async function loadSeed(catalog){
 const file=await safeFile(catalog.seed.file);check(hash(file.raw)===catalog.seed.sha256,'REGION_SEED_ARCHIVE_SHA_MISMATCH');
 const script="import zipfile,sys;sys.stdout.write(zipfile.ZipFile(sys.argv[1]).read(sys.argv[2]).decode())";
 const {stdout}=await run('python',['-B','-c',script,file.file,catalog.seed.member],{timeout:30000,maxBuffer:32*1024**2});
 const seed=JSON.parse(stdout);check(Array.isArray(seed.nativePlan?.geometries),'REGION_SEED_GIS_REQUIRED');
 const gis=await safeFile(catalog.gis.file);check(hash(gis.raw)===catalog.gis.sha256,'REGION_GIS_SHA_MISMATCH');
 const license=await safeFile(catalog.gis.licenseFile);check(hash(license.raw)===catalog.gis.licenseSHA256,'REGION_GIS_LICENSE_SHA_MISMATCH');
 return seed;
}
function boundaryDistance(point,a,b){
 const dx=b[0]-a[0],dy=b[1]-a[1],den=dx*dx+dy*dy,t=den?Math.max(0,Math.min(1,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/den)):0;
 return Math.hypot(point[0]-a[0]-t*dx,point[1]-a[1]-t*dy);
}
function unwrapRing(ring){
 const result=[];for(const p of ring){let x=p[0];if(result.length){while(x-result.at(-1)[0]>180)x-=360;while(x-result.at(-1)[0]<-180)x+=360;}result.push([x,p[1]]);}return result;
}
function ringPoint(point,ring){const xs=ring.map(p=>p[0]),mid=(Math.min(...xs)+Math.max(...xs))/2;let x=point[0];while(x-mid>180)x-=360;while(x-mid< -180)x+=360;return[x,point[1]];}
function ringContains(given,raw){
 const ring=unwrapRing(raw),point=ringPoint(given,ring);
 let inside=false;
 for(let i=0,j=ring.length-1;i<ring.length;j=i++){
  const a=ring[j],b=ring[i];if(boundaryDistance(point,a,b)<1e-9)return true;
  if((a[1]>point[1])!==(b[1]>point[1])&&point[0]<(b[0]-a[0])*(point[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside;
 }return inside;
}
export function pointInCountry(point,record){
 const polygons=record.geometry_type==='Polygon'?[record.coordinates]:record.geometry_type==='MultiPolygon'?record.coordinates:[];
 return polygons.some(poly=>ringContains(point,poly[0])&&!poly.slice(1).some(hole=>ringContains(point,hole)));
}
function countryBoundaryDistance(point,record){
 const polygons=record.geometry_type==='Polygon'?[record.coordinates]:record.coordinates;let distance=Infinity;
 for(const polygon of polygons)for(const raw of polygon){const ring=unwrapRing(raw),p=ringPoint(point,ring);for(let i=1;i<ring.length;i++)distance=Math.min(distance,boundaryDistance(p,ring[i-1],ring[i]));}
 return distance;
}
function segmentIntersectsBounds(a,b,box){
 let lo=0,hi=1;const delta=[b[0]-a[0],b[1]-a[1]];
 for(let axis=0;axis<2;axis++){if(Math.abs(delta[axis])<1e-15){if(a[axis]<box[axis]||a[axis]>box[axis+2])return false;continue;}let t0=(box[axis]-a[axis])/delta[axis],t1=(box[axis+2]-a[axis])/delta[axis];if(t0>t1)[t0,t1]=[t1,t0];lo=Math.max(lo,t0);hi=Math.min(hi,t1);if(lo>hi)return false;}return true;
}
function countryIntersectsBounds(record,bounds){
 if([[bounds[0],bounds[1]],[bounds[0],bounds[3]],[bounds[2],bounds[1]],[bounds[2],bounds[3]]].some(p=>pointInCountry(p,record)))return true;
 const polygons=record.geometry_type==='Polygon'?[record.coordinates]:record.coordinates;
 for(const polygon of polygons)for(const raw of polygon){const ring=unwrapRing(raw);for(const offset of [-360,0,360]){const shifted=[bounds[0]+offset,bounds[1],bounds[2]+offset,bounds[3]];for(let i=1;i<ring.length;i++)if(segmentIntersectsBounds(ring[i-1],ring[i],shifted))return true;}}return false;
}
function countryByRef(countries,ref){
 const key=ref?.normalize('NFKC').toLocaleLowerCase('en-US');
 return countries.find(r=>[r.id,r.name,r.source_feature_id].some(s=>typeof s==='string'&&s.normalize('NFKC').toLocaleLowerCase('en-US')===key));
}
function sourceWindow(source,bounds,gutter=2){
 const [w,s,e,n]=source.bounds,[dx,dy]=source.pixelSpacing,[width,height]=source.dimensions;
 const x0=Math.max(0,Math.floor((bounds[0]-w)/dx)-gutter),y0=Math.max(0,Math.floor((n-bounds[3])/dy)-gutter),x1=Math.min(width,Math.ceil((bounds[2]-w)/dx)+gutter),y1=Math.min(height,Math.ceil((n-bounds[1])/dy)+gutter);
 const actual=[w+x0*dx,n-y1*dy,w+x1*dx,n-y0*dy],spacing=source.pixelSpacing;
 const minimum=Math.min((bounds[0]-actual[0])/spacing[0],(bounds[1]-actual[1])/spacing[1],(actual[2]-bounds[2])/spacing[0],(actual[3]-bounds[3])/spacing[1]);
 return{pixelBox:[x0,y0,x1,y1],dimensions:[x1-x0,y1-y0],bounds:actual,minimumGutterPixels:minimum};
}
async function chooseSource(catalog,region,bounds){
 const wanted=region.sourceId??'AUTO',unavailable=catalog.unavailableOriginals.find(row=>row.id===wanted);
 if(unavailable)throw Object.assign(Error('REGION_SOURCE_NOT_MATERIALIZED'),{status:'UNSUPPORTED',detail:unavailable});
 const candidates=catalog.sources.filter(row=>(wanted==='AUTO'||row.id===wanted)&&contains(row.bounds,bounds)).sort((a,b)=>a.priority-b.priority||a.id.localeCompare(b.id));
 for(const source of candidates){
  const window=sourceWindow(source,bounds,catalog.minimumGutterPixels);
  if(window.minimumGutterPixels<1-1e-9||Math.max(...window.dimensions)>catalog.maxNativeTextureDimension)continue;
  const asset=await safeFile(source.file);check(hash(asset.raw)===source.sha256&&asset.raw.length===source.bytes,'REGION_ASSET_SHA_MISMATCH');
  const license=await safeFile(source.licenseFile);check(hash(license.raw)===source.licenseSHA256,'REGION_LICENSE_SHA_MISMATCH');
  if(source.attributionFile){const credit=await safeFile(source.attributionFile);check(hash(credit.raw)===source.attributionSHA256,'REGION_ATTRIBUTION_SHA_MISMATCH');}
  return{source:clone(source),window};
 }
 throw Object.assign(Error(wanted!=='AUTO'&&!catalog.sources.some(s=>s.id===wanted)?'REGION_SOURCE_ID_UNKNOWN':'REGION_NO_NATIVE_SOURCE_COVERAGE'),{status:'UNSUPPORTED',detail:{bounds,wanted,maxNativeTextureDimension:catalog.maxNativeTextureDimension,minimumGutterPixels:1}});
}
function sceneFacts(value){return value?.facts??value;}

/** Request qualification is a real hash/license/GIS check; trajectory coverage is checked again before draw. */
export async function qualifyRegion({region,facts,scene}={}){
 const result={schema:REGION_SOURCE_VERSION,status:'INVALID',issues:[],phase:'REQUEST_COVERAGE_ONLY',trajectoryCoverageRequiredBeforeStart:true};
 try{
  const validation=validateRegionRequest(region);if(validation.status!=='PASS')return{...result,...validation};
  const {data:catalog,sha256:catalogSHA256}=await loadRegionSourceCatalog();let given=validation.region;
  if(given.legacyProfileId){const old=catalog.legacyProfiles[given.legacyProfileId];if(!old)return{...result,status:'UNSUPPORTED',issues:[issue('UNSUPPORTED','REGION_LEGACY_PROFILE_UNKNOWN','$.region.legacyProfileId','No such preserved profile exists in the server data catalog.',{available:Object.keys(catalog.legacyProfiles)})]};given={...clone(old.region),...given,center:given.center??old.region.center,bbox:given.bbox??old.region.bbox,sourceId:given.sourceId??old.region.sourceId};}
  const preserveLegacyBounds=Boolean(given.legacyProfileId&&region.center===undefined&&region.bbox===undefined);
  const fitted=preserveLegacyBounds?clone(given.bbox):fitGeographicExtent(given.bbox,{center:given.center,output:[1080,1920],padding:1});
  if(fitted[0]<-180||fitted[2]>180||fitted[1]<-85||fitted[3]>85)throw Object.assign(Error('REGION_FITTED_PROJECTION_LIMIT'),{status:'UNSUPPORTED',detail:{fitted}});
  const seed=await loadSeed(catalog),countries=seed.nativePlan.geometries,checks=[];
  let context;
  if(given.countryId!==undefined||given.countryName!==undefined){
   const byId=given.countryId?countryByRef(countries,given.countryId):null,byName=given.countryName?countryByRef(countries,given.countryName):null;
   if(given.countryId&&!byId||given.countryName&&!byName)throw Object.assign(Error('REGION_COUNTRY_REFERENCE_UNKNOWN'),{status:'NEEDS_INPUT',detail:{countryId:given.countryId??null,countryName:given.countryName??null}});
   if(byId&&byName&&byId.id!==byName.id)throw Object.assign(Error('REGION_COUNTRY_NAME_ID_CONFLICT'),{status:'CONFLICT'});
   context=byId??byName;
   if(!pointInCountry(given.center,context)&&countryBoundaryDistance(given.center,context)>catalog.gis.boundaryUncertaintyDegrees)throw Object.assign(Error('REGION_COUNTRY_CENTER_CONFLICT'),{status:'CONFLICT',detail:{countryId:context.id,center:given.center}});
  }else context=countries.find(row=>pointInCountry(given.center,row))??countries.filter(row=>countryIntersectsBounds(row,fitted)).sort((a,b)=>a.id.localeCompare(b.id))[0];
  if(!context)throw Object.assign(Error('REGION_NO_GIS_LAND_CONTEXT'),{status:'UNSUPPORTED',detail:{reason:'The protected native factory requires a real country-context geometry. A pure-ocean extent has no such context; no fake land/ownership ROI is added.'}});
  const data=sceneFacts(facts),locations=scene?.locations??data?.locations??[];
  for(const location of locations){
   if(location?.country_id===undefined)continue;
   const country=countryByRef(countries,location.country_id);
   if(!country)throw Object.assign(Error('REGION_LOCATION_COUNTRY_UNKNOWN'),{status:'NEEDS_INPUT',detail:{locationId:location.id,countryId:location.country_id}});
   const p=location.anchor;if(!finitePoint(p))continue;
   const inside=pointInCountry(p,country),distance=inside?0:countryBoundaryDistance(p,country),uncertain=!inside&&distance<=catalog.gis.boundaryUncertaintyDegrees;
   checks.push({locationId:location.id,countryId:country.id,status:inside?'INSIDE_OR_BOUNDARY':uncertain?'WITHIN_GENERALIZED_BORDER_UNCERTAINTY':'CONFLICT',geographic:clone(p),boundaryDistanceDegrees:distance,boundaryUncertaintyDegrees:catalog.gis.boundaryUncertaintyDegrees});
   if(!inside&&!uncertain)throw Object.assign(Error('REGION_LOCATION_COUNTRY_CONFLICT'),{status:'CONFLICT',detail:checks.at(-1)});
  }
  const selected=await chooseSource(catalog,given,fitted);
  const evidence={schema:'WORLD_ENGINE_REGION_ADMISSION_V2',catalogSHA256,request:clone(given),fittedBounds:fitted,preservedLegacyFraming:preserveLegacyBounds,contextCountryId:context.id,contextCountryName:context.name,contextSelection:pointInCountry(given.center,context)?'CENTER_IN_ACTUAL_SOURCE_GEOMETRY':'REAL_BBOX_INTERSECTING_CONTEXT_ONLY_NO_CENTER_MEMBERSHIP_OR_OWNERSHIP_CLAIM',gisSHA256:catalog.gis.sha256,locationCountryChecks:checks,sourceId:selected.source.id,sourceSHA256:selected.source.sha256,license:selected.source.license,sourceDimensions:selected.source.dimensions,sourceBounds:selected.source.bounds,nativePixelSpacing:selected.source.pixelSpacing,initialWindow:selected.window,terrainTreatment:selected.source.terrainTreatment,styleId:selected.source.styleId,originalNE1Materialized:false,sourceBytesActuallyVerified:true,trajectoryCoverageRequiredBeforeStart:true,noElevationCreated:true,noHistoricalOwnershipInferred:true};
  return{...result,status:'PASS',region:given,regionEvidence:evidence,regionGateSHA256:hash(canonicalJSON(evidence))};
 }catch(error){return{...result,status:error.status??'INVALID',issues:[issue(error.status??'INVALID',String(error.message),'$.region','Region/source qualification failed without a fabricated fallback.',{action:'Correct the region/source request or supply a separately admitted source.',detail:error.detail??null})]};}
}

export async function resolveRegionPlan({scene,region}={}){
 const qualified=await qualifyRegion({region,scene});check(qualified.status==='PASS',qualified.issues?.[0]?.code??'REGION_ADMISSION_FAILED');
 const {data:catalog}=await loadRegionSourceCatalog(),seed=await loadSeed(catalog),nativePlan=clone(seed.nativePlan);
 nativePlan.primary=qualified.regionEvidence.contextCountryId;nativePlan.secondary=[];
 nativePlan.anchor={geometry_type:'Point',crs:'EPSG:4326',coordinates:clone(qualified.region.center)};
 nativePlan.framing={projection:'REGIONAL_EQUIRECTANGULAR',bounds:clone(qualified.regionEvidence.fittedBounds)};
 nativePlan.layout.locationPlacement={schema:'WORLD_ENGINE_LOCATION_PLACEMENT_POLICY_V1',mode:'BOUNDED_GAP_SEARCH',maxGap:216,step:16};
 // Native raster-label metrics and glyph atlas are a single protected binding.
 // Arbitrary supplied text cannot replace their measured seed strings. The
 // presentation wrapper hides these native labels; scene titles stay metadata.
 nativePlan.layout.countryLabels=[];
 nativePlan.scale.information.location=true;
 const compiledNative=compileScalePlan(nativePlan,'REGIONAL',{allCountries:nativePlan.geometries}),primary=nativePlan.geometries.find(item=>item.id===nativePlan.primary);
 const cameraScene={primary_region_id:nativePlan.primary,primary_geometry:clone(primary),event_anchor:clone(qualified.region.center),approved_final_extent:clone(compiledNative.framing.bounds),desired_detail_level:'REGIONAL',scale_admission:{status:'LOCAL_NOT_ADMITTED'},canonical_output:[1080,1920],safe_area:clone(compiledNative.layout.safe),event_geometry:(scene?.geometries??[]).filter(g=>(scene?.camera_intent?.target_geometry_refs??[]).includes(g.id)).map(g=>clone(g.geometry)),context_geometry:[],event_title:'',location_label:'',primary_label:''};
 const baseCameraPlan=compileMinimumContextPlan({scene:cameraScene,profile:clone(seed.cameraPlan.profile),seed:0}),last=evaluateMinimumContextCameraFrame(baseCameraPlan,baseCameraPlan.totalFrames-1);
 check(last.cameraLocked&&last.settle.locked,'REGION_BASE_CAMERA_NOT_LOCKED');check(canonicalJSON(last.camera.flatBounds)===canonicalJSON(compiledNative.framing.bounds),'REGION_BASE_CAMERA_FINAL_EXTENT_CHANGED');
 return{schema:'WORLD_ENGINE_REGION_PLAN_V2',region:qualified.region,nativePlan:compiledNative,regionEvidence:qualified.regionEvidence,regionGateSHA256:qualified.regionGateSHA256,cameraProfile:clone(seed.cameraPlan.profile),baseCameraPlan,cameraPlan:baseCameraPlan,sourceCatalogSHA256:qualified.regionEvidence.catalogSHA256};
}

async function safeCacheRoot(value,options){return ensureQualifiedPrivateDirectory(value,options);}

/** One chosen, actual source covers the whole camera envelope; no per-frame style mixture. */
export async function prepareRegionTerrain({regionPlan,bounds,outputRoot,privateWorkspaceRoot,publicExportRoot}={}){
 check(regionPlan?.schema==='WORLD_ENGINE_REGION_PLAN_V2','REGION_RESOLVED_PLAN_REQUIRED');
 const valid=validateRegionRequest({center:[(bounds?.[0]+bounds?.[2])/2,(bounds?.[1]+bounds?.[3])/2],bbox:bounds});check(valid.status==='PASS',valid.issues?.[0]?.code??'REGION_CAMERA_BOUNDS_INVALID');
 const {data:catalog,sha256:catalogSHA256}=await loadRegionSourceCatalog();check(catalogSHA256===regionPlan.sourceCatalogSHA256,'REGION_SOURCE_CATALOG_CHANGED');
 // The factory also initializes against the immutable approved model framing.
 // A panned movie may never visit one edge of that framing, so camera-only
 // crops cannot satisfy the existing native scale/source admission contract.
 const sourceRequiredBounds=unionBounds(bounds,regionPlan.nativePlan.framing.bounds);
 const {source,window}=await chooseSource(catalog,regionPlan.region,sourceRequiredBounds),cache=await safeCacheRoot(outputRoot,{privateWorkspaceRoot,publicExportRoot});
 const identity={schema:'WORLD_ENGINE_NATIVE_SOURCE_WINDOW_V2',catalogSHA256,requestRegionGateSHA256:regionPlan.regionGateSHA256,sourceSHA256:source.sha256,cameraEnvelope:clone(bounds),initializationAndAnalysisBounds:clone(regionPlan.nativePlan.framing.bounds),sourceRequiredBounds:clone(sourceRequiredBounds),pixelBox:window.pixelBox,dimensions:window.dimensions,bounds:window.bounds,method:'EXACT_SOURCE_PIXEL_WINDOW_NO_RESAMPLE_NO_RECOLOR'},key=hash(canonicalJSON(identity)),directory=path.join(cache,'region-'+key),png=path.join(directory,'terrain.png'),record=path.join(directory,'CACHE.json');
 let created=false;
 try{await mkdir(directory,{mode:0o700});created=true;}catch(error){if(error.code!=='EEXIST')throw error;}
 if(created){
  const script=`import json,hashlib,sys,os\nfrom PIL import Image\nsrc,dst,box,expected,dimensions=sys.argv[1:]\nraw=open(src,'rb').read()\nassert hashlib.sha256(raw).hexdigest()==expected,'REGION_CROP_SOURCE_CHANGED'\nwith Image.open(src) as im:\n assert im.mode=='RGB','REGION_RGB_SOURCE_REQUIRED'\n assert list(im.size)==json.loads(dimensions),'REGION_SOURCE_DIMENSION_MISMATCH'\n crop=im.crop(tuple(json.loads(box)))\n with open(dst,'xb') as out:crop.save(out,format='PNG',compress_level=6)\n os.chmod(dst,0o600)\n with Image.open(dst) as check:assert check.mode=='RGB' and check.size==crop.size and check.tobytes()==crop.tobytes(),'REGION_CROP_BYTES_MISMATCH'\n print(json.dumps({'dimensions':list(crop.size),'decodedRGBSHA256':hashlib.sha256(crop.tobytes()).hexdigest()}))`;
  const {stdout}=await run('python',['-B','-c',script,path.resolve(REPO,source.file),png,JSON.stringify(window.pixelBox),source.sha256,JSON.stringify(source.dimensions)],{timeout:60000,maxBuffer:1024**2});
  const bytes=await readFile(png),metadata=JSON.parse(stdout);check(JSON.stringify(metadata.dimensions)===JSON.stringify(window.dimensions),'REGION_CROP_DIMENSION_MISMATCH');
  await writeFile(record,JSON.stringify({identity,sha256:hash(bytes),bytes:bytes.length,decodedRGBSHA256:metadata.decodedRGBSHA256},null,2)+'\n',{flag:'wx',mode:0o600});
 }else{
  let complete=false;for(let attempt=0;attempt<40;attempt++){try{await lstat(record);complete=true;break;}catch(error){if(error.code!=='ENOENT')throw error;await new Promise(r=>setTimeout(r,50));}}
  check(complete,'REGION_CACHE_INCOMPLETE_NO_OVERWRITE');
 }
 const cacheStat=await lstat(directory);check(cacheStat.isDirectory()&&!cacheStat.isSymbolicLink()&&!(cacheStat.mode&0o077),'REGION_CACHE_DIRECTORY_UNSAFE');
 const pngStat=await lstat(png),recordStat=await lstat(record);check(pngStat.isFile()&&!pngStat.isSymbolicLink()&&recordStat.isFile()&&!recordStat.isSymbolicLink(),'REGION_CACHE_FILE_UNSAFE');
 const saved=JSON.parse(await readFile(record,'utf8')),bytes=await readFile(png);check(canonicalJSON(saved.identity)===canonicalJSON(identity)&&hash(bytes)===saved.sha256&&bytes.length===saved.bytes,'REGION_CACHE_CORRUPTION_REFUSED');
 const asset={file:png,path:png,url:'/presentation-assets/'+key+'.png',sha256:saved.sha256,bytes:saved.bytes,bounds:clone(window.bounds),dimensions:clone(window.dimensions),pixelSpacing:clone(source.pixelSpacing),CRS:'EPSG:4326',classification:source.classification,license:source.license,NoData:null,sourceOriginalSHA256:source.sha256,
  source:{name:source.id,sha256:source.sha256,url:source.sourceOriginal.url,license:source.license,crs:'EPSG:4326',resolution:clone(source.dimensions),geographicExtent:clone(source.bounds),pixelSpacing:clone(source.pixelSpacing)},lodPreparation:{method:identity.method,cropSourcePixelBox:clone(window.pixelBox),gutterSourcePixels:catalog.minimumGutterPixels}};
 const plan=clone(regionPlan.nativePlan);plan.assets.terrain=clone(asset);
 const nativePlan=compileScalePlan(plan,'REGIONAL',{allCountries:plan.geometries});check(nativePlan.scale.lod.rasterCoverage==='FULL_REGIONAL_CROP','REGION_SOURCE_FULL_VIEWPORT_REQUIRED');
 const evidence={...clone(regionPlan.regionEvidence),phase:'FULL_CAMERA_ENVELOPE',trajectoryCoverageRequiredBeforeStart:false,sourceId:source.id,sourceSHA256:source.sha256,sourceDimensions:clone(source.dimensions),sourceBounds:clone(source.bounds),nativePixelSpacing:clone(source.pixelSpacing),cameraEnvelope:clone(bounds),initializationAndAnalysisBounds:clone(regionPlan.nativePlan.framing.bounds),sourceRequiredBounds:clone(sourceRequiredBounds),actualCropBounds:clone(window.bounds),minimumSourceGutterPixels:window.minimumGutterPixels,cacheKey:key,cacheReused:!created,cropSHA256:saved.sha256,decodedNativeCropRGBSHA256:saved.decodedRGBSHA256,terrainTreatment:source.terrainTreatment,styleId:source.styleId,license:source.license,attribution:source.attribution??'Natural Earth contributors; Public Domain',registrationBasis:source.registrationBasis,sourceSelection:'ONE_ACTUAL_SOURCE_FOR_COMPLETE_CAMERA_ENVELOPE_NO_PATCH_MIX',newHeightData:false,resampling:false};
 const sourceStyle={schema:'WORLD_ENGINE_REGION_SOURCE_STYLE_V2',styleId:source.styleId,terrainTreatment:source.terrainTreatment,sourceOriginal:{...clone(source.sourceOriginal),actualParentFileSHA256:source.sha256,actualParentDimensions:clone(source.dimensions),actualParentBounds:clone(source.bounds)},terrainAsset:asset,cropSourcePixelBox:clone(window.pixelBox),sourceRegistration:{CRS:'EPSG:4326',axisOrder:'longitude_latitude',dimensions:clone(source.dimensions),pixelEdgeBounds:clone(source.bounds),pixelSpacing:clone(source.pixelSpacing),pixelCenterConvention:true},outsideSupportPolicy:'FAIL_BEFORE_DRAW_NO_CROP_GLOBAL_STYLE_MIX',nativeWindowPolicy:{operation:identity.method,maxTextureDimension:catalog.maxNativeTextureDimension,gutterSourcePixels:catalog.minimumGutterPixels},license:source.license,attribution:evidence.attribution};
 return{...clone(regionPlan),nativePlan,sourceStyle,terrainTreatment:source.terrainTreatment,regionEvidence:evidence,fullCoverageSHA256:hash(canonicalJSON(evidence)),sourceBindings:[{role:'regionSourceCatalog',path:CATALOG,sha256:catalogSHA256},{role:'terrainParent',path:path.resolve(REPO,source.file),sha256:source.sha256,bytes:source.bytes},{role:'terrain',path:png,sha256:saved.sha256,bytes:saved.bytes}],terrainPath:png,cacheRecordPath:record};
}

/** Recheck untrusted/stored receipts against actual server files; this never authorizes a GPU. */
export async function verifyRegionQualification({prepared,qualification,privateWorkspaceRoot,publicExportRoot}={}){
 try{
  if(!prepared){check(qualification?.status==='PASS'&&qualification.regionEvidence?.phase!=='FULL_CAMERA_ENVELOPE','REGION_REQUEST_RECEIPT_REQUIRED');const locations=(qualification.regionEvidence.locationCountryChecks??[]).map(row=>({id:row.locationId,country_id:row.countryId,anchor:row.geographic}));const region=clone(qualification.region);if(qualification.regionEvidence.preservedLegacyFraming){delete region.center;delete region.bbox;}const actual=await qualifyRegion({region,facts:{locations}});check(actual.status==='PASS'&&actual.regionGateSHA256===qualification.regionGateSHA256,'REGION_REQUEST_RECEIPT_STALE_OR_INVALID');return{status:'PASS',phase:'REQUEST_COVERAGE_ONLY',regionGateSHA256:actual.regionGateSHA256,trajectoryCoverageRequiredBeforeStart:true};}
  await assertPrivateWorkspace({privateWorkspaceRoot,publicExportRoot});
  const e=prepared.regionEvidence;check(e?.phase==='FULL_CAMERA_ENVELOPE'&&e.trajectoryCoverageRequiredBeforeStart===false,'REGION_FULL_CAMERA_RECEIPT_REQUIRED');check(prepared.fullCoverageSHA256===hash(canonicalJSON(e)),'REGION_FULL_CAMERA_RECEIPT_SHA_MISMATCH');
  const {data:catalog,sha256:catalogSHA256}=await loadRegionSourceCatalog();check(catalogSHA256===prepared.sourceCatalogSHA256&&catalogSHA256===e.catalogSHA256,'REGION_SOURCE_CATALOG_CHANGED');
  await loadSeed(catalog); // Includes actual GIS, source archive and license bytes.
  check(canonicalJSON(e.initializationAndAnalysisBounds)===canonicalJSON(prepared.nativePlan?.framing?.bounds)&&canonicalJSON(e.initializationAndAnalysisBounds)===canonicalJSON(e.fittedBounds),'REGION_INITIALIZATION_FRAMING_CHANGED');
  const requiredBounds=unionBounds(e.cameraEnvelope,e.initializationAndAnalysisBounds);check(canonicalJSON(requiredBounds)===canonicalJSON(e.sourceRequiredBounds),'REGION_REQUIRED_COVERAGE_RECEIPT_MISMATCH');
  const selected=await chooseSource(catalog,prepared.region,requiredBounds);check(selected.source.id===e.sourceId&&selected.source.sha256===e.sourceSHA256,'REGION_SOURCE_RECEIPT_MISMATCH');
  const identity={schema:'WORLD_ENGINE_NATIVE_SOURCE_WINDOW_V2',catalogSHA256,requestRegionGateSHA256:prepared.regionGateSHA256,sourceSHA256:selected.source.sha256,cameraEnvelope:clone(e.cameraEnvelope),initializationAndAnalysisBounds:clone(e.initializationAndAnalysisBounds),sourceRequiredBounds:clone(requiredBounds),pixelBox:selected.window.pixelBox,dimensions:selected.window.dimensions,bounds:selected.window.bounds,method:'EXACT_SOURCE_PIXEL_WINDOW_NO_RESAMPLE_NO_RECOLOR'},key=hash(canonicalJSON(identity));check(key===e.cacheKey,'REGION_CACHE_KEY_MISMATCH');
  const png=path.resolve(prepared.terrainPath),record=path.resolve(prepared.cacheRecordPath),dir=path.dirname(png);await assertQualifiedPrivatePath(dir,{privateWorkspaceRoot,publicExportRoot});check(within(png,privateWorkspaceRoot)&&png!==privateWorkspaceRoot&&!within(png,REPO)&&path.basename(dir)==='region-'+key&&path.basename(png)==='terrain.png'&&record===path.join(dir,'CACHE.json'),'REGION_CACHE_RECEIPT_PATH_INVALID');
  for(const file of [dir,png,record]){const stat=await lstat(file);check(!stat.isSymbolicLink()&&stat.uid===process.getuid()&&!(stat.mode&0o077),'REGION_CACHE_FILE_UNSAFE');check((await realpath(file))===file,'REGION_CACHE_FILE_PATH_UNSAFE');}
  const saved=JSON.parse(await readFile(record,'utf8')),bytes=await readFile(png);check(canonicalJSON(saved.identity)===canonicalJSON(identity)&&hash(bytes)===saved.sha256&&saved.sha256===e.cropSHA256&&bytes.length===saved.bytes,'REGION_CACHE_CORRUPTION_REFUSED');
  const a=prepared.sourceStyle?.terrainAsset;check(a?.sha256===saved.sha256&&a.file===png&&a.path===png&&canonicalJSON(a.bounds)===canonicalJSON(selected.window.bounds)&&canonicalJSON(a.dimensions)===canonicalJSON(selected.window.dimensions)&&canonicalJSON(a.pixelSpacing)===canonicalJSON(selected.source.pixelSpacing)&&a.classification===selected.source.classification&&canonicalJSON(prepared.nativePlan?.assets?.terrain)===canonicalJSON(a),'REGION_TERRAIN_BINDING_MISMATCH');
  check(e.terrainTreatment===selected.source.terrainTreatment&&prepared.terrainTreatment===e.terrainTreatment&&prepared.sourceStyle.terrainTreatment===e.terrainTreatment&&e.styleId===selected.source.styleId&&e.decodedNativeCropRGBSHA256===saved.decodedRGBSHA256,'REGION_SOURCE_STYLE_RECEIPT_MISMATCH');
  return{status:'PASS',phase:'FULL_CAMERA_ENVELOPE',fullCoverageSHA256:prepared.fullCoverageSHA256,cropSHA256:saved.sha256,sourceSHA256:selected.source.sha256,cacheKey:key,trajectoryCoverageRequiredBeforeStart:false,actualSourceAndCropBytesVerified:true};
 }catch(error){return{status:'INVALID',issues:[issue('INVALID',String(error.message),'$.regionQualification','Source/crop verification failed; do not start or reuse a job.',{action:'Preserve the failed cache and prepare a new valid, server-owned qualification.'})]};}
}

export async function legacyRegionProfile(id){
 const {data:catalog}=await loadRegionSourceCatalog(),profile=catalog.legacyProfiles[id];if(!profile)return null;
 const zip=await safeFile(catalog.seed.file);check(hash(zip.raw)===catalog.seed.sha256,'REGION_SEED_ARCHIVE_SHA_MISMATCH');
 const script="import zipfile,sys;sys.stdout.write(zipfile.ZipFile(sys.argv[1]).read(sys.argv[2]).decode())";
 const {stdout}=await run('python',['-B','-c',script,zip.file,profile.seedMember],{timeout:30000,maxBuffer:32*1024**2});
 return{region:clone(profile.region),runtime:JSON.parse(stdout),memberSHA256:hash(stdout)};
}
