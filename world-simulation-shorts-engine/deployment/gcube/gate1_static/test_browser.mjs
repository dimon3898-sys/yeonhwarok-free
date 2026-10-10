/** Download existing test-fixture bytes through the actual UI, not GPU evidence. */
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const require = createRequire(process.env.STATIC_PROOF_PLAYWRIGHT_PACKAGE || '/tmp/world-engine-selection-fix-checkout/cinematic-world-map/package.json');
const {chromium} = require('playwright');
const base = process.argv[2], output = process.argv[3];
assert(base && output);
fs.mkdirSync(output, {recursive: true});
const browser = await chromium.launch({executablePath: '/usr/bin/chromium', headless: true, args: ['--no-sandbox'], timeout: 30000});
try {
  for (const profile of [{name:'desktop', viewport:{width:1280,height:900}}, {name:'mobile', viewport:{width:390,height:844}, isMobile:true, hasTouch:true}]) {
    const start = performance.now();
    console.log(JSON.stringify({test:profile.name+'_BROWSER_DOWNLOAD', stage:'START', scope:'HTTP_TEST_FIXTURE_NO_GPU_RENDER'}));
    const context = await browser.newContext({...profile, acceptDownloads:true});
    const page = await context.newPage();
    page.setDefaultTimeout(10000);
    await page.goto(base);
    await page.locator('#password').fill('release-test-owner-code');
    await page.locator('#login button').click();
    await page.locator('#generate').waitFor({state:'visible'});
    await page.locator('#generate').click();
    await page.locator('#png').waitFor({state:'visible'});
    const download = await Promise.all([page.waitForEvent('download'), page.locator('#png').click()]).then(x=>x[0]);
    assert.equal(download.suggestedFilename(), 'SUEZ_STATIC_PROOF_RTX4080S.png');
    const file = output+'/'+profile.name+'.png';
    await download.saveAs(file);
    assert.equal(await download.failure(), null);
    const sha = createHash('sha256').update(fs.readFileSync(file)).digest('hex');
    assert.equal(sha,'3e4830cb7db4b6c585b6caec1d77330c257c54918432af5fad9678d6535f0d17');
    const diagnostic = await Promise.all([page.waitForEvent('download'), page.locator('#diagnostic').click()]).then(x=>x[0]);
    assert.equal(diagnostic.suggestedFilename(), 'SUEZ_STATIC_PROOF_RTX4080S.diagnostic.json');
    const diagnosticFile = output+'/'+profile.name+'.diagnostic.json';
    await diagnostic.saveAs(diagnosticFile);
    assert.equal(JSON.parse(fs.readFileSync(diagnosticFile)).gpu_visual_quality,'NOT_RUN');
    assert.equal(await page.locator('#generate').isEnabled(), true);
    assert.equal(await page.locator('#controls').evaluate(e=>e.scrollWidth<=document.documentElement.clientWidth),true);
    console.log(JSON.stringify({test:profile.name+'_BROWSER_DOWNLOAD',result:'PASS',elapsed_ms:performance.now()-start,png_sha256:sha,diagnostic_download:true}));
    await context.close();
  }
} finally {await browser.close();}
