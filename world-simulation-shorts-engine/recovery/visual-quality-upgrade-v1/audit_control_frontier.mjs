/** CPU evidence over ORIGINAL evaluated territory/frontier sources.
 * Geographic sampling estimates area only; it is not a renderer or GIS survey.
 */
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {compileTerritoryControlPlan,evaluateTerritoryControlFrame,sampleControlBoundary,classifyControlPoint}
 from '../../web/map_infographic_v1/territory_control_adapter_v1.mjs';
import {compileControlFrontierLightMotion,evaluateControlFrontierLightMotion}
 from '../../web/map_infographic_v1/reference_control_frontier_light_v3.mjs';
import {areaGeometryCoordinates} from '../../web/map_infographic_v1/area_core_v3.mjs';
import {applyQualityTerritoryStyle,territorySeparation,DEFAULT_QUALITY_TERRITORY_PROFILE}
 from './territory_style_core.mjs';
const round=value=>Number(value.toFixed(10));

export function auditControlFrontier(scene,{columns=96,rows=128}={}){
 if(!Number.isSafeInteger(columns)||columns<4||columns>256||!Number.isSafeInteger(rows)||rows<4||rows>256)
  throw Error('QUALITY_AUDIT_BOUNDED_GRID_REQUIRED');
 const plan=compileTerritoryControlPlan(scene.controlIntent),motion=compileControlFrontierLightMotion(plan,scene.frontierProfile),
  points=plan.intent.domain.flatMap(d=>areaGeometryCoordinates(d.geometry)),
  bounds=[Math.min(...points.map(p=>p[0])),Math.min(...points.map(p=>p[1])),
   Math.max(...points.map(p=>p[0])),Math.max(...points.map(p=>p[1]))],
  first=evaluateTerritoryControlFrame(plan,plan.startFrame),samples=[];
 for(let x=0;x<columns;x++){
  const longitude=bounds[0]+(x+.5)/columns*(bounds[2]-bounds[0]);
  for(let y=0;y<rows;y++){
   const latitude=bounds[1]+(y+.5)/rows*(bounds[3]-bounds[1]);
   if(classifyControlPoint(first,[longitude,latitude]).inDomain)
    samples.push({longitude,latitude,weight:Math.cos(latitude*Math.PI/180)});
  }
 }
 if(!samples.length)throw Error('QUALITY_AUDIT_NO_LAND_SAMPLES');
 const totalWeight=samples.reduce((sum,p)=>sum+p.weight,0),frames=[];
 let previous=null,minimumAdvance=Infinity,maximumAdvance=0,minimumAreaGain=Infinity;
 for(let i=0;i<plan.totalFrames;i++){
  const controls=evaluateTerritoryControlFrame(plan,plan.startFrame+i),energy=evaluateControlFrontierLightMotion(motion,controls.frame),
   byLongitude=new Map();
  let winner=0,gained=0,winningSamples=0;
  for(const p of samples){
   let limits=byLongitude.get(p.longitude);
   if(!limits){limits={moving:sampleControlBoundary(controls,p.longitude),base:sampleControlBoundary(controls,p.longitude,{kind:'base'})};byLongitude.set(p.longitude,limits);}
   if(controls.advanceSign*(p.latitude-limits.moving)<=0){winner+=p.weight;winningSamples++;
    if(controls.advanceSign*(p.latitude-limits.base)>0)gained+=p.weight;}
  }
  const advancement=previous?controls.boundaryLatitudes.map((v,k)=>controls.advanceSign*(v-previous.controls.boundaryLatitudes[k])):[];
  if(advancement.length){minimumAdvance=Math.min(minimumAdvance,...advancement);maximumAdvance=Math.max(maximumAdvance,...advancement);}
  const winnerFraction=winner/totalWeight;
  if(previous)minimumAreaGain=Math.min(minimumAreaGain,winnerFraction-previous.winnerFraction);
  frames.push({frame:controls.frame,winningSamples,losingSamples:samples.length-winningSamples,
   winnerAreaFractionEstimate:round(winnerFraction),loserAreaFractionEstimate:round(1-winnerFraction),
   gainedAreaFractionEstimate:round(gained/totalWeight),frontierStrength:round(energy.strength),
   frontierSpeedDegreesPerFrame:round(energy.speedDegreesPerFrame),advancing:energy.advancing});
  previous={controls,winnerFraction};
 }
 const effectiveStyle=applyQualityTerritoryStyle(scene.style),backgrounds=[
  {name:'DARK_SYNTHETIC_LAND',rgb:[.12,.18,.10]},{name:'MID_SYNTHETIC_LAND',rgb:[.4,.42,.3]},
  {name:'BRIGHT_SYNTHETIC_LAND',rgb:[.75,.7,.55]}],
  contrast=backgrounds.map(sample=>({name:sample.name,background:sample.rgb,
   before:territorySeparation(sample.rgb,scene.style),after:territorySeparation(sample.rgb,effectiveStyle)}));
 return {schema:'QUALITY_TERRITORY_FRONTIER_CPU_AUDIT_V1',testOnly:true,gpuExecuted:false,actualGpuPixels:false,
  source:'UNCHANGED_ORIGINAL_TERRITORY_AND_FRONTIER_EVALUATORS',totalFrames:plan.totalFrames,fps:plan.fps,
  areaEstimation:{method:'FIXED_GRID_SOURCE_DOMAIN_CLIPPED_COS_LATITUDE_WEIGHTED',columns,rows,
   landSampleCount:samples.length,bounds,surveyAccurate:false,exactAreaClaimed:false},
  geometryChanged:false,timelineChanged:false,classifierChanged:false,
  boundary:{minimumSignedAdvanceDegrees:round(minimumAdvance),maximumSignedAdvanceDegrees:round(maximumAdvance),
   monotonic:minimumAdvance>=-1e-10,minimumWinnerAreaGainEstimate:round(minimumAreaGain),
   sourceKeyframeCount:plan.intent.boundary_keyframes.length,sourceKnotCount:plan.intent.longitudinal_knots.length},
  territory:{cause:'FIXED_SOURCE_ALPHA_RETAINS_VARIABLE_BACKGROUND_IN_SAVED_FIXTURE',
   policy:'GENERIC_PROFILE_OPACITY_FLOOR_PRESERVES_SOURCE_RGB_HUES',profile:DEFAULT_QUALITY_TERRITORY_PROFILE,
   sourceStyle:scene.style,effectiveStyle,contrast,comparisonScope:'CPU_BLEND_ORACLE_ON_EXPLICIT_SYNTHETIC_BACKGROUNDS_NOT_ACTUAL_VIDEO'},
  frontier:{decision:'UNCHANGED_REUSED',reason:'ACTUAL_BOUNDARY_FIELD_SCREEN_PIXEL_WIDTHS_AND_MEASURED_DISPLACEMENT_ENERGY_ALREADY_PRESENT',
   profile:scene.frontierProfile,peakSpeedDegreesPerFrame:round(motion.peakSpeed),
   endAdvancing:frames.at(-1).advancing,stopAssumedAtOutputEnd:false,
   newLines:0,newArrows:0,decorativeFrontGeometry:false,
   stopBehaviorTest:'SEE_FOCUSED_SYNTHETIC_STOP_TEST_NOT_A_NEW_STORY_HOLD'},frames};
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const fixture=path.join(path.dirname(fileURLToPath(import.meta.url)),'../moving-frontier-glow-fix-v1/fixtures/SCENE_PLAN.json');
 console.log(JSON.stringify(auditControlFrontier(JSON.parse(await readFile(fixture,'utf8'))),null,2));
}
