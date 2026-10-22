import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,mkdtemp,writeFile,chmod,rename} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import path from 'node:path';
import {REGION_SOURCE_VERSION,REPO,loadRegionSourceCatalog,validateRegionRequest,qualifyRegion,resolveRegionPlan,prepareRegionTerrain,verifyRegionQualification,legacyRegionProfile,pointInCountry} from '../region_source.mjs';

const run=promisify(execFile),hash=b=>createHash('sha256').update(b).digest('hex');
const japan={center:[138,37],bbox:[130,29,145,46],countryId:'COUNTRY_JPN'};
const australia={center:[139.5,-29.5],bbox:[126,-42,153,-17],countryId:'COUNTRY_AUS'};
const privateRoot=await mkdtemp('/workspace/region-provider-tests-');
await chmod(privateRoot,0o700);
const catalog=await loadRegionSourceCatalog();
let japanPlan,preparedJapan;

test('catalog is server-owned coverage data, not a five-region renderer switch',()=>{
 assert.equal(catalog.data.schema,'WORLD_ENGINE_REGION_SOURCE_CATALOG_V2');
 assert.equal(catalog.data.sources.length,7);assert.equal(Object.keys(catalog.data.legacyProfiles).length,5);
 assert.ok(catalog.data.sources.some(s=>s.id==='GLOBAL_EARTH_DAY_RGB_V1'&&s.bounds.join(',')==='-180,-90,180,90'));
 assert.equal(catalog.data.unavailableOriginals[0].state,'GIT_LFS_POINTER_NOT_MATERIALIZED');
});
test('NE1 global parent is really a pointer; it is never silently accepted as 699 MB TIFF',async()=>{
 const row=catalog.data.unavailableOriginals[0],raw=await readFile(path.join(REPO,row.file));
 assert.equal(raw.length,134);assert.match(raw.toString(),/^version https:\/\/git-lfs.github.com\/spec\/v1/);
 assert.match(raw.toString(),new RegExp(row.expectedOriginalSHA256));
 const q=await qualifyRegion({region:{...japan,sourceId:row.id}});assert.equal(q.status,'UNSUPPORTED');assert.equal(q.issues[0].code,'REGION_SOURCE_NOT_MATERIALIZED');
});
for(const source of catalog.data.sources)test('actual source and redistribution evidence: '+source.id,async()=>{
 const raw=await readFile(path.join(REPO,source.file));assert.equal(hash(raw),source.sha256);assert.equal(raw.length,source.bytes);
 const license=await readFile(path.join(REPO,source.licenseFile));assert.equal(hash(license),source.licenseSHA256);
 if(source.attributionFile)assert.equal(hash(await readFile(path.join(REPO,source.attributionFile))),source.attributionSHA256);
 const {stdout}=await run('python',['-B','-c','from PIL import Image;import sys,json;im=Image.open(sys.argv[1]);print(json.dumps([list(im.size),im.mode]))',path.join(REPO,source.file)]);
 assert.deepEqual(JSON.parse(stdout),[source.dimensions,'RGB']);
 assert.ok(Math.abs((source.bounds[2]-source.bounds[0])/source.dimensions[0]-source.pixelSpacing[0])<1e-12);
 assert.ok(Math.abs((source.bounds[3]-source.bounds[1])/source.dimensions[1]-source.pixelSpacing[1])<1e-12);
});
for(const [id,profile] of Object.entries(catalog.data.legacyProfiles))test('preserved profile and actual source pixels remain available: '+id,async()=>{
 const old=await legacyRegionProfile(id),q=await qualifyRegion({region:{legacyProfileId:id}});
 assert.equal(q.status,'PASS',JSON.stringify(q.issues));assert.equal(q.regionEvidence.sourceId,profile.sourceId);
 assert.equal(q.regionEvidence.sourceSHA256,old.runtime.sourceStyle.terrainAsset.sha256);
 assert.deepEqual(q.regionEvidence.fittedBounds,old.runtime.nativePlan.framing.bounds);
 assert.equal(q.regionEvidence.preservedLegacyFraming,true);
 assert.equal((await verifyRegionQualification({qualification:q})).status,'PASS');
});
for(const [name,region,source,treatment] of [['Japan',japan,'NE1_EAST_ASIA_NATIVE_V1','BAKED_RELIEF_V1'],['Australia',australia,'GLOBAL_EARTH_DAY_RGB_V1','CURRENT']])test('unregistered '+name+' resolves through the same coordinate/source provider',async()=>{
 const q=await qualifyRegion({region});assert.equal(q.schema,REGION_SOURCE_VERSION);assert.equal(q.status,'PASS',JSON.stringify(q.issues));
 assert.equal(q.regionEvidence.sourceId,source);assert.equal(q.regionEvidence.terrainTreatment,treatment);assert.equal(q.regionEvidence.sourceBytesActuallyVerified,true);assert.equal(q.trajectoryCoverageRequiredBeforeStart,true);
 assert.equal((await verifyRegionQualification({qualification:q})).status,'PASS');
 const plan=await resolveRegionPlan({region});assert.equal(plan.nativePlan.primary,region.countryId);assert.equal(plan.baseCameraPlan.directorVersion,'CAMERA_DIRECTOR_V5');assert.ok(plan.baseCameraPlan.totalFrames>1);
 assert.deepEqual(plan.nativePlan.geometries,(await legacyRegionProfile('europe_germany')).runtime.nativePlan.geometries);
 if(name==='Japan')japanPlan=plan;
});
test('no country reference: actual land context can be chosen for an offshore view without assigning center ownership',async()=>{
 const q=await qualifyRegion({region:{center:[4,55],bbox:[-4,48,12,62]}});assert.equal(q.status,'PASS');
 assert.equal(q.regionEvidence.contextSelection,'REAL_BBOX_INTERSECTING_CONTEXT_ONLY_NO_CENTER_MEMBERSHIP_OR_OWNERSHIP_CLAIM');
 assert.equal(q.regionEvidence.noHistoricalOwnershipInferred,true);
});
test('pure-ocean footprint is explicit unsupported when the protected factory requires real land context',async()=>{
 const q=await qualifyRegion({region:{center:[-130,-35],bbox:[-135,-40,-125,-30]}});assert.equal(q.status,'UNSUPPORTED');assert.equal(q.issues[0].code,'REGION_NO_GIS_LAND_CONTEXT');
});
test('country/name matching is based on actual GIS identities, not country exceptions',async()=>{
 assert.equal((await qualifyRegion({region:{...japan,countryName:'Japan'}})).status,'PASS');
 const wrong=await qualifyRegion({region:{...japan,countryName:'Australia'}});assert.equal(wrong.status,'CONFLICT');assert.equal(wrong.issues[0].code,'REGION_COUNTRY_NAME_ID_CONFLICT');
 const coord=await qualifyRegion({region:{...japan,countryId:'COUNTRY_DEU'}});assert.equal(coord.status,'CONFLICT');assert.equal(coord.issues[0].code,'REGION_COUNTRY_CENTER_CONFLICT');
});
test('provided location country and coordinate are checked independently of viewport country',async()=>{
 const q=await qualifyRegion({region:japan,facts:{locations:[{id:'tokyo',country_id:'COUNTRY_JPN',anchor:[139.6917,35.6895]}]}});assert.equal(q.status,'PASS');assert.equal(q.regionEvidence.locationCountryChecks[0].status,'INSIDE_OR_BOUNDARY');assert.equal((await verifyRegionQualification({qualification:q})).status,'PASS');
 const wrong=await qualifyRegion({region:japan,facts:{locations:[{id:'tokyo',country_id:'COUNTRY_DEU',anchor:[139.6917,35.6895]}]}});assert.equal(wrong.status,'CONFLICT');assert.equal(wrong.issues[0].code,'REGION_LOCATION_COUNTRY_CONFLICT');
});
test('antimeridian source geometry does not falsely cover central longitudes',()=>{
 const record={geometry_type:'Polygon',coordinates:[[[179,-2],[-179,-2],[-179,2],[179,2],[179,-2]]]};
 assert.equal(pointInCountry([179.5,0],record),true);assert.equal(pointInCountry([-179.5,0],record),true);assert.equal(pointInCountry([0,0],record),false);
});
for(const [name,region,expected] of [
 ['missing region',undefined,'NEEDS_INPUT'],['missing bbox',{center:[10,50]},'NEEDS_INPUT'],
 ['nonfinite center',{center:[NaN,0],bbox:[0,-1,2,1]},'INVALID'],
 ['dateline',{center:[179,0],bbox:[170,-10,-170,10]},'UNSUPPORTED'],
 ['polar',{center:[10,86],bbox:[0,85,20,88]},'UNSUPPORTED'],
 ['projection',{...japan,crs:'EPSG:3857'},'UNSUPPORTED'],
 ['unknown field',{...japan,blurSeam:true},'UNSUPPORTED'],
 ['center mismatch',{center:[0,0],bbox:[10,10,20,20]},'CONFLICT'],
 ['legacy CRS cannot bypass validation',{legacyProfileId:'europe_germany',crs:'EPSG:3857'},'UNSUPPORTED']
])test('region request gate: '+name,()=>assert.equal(validateRegionRequest(region).status,expected));
test('explicit unknown source is never replaced with a different style',async()=>{
 const q=await qualifyRegion({region:{...japan,sourceId:'NOT_REGISTERED'}});assert.equal(q.status,'UNSUPPORTED');assert.equal(q.issues[0].code,'REGION_SOURCE_ID_UNKNOWN');
});
test('native source upload size limit rejects unsupported extent instead of downsampling',async()=>{
 const q=await qualifyRegion({region:{center:[0,0],bbox:[-170,-80,170,80]}});assert.notEqual(q.status,'PASS');assert.ok(q.issues[0].code.includes('EXTENT')||q.issues[0].code.includes('PROJECTION')||q.issues[0].code==='REGION_NO_NATIVE_SOURCE_COVERAGE');
});
test('prepared terrain is exact original RGB pixels with native row direction, positive gutter and no invented heights',async()=>{
 japanPlan??=await resolveRegionPlan({region:japan});
 preparedJapan=await prepareRegionTerrain({regionPlan:japanPlan,bounds:japanPlan.nativePlan.framing.bounds,outputRoot:path.join(privateRoot,'actual-native')});
 const e=preparedJapan.regionEvidence;assert.equal(e.phase,'FULL_CAMERA_ENVELOPE');assert.equal(e.newHeightData,false);assert.equal(e.resampling,false);assert.ok(e.minimumSourceGutterPixels>=1);
 assert.equal(preparedJapan.nativePlan.scale.lod.rasterCoverage,'FULL_REGIONAL_CROP');
 const source=catalog.data.sources.find(s=>s.id===e.sourceId),box=preparedJapan.sourceStyle.cropSourcePixelBox;
 const {stdout}=await run('python',['-B','-c',"from PIL import Image;import sys,json,hashlib;src=Image.open(sys.argv[1]);dst=Image.open(sys.argv[2]);box=json.loads(sys.argv[3]);raw=src.crop(tuple(box));assert raw.tobytes()==dst.tobytes();print(hashlib.sha256(dst.tobytes()).hexdigest())",path.join(REPO,source.file),preparedJapan.terrainPath,JSON.stringify(box)]);
 assert.equal(stdout.trim(),e.decodedNativeCropRGBSHA256);assert.equal((await verifyRegionQualification({prepared:preparedJapan})).status,'PASS');
});
test('identical request reuses verified new cache; parallel request creates no duplicate output',async()=>{
 const values=await Promise.all([0,1].map(()=>prepareRegionTerrain({regionPlan:japanPlan,bounds:japanPlan.nativePlan.framing.bounds,outputRoot:path.join(privateRoot,'actual-native')})));
 assert.ok(values.every(p=>p.regionEvidence.cacheReused));assert.equal(values[0].terrainPath,values[1].terrainPath);assert.equal(values[0].regionEvidence.cropSHA256,preparedJapan.regionEvidence.cropSHA256);
});
test('concurrent first requests produce exactly one complete source crop',async()=>{
 const values=await Promise.all([0,1].map(()=>prepareRegionTerrain({regionPlan:japanPlan,bounds:japanPlan.nativePlan.framing.bounds,outputRoot:path.join(privateRoot,'parallel-first')})));
 assert.equal(values[0].terrainPath,values[1].terrainPath);assert.deepEqual(values.map(p=>p.regionEvidence.cacheReused).sort(),[false,true]);
 assert.ok((await Promise.all(values.map(prepared=>verifyRegionQualification({prepared})))).every(q=>q.status==='PASS'));
});
test('entire moving-camera envelope chooses one actual source, without regional rectangles or source swapping',async()=>{
 const enlarged=[115,-5,160,65],p=await prepareRegionTerrain({regionPlan:japanPlan,bounds:enlarged,outputRoot:path.join(privateRoot,'full-envelope')});
 assert.equal(p.regionEvidence.sourceId,'GLOBAL_EARTH_DAY_RGB_V1');assert.equal(p.terrainTreatment,'CURRENT');assert.equal(p.sourceStyle.terrainAsset.classification,'RGB_TERRAIN_SOURCE');assert.equal(p.regionEvidence.sourceSelection,'ONE_ACTUAL_SOURCE_FOR_COMPLETE_CAMERA_ENVELOPE_NO_PATCH_MIX');assert.equal((await verifyRegionQualification({prepared:p})).status,'PASS');
});
test('explicit regional source refuses a camera trajectory outside its actual support',async()=>{
 const regionPlan=await resolveRegionPlan({region:{...japan,sourceId:'NE1_EAST_ASIA_NATIVE_V1'}});
 await assert.rejects(prepareRegionTerrain({regionPlan,bounds:[115,-5,160,65],outputRoot:path.join(privateRoot,'explicit-source')}),/REGION_NO_NATIVE_SOURCE_COVERAGE/);
});
test('panned legacy view also covers unchanged factory initialization and analysis framing',async()=>{
 const regionPlan=await resolveRegionPlan({region:{legacyProfileId:'namibia_desert_coast'}}),bounds=[6.523684210526316,-39.81210526315789,27.576315789473686,-6.127894736842105];
 const p=await prepareRegionTerrain({regionPlan,bounds,outputRoot:path.join(privateRoot,'panned-initialization')});
 assert.deepEqual(p.regionEvidence.cameraEnvelope,bounds);assert.deepEqual(p.regionEvidence.initializationAndAnalysisBounds,[5,-38,25,-6]);
 assert.deepEqual(p.regionEvidence.sourceRequiredBounds,[5,bounds[1],bounds[2],-6]);assert.equal(p.nativePlan.scale.lod.rasterCoverage,'FULL_REGIONAL_CROP');
 assert.ok(p.sourceStyle.terrainAsset.bounds[0]<5&&p.sourceStyle.terrainAsset.bounds[3]>-6);assert.equal((await verifyRegionQualification({prepared:p})).status,'PASS');
 const tampered=structuredClone(p);tampered.nativePlan.framing.bounds[0]+=1;assert.equal((await verifyRegionQualification({prepared:tampered})).status,'INVALID');
});
test('exact legacy source rejects real overreach; explicit AUTO request may truthfully select global RGB',async()=>{
 const regionPlan=await resolveRegionPlan({region:{legacyProfileId:'south_america_chile'}}),bounds=[-81.47631578947369,-49.81210526315789,-60.42368421052632,-16.127894736842105];
 await assert.rejects(prepareRegionTerrain({regionPlan,bounds,outputRoot:path.join(privateRoot,'legacy-overreach')}),/REGION_NO_NATIVE_SOURCE_COVERAGE/);
 const generic=await resolveRegionPlan({region:{center:[-71,-33],bbox:[-84,-48,-64,-16],sourceId:'AUTO',countryId:'COUNTRY_CHL'}}),p=await prepareRegionTerrain({regionPlan:generic,bounds,outputRoot:path.join(privateRoot,'explicit-auto-global')});
 assert.equal(p.regionEvidence.sourceId,'GLOBAL_EARTH_DAY_RGB_V1');assert.equal(p.terrainTreatment,'CURRENT');assert.equal((await verifyRegionQualification({prepared:p})).status,'PASS');
});
test('private storage policy rejects repository output roots',async()=>{
 await assert.rejects(prepareRegionTerrain({regionPlan:japanPlan,bounds:japanPlan.nativePlan.framing.bounds,outputRoot:path.join(REPO,'new-cache')}),/REGION_PRIVATE_CACHE_ROOT_REQUIRED/);
});
test('changed envelope creates a distinct cache identity while preserving previous pixels',async()=>{
 const b=japanPlan.nativePlan.framing.bounds.map((v,i)=>v+([0,2].includes(i)?.01:0)),p=await prepareRegionTerrain({regionPlan:japanPlan,bounds:b,outputRoot:path.join(privateRoot,'actual-native')});
 assert.notEqual(p.regionEvidence.cacheKey,preparedJapan.regionEvidence.cacheKey);assert.equal(hash(await readFile(preparedJapan.terrainPath)),preparedJapan.regionEvidence.cropSHA256);
});
test('forged receipt and changed terrain binding are rejected',async()=>{
 const p=structuredClone(preparedJapan);p.regionEvidence.cameraEnvelope[0]-=1;
 assert.equal((await verifyRegionQualification({prepared:p})).status,'INVALID');
 const b=structuredClone(preparedJapan);b.sourceStyle.terrainAsset.classification='INVENTED_DEM';assert.equal((await verifyRegionQualification({prepared:b})).status,'INVALID');
 const c=structuredClone(preparedJapan);c.sourceCatalogSHA256='0'.repeat(64);assert.equal((await verifyRegionQualification({prepared:c})).status,'INVALID');
});
test('corrupt completed crop is refused and never overwritten during reuse',async()=>{
 const p=await prepareRegionTerrain({regionPlan:japanPlan,bounds:japanPlan.nativePlan.framing.bounds,outputRoot:path.join(privateRoot,'corruption-test')});
 await writeFile(p.terrainPath,'INTENTIONAL_NEW_TEST_CACHE_CORRUPTION',{mode:0o600});
 assert.equal((await verifyRegionQualification({prepared:p})).status,'INVALID');
 await assert.rejects(prepareRegionTerrain({regionPlan:japanPlan,bounds:japanPlan.nativePlan.framing.bounds,outputRoot:path.join(privateRoot,'corruption-test')}),/REGION_CACHE_CORRUPTION_REFUSED/);
 assert.equal(await readFile(p.terrainPath,'utf8'),'INTENTIONAL_NEW_TEST_CACHE_CORRUPTION');
});
test('interrupted new cache is preserved and refused rather than overwritten or marked successful',async()=>{
 const p=await prepareRegionTerrain({regionPlan:japanPlan,bounds:japanPlan.nativePlan.framing.bounds,outputRoot:path.join(privateRoot,'interrupted-test')});
 await rename(p.cacheRecordPath,p.cacheRecordPath+'.saved-test-record');
 await assert.rejects(prepareRegionTerrain({regionPlan:japanPlan,bounds:japanPlan.nativePlan.framing.bounds,outputRoot:path.join(privateRoot,'interrupted-test')}),/REGION_CACHE_INCOMPLETE_NO_OVERWRITE/);
 assert.equal(hash(await readFile(p.terrainPath)),p.regionEvidence.cropSHA256);assert.equal((await verifyRegionQualification({prepared:p})).status,'INVALID');
});
