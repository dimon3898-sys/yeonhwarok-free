// Actual mobile app.js, DOM, form submission and saved-plan display. These
// localhost protocol fixtures intentionally do not initialize any renderer.
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const root = process.cwd();
const require = createRequire(path.resolve(root, '../cinematic-world-map/package.json'));
const {chromium} = require('playwright');
const BOLD = 'BOLD_INFOGRAPHIC_V023', OFF = 'V022_LEGACY';
const script = JSON.parse(fs.readFileSync(path.join(root, 'deployment/gcube/fixtures/infographic_production_v022.json'), 'utf8'));
const report = {passed: false, gpu_draw: 'NOT_RUN', video_render: 'NOT_RUN', transport: 'ACTUAL_LOCAL_HTTP', viewport: [393, 851], checks: {}};
const errors = [];
let nextPlan, savedPlan, posts = [];
function plan(kind = 'QA', bold = true) {
  const family = kind === 'QA' ? 'story-progression-v021' : 'production-earth-v1';
  const infographic = {version: 'v022', parent_renderer_family: family};
  const child = {version: 'v023', profile_id: BOLD, profile_sha256: 'a'.repeat(64), registry_sha256: 'b'.repeat(64)};
  const scene = {scene_id: 'S001', start_time: 0, duration: kind === 'QA' ? 24 : 8,
    location: 'Local UI protocol fixture', camera_preset: 'EARTH_ESTABLISH', visual_mode: '3D_EARTH', narration: 'Local UI protocol fixture', infographic};
  if (bold) scene.bold_infographic = structuredClone(child);
  const metadata = {infographic};
  if (bold) metadata.bold_infographic = child;
  return {title: 'BOLD UI selection fixture', duration: scene.duration, plan_hash: 'bold-ui-protocol-hash',
    gate: {passed: true}, request: {direction_profile: 'SECOND_EVENT_ADAPTIVE_WIDE_TEST', quality: 'HIGH'}, metadata, scenes: [scene]};
}
const mime = {'.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.webmanifest': 'application/manifest+json'};
const server = http.createServer(async (req, res) => {
  if (req.url.startsWith('/api/')) {
    const chunks = []; for await (const chunk of req) chunks.push(chunk);
    const body = chunks.length ? JSON.parse(Buffer.concat(chunks).toString()) : null;
    if (req.method === 'POST') posts.push({path: req.url, body});
    let response = {};
    if (req.url === '/api/health') response = {status: 'ok'};
    else if (req.url === '/api/projects' && req.method === 'POST') {savedPlan = structuredClone(nextPlan); response = payload();}
    else if (req.url === '/api/projects') response = {projects: []};
    else if (req.url.endsWith('/versions')) response = {versions: ['v001']};
    else if (req.url.endsWith('/status')) response = {status: 'planned', outputs: []};
    else if (req.url === '/api/projects/ui-bold-project') response = payload();
    else response = {status: 'planned'};
    res.writeHead(200, {'Content-Type': 'application/json'});res.end(JSON.stringify(response));return;
  }
  const pathname = new URL(req.url, 'http://127.0.0.1').pathname;
  const filename = path.resolve(root, 'web', pathname === '/' ? 'index.html' : `.${pathname.replace(/^\/static\//, '/')}`);
  if (!filename.startsWith(path.resolve(root, 'web') + path.sep)) {res.writeHead(403);res.end();return;}
  try {const data=fs.readFileSync(filename);res.writeHead(200, {'Content-Type':mime[path.extname(filename)]||'application/octet-stream'});res.end(data);}
  catch {res.writeHead(404);res.end();}
});
function payload() {return {project: {id:'ui-bold-project',current_version:'v001',title:'BOLD UI fixture'},version:'v001',plan:savedPlan};}
await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-gpu']});
async function open(options={}) {
  posts=[];nextPlan=options.plan||plan();savedPlan=structuredClone(nextPlan);
  const context=await browser.newContext({viewport:{width:393,height:851},isMobile:true,hasTouch:true});
  if(options.storage)await context.addInitScript(storage=>{for(const[key,value]of Object.entries(storage))localStorage.setItem(key,value);},options.storage);
  const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
  await page.goto(origin);await page.waitForFunction(()=>document.getElementById('connection').textContent==='연결됨');
  return{context,page};
}
async function submit(page) {
  const previous=posts.filter(row=>row.path==='/api/projects').length;
  await page.locator('#create-plan').click();await page.waitForFunction(()=>document.getElementById('plan-panel').hidden===false);
  await page.waitForFunction(()=>!document.getElementById('create-plan').disabled);
  assert.equal(posts.filter(row=>row.path==='/api/projects').length,previous+1);
  return posts.filter(row=>row.path==='/api/projects').at(-1).body;
}
async function check(name,operation){await operation();report.checks[name]='PASS';}
try {
  await check('auto_request_omits_visual_field_and_actual_bold_badge',async()=>{
    const{context,page}=await open();await page.locator('#topic').fill('Authored UI topic');await page.locator('#duration').fill('24');
    assert.equal(await page.locator('#infographic-visual-profile').inputValue(),'AUTO');
    const request=await submit(page);assert.equal(request.direction_profile,'REFERENCE_MASTER');assert.equal('infographic_visual_profile'in request,false);
    assert.equal(await page.locator('#infographic-plan-badge').textContent(),'INFOGRAPHIC v023 · BOLD INFOGRAPHIC · QA');
    assert.equal(await page.locator('#direction-profile').inputValue(),'REFERENCE_MASTER');
    assert.equal((await submit(page)).direction_profile,'REFERENCE_MASTER');await context.close();
  });
  await check('explicit_bold_persists_display_repeat_and_reload',async()=>{
    const{context,page}=await open();await page.locator('#topic').fill('Explicit BOLD topic');await page.locator('#infographic-mode').selectOption('QA');
    await page.locator('#infographic-visual-profile').selectOption(BOLD);assert.equal((await submit(page)).infographic_visual_profile,BOLD);
    assert.equal((await submit(page)).infographic_visual_profile,BOLD);
    await page.reload();await page.waitForFunction(()=>document.getElementById('connection').textContent==='연결됨');
    assert.equal(await page.locator('#infographic-visual-profile').inputValue(),BOLD);assert.equal(await page.locator('#infographic-mode').inputValue(),'QA');await context.close();
  });
  await check('saved_bold_badge_does_not_mutate_explicit_off_choice',async()=>{
    const{context,page}=await open({storage:{'world-simulation.last-project':'ui-bold-project','world-simulation.infographic-visual-profile':OFF}});
    await page.locator('#infographic-plan-badge').waitFor();assert.equal(await page.locator('#infographic-plan-badge').textContent(),'INFOGRAPHIC v023 · BOLD INFOGRAPHIC · QA');
    assert.equal(await page.locator('#infographic-visual-profile').inputValue(),OFF);await context.close();
  });
  await check('saved_v022_badge_does_not_migrate_or_override_bold_form',async()=>{
    const{context,page}=await open({plan:plan('QA',false),storage:{'world-simulation.last-project':'ui-bold-project','world-simulation.infographic-visual-profile':BOLD}});
    await page.locator('#infographic-plan-badge').waitFor();assert.equal(await page.locator('#infographic-plan-badge').textContent(),'INFOGRAPHIC v022 · QA');
    assert.equal(await page.locator('#infographic-visual-profile').inputValue(),BOLD);assert.equal(await page.locator('#approve-render').isDisabled(),false);await context.close();
  });
  await check('partial_bold_child_blocks_approve_and_render',async()=>{
    const broken=plan();delete broken.scenes[0].bold_infographic;
    const{context,page}=await open({plan:broken});await page.locator('#topic').fill('Broken BOLD fixture');await page.locator('#infographic-mode').selectOption('QA');await submit(page);
    assert.equal(await page.locator('#infographic-plan-badge').getAttribute('data-infographic-kind'),'MISMATCH');assert.equal(await page.locator('#approve-render').isDisabled(),true);
    await page.evaluate(()=>document.getElementById('resume-render').click());await page.waitForFunction(()=>!document.getElementById('resume-render').disabled);
    assert.equal(posts.some(row=>/\/(approve|render)$/.test(row.path)),false);await context.close();
  });
  await check('production_bold_submission_preserves_authored_only_payload',async()=>{
    const{context,page}=await open({plan:plan('PRODUCTION')});await page.locator('#infographic-mode').selectOption('PRODUCTION');await page.locator('#infographic-visual-profile').selectOption(BOLD);
    await page.locator('#infographic-script-file').setInputFiles({name:'authored-script.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(script))});
    assert.deepEqual(await submit(page),{direction_profile:'MAP_INFOGRAPHIC_PRODUCTION_V022',script_record:script,infographic_visual_profile:BOLD});
    assert.equal(await page.locator('#infographic-plan-badge').getAttribute('data-infographic-kind'),'PRODUCTION');await context.close();
  });
  await check('explicit_off_submission_uses_v022_plan',async()=>{
    const{context,page}=await open({plan:plan('QA',false)});await page.locator('#topic').fill('Explicit OFF topic');await page.locator('#infographic-mode').selectOption('QA');
    await page.locator('#infographic-visual-profile').selectOption(OFF);assert.equal((await submit(page)).infographic_visual_profile,OFF);
    assert.equal(await page.locator('#infographic-plan-badge').textContent(),'INFOGRAPHIC v022 · QA');assert.equal(await page.locator('#approve-render').isDisabled(),false);await context.close();
  });
  await check('actual_helper_rejects_unknown_visual_profile_and_mismatched_pins',async()=>{
    const{context,page}=await open();const results=await page.evaluate(async({BOLD})=>{
      const{buildCreationRequest,infographicPlanSelection}=await import('/static/app.js');
      let rejected=false;try{buildCreationRequest({infographic_mode:'NONE',infographic_visual_profile:'UNKNOWN'});}catch{rejected=true;}
      const parent={version:'v022',parent_renderer_family:'story-progression-v021'};const child={version:'v023',profile_id:BOLD,profile_sha256:'a'.repeat(64),registry_sha256:'b'.repeat(64)};
      const base={metadata:{infographic:parent,bold_infographic:child},scenes:[{infographic:parent,bold_infographic:structuredClone(child)}],request:{direction_profile:'SECOND_EVENT_ADAPTIVE_WIDE_TEST'}};
      const variants=[structuredClone(base),structuredClone(base),structuredClone(base),structuredClone(base),structuredClone(base),structuredClone(base)];
      delete variants[0].metadata.bold_infographic;variants[1].scenes[0].bold_infographic.profile_sha256='c'.repeat(64);variants[2].scenes[0].bold_infographic.registry_sha256='d'.repeat(64);variants[3].metadata.bold_infographic.version='v024';
      delete variants[4].metadata.bold_infographic.profile_sha256;delete variants[4].scenes[0].bold_infographic.profile_sha256;
      delete variants[5].metadata.bold_infographic.registry_sha256;delete variants[5].scenes[0].bold_infographic.registry_sha256;
      return{rejected,valid:infographicPlanSelection(base).valid,variants:variants.map(value=>infographicPlanSelection(value).valid)};
    },{BOLD});assert.equal(results.rejected,true);assert.equal(results.valid,true);assert.deepEqual(results.variants,[false,false,false,false,false,false]);await context.close();
  });
  assert.deepEqual(errors,[]);report.passed=true;report.total=Object.keys(report.checks).length;process.stdout.write(JSON.stringify(report)+'\n');
}finally{await browser.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));http.globalAgent.destroy();}
