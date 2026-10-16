#!/usr/bin/env node
// Real mobile Chromium/HTTP with a fake CPU-only controller, never GPU proof.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
import {mkdtemp, mkdir, rm, writeFile} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import {tmpdir, userInfo} from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {randomBytes} from 'node:crypto';

const here=path.dirname(fileURLToPath(import.meta.url));
let browser, fixture, browserTemp;
const out=process.env.WORLD_ENGINE_STUDIO_EVIDENCE_DIR || await mkdtemp(path.join(tmpdir(),'studio-mobile-evidence-'));
await mkdir(out,{recursive:true});
const report={schema:'WORLD_ENGINE_STUDIO_MOBILE_UI_CPU_TEST_V1',testOnly:true,gpuExecuted:false,gpuRenderingVerified:false,dropboxExternalVerified:false,checks:[]};
function check(name,action){return Promise.resolve().then(action).then(()=>report.checks.push({name,status:'PASS'}));}
try{
  const require=createRequire(import.meta.url);
  let playwright;
  for(const manifest of [path.resolve(here,'../../../../cinematic-world-map/package.json'),'/opt/rtx-package/repo/cinematic-world-map/package.json']){try{if(existsSync(manifest)){playwright=createRequire(manifest)('playwright');break;}}catch{}}
  if(!playwright){try{playwright=require('playwright');}catch{}}
  if(!playwright)throw new Error('PLAYWRIGHT_UNAVAILABLE');
  const owner=randomBytes(32).toString('base64url');
  fixture=spawn(process.env.WORLD_ENGINE_PYTHON || '/usr/bin/python3',['-B',path.join(here,'ui_fixture_server.py')],{stdio:['ignore','pipe','pipe'],env:{...process.env,WORLD_ENGINE_STUDIO_TEST_OWNER:owner}});
  const origin=await new Promise((resolve,reject)=>{
    let stdout='';const timer=setTimeout(()=>reject(new Error('STUDIO_FIXTURE_START_TIMEOUT')),15000);
    fixture.stdout.on('data',data=>{stdout+=data.toString();if(stdout.length>65536){clearTimeout(timer);reject(new Error('STUDIO_FIXTURE_OUTPUT_TOO_LARGE'));}if(stdout.includes('\n')){try{const row=JSON.parse(stdout.split('\n')[0]);clearTimeout(timer);resolve(row.origin);}catch{clearTimeout(timer);reject(new Error('STUDIO_FIXTURE_INVALID_ORIGIN'));}}});
    fixture.stderr.on('data',()=>{});
    fixture.once('exit',code=>{clearTimeout(timer);reject(new Error(`STUDIO_FIXTURE_EXIT_${code}`));});
  });
  assert.match(origin,/^http:\/\/127\.0\.0\.1:\d+$/);
  const executable=process.env.WORLD_ENGINE_CHROMIUM_PATH || ['/usr/bin/chromium','/usr/bin/chromium-browser','/opt/google/chrome/chrome'].find(existsSync);
  browserTemp=await mkdtemp(path.join(tmpdir(),'studio-mobile-browser-'));
  browser=await playwright.chromium.launch({headless:true,executablePath:executable,env:{...process.env,HOME:userInfo().homedir,XDG_CONFIG_HOME:path.join(browserTemp,'config'),XDG_CACHE_HOME:path.join(browserTemp,'cache')},args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage']});
  const context=await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:1,isMobile:true,hasTouch:true});
  let page=await context.newPage();
  await check('anonymous_api_blocked',async()=>{const response=await context.request.get(origin+'/api/jobs/job_test');assert.equal(response.status(),401);});
  await page.goto(origin+'/login');
  await check('owner_login_mobile',async()=>{await page.fill('#owner-code',owner);await page.click('#login');await page.waitForURL(origin+'/');await page.waitForFunction(()=>document.getElementById('prompt')!==null);});
  await check('portrait_layout_no_horizontal_overflow',async()=>{assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);});
  await check('long_prompt_paste_scroll_json_upload',async()=>{
    await page.fill('#prompt','WORLD_ENGINE_PRODUCTION_STUDIO_REQUEST_V1\n'+'검증 자료에 근거한 제작 입력\n'.repeat(300));
    await page.setInputFiles('#scene-file',{name:'verified-plan.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({schema:'CPU_UI_FIXTURE_ONLY',durationSeconds:80}))});
    await page.waitForFunction(()=>document.getElementById('file-note').textContent.includes('verified-plan.json'));
    assert.equal(await page.inputValue('#duration'),'80');
    await page.click('#preflight');await page.waitForFunction(()=>!document.getElementById('start-section').hidden);assert.equal(await page.isDisabled('#start'),true);
  });
  await page.screenshot({path:path.join(out,'01_MOBILE_PREFLIGHT.png'),fullPage:true});
  await check('explicit_consent_and_double_activation_single_job',async()=>{
    await page.check('#start-consent');await page.evaluate(()=>{const button=document.getElementById('start');button.click();button.click();});await page.waitForFunction(()=>!document.getElementById('job-section').hidden);
    const response=await context.request.get(origin+'/api/jobs/job_test');const status=await response.json();assert.equal(status.uniqueStartCount,1);assert.equal(status.actualGpuExecuted,false);
  });
  await check('completion_download_external_state_truthful',async()=>{
    await page.waitForFunction(()=>!document.getElementById('result-section').hidden);
    assert.match(await page.textContent('#job-facts'),/GPU_RENDERING/);
    assert.equal(await page.locator('#downloads a').count(),1);
    assert.match(await page.textContent('#dropbox-state'),/Dropbox 폴더: CPU_UI_FIXTURE_NOT_DROPBOX/);
    assert.match(await page.textContent('#dropbox-state'),/외부.*미검증/);
    const response=await context.request.get(origin+'/api/jobs/job_test/downloads/proof.mp4');assert.equal(response.status(),200);
  });
  await page.close();page=await context.newPage();
  await check('browser_disconnect_reconnect_preserves_job_no_restart',async()=>{
    await page.goto(origin+'/');await page.waitForFunction(()=>!document.getElementById('result-section').hidden);
    const response=await context.request.get(origin+'/api/jobs/job_test');assert.equal((await response.json()).uniqueStartCount,1);
  });
  await check('interval_revision_previews_without_auto_gpu',async()=>{
    await page.fill('#revision-start','25');await page.fill('#revision-end','35');await page.fill('#revision-prompt','효과음 음량 70%');await page.click('#revise');
    await page.waitForFunction(()=>document.getElementById('revision-result').textContent.includes('scene_04'));
    assert.equal(await page.isChecked('#start-consent'),false);assert.equal(await page.isDisabled('#start'),true);
    const response=await context.request.get(origin+'/api/jobs/job_test');assert.equal((await response.json()).uniqueStartCount,1);
  });
  await check('unsupported_camera_revision_explains_exact_limit',async()=>{await page.fill('#revision-prompt','cameraZoom=1.1');await page.click('#revise');await page.waitForFunction(()=>!document.getElementById('error').hidden);assert.match(await page.textContent('#error-message'),/카메라 수정은 검증된 새 Scene JSON/);assert.match(await page.textContent('#error-message'),/sfx.enabled/);});
  await check('malformed_interval_shows_error',async()=>{await page.fill('#revision-start','35');await page.fill('#revision-end','25');await page.click('#revise');await page.waitForFunction(()=>!document.getElementById('error').hidden);assert.match(await page.textContent('#error-message'),/INVALID_REVISION/);});
  await page.screenshot({path:path.join(out,'02_MOBILE_RESULT_REVISION.png'),fullPage:true});
  await check('all_duration_options_same_ui_contract',async()=>{assert.deepEqual(await page.locator('#duration option').evaluateAll(nodes=>nodes.map(n=>Number(n.value))),[80,120,180,300,600]);});
  report.status='PASS';
}catch(error){report.status='FAIL';report.errorCode=String(error.message||'MOBILE_UI_TEST_FAILED').slice(0,180);process.exitCode=2;}
finally{
  if(browser)await browser.close();
  if(browserTemp)await rm(browserTemp,{recursive:true,force:true});
  if(fixture){fixture.kill('SIGTERM');await Promise.race([new Promise(resolve=>fixture.once('exit',resolve)),new Promise(resolve=>setTimeout(resolve,3000))]);if(fixture.exitCode===null)fixture.kill('SIGKILL');}
  await writeFile(path.join(out,'MOBILE_UI_REPORT.json'),JSON.stringify(report,null,2)+'\n');
  process.stdout.write(JSON.stringify(report)+'\n');
}
