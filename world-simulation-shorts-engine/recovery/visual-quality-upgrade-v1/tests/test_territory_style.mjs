import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {applyQualityTerritoryStyle,validateQualityTerritoryProfile,territorySeparation,compositeTerritorySample}
 from '../territory_style_core.mjs';
import {auditControlFrontier} from '../audit_control_frontier.mjs';
import {compileTerritoryControlPlan,evaluateTerritoryControlFrame}
 from '../../../web/map_infographic_v1/territory_control_adapter_v1.mjs';
import {compileControlFrontierLightMotion,evaluateControlFrontierLightMotion}
 from '../../../web/map_infographic_v1/reference_control_frontier_light_v3.mjs';
const here=path.dirname(fileURLToPath(import.meta.url));
const saved=JSON.parse(await readFile(path.join(here,'../../moving-frontier-glow-fix-v1/fixtures/SCENE_PLAN.json'),'utf8'));

test('opacity profile rejects classifier, hue, camera and arbitrary controls',()=>{
 for(const value of [{minimumAlpha:.9},{maximumAlpha:1},{opacityGain:.9},{opacityGain:NaN},
  {minimumAlpha:.8,maximumAlpha:.6},{hue:20},{country:'fixture'},{speed:2},{newFront:true}])
  assert.throws(()=>validateQualityTerritoryProfile(value));
});
test('saved faction RGB and interfaces remain exact; only bounded alphas and style name change',()=>{
 const before=structuredClone(saved.style),after=applyQualityTerritoryStyle(saved.style);
 assert.deepEqual(saved.style,before);
 for(const role of ['losingColor','existingWinningColor','gainedWinningColor']){
  assert.deepEqual(after[role].slice(0,3),before[role].slice(0,3));assert.equal(after[role][3],.72);
 }
 assert.deepEqual(after.existingWinningColor,after.gainedWinningColor);
 assert.deepEqual(after.interfaceColor,before.interfaceColor);assert.equal(after.interfaceWidthPixels,0);
 assert.equal(after.sharedDomainBoundary,before.sharedDomainBoundary);
});
test('explicit invisible roles stay invisible and opaque source roles are not weakened',()=>{
 const source=structuredClone(saved.style);source.losingColor[3]=0;source.existingWinningColor[3]=1;
 const result=applyQualityTerritoryStyle(source);assert.equal(result.losingColor[3],0);assert.equal(result.existingWinningColor[3],1);
});
test('generic role alpha works without fixture names or colors',()=>{
 const source={profileName:'ANY',losingColor:[.1,.7,.8,.3],existingWinningColor:[.9,.5,.1,.8],gainedWinningColor:[.9,.5,.1,.8]};
 const out=applyQualityTerritoryStyle(source,{minimumAlpha:.6,maximumAlpha:.85,opacityGain:1.05});
 assert.equal(out.losingColor[3],.6);assert.ok(Math.abs(out.existingWinningColor[3]-.84)<1e-12);
 assert.deepEqual(out.losingColor.slice(0,3),source.losingColor.slice(0,3));
});
test('all declared dark/mid/bright CPU backgrounds have increased faction RGB separation',()=>{
 const effective=applyQualityTerritoryStyle(saved.style);
 for(const background of [[.12,.18,.1],[.4,.42,.3],[.75,.7,.55]]){
  const old=territorySeparation(background,saved.style),next=territorySeparation(background,effective);
  assert.ok(next.rgbDistance>old.rgbDistance*1.12);
  assert.ok(next.retainedBackgroundFraction.winner>=.27);assert.ok(next.retainedBackgroundFraction.loser>=.27);
 }
});
test('blend oracle preserves varying terrain; it never replaces surface pixels with a flat opaque fill',()=>{
 const effective=applyQualityTerritoryStyle(saved.style),a=compositeTerritorySample([.1,.2,.3],effective.existingWinningColor),
  b=compositeTerritorySample([.5,.6,.7],effective.existingWinningColor);
 for(let i=0;i<3;i++)assert.ok(Math.abs((b[i]-a[i])-.4*.28)<1e-12);
});
test('actual source 150-frame control remains monotonic with increasing sampled winning area',()=>{
 const audit=auditControlFrontier(saved,{columns:48,rows:64});
 assert.equal(audit.frames.length,150);assert.equal(audit.boundary.monotonic,true);
 assert.ok(audit.boundary.minimumWinnerAreaGainEstimate>=-1e-10);
 assert.ok(audit.frames.at(-1).winnerAreaFractionEstimate>audit.frames[0].winnerAreaFractionEstimate+.1);
 assert.equal(audit.frontier.decision,'UNCHANGED_REUSED');assert.equal(audit.frontier.endAdvancing,true);
 assert.equal(audit.actualGpuPixels,false);assert.equal(audit.areaEstimation.exactAreaClaimed,false);
});
test('unchanged frontier settles only when a synthetic evaluated boundary actually stops',()=>{
 const intent={version:'TERRITORY_CONTROL_INTENT_V1',semantic_mode:'REFERENCE_VISUAL_STUDY',
  source:{source_type:'SYNTHETIC_TEST',source_reference:'HELD_SCALAR_BOUNDARY',verification_status:'TEST_ONLY'},
  domain:[{id:'ANY',geometry:{type:'Polygon',coordinates:[[[-2,-2],[2,-2],[2,2],[-2,2],[-2,-2]]]}}],
  factions:{winner:{id:'A'},loser:{id:'B'}},longitudinal_knots:[-2,2],base_boundary_latitudes:[-1,-1],
  boundary_keyframes:[{frame:0,latitudes:[-1,-1]},{frame:5,latitudes:[1,1]},{frame:19,latitudes:[1,1]}],
  advance_direction:'POSITIVE_LATITUDE',start_frame:0,total_frames:20,fps:30,interpolation:'LINEAR'},
  plan=compileTerritoryControlPlan(intent),profile={...saved.frontierProfile,velocityWindowFrames:4},
  motion=compileControlFrontierLightMotion(plan,profile),travel=evaluateControlFrontierLightMotion(motion,3),
  stopped=evaluateControlFrontierLightMotion(motion,15);
 assert.equal(travel.advancing,true);assert.ok(travel.strength>profile.settledStrength);
 assert.equal(stopped.advancing,false);assert.equal(stopped.strength,profile.settledStrength);
 assert.equal(stopped.stopAssumedAtOutputEnd,false);
 assert.deepEqual(evaluateTerritoryControlFrame(plan,15).boundaryLatitudes,[1,1]);
});
