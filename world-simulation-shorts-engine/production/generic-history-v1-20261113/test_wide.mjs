import fs from 'node:fs';
import assert from 'node:assert/strict';
import {fitGeographicPose,geographicCameraFrame,selectGeographicTerrain} from '../../web/map_infographic_v1/geographic_camera_v1.mjs';
import {fitGeographicExtent} from '../../web/map_infographic_v1/scale_contract.mjs';
import {validateRegionRequest,qualifyRegion} from '../../recovery/universal-presentation-v2/region_source.mjs';
const base=new URL('./',import.meta.url),input=JSON.parse(fs.readFileSync(new URL('MONGOL_EMPIRE_SCENE_INPUT.json',base))),
 levels=JSON.parse(fs.readFileSync(new URL('../../recovery/universal-presentation-v2/sources/eurasia/TERRAIN_PYRAMID.json',base))).levels,checks=[];
function check(name,fn){fn();checks.push(name);}
check('full multi-continent geometry fits portrait without changing coordinates',()=>{const b=[17.359594345092773,24.07203483581543,141.55662536621094,62.259857177734375],p=fitGeographicPose(b,{pixelSpacing:1/40}),f=geographicCameraFrame(p);for(const x of [b[0],b[2]])for(const y of [b[1],b[3]]){const q=f.project([x,y]);assert.ok(q[0]>=72-1e-8&&q[0]<=1008+1e-8&&q[1]>=72&&q[1]<=1848);}assert.equal(selectGeographicTerrain(levels,p,{maximumTextureSize:8192}).index,0);});
check('country-scale native detail reuses same existing projection',()=>{const p=fitGeographicPose([92.675827,40.61441,126.171128,55.703118]);assert.equal(selectGeographicTerrain(levels,p,{maximumTextureSize:8192}).index,1);});
check('old regional aspect contract remains independent',()=>{const b=fitGeographicExtent([130,30,145,45],{center:[137.5,37.5],padding:1});assert.ok(b[0]<=130&&b[2]>=145&&b[1]<=30&&b[3]>=45);assert.ok(Math.abs((b[2]-b[0])*Math.cos(37.5*Math.PI/180)/(b[3]-b[1])-1080/1920)<1e-12);assert.equal(validateRegionRequest({center:[137.5,37.5],bbox:[130,30,145,45]}).status,'PASS');});
check('dateline/polar/unavailable detail are explicit failures',()=>{assert.throws(()=>fitGeographicPose([170,-10,-170,10]));assert.throws(()=>fitGeographicPose([0,80,30,90]));assert.throws(()=>selectGeographicTerrain(levels,{center:[-90,30],scale:15,rollDegrees:0}));});
const admitted=await qualifyRegion({region:{sourceId:'AUTO',crs:'EPSG:4326',center:[79.45810985565186,43.1659460067749],bbox:[17.359594345092773,24.07203483581543,141.55662536621094,62.259857177734375],projection:'GEOGRAPHIC_MERCATOR_V1'},facts:input.data.scenes[0].facts});assert.equal(admitted.status,'PASS');checks.push('actual source bytes and full content region admitted');
console.log(JSON.stringify({status:'PASS',scope:'new Mercator/region binding and preserved regional aspect contract',checks},null,2));
