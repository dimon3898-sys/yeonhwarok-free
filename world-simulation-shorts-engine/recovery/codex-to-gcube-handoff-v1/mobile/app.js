'use strict';
const $=id=>document.getElementById(id);
const key='world-engine-nvidia-six-second-job-v1';
const savedJob=localStorage.getItem(key);
const state={csrf:null,busy:false,submission:null,job:/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(savedJob||'')?savedJob:null,timer:null,startKey:null,expires:null,requestedDuration:6};
const terminal=new Set(['complete','completed','failed','blocked','interrupted','cancelled']);
function fail(code){throw new Error(code);}
const up2FieldParts=new Set(`data prompt region presentation schema simulationType topic
subject label durationSeconds fps resolution width height scenes sceneId startFrame endFrame
facts dependsOn version event_type metadata output timing locations geometries routes markers
moving_objects source_notes id coordinates geometry source_id source_reference validity
start end camera mode keyframes frame center zoom routeId followStrength territoryColors
highlights transitions initialStateVisibility labels sceneOverrides countryCodes bounds
legacyProfileId native_context scale preferred scene_timing date startDate endDate
context_location_ids primary_country_id renderSettings sourceRegionId`.split(/\s+/));
function safeUp2Details(error){
 const metadata=error?.diagnostic,fields=error?.fields;
 if(error?.code!=='UP2_COMPLETE_TIMELINE_DATA_REQUIRED'||metadata?.schema!=='WORLD_ENGINE_UP2_DIAGNOSTIC_V1'||metadata?.sceneIdEncoding!=='ZERO_BASED_INPUT_SCENE_INDEX'||metadata?.limit!==16||!Array.isArray(fields?.issues)||!Array.isArray(fields?.blockedSceneIds))return null;
 const safeField=value=>typeof value==='string'&&value.length<=192&&/^\$(?:\.[A-Za-z_]+|\[[0-9]{1,4}\])*$/.test(value)&&[...value.matchAll(/\.([A-Za-z_]+)/g)].every(match=>up2FieldParts.has(match[1]))?value:'REDACTED_FIELD';
 return{issues:fields.issues.slice(0,16).map(row=>({code:typeof row?.code==='string'&&/^[A-Z][A-Z0-9_]{1,159}$/.test(row.code)?row.code:'UNLISTED_CODE',field:safeField(row?.field)})),blockedSceneIds:fields.blockedSceneIds.slice(0,16).map(value=>typeof value==='string'&&/^scene\[(?:[0-9]|[1-5][0-9]|6[0-3])\]$/.test(value)?value:'REDACTED_SCENE_ID')};
}
function clearError(){ $('error').hidden=true;$('error-text').textContent='';$('error-details')?.remove(); }
function showError(error){
 $('error-details')?.remove();$('error').hidden=false;
 const code=/^[A-Z][A-Z0-9_]{0,119}$/.test(error?.message||'')?error.message:'REQUEST_FAILED';
 $('error-text').textContent=`작업을 진행하지 못했습니다. 오류 코드: ${code}`;
 const details=code==='UP2_COMPLETE_TIMELINE_DATA_REQUIRED'?error.up2Details:null;
 if(!details)return;
 const target=document.createElement('div');target.id='error-details';
 const note=document.createElement('p');note.textContent='오류 상세 · 각 목록 최대 16개. 허용된 정보만 표시하며, 가려진 값은 REDACTED 또는 UNLISTED로 표시합니다. 필드의 [0]은 입력의 첫 번째 항목입니다.';target.append(note);
 const list=document.createElement('ul');
 for(const issue of details.issues){const row=document.createElement('li');row.textContent=`${issue.code} · 필드: ${issue.field}`;list.append(row);}
 if(!details.issues.length){const row=document.createElement('li');row.textContent='전달된 하위 오류 항목이 없습니다.';list.append(row);}
 target.append(list);
 const scenes=document.createElement('p');scenes.textContent='차단 장면: '+(details.blockedSceneIds.map(value=>value==='REDACTED_SCENE_ID'?'식별자 가림 (REDACTED_SCENE_ID)':`입력 장면 ${Number(value.slice(6,-1))+1} (${value})`).join(', ')||'전달된 항목 없음');target.append(scenes);$('error').append(target);
}
async function request(url,body){let response;try{response=await fetch(url,{method:body===undefined?'GET':'POST',credentials:'same-origin',headers:body===undefined?{}:{'Content-Type':'application/json','X-Studio-CSRF':state.csrf||''},body:body===undefined?undefined:JSON.stringify(body)});}catch{fail('NETWORK_FAILED');}let data;try{data=await response.json();}catch{fail('INVALID_SERVER_RESPONSE');}if(response.status===401){location.assign('/login');fail('AUTH_REQUIRED');}if(!response.ok){const error=new Error(data.error?.code||'REQUEST_FAILED');error.up2Details=safeUp2Details(data.error);throw error;}return data;}
function clearSubmission(){clearError();state.submission=null;state.startKey=null;state.expires=null;state.requestedDuration=6;$('consent').checked=false;$('start-section').hidden=true;$('start').disabled=true;drawDuration({});}
function updateButtons(){for(const id of ['load-example','input-file','prompt','preflight','refresh','logout'])$(id).disabled=state.busy;$('start').disabled=state.busy||!state.submission||!$('consent').checked;}
async function busy(action){if(state.busy)return;state.busy=true;clearError();updateButtons();try{await action();}catch(error){showError(error);}finally{state.busy=false;updateButtons();}}
function body(){const text=$('prompt').value.trim();if(!text||new TextEncoder().encode(text).length>4*1024*1024)fail('INPUT_SIZE_INVALID');let prompt;try{prompt=JSON.parse(text);}catch{fail('INPUT_JSON_INVALID');}if(!prompt||typeof prompt!=='object'||Array.isArray(prompt))fail('INPUT_JSON_OBJECT_REQUIRED');state.requestedDuration=prompt.data?.durationSeconds===10?10:6;return{schema:'WORLD_ENGINE_NVIDIA_PRESENTATION_REQUEST_V1',prompt,sceneId:'__timeline__'};}
function approvedBudget(value){const budget=value?.budget;const seconds=budget?.maxWallSeconds,expiry=Date.parse(budget?.validUntil||'');return!!budget&&Number.isSafeInteger(seconds)&&seconds>0&&Number.isFinite(Number(budget.gpuHourlyRate))&&Number(budget.gpuHourlyRate)>0&&Number.isFinite(Number(budget.maxCostAmount))&&Number(budget.maxCostAmount)>0&&/^[A-Z]{3}$/.test(budget.currency||'')&&Number.isFinite(expiry)&&expiry>Date.now();}
function drawDuration(value){const seconds=value?.durationSeconds??6,frames=value?.totalFrames??180;if(!((seconds===6&&frames===180)||(seconds===10&&frames===300))||seconds!==state.requestedDuration)return false;document.title=`WORLD ENGINE · ${seconds}초 GPU 검수`;document.querySelector('header h1').textContent=`${seconds}초 GPU 검수`;document.querySelector('header h1 + p').textContent=`1080×1920 · 30fps · ${frames}프레임 · 무음`;const text=[...$('consent').parentNode.childNodes].find(node=>node.nodeType===3);if(!text)return false;text.textContent=`표시된 승인 한도 안에서 ${seconds}초 영상 1개를 제작합니다.`;return true;}
function drawPreflight(value){const timing=drawDuration(value),target=$('checks');target.replaceChildren();const heading=document.createElement('p');heading.textContent=!timing?'영상 길이·프레임 사전검사 확인이 필요합니다.':value.ready===true?(approvedBudget(value)?'서버 사전검사를 통과했습니다.':'승인 요금·비용·만료 시각을 확인할 수 없어 제작을 차단했습니다.'):'실행 전 확인할 항목이 있습니다.';target.append(heading);for(const check of value.checks||[]){const row=document.createElement('p');row.textContent=`${check.name||'검사'}: ${check.status||'미확인'}${check.code?' · '+check.code:''}`;target.append(row);}if(value.error?.code){const row=document.createElement('p');row.textContent=`오류 코드: ${value.error.code}`;target.append(row);}const budget=value.budget||{};$('budget').textContent=`승인 비용 상한: ${budget.maxCostAmount??'미확인'} ${budget.currency??''} · 정책에 등록된 시간당 요금: ${budget.gpuHourlyRate??'미확인'} ${budget.currency??''} · 승인 만료: ${budget.validUntil??'미확인'} · 이번 실행 상한: ${Number.isSafeInteger(budget.maxWallSeconds)?Math.min(600,budget.maxWallSeconds):'미확인'}초 · 자동 재시도: 0회`;
 return timing&&value.valid===true&&value.ready===true&&value.requiresGpu===true&&approvedBudget(value);}
function facts(pairs){const target=$('job-facts');target.replaceChildren();for(const[label,value]of pairs){const name=document.createElement('dt'),field=document.createElement('dd');name.textContent=label;field.textContent=value===undefined||value===null?'미측정':String(value);target.append(name,field);}}
async function result(){const value=await request(`/api/jobs/${encodeURIComponent(state.job)}/result`);$('result-section').hidden=false;$('downloads').replaceChildren();$('video').hidden=true;for(const file of value.downloads||[]){if(!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(file.name||''))continue;const href=`/api/jobs/${encodeURIComponent(state.job)}/downloads/${encodeURIComponent(file.name)}`,link=document.createElement('a');link.href=href;link.download=file.name;link.textContent=`${file.name} 다운로드${/^[a-f0-9]{64}$/.test(file.sha256||'')?' · SHA-256 '+file.sha256:''}`;$('downloads').append(link);if(file.name.endsWith('.mp4')){$('video').src=href;$('video').hidden=false;}}const storage=value.dropbox||{};$('storage').textContent=`저장소 내 검증: ${storage.mountedReadbackVerified===true||storage.mountReadbackVerified===true?'확인됨':'미확인'} · 외부 다운로드 SHA 검증: ${storage.externalDownloadVerified===true?'확인됨':'미확인'}`;}
async function refresh(){if(!state.job)return;clearTimeout(state.timer);const value=await request(`/api/jobs/${encodeURIComponent(state.job)}`);$('job-section').hidden=false;facts([['작업 ID',value.jobId||state.job],['상태',value.state],['단계',value.phase],['완료 장면',value.completedScenes],['전체 장면',value.totalScenes],['처리 프레임',value.processedFrames],['전체 프레임',value.totalFrames],['경과 시간(초)',value.elapsedSeconds],['오류 코드',value.errorCode]]);const status=String(value.state||'').toLowerCase();if(['complete','completed'].includes(status))await result();else if(!terminal.has(status))state.timer=setTimeout(()=>refresh().catch(showError),2500);}
$('load-example').addEventListener('click',()=>{clearSubmission();$('prompt').value=JSON.stringify(JSON.parse($('example-data').value),null,2);});
$('prompt').addEventListener('input',clearSubmission);
$('input-file').addEventListener('change',()=>busy(async()=>{clearSubmission();const file=$('input-file').files[0];if(!file)return;if(file.size>4*1024*1024)fail('INPUT_SIZE_INVALID');const text=await file.text();try{JSON.parse(text);}catch{fail('INPUT_JSON_INVALID');}$('prompt').value=text;}));
$('prepare-form').addEventListener('submit',event=>{event.preventDefault();busy(async()=>{clearSubmission();const input=body();const inspected=await request('/api/preflight',input);if(!drawPreflight(inspected))return;const saved=await request('/api/submissions',input);if(!drawPreflight(saved.preflight))return;if(!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(saved.submissionId||''))fail('SUBMISSION_ID_INVALID');state.submission=saved.submissionId;state.expires=Date.parse(saved.preflight.budget.validUntil);state.startKey=localStorage.getItem('world-nvidia6-start-'+state.submission)||crypto.randomUUID();localStorage.setItem('world-nvidia6-start-'+state.submission,state.startKey);$('start-section').hidden=false;});});
$('consent').addEventListener('change',updateButtons);
$('start').addEventListener('click',()=>busy(async()=>{if(!state.submission||!state.startKey||!$('consent').checked)fail('EXPLICIT_START_CONSENT_REQUIRED');if(!Number.isFinite(state.expires)||state.expires<=Date.now()){clearSubmission();fail('APPROVAL_EXPIRED');}const value=await request('/api/start',{submissionId:state.submission,idempotencyKey:state.startKey,consent:true});if(!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(value.jobId||''))fail('JOB_ID_INVALID');state.job=value.jobId;localStorage.setItem(key,state.job);clearSubmission();await refresh();}));
$('refresh').addEventListener('click',()=>busy(refresh));
$('logout').addEventListener('click',()=>busy(async()=>{clearTimeout(state.timer);await request('/api/logout',{});localStorage.removeItem(key);location.assign('/login');}));
(async()=>{try{const session=await request('/api/session');state.csrf=session.csrf;if(state.job)await refresh();}catch(error){showError(error);}finally{updateButtons();}})();

