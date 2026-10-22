/** Explicit synthetic unit data, never substituted for real reference geography. */
import {createHash} from 'node:crypto';
import {PROGRAM_SCHEMA} from '../director_program.mjs';
const geography={note:'Explicit synthetic contract fixture, not historical or reference geography',point:[9,10],hero:[9.1,10.2],ring:[[8.8,9.8],[9.2,9.85],[9.3,10.15],[9,10.3],[8.8,9.8]],line:[[8.95,9.9],[9.05,10],[9.2,10.1]]};
export const source={id:'GENERATED_SYNTHETIC_CONTRACT_FIXTURE',sha256:createHash('sha256').update(JSON.stringify(geography)).digest('hex'),verification:'SYNTHETIC_TEST'};
export function fixture(){
 const textStyle={fontPx:48,color:[1,1,1,1],haloColor:[.1,.2,.8,1],haloRadiusPx:16,haloOpacity:.65,gapPx:12};
 return structuredClone({schema:PROGRAM_SCHEMA,dataMode:'SYNTHETIC_TEST',frameRange:[700,820],fps:30,output:[1080,1920],safeArea:[86,154,929,1498],
  locations:[{id:'alpha',label:'항구',anchor:geography.point,source},{id:'hero',label:'Long Harbour',anchor:geography.hero,source}],
  areas:[{id:'land',geometry:{type:'Polygon',coordinates:[geography.ring]},source}],
  lines:[{id:'edge',geometry:{type:'LineString',coordinates:geography.line},direction:'FORWARD',source}],
  metrics:[{id:'givenMetric',text:'12 km',source}],
  events:[
   {id:'pin',type:'PIN',locationId:'alpha',startFrame:700,popFrames:12,holdUntilFrame:820,role:'CONTEXT_CULL',style:{assetVariant:'CONTEXT',widthPx:49,heightPx:64}},
   {id:'heroPin',type:'PIN',locationId:'hero',startFrame:710,popFrames:15,holdUntilFrame:820,role:'REQUIRED_VISIBLE_SAFE',style:{assetVariant:'HERO',widthPx:116,heightPx:151}},
   {id:'label',type:'LABEL',locationId:'alpha',pinEventId:'pin',startFrame:712,graphemeIntervalFrames:3,settleFrames:4,holdUntilFrame:820,role:'CONTEXT_CULL',requiredRange:[712,740],style:textStyle},
   {id:'area',type:'AREA',areaId:'land',startFrame:700,revealFrames:30,holdUntilFrame:820,role:'AREA_VIEWPORT_CLIP',style:{fillColor:[.8,.5,.1,.55],coreColor:[1,1,.9,1],widthPx:3,haloColor:[1,1,.9,1],haloRadiusPx:10,haloOpacity:.28}},
   {id:'boundary',type:'LINE',lineId:'edge',startFrame:750,revealFrames:20,holdUntilFrame:820,role:'REQUIRED_VISIBLE_SAFE',style:{coreColor:[1,1,0,1],widthPx:6,haloColor:[1,.9,0,1],haloRadiusPx:24,haloOpacity:.55}},
   {id:'metric',type:'METRIC',lineId:'edge',metricId:'givenMetric',startFrame:772,graphemeIntervalFrames:4,settleFrames:6,fullyReadableFrame:794,holdUntilFrame:820,role:'REQUIRED_VISIBLE_SAFE',style:{fontPx:52,color:textStyle.color,haloColor:textStyle.haloColor,haloRadiusPx:2,haloOpacity:1,offsetPx:24}},
  ],windows:[{id:'first',frameRange:[700,760]},{id:'second',frameRange:[760,820]}]});
}
