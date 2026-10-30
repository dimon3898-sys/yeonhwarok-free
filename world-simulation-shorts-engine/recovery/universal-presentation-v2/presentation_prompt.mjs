/** Bounded bilingual intent extraction plus supplied-data native Scene compilation.
 * This is not an LLM, historical researcher, geocoder, or unrestricted NLU service. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {parsePrompt,analyzePrompt,canonicalJSON} from '../universal-data-pipeline-v1/prompt_pipeline.mjs';
import {compileScenePlan,validateFactDataset,validateScenePlan} from '../../web/map_infographic_v1/planner_scene_v1.mjs';
import {compileExistingEnginePlan} from '../../web/map_infographic_v1/planner_engine_adapter_v1.mjs';
import {validatePresentation} from './presentation_plan.mjs';

export const SCHEMA='WORLD_ENGINE_PRESENTATION_PROMPT_V2';
export const RESULT_SCHEMA='WORLD_ENGINE_PRESENTATION_PIPELINE_RESULT_V2';
export const VERSION='universal-presentation-v2.0.0';
const copy=x=>structuredClone(x);
const object=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
const text=x=>typeof x==='string'&&x.trim().length>0;
const hash=x=>createHash('sha256').update(typeof x==='string'?x:canonicalJSON(x)).digest('hex');
const issue=(status,code,field,reason,example)=>({status,code,field,reason,example});
const statusOf=rows=>['INVALID','CONFLICT','UNSUPPORTED','NEEDS_INPUT'].find(s=>rows.some(r=>r.status===s))??'PASS';
const point=p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite)&&Math.abs(p[0])<=180&&Math.abs(p[1])<=90;
function unknown(value,allowed,field,issues){
 if(value===undefined)return;
 if(!object(value)){issues.push(issue('INVALID','OBJECT_REQUIRED',field,'Supply an object.',{supportedFields:allowed}));return;}
 for(const key of Object.keys(value))if(!allowed.includes(key))issues.push(issue('UNSUPPORTED','UNCONSUMED_FIELD',field+'.'+key,'No field is silently ignored.',{supportedFields:allowed,removeField:key}));
}
function mappedLegacy(row){return{...copy(row),field:'$.data'+row.field.slice(1),validationOwner:'UNCHANGED_DATA_PIPELINE_V1'};}
function literalMatches(prompt,needle){
 // Search the actual input, so offsets always index original UTF-16 text.
 const escaped=String(needle).replace(/[.*+?^${}()|[\]\\]/gu,'\\$&'),out=[];
 if(!escaped)return out;
 for(const m of prompt.matchAll(new RegExp(escaped,'giu'))){
  const before=prompt[m.index-1]??'',after=prompt[m.index+m[0].length]??'';
  if(!/^[A-Za-z0-9_]+$/u.test(needle)||!/[A-Za-z0-9_]/u.test(before)&&!/[A-Za-z0-9_]/u.test(after))out.push({start:m.index,end:m.index+m[0].length,text:m[0]});
 }
 return out;
}
function clauseAt(prompt,index){
 // Only explicit sentence/semicolon/newline clauses determine scene scope.
 // Decimal points and date punctuation are not sentence boundaries.
 let start=0,end=prompt.length;
 for(const m of prompt.matchAll(/[!?。;\n]|\.(?=\s|$)/gu)){if(m.index<index)start=m.index+1;else{end=m.index;break;}}
 return {start,end,text:prompt.slice(start,end)};
}
function sceneScope(prompt,span,scenes){
 const clause=clauseAt(prompt,span.start),explicit=[];
 for(const [i,row]of scenes.entries())if(text(row?.sceneId)&&literalMatches(clause.text,row.sceneId).length)explicit.push(i);
 for(const m of clause.text.matchAll(/(?:첫(?:\s*번째)?|첫째|first)\s*(?:장면|scene)|(?:두\s*번째|둘째|second)\s*(?:장면|scene)|(?:세\s*번째|셋째|third)\s*(?:장면|scene)|(?:제\s*)?(\d+)\s*(?:번째|번)\s*장면|scene\s*(\d+)|(?<!\w)(\d+)(?:st|nd|rd|th)\s+scene/giu)){
  const v=m[1]??m[2]??m[3];explicit.push(v?Number(v)-1:/(?:두|둘|second)/iu.test(m[0])?1:/(?:세|셋|third)/iu.test(m[0])?2:0);
 }
 const indices=[...new Set(explicit)];
 return indices.length?{sceneIndices:indices,clause:{start:clause.start,end:clause.end,text:clause.text},method:'EXPLICIT_SCENE_ID_OR_ORDINAL_IN_CLAUSE'}:{sceneIndices:null,method:'UNSCOPED_SHARED_INTENT'};
}
function scopedNL(nl,index){
 const out={...nl};
 for(const key of ['intents','dates','locations','routes','connections','coordinates'])out[key]=nl[key].filter(x=>!x.scope?.sceneIndices||x.scope.sceneIndices.includes(index));
 return out;
}
const INTENTS=Object.freeze([
 ['ROUTE_FOLLOW',/(?:항로|경로|노선|route|path).{0,28}(?:따라|추적|follow|track)|(?:따라|추적|follow|track).{0,28}(?:항로|경로|노선|route|path)/giu],
 ['CAMERA_MOVE',/카메라.{0,22}(?:이동|움직|추적)|(?:move|pan|track).{0,20}(?:the\s+)?camera|camera.{0,22}(?:move|pan|follow)/giu],
 ['ZOOM_IN',/줌\s*인|확대|zoom\s*in/giu],
 ['ZOOM_OUT',/줌\s*아웃|축소|zoom\s*out/giu],
 ['LOCATION_HIGHLIGHT',/도시.{0,18}(?:강조|하이라이트)|(?:강조|하이라이트).{0,18}도시|highlight.{0,28}(?:cit(?:y|ies)|location|node)|(?:cit(?:y|ies)|location|node).{0,28}(?:highlight|emphasi)/giu],
 ['EVENT_HIGHLIGHT',/사건.{0,18}(?:강조|하이라이트)|(?:강조|하이라이트).{0,18}사건|highlight.{0,20}event|event.{0,20}(?:highlight|emphasi)/giu],
 ['TERRITORY_CHANGE',/(?:영토|영역|점령|territor(?:y|ies)|area).{0,30}(?:변화|확장|축소|change|expand|contract|grow|shrink)/giu],
 ['SCENE_TRANSITION',/장면.{0,16}(?:전환|컷)|(?:전환|컷).{0,16}장면|cut.{0,30}scenes?|scenes?.{0,30}(?:cut|transition)|transition.{0,20}scenes?/giu],
]);
const UNSUPPORTED_INTENTS=Object.freeze([
 ['UNSUPPORTED_VISIBLE_LABELS',/(?:라벨|도시\s*이름|지명|텍스트|문자|캡션).{0,24}(?:표시|보여|출력|추가|넣|붙)|(?:show|display|render|add|write).{0,24}(?:labels?|place\s*names?|cit(?:y|ies)\s*names?|captions?|on[- ]screen\s*text)|(?:labels?|captions?|place\s*names?).{0,24}(?:show|display|render)/giu],
 ['UNSUPPORTED_AUDIO',/\b(?:tts|narration|background music|bgm)\b|배경\s*음악|음성\s*합성|내레이션/giu],
 ['UNSUPPORTED_EXPLOSION',/폭발\s*(?:효과|연출)|explosion\s*(?:effect|animation)/giu],
 ['UNSUPPORTED_LIVE_DATA',/실시간\s*(?:위성|주가|항공편)|live\s*(?:satellite|flight|stock)/giu],
 ['UNSUPPORTED_3D',/\b3d\b|입체\s*모델/giu],
 ['UNSUPPORTED_FADE',/페이드|cross\s*fade|dissolve/giu],
 ['UNSUPPORTED_CAMERA_ROTATION',/카메라.{0,16}(?:회전|공전)|(?:orbit|rotate|rotation).{0,18}(?:camera|view)|camera.{0,18}(?:orbit|rotat)/giu],
]);

/** Extraction is explicit grammar/entity linking. Every extracted span keeps its source. */
export function extractNaturalLanguage(prompt,{data}={}){
 const out={schema:'WORLD_ENGINE_BOUNDED_NL_INTENT_V2',method:'BOUNDED_KOREAN_ENGLISH_GRAMMAR_AND_SUPPLIED_ENTITY_LINKING',
  unrestrictedLanguageUnderstanding:false,externalLLMUsed:false,rawPrompt:prompt,topic:null,intents:[],durations:[],fps:[],dates:[],locations:[],routes:[],connections:[],coordinates:[],unsupported:[],uninterpretedText:prompt};
 if(!text(prompt)||Buffer.byteLength(prompt,'utf8')>32768||/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/u.test(prompt))throw Error('NATURAL_PROMPT_TEXT_REQUIRED');
 const add=(type,match,value)=>({type,value,start:match.index,end:match.index+match[0].length,text:match[0],origin:'NATURAL_LANGUAGE_EXPLICIT_SPAN'});
 out.topic={text:prompt.split(/[.!?。\n]/u)[0].trim(),origin:'NATURAL_LANGUAGE_FIRST_CLAUSE_DISPLAY_ONLY',factsInferred:false};
 for(const [name,regex]of INTENTS)for(const m of prompt.matchAll(new RegExp(regex.source,regex.flags)))out.intents.push(add(name,m,name));
 for(const [name,regex]of UNSUPPORTED_INTENTS)for(const m of prompt.matchAll(new RegExp(regex.source,regex.flags)))out.unsupported.push(add(name,m,name));
 for(const m of prompt.matchAll(/(?<![\d.])(\d+(?:\.\d+)?)\s*(초|분|seconds?|secs?|minutes?|mins?)(?![A-Za-z])/giu)){
  const multiplier=/^(?:분|minutes?|mins?)$/iu.test(m[2])?60:1;out.durations.push(add('DURATION',m,Number(m[1])*multiplier));
 }
 if(out.durations.length===2&&/\d+(?:\.\d+)?\s*(?:분|minutes?|mins?)\s*\d+(?:\.\d+)?\s*(?:초|seconds?|secs?)/iu.test(prompt)){
  const a=out.durations[0],b=out.durations[1];out.durations=[{type:'DURATION',value:a.value+b.value,start:a.start,end:b.end,text:prompt.slice(a.start,b.end),origin:'NATURAL_LANGUAGE_COMPOUND_DURATION'}];
 }
 for(const m of prompt.matchAll(/(?<!\d)(\d+)\s*fps\b/giu))out.fps.push(add('FPS',m,Number(m[1])));
 const dateSpans=[];
 for(const m of prompt.matchAll(/(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)/gu)){out.dates.push({...add('DATE',m,m[0]),precision:'DAY'});dateSpans.push([m.index,m.index+m[0].length]);}
 for(const m of prompt.matchAll(/(?<!\d)(\d{4})년(?:\s*(\d{1,2})월)?(?:\s*(\d{1,2})일)?/gu)){
  if(dateSpans.some(([a,b])=>m.index<b&&m.index+m[0].length>a))continue;
  const precision=m[3]?'DAY':m[2]?'MONTH':'YEAR',value=m[1]+(m[2]?'-'+m[2].padStart(2,'0'):'')+(m[3]?'-'+m[3].padStart(2,'0'):'');
  out.dates.push({...add('DATE',m,value),precision});
 }
 for(const m of prompt.matchAll(/\bfrom\s+([A-Za-z0-9_ .'-]+?)\s+to\s+([A-Za-z0-9_ .'-]+?)(?=\s+(?:and|then|with|for|by|using)\b|[.!?;,]|\s*$)/giu))out.connections.push({...add('SUPPLIED_LOCATION_CONNECTION',m,{from:m[1].trim(),to:m[2].trim()}),direction:'AS_WRITTEN'});
 for(const m of prompt.matchAll(/([^\s,.]+)에서\s+([^\s,.]+?)(?:까지|으로|로)(?=\s|[,.!?]|$)/gu))out.connections.push({...add('SUPPLIED_LOCATION_CONNECTION',m,{from:m[1],to:m[2]}),direction:'AS_WRITTEN'});
 for(const m of prompt.matchAll(/\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]/gu))out.coordinates.push(add('COORDINATE',m,[Number(m[1]),Number(m[2])]));
 const scenes=Array.isArray(data?.scenes)?data.scenes:[],locations=new Map(),routes=new Map();
 for(const row of scenes){
  for(const location of Array.isArray(row?.facts?.locations)?row.facts.locations:[])if(object(location)&&text(location.id)){const prior=locations.get(location.id);locations.set(location.id,{...location,ambiguousAnchor:Boolean(prior&&(prior.ambiguousAnchor||canonicalJSON(prior.anchor)!==canonicalJSON(location.anchor)))});}
  for(const route of Array.isArray(row?.facts?.routes)?row.facts.routes:[])if(object(route)&&text(route.id))routes.set(route.id,route);
 }
 if(locations.size>256||routes.size>256)throw Error('NATURAL_ENTITY_LINKING_LIMIT');
 for(const [id,location]of locations)for(const alias of new Set([location.id,location.label].filter(text)))for(const span of literalMatches(prompt,alias))out.locations.push({...span,id,alias,origin:'NATURAL_LANGUAGE_REFERENCE_TO_SUPPLIED_LOCATION',suppliedAnchor:copy(location.anchor),ambiguousAnchor:location.ambiguousAnchor});
 for(const [id]of routes)for(const span of literalMatches(prompt,id))out.routes.push({...span,id,origin:'NATURAL_LANGUAGE_REFERENCE_TO_SUPPLIED_ROUTE'});
 for(const key of ['intents','dates','locations','routes','connections','coordinates'])for(const span of out[key])span.scope=sceneScope(prompt,span,scenes);
 return out;
}

function calendarInterval(span){
 const parts=span.value.split('-').map(Number),[year,month,day]=parts;
 if(year<1||year>9999||month!==undefined&&(month<1||month>12))return null;
 const leap=year%4===0&&(year%100!==0||year%400===0),days=[31,leap?29:28,31,30,31,30,31,31,30,31,30,31];
 if(day!==undefined&&(!month||day<1||day>days[month-1]))return null;
 const pad=v=>String(v).padStart(2,'0'),prefix=String(year).padStart(4,'0');
 return span.precision==='YEAR'?[prefix+'-01-01',prefix+'-12-31']:span.precision==='MONTH'?[prefix+'-'+pad(month)+'-01',prefix+'-'+pad(month)+'-'+pad(days[month-1])]:[span.value,span.value];
}
function validateExplicitSpans(nl,data,region,issues){
 const rows=Array.isArray(data.scenes)?data.scenes:[];
 for(const value of [...nl.intents,...nl.dates,...nl.connections,...nl.coordinates])if(value.scope?.sceneIndices?.some(i=>i<0||i>=rows.length))issues.push(issue('NEEDS_INPUT','NATURAL_SCENE_REFERENCE_MISSING','$.prompt','An explicit scene ordinal or ID is outside the attached scene list.',{span:value.text,sceneIndices:value.scope.sceneIndices,availableSceneIds:rows.map(x=>x?.sceneId)}));
 for(const date of nl.dates){
  const interval=calendarInterval(date);
  if(!interval){issues.push(issue('INVALID','NATURAL_DATE_INVALID','$.prompt','Explicit dates must be valid Gregorian dates at the stated precision.',{span:date.text,value:date.value,precision:date.precision}));continue;}
  const matching=rows.filter((_,i)=>!date.scope.sceneIndices||date.scope.sceneIndices.includes(i)),ranges=matching.map(row=>row?.facts?.time_range).filter(r=>text(r?.start)&&text(r?.end));
  if(ranges.length&&ranges.every(r=>interval[1]<r.start||interval[0]>r.end))issues.push(issue('CONFLICT','NATURAL_DATE_OUTSIDE_ATTACHED_DATA','$.prompt','The requested date interval does not intersect the matching attached scene validity range; attached dates were not overwritten.',{requested:date.value,precision:date.precision,allowedIntervals:ranges,action:'Attach matching dated facts or correct the prompt'}));
 }
 for(const coordinate of nl.coordinates){
  if(!point(coordinate.value)){issues.push(issue('INVALID','NATURAL_COORDINATE_INVALID','$.prompt','Explicit coordinate text must use finite longitude/latitude within ±180/±90.',{span:coordinate.text,order:'[longitude,latitude]'}));continue;}
  const clause=clauseAt(nl.rawPrompt,coordinate.start),prefix=nl.rawPrompt.slice(Math.max(clause.start,coordinate.start-40),coordinate.start),same=(a,b)=>point(a)&&point(b)&&a.every((x,i)=>Math.abs(x-b[i])<=1e-9);
  if(/(?:center|centre|중심|중앙)(?:\s*(?:coordinate|coordinates|좌표|점|is|=|:|은|는|이|가))*\s*$/iu.test(prefix)){
   if(!same(coordinate.value,region?.center))issues.push(issue('CONFLICT','NATURAL_REGION_CENTER_CONFLICT','$.prompt','The explicit natural-language center conflicts with the attached region; neither was silently overwritten.',{requested:coordinate.value,attachedCenter:region?.center}));
   continue;
  }
  const points=[];function visit(x){if(point(x))points.push(x);else if(Array.isArray(x))x.forEach(visit);}
  if(point(region?.center))points.push(region.center);
  for(const [i,row]of rows.entries())if(!coordinate.scope.sceneIndices||coordinate.scope.sceneIndices.includes(i)){
   for(const l of Array.isArray(row?.facts?.locations)?row.facts.locations:[])if(point(l.anchor))points.push(l.anchor);
   for(const g of Array.isArray(row?.facts?.geometries)?row.facts.geometries:[])visit(g?.geometry?.coordinates);
  }
  if(!points.some(p=>same(p,coordinate.value)))issues.push(issue('NEEDS_INPUT','NATURAL_COORDINATE_BINDING_REQUIRED','$.prompt','This explicit coordinate has no supplied location, geometry, or approved region binding. Add a named structured binding; it was not dropped or invented.',{coordinate:coordinate.value,order:'[longitude,latitude]',action:'Attach the intended location/geometry or correct the text'}));
 }
 for(const connection of nl.connections){
  const key=s=>String(s).normalize('NFKC').toLocaleLowerCase('en-US').trim(),matching=rows.filter((_,i)=>!connection.scope.sceneIndices||connection.scope.sceneIndices.includes(i));
  let knownFrom=false,knownTo=false,matchedRoute=false;
  for(const row of matching){
   const locations=Array.isArray(row?.facts?.locations)?row.facts.locations:[],find=alias=>locations.filter(l=>[l.id,l.label].filter(text).some(x=>key(x)===key(alias))),from=find(connection.value.from),to=find(connection.value.to);
   knownFrom ||= from.length>0;knownTo ||= to.length>0;
   for(const route of Array.isArray(row?.facts?.routes)?row.facts.routes:[]){
    const line=row.facts.geometries?.find(g=>g.id===route.geometry_ref)?.geometry;
    if(line?.type!=='LineString'||!line.coordinates?.length)continue;
    const pts=route.direction==='REVERSE'?[...line.coordinates].reverse():line.coordinates,same=(a,b)=>point(a)&&point(b)&&a.every((x,i)=>Math.abs(x-b[i])<=1e-6);
    if(from.some(l=>same(l.anchor,pts[0]))&&to.some(l=>same(l.anchor,pts.at(-1))))matchedRoute=true;
   }
  }
  if(!knownFrom||!knownTo)issues.push(issue('NEEDS_INPUT','NATURAL_LOCATION_DATA_REQUIRED','$.prompt','A requested connection endpoint has no matching supplied location. Coordinates are not inferred from a name.',{requested:connection.value,missingEndpoints:[...(!knownFrom?[connection.value.from]:[]),...(!knownTo?[connection.value.to]:[])],action:'Attach the named location and route facts or correct the endpoint'}));
  else if(!matchedRoute)issues.push(issue('CONFLICT','NATURAL_CONNECTION_NOT_IN_ATTACHED_DATA','$.prompt','The requested directed endpoints do not match an attached route; no connection was invented or reversed.',{requested:connection.value,action:'Supply a matching directed route or correct the text'}));
 }
 for(const location of nl.locations)if(location.ambiguousAnchor&&!location.scope.sceneIndices)issues.push(issue('NEEDS_INPUT','NATURAL_LOCATION_AMBIGUOUS','$.prompt','A referenced location ID has different supplied coordinates in different scenes. Specify its scene explicitly.',{locationId:location.id,span:location.text}));
}

function completeData(data,nl,trace,issues){
 if(!object(data)){issues.push(issue('NEEDS_INPUT','ATTACHED_DATA_REQUIRED','$.data','Natural-language intent does not supply verified coordinates, boundaries or provenance.',{attach:'WORLD_ENGINE_DATA_PROMPT_V1 or an existing validated data package'}));return null;}
 const out=copy(data),durations=[...new Set(nl.durations.map(x=>x.value))],fps=[...new Set(nl.fps.map(x=>x.value))];
 if(durations.length>1)issues.push(issue('CONFLICT','AMBIGUOUS_NL_DURATION','$.prompt','The text contains conflicting video durations.',{durations,action:'Choose one duration'}));
 if(fps.length>1)issues.push(issue('CONFLICT','AMBIGUOUS_NL_FPS','$.prompt','The text contains conflicting frame rates.',{fps,action:'Choose one frame rate'}));
 for(const [key,values]of [['durationSeconds',durations],['fps',fps]])if(values.length===1){
  if(out[key]!==undefined&&out[key]!==values[0])issues.push(issue('CONFLICT','NATURAL_LANGUAGE_DATA_CONFLICT','$.data.'+key,'The explicit text conflicts with authoritative attached settings; the data was not overwritten.',{attachedValue:out[key],requestedValue:values[0]}));
  else if(out[key]===undefined){out[key]=values[0];trace.push({field:'$.data.'+key,origin:'NATURAL_LANGUAGE_EXPLICIT_SCALAR',value:values[0]});}
 }
 if(out.fps===undefined){out.fps=30;trace.push({field:'$.data.fps',origin:'DOCUMENTED_DISPLAY_DEFAULT',value:30,worldFactCreated:false});}
 if(out.resolution===undefined){out.resolution={width:1080,height:1920};trace.push({field:'$.data.resolution',origin:'DOCUMENTED_DISPLAY_DEFAULT',value:copy(out.resolution),worldFactCreated:false});}
 if(!text(out.topic)){
  const alias=out.scenes?.[0]?.facts?.subject?.aliases?.find(text);
  if(alias){out.topic=alias;trace.push({field:'$.data.topic',origin:'SUPPLIED_SUBJECT_ALIAS_FOR_EXISTING_COMPILER',value:alias,naturalTopicPreservedSeparately:true});}
 }
 return out;
}
function has(nl,name){return nl.intents.some(x=>x.type===name);}
function displayTiming(facts,frames,fps){
 const hold=Math.max(2,Math.floor(frames*.25)),action=frames-hold,count=facts.subject.event_family==='WAR'?facts.stages.length:1;
 return{fps,total_frames:frames,duration_seconds:frames/fps,camera_lock_frame:0,event_start_frame:0,
  initial_reveal_frames:count>1?action-Math.floor(action/count)*(count-1):0,state_transition_frames:count>1?Math.floor(action/count):0,
  final_hold_frames:hold,action_frames:action,frame_policy:'INTEGER_DETERMINISTIC',blank_interstage_frames:0};
}
function geometryCenter(geometry){
 const points=[];function visit(x){if(Array.isArray(x)&&x.length===2&&x.every(Number.isFinite))points.push(x);else if(Array.isArray(x))x.forEach(visit);}
 visit(geometry?.coordinates);return points.length?[(Math.min(...points.map(p=>p[0]))+Math.max(...points.map(p=>p[0])))/2,(Math.min(...points.map(p=>p[1]))+Math.max(...points.map(p=>p[1])))/2]:null;
}
function deriveCamera(nl,scene,region,trace,issues,field){
 if(has(nl,'ROUTE_FOLLOW')){
  const mentioned=scene.routes?.filter(r=>nl.routes.some(x=>x.id===r.id))??[],routes=mentioned.length?mentioned:scene.routes??[];
  if(routes.length!==1){issues.push(issue('NEEDS_INPUT','ROUTE_FOLLOW_REFERENCE_REQUIRED',field+'.camera.routeId','Choose exactly one supplied route to follow in this scene.',{availableRouteIds:routes.map(x=>x.id)}));return null;}
  const result={mode:'ROUTE_FOLLOW',routeId:routes[0].id,zoom:.8,followStrength:.2};trace.push({field:field+'.camera',origin:'NL_FOLLOW_INTENT_AND_SUPPLIED_ROUTE_REFERENCE',value:copy(result),worldFactCreated:false});return result;
 }
 if(!['CAMERA_MOVE','ZOOM_IN','ZOOM_OUT'].some(name=>has(nl,name))){issues.push(issue('NEEDS_INPUT','CAMERA_INTENT_REQUIRED',field+'.camera','Provide a supported moving camera profile or ask to move, zoom, or follow a supplied route.',{camera:{mode:'ROUTE_FOLLOW',routeId:'a_supplied_route'}}));return null;}
 if(has(nl,'ZOOM_OUT')&&!has(nl,'ZOOM_IN')){issues.push(issue('UNSUPPORTED','FINAL_ZOOM_OUT_NOT_ADMITTED',field+'.camera','The preserved camera requires its final view to be closest. Provide an explicit out-and-in profile; a final zoom-out is not silently replaced.',{camera:'KEYFRAMES with final zoom equal to the maximum'}));return null;}
 const n=scene.timing.total_frames,base=copy(region.center),locations=scene.locations.filter(l=>nl.locations.some(x=>x.id===l.id)),targets=scene.geometries.filter(g=>scene.camera_intent.target_geometry_refs.includes(g.id)).map(g=>geometryCenter(g.geometry)).filter(point);
 const anchors=locations.length?locations.map(l=>l.anchor):targets.length?targets:[scene.camera_intent.anchor];
 const c1=has(nl,'CAMERA_MOVE')?base.map((v,i)=>v+(anchors[0][i]-v)*.12):base,
  c2=has(nl,'CAMERA_MOVE')?base.map((v,i)=>v+(anchors.at(-1)[i]-v)*.12):base;
 const zooms=has(nl,'ZOOM_OUT')?[.8,.6,1]:has(nl,'ZOOM_IN')?[.65,.8,1]:[1,1,1];
 const result={mode:'KEYFRAMES',keyframes:[{frame:0,center:c1,zoom:zooms[0]},{frame:Math.floor((n-1)/2),center:c2,zoom:zooms[1]},{frame:n-1,center:base,zoom:zooms[2]}]};
 trace.push({field:field+'.camera',origin:'NL_DISPLAY_INTENT_FRAMED_FROM_SUPPLIED_GEOMETRY',value:copy(result),worldFactCreated:false});return result;
}
function localPresentation(shared,override,nl,scene,region,trace,issues,field){
 unknown(override,['camera','territoryColors','highlights','initialStateVisibility'],field,issues);
 const value={};for(const key of ['camera','territoryColors','highlights','initialStateVisibility'])if(override?.[key]!==undefined)value[key]=copy(override[key]);else if(shared[key]!==undefined)value[key]=copy(shared[key]);
 if(value.camera===undefined)value.camera=deriveCamera(nl,scene,region,trace,issues,field);
 else if(has(nl,'ROUTE_FOLLOW')&&value.camera?.mode!=='ROUTE_FOLLOW')issues.push(issue('CONFLICT','NATURAL_CAMERA_MODE_CONFLICT',field+'.camera','Natural-language route following conflicts with the attached keyframe camera. Neither is silently ignored.',{requestedMode:'ROUTE_FOLLOW',attachedMode:value.camera?.mode}));
 if(value.camera?.mode==='KEYFRAMES'&&Array.isArray(value.camera.keyframes)){
  const keys=value.camera.keyframes,increase=keys.some((k,i)=>i>0&&k.zoom>keys[i-1].zoom),decrease=keys.some((k,i)=>i>0&&k.zoom<keys[i-1].zoom),motion=keys.some((k,i)=>i>0&&point(k.center)&&point(keys[i-1].center)&&k.center.some((v,j)=>v!==keys[i-1].center[j]));
  if(has(nl,'ZOOM_IN')&&!increase||has(nl,'ZOOM_OUT')&&!decrease)issues.push(issue('CONFLICT','NATURAL_ZOOM_PROFILE_CONFLICT',field+'.camera','The supplied keyframes do not implement the explicit zoom intent.',{zoomInRequested:has(nl,'ZOOM_IN'),zoomOutRequested:has(nl,'ZOOM_OUT'),zoomIncreasePresent:increase,zoomDecreasePresent:decrease}));
  if(has(nl,'CAMERA_MOVE')&&!motion)issues.push(issue('CONFLICT','NATURAL_CAMERA_MOTION_CONFLICT',field+'.camera','The text requests camera movement but supplied centers remain fixed.',{action:'Supply changing keyframe centers or a real route-follow profile'}));
 }
 if(value.camera?.mode==='ROUTE_FOLLOW'&&(has(nl,'ZOOM_IN')||has(nl,'ZOOM_OUT')))issues.push(issue('UNSUPPORTED','ROUTE_FOLLOW_DYNAMIC_ZOOM_NOT_CONNECTED',field+'.camera','The current route-follow profile has one constant zoom; text requesting dynamic zoom is not ignored.',{action:'Use explicit keyframes for zoom changes'}));
 if(has(nl,'TERRITORY_CHANGE')&&scene.event_type!=='WAR')issues.push(issue('NEEDS_INPUT','TERRITORY_DATA_REQUIRED',field,'Territory-change intent needs supplied area/front states; transport routes do not supply ownership.',{required:'Dated territory and front geometries'}));
 if(value.highlights===undefined&&has(nl,'EVENT_HIGHLIGHT'))issues.push(issue('NEEDS_INPUT','EXPLICIT_EVENT_LOCATION_REQUIRED',field+'.highlights','An event emphasis needs an explicit supplied location binding and timing.',{highlights:[{id:'event_1',locationId:'supplied_location_id',startFrame:0,endFrame:30}]}));
 if(value.highlights===undefined&&has(nl,'LOCATION_HIGHLIGHT')){
  const mentioned=scene.locations.filter(l=>nl.locations.some(x=>x.id===l.id)),locations=mentioned.length?mentioned:scene.locations;
  if(locations.length>16)issues.push(issue('UNSUPPORTED','HIGHLIGHT_CAPACITY',field+'.highlights','At most16 supplied locations may be highlighted per scene.',{maximumLocations:16}));
  else{
   const width=Math.max(2,Math.floor(scene.timing.total_frames/Math.max(1,locations.length)));
   value.highlights=locations.map((l,i)=>({id:'NL_HIGHLIGHT_'+l.id,locationId:l.id,startFrame:Math.min(i*width,scene.timing.total_frames-2),endFrame:Math.min((i+1)*width,scene.timing.total_frames)}));
   trace.push({field:field+'.highlights',origin:'NL_CITY_HIGHLIGHT_INTENT_AND_SUPPLIED_LOCATION_IDS',value:copy(value.highlights),worldFactCreated:false});
  }
 }
 return value;
}

function validateNativeContextBindings(facts,region,admission,field){
 const errors=[],contexts=[['native_context',facts?.native_context],['camera.native_context',facts?.camera?.native_context]].filter(([,value])=>value!==undefined),locations=Array.isArray(facts?.locations)?facts.locations:[],geometries=Array.isArray(facts?.geometries)?facts.geometries:[],locationIds=new Set(locations.map(l=>l?.id)),countryRefs=new Set([...locations.map(l=>l?.country_id),...geometries.map(g=>g?.id)].filter(text));
 if(contexts.length===2&&canonicalJSON(contexts[0][1])!==canonicalJSON(contexts[1][1]))errors.push(issue('CONFLICT','NATIVE_CONTEXT_PRECEDENCE_CONFLICT',field+'.native_context','Two supplied native contexts disagree; neither is silently discarded.',{action:'Supply one consistent context in the existing supported field'}));
 const admittedCountry=admission?.regionEvidence?.contextCountryId??(/^COUNTRY_/u.test(region.countryId??'')?region.countryId:undefined),explicitCountry=region.countryId!==undefined||region.countryName!==undefined||region.legacyProfileId!==undefined;
 for(const [key,context]of contexts){
  if(!object(context))continue; // Original native shape validator retains responsibility.
  const countries=[...(Array.isArray(context.country_ids)?context.country_ids:[]),...(text(context.primary_country_id)?[context.primary_country_id]:[]),...(Array.isArray(context.secondary_country_ids)?context.secondary_country_ids:[])];
  for(const countryId of [...new Set(countries)])if(!countryRefs.has(countryId))errors.push(issue('CONFLICT','NATIVE_CONTEXT_COUNTRY_BINDING_MISSING',field+'.'+key,'A declared native country has no supplied source geometry or location-country binding.',{countryId,providedCountryBindings:[...countryRefs],action:'Correct the supplied native context; no country geometry is fabricated'}));
  for(const id of Array.isArray(context.context_location_ids)?context.context_location_ids:[])if(!locationIds.has(id))errors.push(issue('CONFLICT','NATIVE_CONTEXT_LOCATION_BINDING_MISSING',field+'.'+key+'.context_location_ids','A native context location does not exist in the supplied Scene locations.',{locationId:id,availableLocationIds:[...locationIds]}));
  if(explicitCountry&&text(context.primary_country_id)&&admittedCountry&&context.primary_country_id!==admittedCountry)errors.push(issue('CONFLICT','NATIVE_CONTEXT_REGION_COUNTRY_CONFLICT',field+'.'+key+'.primary_country_id','The supplied primary context country differs from the explicitly admitted region country.',{supplied:context.primary_country_id,admitted:admittedCountry}));
  if(Array.isArray(context.country_ids))for(const id of [context.primary_country_id,...(Array.isArray(context.secondary_country_ids)?context.secondary_country_ids:[])].filter(text))if(!context.country_ids.includes(id))errors.push(issue('CONFLICT','NATIVE_CONTEXT_COUNTRY_LIST_CONFLICT',field+'.'+key,'Primary and secondary countries must agree with the supplied country list.',{countryId:id,countryIds:context.country_ids}));
 }
 return errors;
}

async function defaultQualifier(input){return(await import('./region_source.mjs')).qualifyRegion(input);}
function finalize(result){result.status=statusOf(result.issues);result.clarifications=result.issues.filter(x=>['NEEDS_INPUT','CONFLICT'].includes(x.status));return result;}
function errorIssue(error,field){const code=String(error.message??error);return issue(/UNKNOWN|UNSUPPORTED|NOT_CONNECTED/u.test(code)?'UNSUPPORTED':/REQUIRED/u.test(code)?'NEEDS_INPUT':'INVALID',code,field,'The connected existing contract rejected this input; no fallback was rendered.',{action:'Correct the referenced field using PRESENTATION_INPUT_CONTRACT.md'});}

/** Natural text + authoritative attached data. Region qualification is a real independent gate. */
export async function analyzePresentationPrompt(input,{evidenceRegistry=[],qualifyRegion=defaultQualifier,allowTenSecondStudioSample=false}={}){
 const result={schema:RESULT_SCHEMA,compilerVersion:VERSION,status:'INVALID',issues:[],clarifications:[],sceneResults:[],renderRequests:[],renderableSceneIds:[],blockedSceneIds:[],transitionPlan:[],
  unrestrictedLanguageUnderstanding:false,externalLLMUsed:false,paidExecutionAllowed:false,historicalRenderAllowed:false};
 let envelope;
 try{envelope=parsePrompt(input);}catch(error){result.issues.push(errorIssue(error,'$'));result.status=statusOf(result.issues);return finalize(result);}
 result.inputSHA256=hash(envelope);
 unknown(envelope,['schema','prompt','data','region','presentation'],'$',result.issues);
 if(envelope.schema!==SCHEMA)result.issues.push(issue('INVALID','PRESENTATION_PROMPT_SCHEMA_REQUIRED','$.schema','Select the opt-in natural-text and data attachment contract.',{schema:SCHEMA}));
 let nl;try{nl=extractNaturalLanguage(envelope.prompt,{data:envelope.data});}catch(error){result.issues.push(errorIssue(error,'$.prompt'));}
 if(!nl){result.status=statusOf(result.issues);return finalize(result);}
 result.naturalLanguage=nl;result.inputDerivations=[];
 for(const value of nl.intents)if(value.scope?.sceneIndices)result.inputDerivations.push({field:'$.prompt',origin:'BOUNDED_SCENE_CLAUSE_SCOPE',intent:value.type,sceneIndices:value.scope.sceneIndices,span:{start:value.start,end:value.end,text:value.text},scope:value.scope});
 for(const unsupported of nl.unsupported)result.issues.push(issue('UNSUPPORTED',unsupported.type,'$.prompt','This requested effect has no connected consumer in the new profile.',{unsupportedSpan:unsupported.text,action:'Remove the effect or provide a supported presentation intent'}));
 const data=completeData(envelope.data,nl,result.inputDerivations,result.issues);
 if(!data){result.status=statusOf(result.issues);result.clarifications=result.issues.filter(x=>x.status==='NEEDS_INPUT');return finalize(result);}
 result.simulationType=data.simulationType;result.normalizedDataSHA256=hash(data);result.totalFrames=data.durationSeconds*data.fps;
 unknown(envelope.region,['center','bbox','countryId','countryName','sourceId','crs','legacyProfileId'],'$.region',result.issues);
 if(!object(envelope.region)||!point(envelope.region.center)||!Array.isArray(envelope.region.bbox)||envelope.region.bbox.length!==4||!envelope.region.bbox.every(Number.isFinite))result.issues.push(issue('NEEDS_INPUT','EXPLICIT_REGION_REQUIRED','$.region','Supply the source-covered center and [west,south,east,north] map range; places are not geocoded or guessed.',{center:[0,0],bbox:[-5,-8,5,8],crs:'EPSG:4326',sourceId:'AUTO'}));
 unknown(envelope.presentation,['camera','territoryColors','highlights','initialStateVisibility','sceneOverrides','transitions'],'$.presentation',result.issues);
 const shared=envelope.presentation??{},ids=new Set(Array.isArray(data.scenes)?data.scenes.map(x=>x?.sceneId).filter(text):[]);
 unknown(shared.sceneOverrides,[...ids],'$.presentation.sceneOverrides',result.issues);
 validateExplicitSpans(nl,data,envelope.region,result.issues);
 const tenSecondStudioSample=allowTenSecondStudioSample===true&&data.durationSeconds===10&&data.fps===30&&result.totalFrames===300;
 if(Number.isSafeInteger(result.totalFrames)&&result.totalFrames>240&&!tenSecondStudioSample)result.issues.push(issue('UNSUPPORTED','BOUNDED_COMPOSITE_PREVIEW_LIMIT','$.data.durationSeconds','The free composite preview is limited to240frames; preserved long production code is unchanged.',{maximumFrames:240,maximumSecondsAt30fps:8}));
 const legacy=analyzePrompt(data,{evidenceRegistry});
 if(result.issues.length){
  // Input errors remain visible even when a natural-language request needs clarification.
  // In particular an ambiguous name cannot hide an invalid supplied coordinate.
  result.issues.push(...legacy.issues.filter(x=>x.code!=='SOURCE_REGION_NOT_AVAILABLE').map(mappedLegacy));
  result.status=statusOf(result.issues);result.clarifications=result.issues.filter(x=>x.status==='NEEDS_INPUT'||x.status==='CONFLICT');return finalize(result);
 }
 result.legacyValidationAudit={status:legacy.status,profile:'UNCHANGED_WORLD_ENGINE_DATA_PROMPT_V1',deferredIssues:legacy.issues.filter(x=>x.code==='SOURCE_REGION_NOT_AVAILABLE').map(copy),
  replacementGate:'ACTUAL_NEW_REGION_SOURCE_QUALIFICATION_REQUIRED',legacyProfileReportedAsPassed:legacy.status==='PASS'};
 const sharedErrors=legacy.sceneResults.length?[]:legacy.issues.filter(x=>x.code!=='SOURCE_REGION_NOT_AVAILABLE');
 if(sharedErrors.length){result.issues.push(...sharedErrors.map(mappedLegacy));result.status=statusOf(result.issues);return finalize(result);}
 const boundaryFrames=data.scenes.slice(1).map(row=>row.startFrame);
 let transitions=shared.transitions;
 if(transitions===undefined&&boundaryFrames.length&&has(nl,'SCENE_TRANSITION')){
  transitions=boundaryFrames.map(frame=>({type:'CUT',frame}));result.inputDerivations.push({field:'$.presentation.transitions',origin:'NL_TRANSITION_INTENT_AND_SUPPLIED_SCENE_BOUNDARIES',value:copy(transitions),worldFactCreated:false});
 }
 transitions??=[];
 if(!Array.isArray(transitions))result.issues.push(issue('INVALID','TRANSITION_ARRAY_REQUIRED','$.presentation.transitions','Supply an explicit array of supported scene transitions.',{transitions:boundaryFrames.map(frame=>({type:'CUT',frame}))}));
 else{
  for(const [i,t]of transitions.entries()){
   unknown(t,['type','frame'],`$.presentation.transitions[${i}]`,result.issues);
   if(!object(t)||t.type!=='CUT')result.issues.push(issue('UNSUPPORTED','ONLY_CUT_TRANSITION_CONNECTED',`$.presentation.transitions[${i}]`,'The connected sequence consumer supports actual cuts only.',{type:'CUT',frame:boundaryFrames[0]}));
  }
  if(canonicalJSON(transitions.map(t=>t?.frame))!==canonicalJSON(boundaryFrames))result.issues.push(issue('CONFLICT','CUT_BOUNDARY_MISMATCH','$.presentation.transitions','Cuts must match every supplied scene boundary exactly, in order; no interval is dropped.',{expectedFrames:boundaryFrames}));
 }
 result.transitionPlan=copy(transitions);
 if(result.issues.length){result.status=statusOf(result.issues);return finalize(result);}
 for(const [index,row]of data.scenes.entries()){
  const field=`$.data.scenes[${index}]`,legacyRow=legacy.sceneResults.find(x=>x.sceneId===row.sceneId),problems=(legacyRow?.issues??[]).filter(x=>x.code!=='SOURCE_REGION_NOT_AVAILABLE').map(mappedLegacy),trace=[],sceneNL=scopedNL(nl,index);
  problems.push(...validateNativeContextBindings(row.facts,envelope.region,null,field+'.facts'));
  const requestedLegacySource={...data.renderSettings,...row.renderSettings}.sourceRegionId;
  if(requestedLegacySource!==undefined&&envelope.region.legacyProfileId!==requestedLegacySource)problems.push(issue('CONFLICT','LEGACY_SOURCE_SELECTION_CONFLICT',row.renderSettings?.sourceRegionId!==undefined?field+'.renderSettings.sourceRegionId':'$.data.renderSettings.sourceRegionId','The old source selection is not silently ignored by the new regional profile. Explicitly bind its matching legacyProfileId or remove the old rendering selection from the new envelope.',{legacySourceRegionId:requestedLegacySource,regionLegacyProfileId:envelope.region.legacyProfileId??null,action:'Use the explicit new region or a matching preserved legacy profile'}));
  else if(requestedLegacySource!==undefined)trace.push({field:'$.region.legacyProfileId',origin:'EXPLICIT_MATCHED_LEGACY_SOURCE_SELECTION',value:requestedLegacySource,requiresActualSourceQualification:true});
  let scene,enginePlan,admission,presentation;
  if(!problems.length){
   try{
    admission=await qualifyRegion({region:copy(envelope.region),facts:copy(row.facts)});
    if(admission?.status!=='PASS'){
     const errors=Array.isArray(admission?.issues)?admission.issues:[];
     problems.push(...(errors.length?errors.map(x=>({...copy(x),field:x.field??'$.region'})):[issue('UNSUPPORTED','REGION_SOURCE_NOT_ADMITTED','$.region','The actual map source did not qualify this region.',{providerStatus:admission?.status??'UNAVAILABLE'})]));
    }
   }catch(error){problems.push(errorIssue(error,'$.region'));}
  }
  if(!problems.length)problems.push(...validateNativeContextBindings(row.facts,envelope.region,admission,field+'.facts'));
  if(!problems.length)try{
   const facts=copy(row.facts),frames=row.endFrame-row.startFrame;
   if(Array.isArray(facts.stages))facts.stages.sort((a,b)=>a.date.localeCompare(b.date));
   if(facts.scene_timing===undefined){facts.scene_timing=displayTiming(facts,frames,data.fps);trace.push({field:field+'.facts.scene_timing',origin:'EXACT_FRAME_BUDGET_DISPLAY_ALLOCATION',worldFactCreated:false,value:copy(facts.scene_timing)});}
   validateFactDataset(facts);scene=compileScenePlan({topic:data.topic,facts,output:{fps:data.fps,width:data.resolution.width,height:data.resolution.height}});validateScenePlan(scene);enginePlan=compileExistingEnginePlan(scene);
   if(scene.timing.total_frames!==frames)problems.push(issue('CONFLICT','SCENE_FRAME_BUDGET_MISMATCH',field,'Native Scene timing differs from its exact original frame interval.',{expectedFrames:frames,actualFrames:scene.timing.total_frames}));
   const local=localPresentation(shared,shared.sceneOverrides?.[row.sceneId],sceneNL,scene,envelope.region,trace,problems,'$.presentation.sceneOverrides.'+row.sceneId);
   if(!problems.length){presentation=validatePresentation(local,{scene,region:envelope.region});trace.push({field:'$.presentation.sceneOverrides.'+row.sceneId+'.initialStateVisibility',origin:local.initialStateVisibility===undefined?'PRESERVED_REVEAL_DEFAULT':'EXPLICIT_PUBLIC_AREA_OPERATION_MODE',value:presentation.initialStateVisibility,worldGeometryChanged:false,worldClockChanged:false});}
  }catch(error){problems.push(errorIssue(error,field));}
  const state={sceneId:row.sceneId,startFrame:row.startFrame,endFrame:row.endFrame,status:statusOf(problems),issues:problems,dependsOn:row.dependsOn??[]};
  result.sceneResults.push(state);
  if(!problems.length){
   const inputTrace=[{inputPath:field,scenePath:'$',sceneId:row.sceneId,inputDataSHA256:hash(row),sceneSHA256:hash(scene),authoritativeSource:'USER_ATTACHED_STRUCTURE'},
    {inputPath:'$.prompt',scenePath:'$.presentation',rawPromptSHA256:hash(envelope.prompt),boundedIntentExtraction:true,factsGenerated:false},
    {inputPath:'$.region',scenePath:'$.runtime.region',regionSHA256:hash(envelope.region),actualSourceQualification:copy(admission.regionEvidence??admission.evidence??admission)},
    {inputPath:'$.presentation',scenePath:'$.runtime.presentation',presentationSHA256:hash(presentation)},
    ...scene.geometries.map(g=>({inputPath:field+'.facts.geometries['+row.facts.geometries.findIndex(x=>x.id===g.id)+']',scenePath:'$.geometries['+scene.geometries.findIndex(x=>x.id===g.id)+']',geometryId:g.id,geometrySHA256:hash(g.geometry),sourceId:g.source_id})),...trace];
   result.renderRequests.push({sceneId:row.sceneId,startFrame:row.startFrame,endFrame:row.endFrame,scene,enginePlan,sceneSHA256:hash(scene),region:copy(envelope.region),presentation,
    regionEvidence:copy(admission.regionEvidence??admission.evidence??admission),regionGateSHA256:admission.regionGateSHA256??hash(admission),sourceGate:'ACTUAL_PROVIDER_QUALIFICATION_PASS_CAMERA_ENVELOPE_GATE_STILL_REQUIRED',inputTrace,
    sourceManifest:scene.source_notes.map(s=>({sourceId:s.id,sourceReference:s.source_reference,canonicalMetadataSHA256:hash(s),originalSHA256:s.original_sha256??s.sha256??null,originalBytesVerified:false})),
    presentationDerivations:trace,displayMetadataOnly:['subject.label','locations[].label','markers[].label','moving_objects[].profile']});
  }
 }
 let changed=true;
 while(changed){changed=false;for(const row of result.sceneResults)if(row.status==='PASS'&&row.dependsOn.some(id=>result.sceneResults.find(s=>s.sceneId===id)?.status!=='PASS')){row.issues.push(issue('NEEDS_INPUT','DEPENDENCY_BLOCKED','$.data.scenes.'+row.sceneId+'.dependsOn','A declared dependency remains blocked; unrelated scenes retain their original intervals.',{dependsOn:row.dependsOn}));row.status='NEEDS_INPUT';changed=true;}}
 result.renderableSceneIds=result.sceneResults.filter(x=>x.status==='PASS').map(x=>x.sceneId);result.blockedSceneIds=result.sceneResults.filter(x=>x.status!=='PASS').map(x=>x.sceneId);
 result.renderRequests=result.renderRequests.filter(x=>result.renderableSceneIds.includes(x.sceneId));
 result.issues=result.sceneResults.flatMap(x=>x.issues);result.status=statusOf(result.issues);result.clarifications=result.issues.filter(x=>['NEEDS_INPUT','CONFLICT'].includes(x.status));
 result.timelinePreserved=true;result.partialRenderRequiresExplicitSceneSelection=result.blockedSceneIds.length>0;
 return finalize(result);
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 try{
  const args={};for(let i=2;i<process.argv.length;i+=2){if(!['--input','--output','--evidence-registry'].includes(process.argv[i])||!process.argv[i+1]||args[process.argv[i]])throw Error('PRESENTATION_CLI_ARGUMENTS_INVALID');args[process.argv[i]]=process.argv[i+1];}
  if(!args['--input'])throw Error('PRESENTATION_CLI_INPUT_REQUIRED');
  const result=await analyzePresentationPrompt(fs.readFileSync(args['--input'],'utf8'),{evidenceRegistry:args['--evidence-registry']?JSON.parse(fs.readFileSync(args['--evidence-registry'],'utf8')):[]});
  const raw=JSON.stringify(result,null,2)+'\n';if(args['--output'])fs.writeFileSync(args['--output'],raw,{flag:'wx',mode:0o600});else process.stdout.write(raw);
  process.stderr.write(JSON.stringify({status:result.status,renderableScenes:result.renderableSceneIds.length,blockedScenes:result.blockedSceneIds.length})+'\n');
 }catch(error){process.stderr.write(JSON.stringify({status:'INVALID',error:String(error.message)})+'\n');process.exitCode=2;}
}
