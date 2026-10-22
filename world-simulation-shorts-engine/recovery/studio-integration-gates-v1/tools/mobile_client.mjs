/** Actual mobile Chromium -> preserved Studio HTTP routes. No credential output. */
import {readFile, writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
const require = createRequire('/workspace/exact-65422-capsule-20261020/package.json');
const {chromium} = require('playwright');
const [origin, privateRoot, requestFile] = process.argv.slice(2);
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(origin)) throw new Error('LOOPBACK_ONLY');
const request = JSON.parse(await readFile(requestFile, 'utf8'));
const browser = await chromium.launch({headless:true, args:['--no-sandbox']});
const context = await browser.newContext({viewport:{width:412,height:915},isMobile:true,hasTouch:true,
  userAgent:'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/154.0.0.0 Mobile Safari/537.36'});
try {
  const page = await context.newPage();
  await page.goto(origin + '/login');
  const unauth = await page.evaluate(async request => {
    const r = await fetch('/api/preflight',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});
    return {status:r.status,body:await r.json()};
  }, request);
  if(unauth.status !== 401) throw new Error('AUTH_GATE_FAILED');
  await page.locator('#owner-code').fill((await readFile(privateRoot+'/owner-code','utf8')).trim());
  await Promise.all([page.waitForURL(origin+'/'),page.locator('#login').click()]);
  const facts = await page.evaluate(async request => {
    const session = await (await fetch('/api/session')).json();
    const post=async (path,body,csrf=session.csrf)=>{
      const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Studio-CSRF':csrf},body:JSON.stringify(body)});
      return {status:r.status,body:await r.json()};
    };
    const noCsrf=await post('/api/preflight',request,'');
    const preflight=await post('/api/preflight',request);
    if(noCsrf.status!==403 || preflight.status!==200 || !preflight.body.ready) throw new Error('PREFLIGHT_OR_CSRF_FAILED');
    const submission=await post('/api/submissions',request);
    if(submission.status!==201) throw new Error('SUBMIT_FAILED');
    const startBody={submissionId:submission.body.submissionId,idempotencyKey:'g1-mobile-exact-original-20261022',consent:true};
    const started=await post('/api/start',startBody);
    if(started.status!==202 || !started.body.jobId) throw new Error('START_FAILED');
    const duplicate=await post('/api/start',startBody);
    if(duplicate.body.jobId!==started.body.jobId) throw new Error('DUPLICATE_LAUNCH');
    return {unauthStatus:401,missingCsrfStatus:noCsrf.status,loginViaOriginalForm:true,sessionAuthenticated:session.authenticated,
      preflight:preflight.body,submissionId:submission.body.submissionId,startStatus:started.status,
      jobId:started.body.jobId,duplicateJobId:duplicate.body.jobId,viewport:[innerWidth,innerHeight],mobileBrowser:true};
  },request);
  await writeFile(privateRoot+'/MOBILE_HTTP_START.json',JSON.stringify({...facts,browserDisconnectedAfterStart:true},null,2),{mode:0o600,flag:'wx'});
  process.stdout.write(JSON.stringify({jobId:facts.jobId,status:'AUTHENTICATED_HTTP_START_AND_DUPLICATE_CHECK_PASS'})+'\n');
} finally {await context.close();await browser.close();}
