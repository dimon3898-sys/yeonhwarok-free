/** Reference-director V1 event sidecar. Data/state only; no native-map draw hook.
 * Existing Event validation and freezing are reused unchanged. The protected
 * Event line's projected-pixel arclength is deliberately not used as source time.
 */
import {compileEventIntent, freezeEventData, validateEventAnchor} from '../../web/map_infographic_v1/event_contract_v1.mjs';
import {createMeasuredGlyph} from '../../web/map_infographic_v1/glyph_atlas.mjs';

export const VERSION = 'REFERENCE_DIRECTOR_EVENTS_V1';
export const ROLES = Object.freeze(['REQUIRED_VISIBLE_SAFE', 'CONTEXT_CULL', 'AREA_VIEWPORT_CLIP']);
const POP = Object.freeze([0,.11304,.27826,.46087,.68696,.95652,.92174,.86087,.84348,.86957,.93913,.9913,.98261,1,1]);
const clamp = v => Math.max(0, Math.min(1, v));
const easeOut = v => 1 - (1 - clamp(v)) ** 3;
const xy = p => Array.isArray(p) && p.length === 2 && p.every(Number.isFinite);
function object(value, keys, label) {
 if (!value || typeof value !== 'object' || Array.isArray(value) || ![Object.prototype,null].includes(Object.getPrototypeOf(value))) throw Error(`RD_EVENT_${label}_OBJECT_REQUIRED`);
 if (Object.keys(value).some(key => !keys.includes(key))) throw Error(`RD_EVENT_${label}_UNKNOWN_FIELD`);
 return value;
}
function text(value, label) {
 if (typeof value !== 'string' || !value.trim() || /[\u0000-\u001f\u007f]/u.test(value)) throw Error(`RD_EVENT_${label}_TEXT_REQUIRED`);
 return value;
}
function frame(value) {
 if (!Number.isSafeInteger(value) || value < 29 || value >= 575) throw Error('RD_EVENT_REFERENCE_FRAME_OUTSIDE_CORE');
 return value;
}
export function graphemes(value) {
 return [...new Intl.Segmenter('und', {granularity:'grapheme'}).segment(text(value,'GRAPHEME'))].map(item => item.segment);
}
function source(value, mode, label, observationAllowed = false) {
 const s = object(value, ['id','sha256','verification'], `${label}_SOURCE`);
 const verification = text(s.verification, `${label}_VERIFICATION`);
 const accepted = mode === 'SYNTHETIC_TEST' ? ['SYNTHETIC_TEST'] : observationAllowed ? ['VERIFIED','OBSERVED_REFERENCE_TEXT'] : ['VERIFIED'];
 if (!accepted.includes(verification)) throw Error(`RD_EVENT_${label}_SOURCE_VERIFICATION_REQUIRED`);
 if (!/^[a-f0-9]{64}$/u.test(s.sha256)) throw Error(`RD_EVENT_${label}_SOURCE_SHA256_REQUIRED`);
 return {id:text(s.id,`${label}_SOURCE_ID`),sha256:s.sha256,verification};
}
function location(value, mode, label) {
 const l = object(value, ['id','label','anchor','source'], label);
 return {id:text(l.id,`${label}_ID`),label:text(l.label,`${label}_LABEL`),anchor:validateEventAnchor(l.anchor),source:source(l.source,mode,label)};
}
function line(value, mode) {
 const b = object(value, ['id','geometry','direction','source'], 'BOUNDARY');
 object(b.geometry,['type','coordinates'],'BOUNDARY_GEOMETRY');
 const s = source(b.source, mode, 'BOUNDARY');
 const intent = compileEventIntent({data_mode:mode === 'SYNTHETIC_TEST' ? 'SYNTHETIC_TEST':'PRODUCTION', line:{
  geometry:b.geometry,direction:b.direction,style_role:'PRIMARY',source:{source_type:mode === 'SYNTHETIC_TEST' ? 'SYNTHETIC_TEST':'SUPPLIED_GEOGRAPHIC_LINE',source_reference:s.id,verification_status:mode === 'SYNTHETIC_TEST' ? 'SYNTHETIC_TEST':'VERIFIED'}}});
 return {id:text(b.id,'BOUNDARY_ID'),geometry:intent.line.geometry,direction:intent.line.direction,source:s};
}
/** Strict independent contract. Target JSON null bindings cannot silently pass. */
export function compileReferenceEvents(input) {
 const p = object(input,['schema','dataMode','contextLocations','heroLocation','boundary','metric'],'INPUT');
 if (p.schema !== 'REFERENCE_DIRECTOR_EVENT_INPUT_V1') throw Error('RD_EVENT_SCHEMA_REQUIRED');
 if (!['REFERENCE_BOUND','SYNTHETIC_TEST'].includes(p.dataMode)) throw Error('RD_EVENT_DATA_MODE_REQUIRED');
 if (!Array.isArray(p.contextLocations) || p.contextLocations.length !== 2) throw Error('RD_EVENT_TWO_BOUND_CONTEXT_LOCATIONS_REQUIRED');
 const contexts = p.contextLocations.map((value,index) => location(value,p.dataMode,`CONTEXT_${index}`));
 const hero = location(p.heroLocation,p.dataMode,'HERO'), boundary = line(p.boundary,p.dataMode);
 const givenMetric = object(p.metric,['id','text','source'],'METRIC');
 const metric = {id:text(givenMetric.id,'METRIC_ID'),text:text(givenMetric.text,'METRIC_TEXT'),source:source(givenMetric.source,p.dataMode,'METRIC',true)};
 const contextGraphemes = contexts.map(item=>graphemes(item.label));
 const metricGraphemes = graphemes(metric.text);
 // Whitespace reserves horizontal advance but has no reveal beat.
 const metricVisible = metricGraphemes.filter(g=>!/^[\s]+$/u.test(g));
 if (contextGraphemes[0].length * 4 + 289 > 311 || contextGraphemes[1].length * 4 + 311 > 333) throw Error('RD_EVENT_LOCATION_REVEAL_WINDOW_TOO_SHORT');
 if (!metricVisible.length || 487 + (metricVisible.length - 1) * 5 + 8 > 505) throw Error('RD_EVENT_METRIC_REVEAL_WINDOW_TOO_SHORT');
 const ids = [contexts[0].id,contexts[1].id,hero.id,boundary.id,metric.id];
 if (new Set(ids).size !== ids.length) throw Error('RD_EVENT_UNIQUE_INPUT_IDS_REQUIRED');
 return freezeEventData({version:VERSION,pixelConnected:false,status:'CONTRACT_ONLY_AWAITING_NATIVE_CONSUMER',dataMode:p.dataMode,
  contextLocations:contexts,heroLocation:hero,boundary,metric,contextGraphemes,metricGraphemes,
  arclength:compileSourceArclength(boundary.geometry.coordinates,boundary.direction)});
}
/** Compile supplied target timings without pretending its null geography is bound.
 * Output is authoring data, never an executable Scene or a renderer admission.
 */
export function compileUnboundReferenceSchedule(target) {
 object(target,['schema','status','reference','framePolicy','reviewWindows','dataBindings','styleDefaults','camera','events','acceptance','executionScope','notObservedAndNotToInvent'],'TARGET');
 if(target.schema!=='WORLD_ENGINE_REFERENCE_DIRECTOR_TARGET_V1' || target.status!=='AUTHORING_SPEC_NOT_EXISTING_EXECUTABLE_SCENE')throw Error('RD_EVENT_AUTHORING_TARGET_SCHEMA_REQUIRED');
 if(JSON.stringify(target.framePolicy?.coreSourceFrames)!=='[29,575]' || target.framePolicy.coreFrameCount!==546 || target.framePolicy.fps!==30)throw Error('RD_EVENT_AUTHORING_GLOBAL_TIMELINE_REQUIRED');
 const expectedWindows=[['A_CONTEXT',29,209,180],['B_FOCUS',209,389,180],['C_BOUNDARY_METRIC',389,575,186]];
 if(!Array.isArray(target.reviewWindows)||target.reviewWindows.length!==3||target.reviewWindows.some((w,i)=>JSON.stringify([w.id,...w.sourceFrameRange,w.outputFrames])!==JSON.stringify(expectedWindows[i])))throw Error('RD_EVENT_AUTHORING_REVIEW_WINDOWS_REQUIRED');
 if(!Array.isArray(target.events)||new Set(target.events.map(e=>e.id)).size!==7)throw Error('RD_EVENT_AUTHORING_EVENT_SET_REQUIRED');
 const eventKeys={context_pins:['id','type','referenceFrames','targets','holdUntilCulled','normalSize','timingNote'],context_tint:['id','type','referenceFrames','target','geometryMotion'],label_A:['id','type','glyphStartReferenceFrames','glyphSettleFrames','visibleHoldUntilCulled','sampleVisibleText'],label_B:['id','type','glyphStartReferenceFrames','glyphSettleFrames','visibleHoldUntilCulled','sampleVisibleText'],hero_pin:['id','type','referenceFrames','sizeSamples','anchor','holdUntilFrameExclusive'],boundary:['id','type','referenceFrames','startReferenceFrame','completeReferenceFrame','fractionAtEndpoints','easing','direction','holdUntilFrameExclusive'],metric:['id','type','glyphStartReferenceFrames','glyphSettleFrames','fullyReadableByReferenceFrame','sampleVisibleText','sourceTruth','holdUntilFrameExclusive','countUp']};
 const eventTypes={context_pins:'PIN_POP_ONCE',context_tint:'STATIC_AREA_OPACITY_REVEAL',label_A:'GRAPHEME_POP_REVEAL',label_B:'GRAPHEME_POP_REVEAL',hero_pin:'PIN_POP_ONCE',boundary:'LINE_REVEAL_THEN_HOLD',metric:'GRAPHEME_POP_REVEAL'};
 for(const event of target.events){
  if(!eventKeys[event.id]||event.type!==eventTypes[event.id])throw Error('RD_EVENT_AUTHORING_EVENT_TYPE_REQUIRED');
  object(event,eventKeys[event.id],`AUTHORING_${event.id}`);
 }
 const e=Object.fromEntries(target.events.map(event=>[event.id,event]));
 const exact=(given,wanted)=>JSON.stringify(given)===JSON.stringify(wanted);
 if(!exact(e.context_pins?.referenceFrames,[177,193])||!exact(e.context_tint?.referenceFrames,[202,240])||!exact(e.hero_pin?.referenceFrames,[333,348])||!exact(e.label_A?.glyphStartReferenceFrames,[289,293,297])||!exact(e.label_B?.glyphStartReferenceFrames,[311,315,319])||!exact(e.metric?.glyphStartReferenceFrames,[487,492,497])||e.label_A.glyphSettleFrames!==4||e.label_B.glyphSettleFrames!==4||e.metric.glyphSettleFrames!==8||e.metric.fullyReadableByReferenceFrame!==505||e.metric.countUp!==false||e.boundary?.startReferenceFrame!==455||e.boundary.completeReferenceFrame!==485)throw Error('RD_EVENT_AUTHORING_EVENT_TIMING_MISMATCH');
 if(!exact(e.hero_pin.sizeSamples.map(s=>s.scale),POP)||!exact(e.hero_pin.sizeSamples.map(s=>s.frame),Array.from({length:15},(_,i)=>333+i)))throw Error('RD_EVENT_AUTHORING_POP_CURVE_MISMATCH');
 const labels=[text(e.label_A.sampleVisibleText,'AUTHORING_LABEL_A'),text(e.label_B.sampleVisibleText,'AUTHORING_LABEL_B')],metricText=text(e.metric.sampleVisibleText,'AUTHORING_METRIC');
 if(labels.some(label=>graphemes(label).length!==3)||graphemes(metricText).filter(g=>!/^\s+$/u.test(g)).length!==3)throw Error('RD_EVENT_AUTHORING_TEXT_EVENT_COUNT_MISMATCH');
 return freezeEventData({version:VERSION,pixelConnected:false,status:'AUTHORING_ONLY_UNBOUND_NOT_EXECUTABLE',dataMode:'UNBOUND',
  contextLocations:labels.map((label,index)=>({id:null,bindingKey:`contextLocationIds[${index}]`,label,anchor:null,source:null})),heroLocation:{id:null,bindingKey:'detailLocationId',label:null,anchor:null,source:null},
  boundary:{id:null,bindingKey:'detailBoundaryGeometryId',geometry:null,source:null},metric:{id:null,bindingKey:'metricValueId',text:metricText,source:{verification:'OBSERVED_REFERENCE_TEXT',sha256:target.reference.sha256}},
  contextGraphemes:labels.map(graphemes),metricGraphemes:graphemes(metricText),arclength:null,renderAllowed:false,projection:null});
}
function assertPlan(plan) {
 if (plan?.version !== VERSION || plan.pixelConnected !== false || !['CONTRACT_ONLY_AWAITING_NATIVE_CONSUMER','AUTHORING_ONLY_UNBOUND_NOT_EXECUTABLE'].includes(plan.status)) throw Error('RD_EVENT_COMPILED_CONTRACT_REQUIRED');
 return plan;
}
/** Global-frame evaluation never depends on job/window/localFrame/wall-clock. */
export function evaluateReferenceEvents(plan, referenceFrame) {
 const p = assertPlan(plan), f = frame(referenceFrame);
 const label = (index) => ({inputId:p.contextLocations[index].id,text:p.contextLocations[index].label,
  role:f >= 289 && f < 333 ? 'REQUIRED_VISIBLE_SAFE':'CONTEXT_CULL',
  glyphs:p.contextGraphemes[index].map((grapheme,i)=>({grapheme,startFrame:289 + index * 22 + i * 4,scale:easeOut((f-(289+index*22+i*4))/4),opacity:easeOut((f-(289+index*22+i*4))/4)}))});
 let metricBeat = -1;
 const metricGlyphs = p.metricGraphemes.map(grapheme=>{
  if (/^[\s]+$/u.test(grapheme)) return {grapheme,layoutOnly:true,startFrame:null,scale:1,opacity:0};
  const startFrame=487+(++metricBeat)*5,t=easeOut((f-startFrame)/8);
  return {grapheme,layoutOnly:false,startFrame,scale:t,opacity:t};
 });
 return freezeEventData({referenceFrame:f,coreFrame:f-29,pixelConnected:false,status:p.status,
  contextPins:p.contextLocations.map(item=>({inputId:item.id,anchor:item.anchor,scale:popScale(f,177,16),role:'CONTEXT_CULL',widthPx:49,heightPx:64,holeDiameterPx:29,anchorMode:'BOTTOM_TIP',sizeSpace:'SCREEN_PIXELS',orientation:'SCREEN_UPRIGHT'})),
  labels:[label(0),label(1)],heroPin:{inputId:p.heroLocation.id,anchor:p.heroLocation.anchor,scale:popScale(f,333,15),role:'REQUIRED_VISIBLE_SAFE',widthPx:116,heightPx:151,holeDiameterPx:68,anchorMode:'BOTTOM_TIP',sizeSpace:'SCREEN_PIXELS',orientation:'SCREEN_UPRIGHT'},
  contextArea:{opacityFraction:clamp((f-202)/38),geometryMotion:false,role:'AREA_VIEWPORT_CLIP'},
  boundary:{inputId:p.boundary.id,revealFraction:clamp((f-455)/30),measurementSpace:'SOURCE_GEOGRAPHIC_ARCLENGTH',coreWidthPx:6,coreSRGB:'#FFF000',haloRadiusPx:24,haloSRGB:'#FFE000',haloOpacity:.55,repeatPulse:false},
  metric:{inputId:p.metric.id,text:p.metric.text,sourceTruth:p.metric.source.verification,glyphs:metricGlyphs,fullyReadable:f>=505,role:'REQUIRED_VISIBLE_SAFE',fontPx:52,offsetFromBoundaryPx:24,countUp:false}});
}
const OUTER_PATH='M58 151 C45 132 0 96 0 58 C0 26 26 0 58 0 C90 0 116 26 116 58 C116 96 71 132 58 151 Z';
/** New authored variant, not recovered source artwork. Real even-odd hole. */
export function authoredPinSvg(size='HERO') {
 if(!['HERO','CONTEXT'].includes(size))throw Error('RD_EVENT_PIN_STYLE_REQUIRED');
 const [w,h,d]=size==='HERO'?[116,151,68]:[49,64,29],sx=w/116,sy=h/151;
 let index=0;const outer=OUTER_PATH.replace(/\d+(?:\.\d+)?/gu,n=>String(Number(n)*(index++%2?sy:sx)));
 const cx=58*sx,cy=56*sy,r=d/2;
 const hole=`M${cx+r} ${cy} A${r} ${r} 0 1 0 ${cx-r} ${cy} A${r} ${r} 0 1 0 ${cx+r} ${cy} Z`;
 return `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" data-authorship="NEW_PROFILE_AUTHORED_NOT_EXTRACTED" data-tip="${w/2},${h}" data-hole-diameter="${d}" data-size-space="SCREEN_PIXELS"><path d="${outer} ${hole}" fill="#FEE901" fill-rule="evenodd"/><path d="${outer}" fill="none" stroke="#8C8200" stroke-width="1.5" stroke-linejoin="round"/></svg>`;
}
export function popScale(f, startFrame, duration) {
 if (!Number.isFinite(f) || !Number.isSafeInteger(startFrame) || !Number.isSafeInteger(duration) || duration<2) throw Error('RD_EVENT_POP_INPUT_REQUIRED');
 if (f<startFrame) return 0;
 if (f>=startFrame+duration-1) return 1;
 const t=(f-startFrame)*(POP.length-1)/(duration-1),i=Math.floor(t),a=t-i;
 return POP[i]+(POP[i+1]-POP[i])*a;
}
/** Integrate the unchanged linear-lon/lat edge on an explicitly spherical Earth.
 * This is not great-circle endpoint distance and does not replace the source edge
 * with a shortest route. Adaptive Simpson tolerance is max(1e-6m, 1e-11 relative).
 */
function sourceEdgeLength(a,b,end=1) {
 const r=Math.PI/180,dLat=(b[1]-a[1])*r,dLon=(b[0]-a[0])*r,lat=a[1]*r;
 if(end===0 || (dLat===0&&dLon===0))return 0;
 const speed=t=>6371008.8*Math.hypot(dLat,Math.cos(lat+t*dLat)*dLon);
 const f0=speed(0),fm=speed(end/2),f1=speed(end),whole=end*(f0+4*fm+f1)/6;
 const refine=(l,h,fl,fmid,fh,estimate,tolerance,depth)=>{
  const m=(l+h)/2,lm=(l+m)/2,hm=(m+h)/2,fleft=speed(lm),fright=speed(hm);
  const left=(m-l)*(fl+4*fleft+fmid)/6,right=(h-m)*(fmid+4*fright+fh)/6,delta=left+right-estimate;
  if(Math.abs(delta)<=15*tolerance)return left+right+delta/15;
  if(depth===0)throw Error('RD_EVENT_GEOGRAPHIC_ARCLENGTH_PRECISION_UNRESOLVED');
  return refine(l,m,fl,fleft,fmid,left,tolerance/2,depth-1)+refine(m,h,fmid,fright,fh,right,tolerance/2,depth-1);
 };
 return refine(0,end,f0,fm,f1,whole,Math.max(1e-6,Math.abs(whole)*1e-11),20);
}
/** Source geographic arclength; never recomputed from the camera projection. */
export function compileSourceArclength(coordinates,direction='FORWARD') {
 if (!Array.isArray(coordinates) || coordinates.length<2 || !['FORWARD','REVERSE'].includes(direction)) throw Error('RD_EVENT_LINE_COORDINATES_REQUIRED');
 const points=coordinates.map(p=>validateEventAnchor(p));
 if (points.some((p,i)=>i>0 && Math.abs(p[0]-points[i-1][0])>180)) throw Error('RD_EVENT_WRAPPED_LINE_UNSUPPORTED');
 if (direction==='REVERSE') points.reverse();
 const lengths=points.slice(1).map((b,i)=>sourceEdgeLength(points[i],b));
 const cumulative=[0]; for(const length of lengths)cumulative.push(cumulative.at(-1)+length);
 if (!(cumulative.at(-1)>0))throw Error('RD_EVENT_SOURCE_LINE_ZERO_LENGTH');
 return freezeEventData({coordinates:points,lengths,cumulative,total:cumulative.at(-1),distanceModel:'SPHERICAL_LINE_INTEGRAL_ALONG_SUPPLIED_LINEAR_LON_LAT_EDGES',earthRadiusMeters:6371008.8,integrationTolerance:{absoluteMeters:1e-6,relative:1e-11},edgeInterpolation:'SUPPLIED_LINEAR_LON_LAT',direction});
}
export function geographicPointAt(arc,fraction) {
 if (!Number.isFinite(fraction) || fraction<0 || fraction>1 || !arc?.total) throw Error('RD_EVENT_ARCLENGTH_FRACTION_REQUIRED');
 if (fraction===0)return [...arc.coordinates[0]];
 if (fraction===1)return [...arc.coordinates.at(-1)];
 const distance=arc.total*fraction;
 let i=1;while(i<arc.coordinates.length-1 && arc.cumulative[i]<distance)i++;
 while(arc.lengths[i-1]===0 && i<arc.coordinates.length-1)i++;
 const localDistance=distance-arc.cumulative[i-1],a=arc.coordinates[i-1],b=arc.coordinates[i];let lo=0,hi=1;
 if(a[0]===b[0]||a[1]===b[1])lo=hi=localDistance/arc.lengths[i-1];
 for(let step=0;step<48&&lo!==hi;step++){
  const t=(lo+hi)/2, length=sourceEdgeLength(arc.coordinates[i-1],arc.coordinates[i],t);
  if(length<localDistance)lo=t;else hi=t;
 }
 const t=(lo+hi)/2;
 return arc.coordinates[i-1].map((v,axis)=>v+(arc.coordinates[i][axis]-v)*t);
}
export function revealSourceLine(arc,fraction) {
 if (!Number.isFinite(fraction)||fraction<0||fraction>1)throw Error('RD_EVENT_ARCLENGTH_FRACTION_REQUIRED');
 if (fraction===0)return [];
 if (fraction===1)return arc.coordinates.map(p=>[...p]);
 const distance=arc.total*fraction,result=[[...arc.coordinates[0]]];
 for(let i=1;i<arc.coordinates.length;i++){
  if(arc.cumulative[i]<=distance)result.push([...arc.coordinates[i]]);
  else {result.push(geographicPointAt(arc,fraction));break;}
 }
 return result;
}
/** Fixed full geographic midpoint, not clipped visible-segment substitution. */
export function metricScreenPlacement(arc,{project,previousReadableAngle=null,normalSign=1}={}) {
 if(typeof project!=='function')throw Error('RD_EVENT_CURRENT_MAP_PROJECTION_REQUIRED');
 const midpoint=geographicPointAt(arc,.5),a=project(geographicPointAt(arc,.49999)),b=project(geographicPointAt(arc,.50001)),p=project(midpoint);
 if(![a,b,p].every(xy))throw Error('RD_EVENT_FINITE_METRIC_PROJECTION_REQUIRED');
 let dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy);
 if(!(length>1e-10))throw Error('RD_EVENT_DEGENERATE_METRIC_TANGENT');
 if(![-1,1].includes(normalSign))throw Error('RD_EVENT_CANONICAL_NORMAL_SIGN_REQUIRED');
 // Side is attached to the supplied direction, separately from glyph reading.
 const normal=[normalSign*dy/length,-normalSign*dx/length];
 if(dx<0){dx=-dx;dy=-dy;}
 const angle=Math.atan2(dy,dx);
 if(previousReadableAngle!==null && (!Number.isFinite(previousReadableAngle)||Math.abs(angle-previousReadableAngle)>Math.PI/2))throw Error('RD_EVENT_READABLE_ORIENTATION_DISCONTINUITY');
 return {geographicAnchor:midpoint,projectedAnchor:p,position:[p[0]+24*normal[0],p[1]+24*normal[1]],angleRadians:angle,normal,offsetPixels:24,anchorPolicy:'CANONICAL_SOURCE_ARCLENGTH_MIDPOINT'};
}
/** Select the initial upward side once; preserve it over the global camera track.
 * If the track would force an unreadable/180-degree text flip, refuse admission.
 */
export function compileMetricScreenTrack(arc,{projectAt,referenceFrames}={}){
 if(typeof projectAt!=='function'||!Array.isArray(referenceFrames)||!referenceFrames.length||referenceFrames.some((f,i)=>!Number.isSafeInteger(f)||(i&&f<=referenceFrames[i-1])))throw Error('RD_EVENT_GLOBAL_METRIC_TRACK_REQUIRED');
 const first=metricScreenPlacement(arc,{project:p=>projectAt(referenceFrames[0],p)}),normalSign=first.normal[1]>0?-1:1;
 let previous=null;
 const placements=referenceFrames.map(referenceFrame=>{
  const placement=metricScreenPlacement(arc,{project:p=>projectAt(referenceFrame,p),previousReadableAngle:previous,normalSign});
  previous=placement.angleRadians;return {referenceFrame,...placement};
 });
 return freezeEventData({normalSign,sideSelection:'ONCE_AT_GLOBAL_TRACK_START_UPWARD',placements});
}
export function visibilityDecision(role,box,{safe=[86,154,929,1498],viewport=[0,0,1080,1920]}={}){
 if(!ROLES.includes(role)||![box,safe,viewport].every(v=>Array.isArray(v)&&v.length===4&&v.every(Number.isFinite)&&v[0]<=v[2]&&v[1]<=v[3]))throw Error('RD_EVENT_VISIBILITY_INPUT_REQUIRED');
 const intersects=(a,b)=>a[0]<b[2]&&a[2]>b[0]&&a[1]<b[3]&&a[3]>b[1];
 const inside=box[0]>=safe[0]&&box[1]>=safe[1]&&box[2]<=safe[2]&&box[3]<=safe[3];
 if(role==='REQUIRED_VISIBLE_SAFE'&&!inside)throw Error('RD_EVENT_REQUIRED_FOOTPRINT_OUTSIDE_SAFE');
 return {role,draw:role==='REQUIRED_VISIBLE_SAFE'||intersects(box,viewport),clipToViewport:role!=='REQUIRED_VISIBLE_SAFE',geometryMutation:false};
}
/** Browser-only real font metrics, reused from protected measured-glyph module. */
export function measureDirectorWord(word,{fontPx=48,haloRadiusPx=16}={}) {
 const glyph=createMeasuredGlyph(word,{fontSize:fontPx,fontFamily:'Gate1Bold',outlineRadius:haloRadiusPx,maxLines:1});
 if(!glyph.fits||glyph.alphaTouchesEdge||glyph.lines.length!==1)throw Error('RD_EVENT_REAL_GLYPH_MEASUREMENT_FAILED');
 const c=glyph.canvas.getContext('2d'),parts=graphemes(word),advances=[];let prefix='';
 for(const part of parts){advances.push(c.measureText(prefix).width);prefix+=part;}
 const ink=glyph.measuredInk[0];
 return {font:'Gate1Bold',fontPx,haloRadiusPx,fullWord:word,graphemes:parts,advances,totalAdvance:c.measureText(word).width,fullWordInkBounds:[-ink.left,-ink.ascent,ink.right,ink.descent],alphaBounds:glyph.alphaBounds,atlasDimensions:glyph.atlasDimensions,alphaPixels:glyph.alphaPixels,measurement:'EXISTING_PINNED_NATIVE_BROWSER_GLYPH'};
}
export function labelPlacement(measurement,pinTip,{pinHeightPx=64,pinScale=1,gapPx=12}={}) {
 if(!measurement || !Array.isArray(measurement.advances)||!measurement.advances.every(Number.isFinite)||!Number.isFinite(measurement.totalAdvance)||!Array.isArray(measurement.fullWordInkBounds)||measurement.fullWordInkBounds.length!==4||!measurement.fullWordInkBounds.every(Number.isFinite)||!xy(pinTip)||![pinHeightPx,pinScale,gapPx].every(v=>Number.isFinite(v)&&v>=0))throw Error('RD_EVENT_MEASURED_LABEL_PLACEMENT_REQUIRED');
 const [inkLeft,,inkRight,descent]=measurement.fullWordInkBounds;
 const left=pinTip[0]-(inkLeft+inkRight)/2,bottom=pinTip[1]-pinHeightPx*pinScale-gapPx,baseline=bottom-descent;
 return {fullWord:measurement.fullWord,left,bottom,baseline,glyphOrigins:measurement.advances.map(advance=>[left+advance,baseline]),centering:'FULL_WORD_INK_FIXED',orientation:'SCREEN_UPRIGHT'};
}
