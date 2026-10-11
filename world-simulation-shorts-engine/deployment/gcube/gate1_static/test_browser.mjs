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
    assert.equal(await page.locator('#generate').isEnabled(), false, 'Generate must remain disabled before CHECK GPU');
    await page.locator('#check').click();
    await page.waitForFunction(() => !document.getElementById('generate').disabled);
    assert.match(await page.locator('#gpu').innerText(), /TEST_FIXTURE_NOT_HARDWARE/);
    await page.locator('#generate').click();
    await page.locator('#png').waitFor({state:'visible'});
    const download = await Promise.all([page.waitForEvent('download'), page.locator('#png').click()]).then(x=>x[0]);
    assert.equal(download.suggestedFilename(), 'SUEZ_TERRAIN_SHADING_RTX4080S.png');
    const file = output+'/'+profile.name+'.png';
    await download.saveAs(file);
    assert.equal(await download.failure(), null);
    const sha = createHash('sha256').update(fs.readFileSync(file)).digest('hex');
    assert.equal(sha,'29323353b1e76af7dfbc54407a9cdbdbb559fbfefe9ffac08d70f65f54e98a8d');
    const diagnostic = await Promise.all([page.waitForEvent('download'), page.locator('#diagnostic').click()]).then(x=>x[0]);
    assert.equal(diagnostic.suggestedFilename(), 'SUEZ_TERRAIN_SHADING_RTX4080S.diagnostic.json');
    const diagnosticFile = output+'/'+profile.name+'.diagnostic.json';
    await diagnostic.saveAs(diagnosticFile);
    const data = JSON.parse(fs.readFileSync(diagnosticFile));
    assert.equal(data.gpu_visual_quality,'NOT_RUN');
    assert.equal(data.test_fixture,true);
    assert.equal(data.renderer_source_hash,'e0108a8bf3cb3828529b9077925b9429455dbccd2c695f797f2578ac904b067d');
    assert.equal(data.dem_hash,'08a1b86fbe9c47a9495336e0e83d0bfdea014a4e5c7b36beaaa544aa283fd5a8');
    assert.equal(data.software_d_final_hash,sha);
    assert.equal(data.gl_error,0);
    assert.equal(data.selected_gpu_backend,'egl');
    assert.equal(data.render_parameters.shadingCorrection,'OUTPUT');
    assert.equal(data.render_parameters.verticalExaggeration,2);
    assert.deepEqual(data.output_resolution,[1080,1920]);
    assert.equal(data.dem_source_hashes.length,4);
    assert.equal(await page.locator('#generate').isEnabled(), true);
    assert.equal(await page.locator('#controls').evaluate(e=>e.scrollWidth<=document.documentElement.clientWidth),true);
    console.log(JSON.stringify({test:profile.name+'_BROWSER_DOWNLOAD',result:'PASS',elapsed_ms:performance.now()-start,png_sha256:sha,diagnostic_download:true}));
    await context.close();
  }
} finally {await browser.close();}
