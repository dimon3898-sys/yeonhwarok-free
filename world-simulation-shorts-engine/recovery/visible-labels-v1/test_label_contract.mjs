/** New visible-label contracts only. No previous PASS suite is imported. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {validateLabelSpec,validateLabelText} from '../universal-presentation-v2/presentation_labels.mjs';
import {validatePresentation} from '../universal-presentation-v2/presentation_plan.mjs';
import {analyzePresentationPrompt} from '../universal-presentation-v2/presentation_prompt.mjs';

const scene={timing:{fps:30,total_frames:180},event_type:'WAR',locations:[{id:'source-point',anchor:[17.08,-22.57]},{id:'other-point',anchor:[17.5,-23]}],routes:[],time_steps:[]};
const highlights=[{id:'provided-event',locationId:'source-point',startFrame:20,endFrame:120}];
const country={id:'region-name',role:'COUNTRY',text:'합성 지역',locationId:'source-point',startFrame:0,endFrame:180};
const event={id:'event-name',role:'EVENT',text:'영역 확장',locationId:'source-point',eventId:'provided-event',startFrame:20,endFrame:120};
const numeric={id:'event-value',role:'NUMERIC',text:'120명',locationId:'source-point',eventId:'provided-event',startFrame:20,endFrame:120};
const spec=()=>({enabled:true,items:structuredClone([country,event,numeric])});
const validated=value=>validateLabelSpec(value,{scene,highlights});
const reject=(edit,pattern)=>{const value=spec();edit(value);assert.throws(()=>validated(value),pattern);};

test('new-label01 explicit three roles normalize only supplied anchors and defaults',()=>{
 const value=validated(spec());
 assert.deepEqual(value.items.map(item=>item.role),['COUNTRY','EVENT','NUMERIC']);
 assert.ok(value.items.every(item=>JSON.stringify(item.anchor)==='[17.08,-22.57]'));
 assert.deepEqual(value.items.map(item=>item.priority),[30,100,80]);
 assert.deepEqual(validated(value),value);
});
test('new-label02 geographic anchor cannot override a supplied location',()=>{
 reject(value=>value.items[0].anchor=[0,0],/ANCHOR_BINDING_CHANGED/);
 reject(value=>value.items[0].locationId='missing',/LOCATION_BINDING_REQUIRED/);
 const duplicate={...scene,locations:[...scene.locations,scene.locations[0]]};
 assert.throws(()=>validateLabelSpec(spec(),{scene:duplicate,highlights}),/LOCATION_BINDING_REQUIRED/);
});
test('new-label03 event and numeric text retain event-location-time association',()=>{
 for(const edit of [item=>delete item.eventId,item=>item.eventId='missing',item=>item.locationId='other-point',item=>item.startFrame=19,item=>item.endFrame=121]){
  reject(value=>edit(value.items[1]),/LABEL_EVENT/);
 }
 reject(value=>value.items[2].eventId='missing',/LABEL_EVENT/);
 reject(value=>value.items[0].eventId='provided-event',/COUNTRY_LABEL_EVENT_FORBIDDEN/);
});
test('new-label04 short NFC Korean text is bounded and unsafe display controls fail',()=>{
 for(const text of ['<script>','이름\n다음','이름\u202e','e\u0301','가'.repeat(25),' '+event.text]){
  reject(value=>value.items[1].text=text,/LABEL_TEXT/);
 }
 assert.equal(validated(spec()).items[1].text,'영역 확장');
});
test('new-label05 numeric values are supplied and roles do not infer facts',()=>{
 reject(value=>value.items[2].text='관측값',/NUMERIC_LABEL_VALUE_REQUIRED/);
 reject(value=>value.items[1].role='BRAND',/LABEL_ROLE_INVALID/);
 assert.equal(validated(spec()).items[2].text,numeric.text);
});
test('new-label06 bounded item count and unique label IDs prevent uncontrolled work',()=>{
 reject(value=>value.items.push({...value.items[0]}),/LABEL_ID_INVALID/);
 reject(value=>value.items=Array.from({length:17},(_,index)=>({...country,id:'label-'+index})),/LABEL_CAPACITY/);
 assert.equal(validated({enabled:true,items:Array.from({length:16},(_,index)=>({...country,id:'label-'+index}))}).items.length,16);
});
test('new-label07 reveal hold and exit remain within exact scene frames',()=>{
 reject(value=>value.items[0].startFrame=-1,/LABEL_TIMING_INVALID/);
 reject(value=>value.items[0].endFrame=181,/LABEL_TIMING_INVALID/);
 reject(value=>value.items[1].revealFrames=0,/REVEAL_HOLD_EXIT_INVALID/);
 reject(value=>{value.items[1].endFrame=24;value.items[1].revealFrames=2;value.items[1].exitFrames=2;},/REVEAL_HOLD_EXIT_INVALID/);
 assert.throws(()=>validateLabelSpec(spec(),{scene:{...scene,timing:{fps:60,total_frames:180}},highlights}),/SCENE_TIMING_REQUIRED/);
});
test('new-label08 priorities and accepted fields are closed and sources stay immutable',()=>{
 reject(value=>value.items[0].priority=101,/PRIORITY_INVALID/);
 reject(value=>value.items[0].priority=1.5,/PRIORITY_INVALID/);
 reject(value=>value.items[0].fontURL='https://invalid.example/font',/UNKNOWN_FIELD/);
 reject(value=>value.items[0].screenPosition=[12,12],/UNKNOWN_FIELD/);
 const value=spec(),before=JSON.stringify({scene,value});validated(value);
 assert.equal(JSON.stringify({scene,value}),before);
});
test('new-label09 absent labels preserve a new six-second default presentation byte contract',()=>{
 const input={camera:{mode:'KEYFRAMES',keyframes:[{frame:0,center:[17,-23],zoom:.8},{frame:179,center:[17,-23],zoom:1}]}};
 const result=validatePresentation(input,{scene});
 assert.equal(JSON.stringify(result),JSON.stringify({...input,initialStateVisibility:'REVEAL',highlights:[],transitions:[]}));
 assert.ok(!('labels' in result));
 assert.throws(()=>validatePresentation({...input,labels:{enabled:false,items:[]}},{scene}),/EXPLICIT_OPT_IN_REQUIRED/);
});

const admission=async()=>({status:'PASS',regionEvidence:{contextCountryId:'COUNTRY_NAM',sourceId:'REUSED_SOURCE_TEST_BOUNDARY'},regionGateSHA256:'b'.repeat(64)});
async function inputWithLabels(){
 // Existing supplied input data is a fixture, not an existing PASS rerun:
 // only the new label controls and new label-language intent are being tested.
 const input=JSON.parse(await fs.readFile(new URL('../studio-ten-second-v1/GENERIC_CAMERA_TERRITORY_10S.json',import.meta.url),'utf8'));
 input.prompt+=' 라벨을 표시해줘.';
 const make=(eventId,start,end,text,value)=>({enabled:true,items:[{...country,locationId:'WINDHOEK',endFrame:150},{...event,locationId:'WINDHOEK',eventId,startFrame:start,endFrame:end,text},{...numeric,locationId:'WINDHOEK',eventId,startFrame:start,endFrame:end,text:value}]});
 input.presentation.labels=make('event-a-focus',30,60,'합성 사건 A','120명');
 input.presentation.sceneOverrides['synthetic-event-b'].labels=make('event-b-focus',60,90,'합성 사건 B','80명');
 return input;
}
const compile=input=>analyzePresentationPrompt(input,{qualifyRegion:admission,allowTenSecondStudioSample:true});
test('new-label10 actual V2 compiler consumes explicit visible labels for both supplied events',async()=>{
 const result=await compile(await inputWithLabels());
 assert.equal(result.status,'PASS',JSON.stringify(result.issues));
 assert.equal(result.totalFrames,300);assert.equal(result.renderRequests.length,2);
 assert.ok(result.renderRequests.every(row=>row.presentation.labels.items.length===3));
 assert.ok(result.renderRequests.every(row=>row.presentation.labels.items.every(item=>JSON.stringify(item.anchor)===JSON.stringify(row.scene.locations.find(location=>location.id===item.locationId).anchor))));
 assert.ok(result.inputDerivations.some(row=>row.origin==='EXPLICIT_LABEL_CONSUMER_WITH_SUPPLIED_LOCATION_EVENT_AND_FRAME_BINDINGS'));
});
test('new-label11 missing or misbound label controls never silently admit visible-label intent',async()=>{
 const missing=await inputWithLabels();delete missing.presentation.labels;delete missing.presentation.sceneOverrides['synthetic-event-b'].labels;
 const blocked=await compile(missing);assert.notEqual(blocked.status,'PASS');assert.ok(blocked.issues.some(row=>row.code==='UNSUPPORTED_VISIBLE_LABELS'));
 const wrong=await inputWithLabels();wrong.presentation.sceneOverrides['synthetic-event-b'].labels.items[1].eventId='event-a-focus';
 const rejected=await compile(wrong);assert.notEqual(rejected.status,'PASS');assert.ok(rejected.issues.some(row=>row.code==='PRESENTATION_LABEL_EVENT_LOCATION_OR_TIMING_MISMATCH'));
 const partial=await inputWithLabels();delete partial.presentation.sceneOverrides['synthetic-event-b'].labels;delete partial.presentation.labels;
 partial.presentation.sceneOverrides['synthetic-event-a']={labels:(await inputWithLabels()).presentation.labels};
 const absentScene=await compile(partial);assert.notEqual(absentScene.status,'PASS');
});
test('new-label12 unsupported font glyphs fail before layout instead of falling back',()=>{
 for(const text of ['사건🚀','区域','Событие','ㅅ']){
  assert.throws(()=>validateLabelText(text),/PRESENTATION_LABEL_FONT_GLYPH_UNSUPPORTED/);
  reject(value=>value.items[1].text=text,/PRESENTATION_LABEL_FONT_GLYPH_UNSUPPORTED/);
 }
 assert.equal(validateLabelText('합성 지역 A: 120명 (25%)'),'합성 지역 A: 120명 (25%)');
});
