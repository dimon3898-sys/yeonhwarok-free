/** Author display timing only. Never calls the geometry compiler or a renderer. */
import fs from 'node:fs/promises';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {geographicCameraFrame,mercatorY,inverseMercatorY,selectGeographicTerrain} from '../../web/map_infographic_v1/geographic_camera_v1.mjs';
import {canonicalJSON} from '../../recovery/universal-presentation-v2/region_source.mjs';
import {compileExistingEnginePlan} from '../../web/map_infographic_v1/planner_engine_adapter_v1.mjs';
const base=new URL('./',import.meta.url),copy=structuredClone,sha=x=>createHash('sha256').update(x).digest('hex');
const write=(name,value)=>fs.writeFile(new URL(name,base),typeof value==='string'?value:JSON.stringify(value,null,2)+'\n');
const oldRaw=await fs.readFile(new URL('../continuous-territory-20261114/RUNTIME_REQUEST.json',base));
assert.equal(sha(oldRaw),'adf13d8c7c9ed0ee06bf7c2ef867d4e55d2ce405c33203adf76f77463580c95e');
const old=JSON.parse(oldRaw),request=copy(old),s=request.segments[0],p=s.presentation,scene=s.scene;
const originalContinuous=canonicalJSON(p.territoryChanges.items[0].continuous);
const phaseRows=[
 ['S1',0,30,'R0 0:29 + omitted R1 29:30','초기 영역과 제목 제시','INITIAL','LOCK'],
 ['S2',30,175,'R2 30:175','동아시아 자연지리 맥락을 보이는 완만한 축소','INITIAL','CONTINUOUS'],
 ['S3',175,283,'R3 175:283','변화 지역 접근과 단 한 번의 출처 상태 변화','INITIAL_TO_FINAL','CONTINUOUS'],
 ['S4',283,330,'R4 283:330','완료된 상태를 읽는 구간','FINAL','LOCK'],
 ['S5',330,452,'R5 330:452','소스 해상도 안에서 제한된 추가 접근','FINAL','CONTINUOUS'],
 ['S6',452,600,'R6 452:575 + designed 25 frames','결과를 명확히 읽는 최종 유지','FINAL','LOCK'],
];
const pose=(center,scale)=>({center,scale,rollDegrees:0});
const keys=[
 {frame:0,pose:pose([109.42347717285156,41.342550236362946],22)},
 {frame:29,pose:pose([109.42347717285156,41.342550236362946],22)},
 {frame:174,pose:pose([109.42347717285156,41.342550236362946],15.19696127374627)},
 {frame:282,pose:pose([108.29511260986328,42.2],23)},
 {frame:329,pose:pose([108.29511260986328,42.2],23)},
 {frame:451,pose:pose([108.29511260986328,42.5313915615388],24.94963263616363)},
 {frame:599,pose:pose([108.29511260986328,42.5313915615388],24.94963263616363)},
];
const smooth=t=>t*t*t*(10+t*(-15+6*t));
const frames=Array.from({length:600},(_,f)=>{
 const b=keys.find(k=>k.frame>=f),a=keys[Math.max(0,keys.indexOf(b)-1)];
 if(a===b||JSON.stringify(a.pose)===JSON.stringify(b.pose))return copy(b.pose);
 const t=smooth((f-a.frame)/(b.frame-a.frame)),mix=(x,y)=>x+(y-x)*t;
 return pose([mix(a.pose.center[0],b.pose.center[0]),inverseMercatorY(mix(mercatorY(a.pose.center[1]),mercatorY(b.pose.center[1])))],Math.exp(mix(Math.log(a.pose.scale),Math.log(b.pose.scale))));
});
request.totalFrames=600;request.durationSeconds=20;s.endFrame=600;
scene.timing={...scene.timing,total_frames:600,duration_seconds:20,initial_reveal_frames:177,state_transition_frames:275,action_frames:452,final_hold_frames:148};
scene.time_steps[0].transition_frames=177;scene.time_steps[1].start_frame=177;scene.time_steps[1].transition_frames=275;
scene.beats=[['EVENT_ACTION',0,177],['STATE_CHANGE',177,452],['HOLD',452,600]].map(([type,a,b],i)=>({id:'BEAT_'+String(i+1).padStart(2,'0'),type,start_frame:a,end_frame:b,duration_frames:b-a,geometry_refs:copy(scene.camera_intent.target_geometry_refs),...(type==='HOLD'?{camera_intent:'LOCK'}:{})}));
p.camera={mode:'GEOGRAPHIC_TRACK',projection:'GEOGRAPHIC_MERCATOR_V1',frames};
p.territoryChanges.items[0].startFrame=177;p.territoryChanges.items[0].endFrame=283;
p.territoryChanges.config.visualProfile='FRONTIER_LIGHT_V1';
p.mapStyle={...p.mapStyle,sourceReliefDetail:'SOURCE_RELIEF_V1'};
p.territoryColors=Object.fromEntries(scene.time_steps.map(x=>[x.id,[1,.75,.12,.28]]));
p.labels.items.forEach(x=>{x.endFrame=600;if(x.id==='HISTORY_YEAR_0')x.endFrame=230;if(x.id==='HISTORY_YEAR_1')x.startFrame=230;});
// Keep provenance of source facts, replace the OLD display derivations explicitly.
const sourceTrace=s.inputTrace.filter(x=>x.origin!=='COMMON_HISTORY_POLICY'&&x.origin!=='EXACT_FRAME_BUDGET_DISPLAY_ALLOCATION'&&x.inputPath!=='$.presentation');
const authored={origin:'EXPLICIT_AUTHORED_HISTORY_DISPLAY_V1',worldFactCreated:false,sourceGeometryChanged:false,sourceDatesChanged:false,
 timing:copy(scene.timing),referenceSHA256:'853ce5be22dc95c95e0c4b3eddbd603930e499bc88ee40cb4e59b50aad1187bc',
 designFiles:['SHOT_PLAN_600F.csv','CAMERA_PLAN_600F.json','TERRITORY_PLAN_600F.json','LABEL_PLAN_600F.json'],continuousSHA256:sha(originalContinuous)};
s.inputTrace=[...sourceTrace,authored];s.presentationDerivations=[authored];
s.automaticDirection={profile:'HISTORICAL_CONTINUOUS_V1',mode:'EXPLICIT_AUTHORED_RUNTIME',cameraKeys:keys,
 timing:{profile:'HISTORICAL_CONTINUOUS_V1',choreography:[{fromStateId:'SNAPSHOT_1206',toStateId:'SNAPSHOT_1210',cycleStart:0,startFrame:177,endFrame:283,readEnd:600,cameraStart:175,cameraEnd:282,holdFrames:148,sourcePeriods:scene.time_steps.map(x=>x.date)}]},
 sourceGeometryChanged:false,sourceDatesChanged:false,geometryRecompiled:false};
s.enginePlan=compileExistingEnginePlan(scene);s.sceneSHA256=sha(canonicalJSON(scene));
assert.equal(canonicalJSON(p.territoryChanges.items[0].continuous),originalContinuous);
const shapeHashes=p.territoryChanges.items[0].continuous.frames.map((x,i)=>({index:i,geometrySHA256:sha(canonicalJSON(x.geometry)),boundaryBandSHA256:sha(canonicalJSON(x.boundaryBand))}));
const cameraPlan={schema:'WORLD_ENGINE_AUTHORED_CAMERA_600F_V1',valueType:'DESIGNED_NOT_MEASURED',totalFrames:600,fps:30,
 frameConvention:'ZERO_BASED_HALF_OPEN',runtime:p.camera,keyframes:keys,
 movementIntervals:[[30,175],[175,283],[330,452]],velocityPolicy:'QUINTIC_SMOOTHERSTEP_IN_MERCATOR_CENTER_AND_LOG_SCALE; zero velocity and acceleration at each authored key',
 tracking:{mode:'SOURCE_BOUND_CHANGED_REGION_CONTEXT',changedBounds:old.segments[0].automaticDirection.changes[0].bounds,noInventedRoute:true,keepEveryChangedVertexVisible:true},
 safeAreaPixels:[72,320,1008,1320],terrainSourceLevels:copy(s.regionEvidence.sourceLevels),
 detailLimit:{closestApprovedBounds:copy(s.regionEvidence.fittedBounds),maximumDesignedScale:24.94963263616363,screenPixelsPerNativePixelMaximum:1},
 reference:phaseRows.map(([id,start,end,ref])=>({id,startFrame:start,endFrameExclusive:end,referenceRange:ref})),
 limitations:['Original true camera/projection/velocity UNKNOWN. Screen-space relative zoom is comparable only as an estimate.',
 '13.073x approach and unreliable 48.885x deep zoom cannot be reproduced with current source density and the full Mongol extent.',
 'Final 148-frame exact hold is a deliberate adaptation of the reference slow close reading, not a measured original lock.']};
const territoryPlan={schema:'WORLD_ENGINE_AUTHORED_TERRITORY_600F_V1',profile:'HISTORICAL_CONTINUOUS_V1',
 initialState:{id:'SNAPSHOT_1206',period:scene.time_steps[0].date},finalState:{id:'SNAPSHOT_1210',period:scene.time_steps[1].date},
 intermediateSource:'../continuous-territory-20261114/RUNTIME_REQUEST.json#/segments/0/presentation/territoryChanges/items/0/continuous',
 sourceRequestSHA256:sha(oldRaw),continuousSHA256:sha(originalContinuous),shapeCount:106,shapeHashes,
 interpolationFrames:[177,283],interpolationSeconds:[5.9,283/30],indexRule:'index = clamp(frame - 177, 0, 105); each supplied shape used once, no regenerated or duplicated intermediate geometry',
 semantics:'GEOMETRIC_VISUAL_INTERPOLATION_NOT_HISTORICAL_ROUTE',removedAreasPreserved:true,
 baseColor:[1,.75,.12,.28],newAreaColorPolicy:'EXISTING_FRONTIER_LIGHT_V1_VISIBLE_ADDED',removedAreaColorPolicy:'EXISTING_VISIBLE_REMOVED_UNTIL_REMOVED',
 glow:{profile:'FRONTIER_LIGHT_V1',activeFrames:[177,283],settleFrames:[283,301],staticBoundaryGlow:'NOT_IMPLEMENTED_NO_SOURCED_LINE'},
 cameraSync:{moveFrames:[175,283],overlapFrames:106,resultReadFrames:[[283,330],[452,600]]}};
const labelPlan={schema:'WORLD_ENGINE_AUTHORED_LABEL_600F_V1',layer:'presentation_label_layer',items:copy(p.labels.items),
 placement:{TITLE:{center:[540,192]},TIMELINE:{center:[540,1440]},DISCLOSURE:{center:[540,1555.2]}},
 timelineSwitchFrame:230,timelinePolicy:'Existing source-period label midpoint policy; the disclosure makes interpolation explicit.',
 additionalPlaceLabels:[],extraFactualClaims:false,verification:'Actual glyph metrics/collision verification pending new-scope preflight'};
await write('CAMERA_PLAN_600F.json',cameraPlan);await write('TERRITORY_PLAN_600F.json',territoryPlan);await write('LABEL_PLAN_600F.json',labelPlan);
const csv=x=>'"'+String(x).replaceAll('"','""')+'"';
const header=['shot_id','start_frame','end_frame_exclusive','duration_frames','duration_seconds','reference_interval','purpose','map_center_start_end','camera_framing','territory_state','emphasis','labels','transition','value_type'];
await write('SHOT_PLAN_600F.csv',[header,...phaseRows.map(([id,a,b,ref,purpose,state,transition])=>[id,a,b,b-a,(b-a)/30,ref,purpose,JSON.stringify([frames[a].center,frames[b-1].center]),JSON.stringify({startScale:frames[a].scale,endScale:frames[b-1].scale,roll:0}),state,id==='S3'?'FRONTIER_LIGHT_V1; frames 177:283':id==='S4'?'added color settles over 18 frames':'existing colors; no invented static glow',id==='S3'?'몽골제국; 1206-1209 to 1210-1215 at 230; interpolation disclosure':'몽골제국; '+(a<230?'1206-1209':'1210-1215')+'; interpolation disclosure',transition,'DESIGNED_TIMING; reference interval measured/annotated'])].map(row=>row.map(csv).join(',')).join('\n')+'\n');
// This is explicitly a runtime design, NOT yet a Studio execution submission.
request.sourceInputSHA256=sha(canonicalJSON({scene,authored,presentation:p}));
await write('AUTHORED_RUNTIME_REQUEST.json',request);
await write('MAP_PLAN.md',`# 몽골제국 20초 지도 설계\n\nNASA BMNG 기존 지형과 native renderer만 사용한다. 원자료 EPSG:4326, 화면 GEOGRAPHIC_MERCATOR_V1. BMNG 최고 원본 21600×10800, 1각분이며 현재 승인된 Eurasia levels는 6600×6800(0.025°) 및 6000×7500(1/60°)다. 정확한 범위·SHA는 CAMERA_PLAN_600F.json의 terrainSourceLevels에 있다.\n\nSOURCE_RELIEF_V1은 실제 지형 원본의 명암을 처리하며 고도·건물·파도를 생성하지 않는다. REFERENCE_FOCUS_V2, nativeBoundaries=false를 유지한다. 현대 국경을 역사 경계로 노출하지 않는다. 영역 기본 RGBA=[1,.75,.12,.28]; 추가·축소 색과 이동 경계는 기존 FRONTIER_LIGHT_V1을 사용한다. 채색 아래 지형 질감을 보존한다.\n\n모든 600 pose에서 실제 source coverage 1px gutter, screen/native density≤1, 승인된 closestBounds를 검사한다. 최대 scale=24.94963263616363px/Mercator degree. 원본 레퍼런스의 건물 수준 근접 디테일과 13배/약49배 확대는 이 자료로 재현 불가다. 이번에는 전체 변화영역을 유지하는 광역/지역 구도를 사용한다. 소스 한계를 감추기 위한 업스케일·가짜 지형은 없다.\n`);
await write('PACING_PLAN.md',`# 600프레임 시간 감독\n\n0 기반 [시작,끝), 30fps. 원본 분석은 재실행하지 않았다. R7 575:635는 편집기 아웃트로라 제외한다.\n\n|단계|기존 원본|새 설계|차이|\n|---|---:|---:|---|\n|도입|29f + 1f 화면 교체|30f / 1초|화면 교체를 도입에 흡수|\n|광역 이동|145f|145f / 4.833초|시간 유지, 지리·이동량은 몽골 source에 맞춤|\n|접근|108f|108f / 3.6초|시간 유지|\n|읽기|47f|47f / 1.567초|미세 움직임 대신 정지|\n|추가 접근|122f|122f / 4.067초|시간 유지, 확대량 제한|\n|최종 결과|123f|148f / 4.933초|20초 맞춤 +25f, 정확한 hold로 설계|\n\n카메라 주요 이동 합계 375f/12.5초로 기존 구간 분류를 유지한다. 영토 변화 177:283의 106f/3.533초는 새 역사 상태 연결을 위한 **설계값**이다. 원본 205:230의 25f 청록 표시를 정복 속도로 해석하지 않는다. 106개 기존 도형은 원래 배열 그대로 한 번씩 재생하며 역사 관측 시점이나 진군 순서를 뜻하지 않는다.\n\n최종 상태는 283부터 읽을 수 있다. 283:330은 47f 읽기, 330:452는 122f 제한 접근, 452:600은 148f 결과 유지다. 발광은 변화 구간에서만 실제 boundary band를 따른다. 283:301의 18f에는 기존 added/removed 색 안정화만 적용한다. 출처 없는 정적 85m 발광선은 만들지 않는다.\n\n상대 확대: 새 광역 ${frames[174].scale/frames[29].scale}, 새 접근 ${frames[282].scale/frames[174].scale}, 새 추가 접근 ${frames[451].scale/frames[329].scale}. 원본 추정은 각각 0.2103,13.0734,48.8851이며 마지막 값은 추적 결손으로 부정확하다. 이동 시간은 보존하지만 확대 강도는 source gate 때문에 훨씬 작다. 원본 실제 camera 좌표·3D 속도는 UNKNOWN이며 화면 픽셀 속도를 세계좌표 속도와 동일시하지 않는다.\n\nC2 smootherstep을 투영 중심과 log scale에 적용하여 각 전환점의 속도·가속도를 0으로 연결한다. 카메라를 자동 프로필로 다시 생성하지 않고 명시 runtime 입력으로 전달하는 A안을 사용한다. GPU 전달과 glyph 실측은 후속 신규 계약 검사 대상이다.\n`);
// This checks only NEW camera samples. It is not a rerun of old source evidence.
const samples=frames.map((pose,frame)=>({frame,selection:selectGeographicTerrain(s.regionEvidence.sourceLevels,pose),bounds:geographicCameraFrame(pose).flatBounds}));
await write('DESIGN_SOURCE_DENSITY.json',{scope:'NEW_600_CAMERA_POSES_ONLY',frames:600,maximumScreenPixelsPerSourcePixel:Math.max(...samples.flatMap(x=>x.selection.density)),minimumGutterPixels:Math.min(...samples.map(x=>x.selection.gutter)),oldPassReruns:0,renderedFrames:0});
console.log(JSON.stringify({status:'DESIGN_WRITTEN_NOT_GPU_ADMITTED',totalFrames:600,shots:6,intermediateShapes:106,continuousSHA256:sha(originalContinuous)}));
