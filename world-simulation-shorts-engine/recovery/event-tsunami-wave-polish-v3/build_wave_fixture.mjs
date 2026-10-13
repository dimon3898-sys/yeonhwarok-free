/** Data-only derivative: retain the approved event and native camera inputs. */
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const folder=path.dirname(fileURLToPath(import.meta.url));
const engine=path.resolve(folder,'../..');
const parentFixturePath='recovery/event-area-propagation-v3/fixtures/REAL_FIXTURE.json';
const nativeCountryPath='recovery/event-area-propagation-v3/fixtures/CONTINENT-plan.json';
const load=async relative=>{
 const bytes=await readFile(path.join(engine,relative));
 return {bytes,value:JSON.parse(bytes)};
};
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const canonicalHash=value=>hash(Buffer.from(JSON.stringify(value)));
const write=async (relative,value)=>writeFile(path.join(folder,relative),JSON.stringify(value,null,2)+'\n');
const parent=await load(parentFixturePath),native=await load(nativeCountryPath);
const country=native.value.geometries.find(record=>record.id==='COUNTRY_JPN');
if(!country||country.geometry_type!=='MultiPolygon')throw Error('NATIVE_COUNTRY_SOURCE_REQUIRED');

// This is a data selector, never a country or coordinate branch in the engine.
// One contiguous original Pacific-side Honshu chain; no resampling or stitching.
const polygonIndex=25,ringIndex=0,startVertex=10,endVertexInclusive=49;
const originalRing=country.coordinates[polygonIndex][ringIndex];
const coordinates=structuredClone(originalRing.slice(startVertex,endVertexInclusive+1));
if(coordinates.length!==40)throw Error('NATIVE_COAST_VERTEX_COUNT_CHANGED');
const coastGeometry={type:'LineString',coordinates};
const origin=structuredClone(parent.value.areaPlan.intent.origin);
const source=structuredClone(parent.value.areaPlan.intent.source);
const cosLatitude=Math.cos(origin[1]*Math.PI/180);
const displayDistance=point=>Math.hypot((point[0]-origin[0])*cosLatitude,point[1]-origin[1]);
const contactSegments=[];
for(let first=0;first<coordinates.length-1;first+=4){
 const last=Math.min(first+4,coordinates.length-1);
 const segment=coordinates.slice(first,last+1);
 contactSegments.push({id:`coast-native-${String(first).padStart(2,'0')}`,
  geometry:{type:'LineString',coordinates:segment},
  sourceVertexRange:[startVertex+first,startVertex+last],
  minimumDisplayDistanceDegrees:Math.min(...segment.map(displayDistance))});
}
const distanceOrder=[...contactSegments].sort((a,b)=>a.minimumDisplayDistanceDegrees-b.minimumDisplayDistanceDegrees).map(segment=>segment.id);
const sourceRecord={nativeCountryPath,nativeCountryFileSha256:hash(native.bytes),
 nativeCountryId:country.id,nativeCountrySha256:canonicalHash(country),
 nativeGeometrySha256:canonicalHash(country.coordinates),
 sourceId:country.source_id,sourceVersion:country.source_version,
 sourceFileSha256:country.source_file_sha256,crs:country.crs,
 polygonIndex,ringIndex,sourceVertexRange:[startVertex,endVertexInclusive],
 coastGeometrySha256:canonicalHash(coastGeometry),
 derivative:'EXACT_CONTIGUOUS_NATIVE_VERTEX_SLICE_NO_RESAMPLING',
 topologyClaim:'PACIFIC_COAST_POLYLINE_ONLY_NOT_INUNDATION_EXTENT'};

const waveVisualInput={origin,coastGeometry,source,data_mode:'PRODUCTION',fps:30,
 total_frames:240,start_frame:12,travel_frames:150,stagger_frames:18,
 wave_count:3,fade_frames:12,contact_frames:20,pulse_frames:24};
const presentation=structuredClone(parent.value.presentation);
presentation.videoFilename='TOHOKU_2011_TSUNAMI_WAVE_VISUAL_POLISH.mp4';
presentation.checkpoints=[
 {frame:0,file:'01_EVENT_ARRIVAL.png'},
 {frame:54,file:'02_ORIGIN.png'},
 {frame:65,file:'03_FIRST_WAVE.png'},
 {frame:110,file:'04_WAVE_TRAIN.png'},
 {frame:125,file:'05_COAST_APPROACH.png'},
 {frame:150,file:'06_SEQUENTIAL_IMPACT.png'},
 {frame:187,file:'07_ENERGY_FADE.png'},
 {frame:269,file:'08_FINAL_HOLD.png'}];
// Keep the source date, unchanged title and native country label. The previous
// explanatory COAST/HOLD annotations were fixture text, not event facts.
presentation.annotations=presentation.annotations.filter(label=>label.id==='ORIGIN');
const fixture={schema:1,subject:parent.value.subject,
 parentFixturePath,areaPlanPath:parentFixturePath,nativeFiles:parent.value.nativeFiles,
 presentation,waveVisualInput,
 sourcePolicy:parent.value.sourcePolicy,factIntegrity:parent.value.factIntegrity,
 protectedParent:{fixtureSha256:hash(parent.bytes),areaPlanSha256:canonicalHash(parent.value.areaPlan),
  nativeCountrySha256:sourceRecord.nativeCountrySha256},
 waveCoastSource:sourceRecord,
 warnings:[...parent.value.warnings,'COAST_FRONT_AND_ARRIVAL_ORDER_ARE_VISUAL_NOT_PHYSICAL_TIME'],
 textCleanup:{removed:['해안 도달 확산 개념도'],
  retained:['2011.03.11 발생','동일본 쓰나미','일본']}};

await mkdir(path.join(folder,'fixtures'),{recursive:true});
await mkdir(path.join(folder,'data'),{recursive:true});
await write('fixtures/REAL_FIXTURE.json',fixture);
await write('data/NATIVE_COASTLINE.json',{schema:1,origin,source:sourceRecord,geometry:coastGeometry,
 contactSegments,displayDistanceOrder:distanceOrder,
 distancePolicy:'PROJECTED_VISUAL_ORDER_HINT_NOT_METRES_VELOCITY_OR_OBSERVED_ARRIVAL_TIME',
 license:'Natural Earth public domain',buildRecipe:'node recovery/event-tsunami-wave-polish-v3/build_wave_fixture.mjs',
 originalEventFixture:parentFixturePath,newEventDataResearch:false});
await write('data/FIXTURE_PROTECTION.json',{schema:1,status:'PASS',
 parentFixtureSha256:hash(parent.bytes),areaPlanSha256:canonicalHash(parent.value.areaPlan),
 originUnchanged:JSON.stringify(origin)===JSON.stringify(parent.value.areaPlan.intent.origin),
 factIntegrityUnchanged:JSON.stringify(fixture.factIntegrity)===JSON.stringify(parent.value.factIntegrity),
 nativeInputsUnchanged:JSON.stringify(fixture.nativeFiles)===JSON.stringify(parent.value.nativeFiles),
 cameraStartFrameUnchanged:presentation.cameraStartFrame===parent.value.presentation.cameraStartFrame,
 eventLockFrameUnchanged:presentation.eventStartFrame===parent.value.presentation.eventStartFrame,
 coastUsesOriginalVertices:coordinates.every((point,index)=>JSON.stringify(point)===JSON.stringify(originalRing[startVertex+index])),
 coastVertexCount:coordinates.length,coastContactSegmentCount:contactSegments.length,
 historicalSourceReResearch:false});
console.log(JSON.stringify({fixture:'fixtures/REAL_FIXTURE.json',parentFixturePath,
 coastVertexCount:coordinates.length,coastContactSegments:contactSegments.length,
 nativeCountrySha256:sourceRecord.nativeCountrySha256,coastGeometrySha256:sourceRecord.coastGeometrySha256,
 duration:presentation.totalFrames/30,publicAnnotations:presentation.annotations.map(a=>`${a.display_value} ${a.unit}`),
 status:'PASS'}));
