/** Explicit NASA pyramid connection; the existing renderer owns all drawing. */
import{readFile}from'node:fs/promises';
import path from'node:path';
import{createHash}from'node:crypto';
import{compileGeographicCamera,selectGeographicTerrain}from'../../web/map_infographic_v1/geographic_camera_v1.mjs';
const hash=x=>createHash('sha256').update(x).digest('hex'),check=(v,c)=>{if(!v)throw Error(c);},copy=structuredClone;
export async function loadGeographicTerrain({source,safeFile}){
 const manifest=await safeFile(source.pyramid.file);check(hash(manifest.raw)===source.pyramid.sha256,'GEOGRAPHIC_PYRAMID_MANIFEST_CHANGED');
 const data=JSON.parse(manifest.raw);check(data.schema==='WORLD_ENGINE_GEOGRAPHIC_TERRAIN_PYRAMID_V1'&&data.upscaling===false&&data.newElevation===false,'GEOGRAPHIC_PYRAMID_SCHEMA');
 const license=await safeFile(source.licenseFile);check(hash(license.raw)===source.licenseSHA256,'GEOGRAPHIC_LICENSE_CHANGED');
 const levels=[],bindings=[{role:'terrainPyramidManifest',path:manifest.file,sha256:source.pyramid.sha256},{role:'terrainLicense',path:license.file,sha256:source.licenseSHA256}];
 for(const level of data.levels){
  const bytes=await safeFile(level.file);check(hash(bytes.raw)===level.sha256&&bytes.raw.length===level.bytes,'GEOGRAPHIC_TERRAIN_BYTES_CHANGED');
  check(bytes.raw.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))&&bytes.raw.readUInt32BE(16)===level.dimensions[0]&&bytes.raw.readUInt32BE(20)===level.dimensions[1]&&bytes.raw[24]===8&&bytes.raw[25]===2,'GEOGRAPHIC_PNG_RGB_DIMENSIONS_CHANGED');
  levels.push({...copy(level),file:bytes.file,path:bytes.file,url:'/presentation-assets/'+level.sha256+'.png',source:{name:source.id,sha256:level.sourceOriginalSHA256,url:data.sourcePage,license:source.license,crs:'EPSG:4326',resolution:copy(level.dimensions),geographicExtent:copy(level.bounds),pixelSpacing:copy(level.pixelSpacing)}});
  bindings.push({role:'terrainLevel:'+level.id,path:bytes.file,sha256:level.sha256,bytes:level.bytes});
 }
 check(levels[0].sha256===source.sha256,'GEOGRAPHIC_OVERVIEW_BINDING');return{levels,bindings,data};
}
export async function prepareGeographicTerrain({source,regionPlan,presentationPlan,catalogSHA256,catalogPath,safeFile,canonicalJSON,compileScalePlan}){
 check(presentationPlan?.mode==='GEOGRAPHIC_TRACK','GEOGRAPHIC_PYRAMID_REQUIRES_REGISTERED_CAMERA');
 const {levels,bindings}=await loadGeographicTerrain({source,safeFile});
 const track=compileGeographicCamera(presentationPlan.presentation.camera,{totalFrames:presentationPlan.geographicTrack.totalFrames,holdFrames:presentationPlan.geographicTrack.holdFrames,closestBounds:presentationPlan.closestBounds});
 check(canonicalJSON(track)===canonicalJSON(presentationPlan.geographicTrack),'GEOGRAPHIC_SOURCE_CAMERA_BINDING');
 const admissions=track.frames.map((pose,frame)=>({frame,...selectGeographicTerrain(levels,pose,{maximumTextureSize:8192})}));
 const plan=copy(regionPlan.nativePlan);plan.assets.terrain=copy(levels[0]);
 const nativePlan=compileScalePlan(plan,'REGIONAL',{allCountries:plan.geometries});
 const evidence={...copy(regionPlan.regionEvidence),phase:'FULL_CAMERA_PYRAMID',trajectoryCoverageRequiredBeforeStart:false,catalogSHA256,cameraEnvelope:copy(track.coverageBounds),initializationAndAnalysisBounds:copy(nativePlan.framing.bounds),sourceSelection:'PINNED_SAME_EPOCH_SOURCE_GRID_PYRAMID',terrainTreatment:source.terrainTreatment,styleId:source.styleId,attribution:source.attribution,license:source.license,sourcePyramidSHA256:source.pyramid.sha256,admissions,minimumSourceGutterPixels:Math.min(...admissions.map(a=>a.gutter)),maximumOutputPixelsPerNativeTexel:Math.max(...admissions.flatMap(a=>a.density)),actualSourceBytesVerified:true,newHeightData:false,upscaling:false};
 const sourceStyle={schema:'WORLD_ENGINE_REGION_SOURCE_STYLE_V2',styleId:source.styleId,terrainTreatment:source.terrainTreatment,sourceOriginal:copy(source.sourceOriginal),terrainAsset:copy(levels[0]),terrainLevels:levels,license:source.license,attribution:source.attribution,outsideSupportPolicy:'FAIL_BEFORE_DRAW',nativeWindowPolicy:{maxTextureDimension:8192,gutterSourcePixels:1,maximumOutputPixelsPerNativeTexel:1}};
 return{...copy(regionPlan),nativePlan,sourceStyle,terrainTreatment:source.terrainTreatment,regionEvidence:evidence,fullCoverageSHA256:hash(canonicalJSON(evidence)),sourceBindings:[{role:'regionSourceCatalog',path:catalogPath,sha256:catalogSHA256},...bindings],terrainPath:levels[0].file,geographicSourceTrack:track,...(presentationPlan.presentation.camera.interpolation?{geographicSourceCamera:copy(presentationPlan.presentation.camera)}:{})};
}
export async function verifyGeographicTerrain({prepared,source,safeFile,canonicalJSON,compileScalePlan,catalogSHA256,catalogPath}){
 const recreated=await prepareGeographicTerrain({source,regionPlan:prepared,presentationPlan:{mode:'GEOGRAPHIC_TRACK',geographicTrack:prepared.geographicSourceTrack,presentation:{camera:prepared.geographicSourceCamera??{mode:'GEOGRAPHIC_TRACK',projection:prepared.geographicSourceTrack.schema,frames:prepared.geographicSourceTrack.frames}},closestBounds:prepared.nativePlan.framing.bounds},catalogSHA256,catalogPath,safeFile,canonicalJSON,compileScalePlan});
 check(canonicalJSON(recreated.sourceStyle)===canonicalJSON(prepared.sourceStyle)&&canonicalJSON(recreated.nativePlan.assets.terrain)===canonicalJSON(prepared.nativePlan.assets.terrain),'GEOGRAPHIC_TERRAIN_BINDING_MISMATCH');
 check(canonicalJSON(recreated.regionEvidence)===canonicalJSON(prepared.regionEvidence)&&recreated.fullCoverageSHA256===prepared.fullCoverageSHA256,'GEOGRAPHIC_PYRAMID_RECEIPT_CHANGED');
 return{status:'PASS',phase:'FULL_CAMERA_PYRAMID',fullCoverageSHA256:prepared.fullCoverageSHA256,actualSourceAndCropBytesVerified:true,trajectoryCoverageRequiredBeforeStart:false,frames:prepared.geographicSourceTrack.totalFrames,maximumOutputPixelsPerNativeTexel:prepared.regionEvidence.maximumOutputPixelsPerNativeTexel};
}
