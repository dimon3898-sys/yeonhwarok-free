/** CPU Canvas evidence for the exact v024 region helper and inherited overlay.
 * This does not render GPU shaders, lighting, cloud or atmosphere, and cannot
 * stand in for the uploaded CURRENT MP4 or an RTX4080S AFTER render.
 */
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';

const app = path.resolve('.'), repo = path.resolve('..'), args = process.argv.slice(2);
const option = name => {const index = args.indexOf(name); return index < 0 ? null : args[index + 1];};
const detectorOnly = args.includes('--detector-only'), planPath = option('--plan');
if (!detectorOnly && !planPath) throw Error('Provide --plan with the actual selected v024 plan');
const plan = detectorOnly ? null : JSON.parse(fs.readFileSync(planPath));
const output = path.resolve(option('--output') || '/tmp/world-v024/iteration-01');
const require = createRequire(path.join(repo, 'cinematic-world-map/package.json'));
const {chromium} = require('playwright');
const sha = value => createHash('sha256').update(value).digest('hex');
const files = {
  '/three.js': path.join(repo, 'cinematic-world-map/node_modules/three/build/three.module.js'),
  '/infographic.js': path.join(app, 'web/infographic_adapter.js'),
  '/bold.js': path.join(app, 'web/bold_infographic_adapter.js'),
  '/terrain.js': path.join(app, 'web/terrain_infographic_adapter.js'),
  '/preview-runner.mjs': path.join(app, 'tools/terrain_canvas_preview_v024.mjs'),
  '/metrics.mjs': path.join(app, 'tools/terrain_pixel_metrics_v024.mjs'),
  '/bold_pixel_metrics_v023.mjs': path.join(app, 'tools/bold_pixel_metrics_v023.mjs'),
  '/reference.js': path.join(app, 'web/reference_effects_adapter.js'),
  '/earth.js': path.join(app, 'web/earth_adapter.js'),
  '/single.js': path.join(app, 'web/single_event_camera.js'),
  '/return.js': path.join(app, 'web/return_wide_camera.js'),
  '/second.js': path.join(app, 'web/second_event_camera.js'),
  '/registry.json': path.join(app, 'web/infographic/v022/registry.json'),
  '/profile.json': path.join(app, 'web/infographic/v024/terrain_profile.json'),
  '/data_profile.json': path.join(app, 'data/infographic/v024/terrain_profile.json'),
  '/bold_profile.json': path.join(app, 'web/infographic/v023/bold_profile.json'),
  '/native_profile.json': path.join(app, 'web/infographic/v022/profile.json'),
  '/manifest.json': path.join(app, 'web/earth-detail/v018/manifest.json'),
  '/day.jpg': path.join(repo, 'cinematic-world-map/assets/v3/earth/earth-day-8k.jpg'),
  '/detail_0.png': path.join(app, 'web/earth-detail/v018/detail_0.png'),
  '/detail_1.png': path.join(app, 'web/earth-detail/v018/detail_1.png'),
  '/detail_0_land.png': path.join(app, 'web/earth-detail/v018/detail_0_land.png'),
  '/detail_1_land.png': path.join(app, 'web/earth-detail/v018/detail_1_land.png'),
  '/regular.otf': path.join(app, 'web/fonts/NotoSansCJKkr-Regular.otf'),
  '/bold.otf': path.join(app, 'web/fonts/NotoSansCJKkr-Bold.otf'),
};
// Hash exactly the bytes executed, including font/source texture inputs.
const servedBytes = Object.fromEntries(Object.entries(files).map(([url, file]) => [url, fs.readFileSync(file)]));
assert(servedBytes['/profile.json'].equals(servedBytes['/data_profile.json']), 'TERRAIN_MIRRORED_PROFILE_BYTES_DIFFER');
const html = `<!doctype html><meta charset="utf-8"><style>
@font-face{font-family:'Noto Cinema';font-weight:400;src:url('/regular.otf')}
@font-face{font-family:'Noto Cinema';font-weight:700;src:url('/bold.otf')}
body{margin:0;background:#061016}canvas{display:block}</style><canvas id="frame" width="1080" height="1920"></canvas>`;
const server = http.createServer((request, response) => {
  if (request.url === '/') {response.setHeader('Content-Type', 'text/html'); response.end(html); return;}
  if (request.url === '/plan.json') {response.setHeader('Content-Type', 'application/json'); response.end(JSON.stringify(plan)); return;}
  const file = files[request.url];
  if (!file) {response.writeHead(404); response.end(); return;}
  response.setHeader('Content-Type', file.endsWith('.js') || file.endsWith('.mjs') ? 'text/javascript'
    : file.endsWith('.json') ? 'application/json' : file.endsWith('.otf') ? 'font/otf'
      : file.endsWith('.jpg') ? 'image/jpeg' : 'image/png');
  response.end(servedBytes[request.url]);
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
fs.mkdirSync(output, {recursive: true}); let browser,page;
if(plan)fs.writeFileSync(path.join(output,'scene-plan.json'),JSON.stringify(plan,null,2)+'\n');
const snapshotDirectory = path.join(output, 'executed-source'); fs.mkdirSync(snapshotDirectory, {recursive: true});
const sourceSnapshots = [];
for (const [url, name] of [['/profile.json','terrain_profile.json'],['/terrain.js','terrain_infographic_adapter.js'],
  ['/metrics.mjs','terrain_pixel_metrics_v024.mjs'],['/preview-runner.mjs','terrain_canvas_preview_v024.mjs']]) {
  fs.writeFileSync(path.join(snapshotDirectory, name), servedBytes[url]);
  sourceSnapshots.push({url, file: 'executed-source/' + name, sha256: sha(servedBytes[url])});
}
try {
  browser = await chromium.launch({executablePath: '/usr/bin/chromium', headless: true,
    args: ['--no-sandbox', '--disable-gpu', '--disable-gpu-compositing']});
  page = await browser.newPage({viewport: {width: 1080, height: 1920}, deviceScaleFactor: 1});
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    globalThis.__terrainWebGLAttempts = 0;
    HTMLCanvasElement.prototype.getContext = function(kind, ...rest) {
      if (/webgl/i.test(String(kind))) {globalThis.__terrainWebGLAttempts++; throw Error('CPU_PREVIEW_GPU_CONTEXT_FORBIDDEN');}
      return original.call(this, kind, ...rest);
    };
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  const receipt = await page.evaluate(async ({detectorOnly}) => {
    const THREE = await import('/three.js'), metrics = await import('/metrics.mjs');
    const get = async url => (await fetch(url)).text();
    const strip = source => source.replace(/^import .*;\s*$/gm, '').replace(/^export /gm, '');
    const unused = () => {throw Error('CPU_PREVIEW_UNUSED_GPU_PATH');};
    const reference = new Function('THREE', 'SceneEventQualityRenderer', 'digestBytes', 'trustedStaticURL',
      'flatCoordinate', 'productionUsesRouteHeadAnchor', strip(await get('/reference.js'))
      + '\nreturn {characterRevealState,markerPopState};')(THREE, class {}, unused, unused, unused, unused);
    const infographic = new Function('THREE', 'SceneStoryProgressionRenderer', 'SceneProductionEarthRenderer',
      'createStoryProgressionRenderer', 'characterRevealState', 'markerPopState', 'digestBytes', 'trustedStaticURL',
      strip(await get('/infographic.js')) + '\nreturn {prepareInfographicGeometry,projectInfographicGeometry,'
      + 'validateInfographicGeometry,SceneInfographicRenderer,SceneProductionInfographicRenderer,createInfographicRenderer};')(
      THREE, class {}, class {}, unused, reference.characterRevealState, reference.markerPopState, unused, unused);
    const bold = new Function('SceneInfographicRenderer', 'SceneProductionInfographicRenderer',
      'createInfographicRenderer', 'validateInfographicGeometry', 'prepareInfographicGeometry',
      'projectInfographicGeometry', 'digestBytes', 'trustedStaticURL', strip(await get('/bold.js'))
      + '\nreturn {drawBoldRegionLayer,boldRegionStyle,validateBoldSelection,withoutLegacyCountryDraw,createBoldInfographicRenderer};')(
      infographic.SceneInfographicRenderer, infographic.SceneProductionInfographicRenderer, infographic.createInfographicRenderer,
      infographic.validateInfographicGeometry, infographic.prepareInfographicGeometry, infographic.projectInfographicGeometry, unused, unused);
    const terrain = new Function('THREE','SceneInfographicRenderer', 'SceneProductionInfographicRenderer',
      'prepareInfographicGeometry', 'projectInfographicGeometry', 'validateBoldSelection', 'withoutLegacyCountryDraw',
      'createBoldInfographicRenderer', 'digestBytes', 'trustedStaticURL', strip(await get('/terrain.js'))
      + '\nreturn {validateTerrainProfile,terrainRegionStyle,drawTerrainRegionLayer,createTerrainInfographicRenderer,prepareTerrainInfographicGeometry:typeof prepareTerrainInfographicGeometry===\"function\"?prepareTerrainInfographicGeometry:null,traceTerrainFillPath:typeof traceTerrainFillPath===\"function\"?traceTerrainFillPath:null};')(
      THREE,infographic.SceneInfographicRenderer, infographic.SceneProductionInfographicRenderer,
      infographic.prepareInfographicGeometry, infographic.projectInfographicGeometry,
      bold.validateBoldSelection, bold.withoutLegacyCountryDraw, bold.createBoldInfographicRenderer, unused, unused);
    const profile = await (await fetch('/profile.json')).json(), boldProfile = await (await fetch('/bold_profile.json')).json();
    terrain.validateTerrainProfile(profile);
    const width = 1080, height = 1920, canvas = document.getElementById('frame');
    const makeCanvas = (w = width, h = height) => {const c = document.createElement('canvas'); c.width = w; c.height = h; return c;};
    const rgba = c => c.getContext('2d', {willReadFrequently: true}).getImageData(0, 0, c.width, c.height).data;
    const snapshots = [], checks = [], cases = [];
    globalThis.__terrainCPUProgress={snapshots,checks,cases};
    const check = (id, passed, details = {}) => checks.push({id, passed: !!passed, ...details});
    const capture = (name, c = canvas) => snapshots.push({name, png: c.toDataURL('image/png')});
    const draw = (projected, role, target = canvas, options = {}) => terrain.drawTerrainRegionLayer(
      target.getContext('2d', {willReadFrequently: true}), projected, terrain.terrainRegionStyle(profile, role),
      {...options, width: target.width, height: target.height});
    const glowOnly = (projected, role) => {
      const c = makeCanvas(), context = c.getContext('2d');
      const proxy = new Proxy(context, {get(target, key) {
        if (key === 'stroke') return (...args) => target.shadowBlur > 0 ? target.stroke(...args) : undefined;
        const value = Reflect.get(target, key, target); return typeof value === 'function' ? value.bind(target) : value;
      }, set(target, key, value) {return Reflect.set(target, key, value, target);}});
      terrain.drawTerrainRegionLayer(proxy, projected, terrain.terrainRegionStyle(profile, role),
        {drawFill: false, width, height});
      return c;
    };
    const polygonMask = (projected,nativeTrace=true) => {
      const c = makeCanvas(), ctx = c.getContext('2d'); ctx.fillStyle = '#fff';
      if(nativeTrace){
        if(typeof terrain.traceTerrainFillPath!=='function')throw Error('ACTUAL_V024_FILL_TRACE_REQUIRED');
        terrain.traceTerrainFillPath(ctx,projected);
      }else{
        ctx.beginPath();for (const polygon of projected.polygons) {
          ctx.moveTo(polygon[0].x, polygon[0].y);
          for (const point of polygon.slice(1)) ctx.lineTo(point.x, point.y); ctx.closePath();
        }
      }
      ctx.fill(); return c;
    };
    const nativeEdgeMask = projected => {
      const c = makeCanvas(), ctx = c.getContext('2d'); ctx.strokeStyle = '#fff'; ctx.lineWidth = 1;
      ctx.beginPath(); for (const [a,b] of projected.segments) {ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);} ctx.stroke();
      return rgba(c);
    };

    if (detectorOnly) {
      // Explicit artificial detector raster, never a Scene/registry/production geometry.
      const source = new ImageData(width, height), projected = {visible: true,
        polygons: [[{x:80,y:200},{x:1000,y:200},{x:1000,y:1700},{x:80,y:1700}]],
        segments: [[{x:100,y:960},{x:980,y:960}]]};
      for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
        const i = (y * width + x) * 4, v = 80 + (x * 7 + y * 3) % 100;
        source.data.set([v + 20, v + 5, v, 255], i);
      }
      const mask = rgba(polygonMask(projected)), native = makeCanvas(), old = makeCanvas();
      for (const c of [native, old]) c.getContext('2d').putImageData(source, 0, 0);
      const fillReceipt = draw(projected, 'PRIMARY', native, {drawBoundary: false});
      bold.drawBoldRegionLayer(old.getContext('2d'), projected, bold.boldRegionStyle(boldProfile, 'PRIMARY'),
        {drawBoundary: false, width, height});
      const actual = metrics.terrainRegionPixels(source.data, rgba(native), mask, width, height,
        {stride: 4, expectedLuminanceScale: fillReceipt.multiply_gray_factor});
      actual.local_tone = {requested_scale: fillReceipt.luminance_scale, browser_applied_scale: fillReceipt.multiply_gray_factor,
        browser_multiply_color: fillReceipt.multiply_color, scope: 'Canvas CSS neutral-gray quantization, measured draw receipt; raw source losses remain separately reported.'};
      const previous = metrics.terrainRegionPixels(source.data, rgba(old), mask, width, height, {stride: 4});
      check('NATIVE_COLOR_MATCHES_LOCAL_SCALED_W3C_LUMINANCE', actual.luminance.W3C.mean_absolute_error_against_scaled_source < .005, {measured: actual});
      check('NATIVE_COLOR_RETAINS_THREE_DETAIL_SCALES', actual.detail.every(row => row.W3C.retention >= .80
        && row.W3C.normalized_retention_against_expected_local_scale >= .97 && row.W3C.correlation > .995));
      check('OLD_SOURCE_OVER_ATTENUATION_MEASURED', previous.detail.every(row => row.W3C.retention < .6));
      for (const role of ['PRIMARY', 'SECONDARY']) {
        const c = makeCanvas(); draw(projected, role, c, {drawFill: false, drawGlow: false});
        const measured = metrics.boundaryPixelMetrics(rgba(c), width, height, projected.segments, {brightCore: true});
        check(role + '_ACTUAL_CORE_WIDTH', measured.cross_sections > 0
          && Math.abs(measured.width_px_median - (role === 'PRIMARY' ? 8 : 3)) < .3, {measured});
      }
      const glow = glowOnly(projected, 'PRIMARY'), halo = metrics.haloPixelMetrics(rgba(glow), width, height,
        projected.segments, {nativeEdgeMask: nativeEdgeMask(projected)});
      check('PRIMARY_HALO_ACTUAL_BOUNDED_REACH', halo.cross_sections > 0 && halo.sampling_limit_hits === 0
        && halo.reach_from_native_edge_px_max <= 16 && halo.peak_alpha_median <= .35, {measured: halo});
      const secondaryGlow = glowOnly(projected, 'SECONDARY');
      check('SECONDARY_HAS_ZERO_GLOW_PIXELS', rgba(secondaryGlow).every((v, i) => i % 4 !== 3 || v === 0));
      const off = makeCanvas(); off.getContext('2d').drawImage(old, 0, 0);
      terrain.drawTerrainRegionLayer(off.getContext('2d'), projected, null, {width, height});
      check('OFF_EXACT_V023_PIXELS', metrics.imageDifference(rgba(old), rgba(off), width, height).identical);
      const cx = native.getContext('2d'); cx.globalCompositeOperation = 'multiply'; cx.globalAlpha = .37; cx.shadowBlur = 7;
      draw(projected, 'PRIMARY', native);
      check('NATIVE_CONTEXT_STATE_RESTORED', cx.globalCompositeOperation === 'multiply' && cx.globalAlpha === .37 && cx.shadowBlur === 7);
      check('ZERO_WEBGL_CONTEXT_ATTEMPTS', globalThis.__terrainWebGLAttempts === 0);
      return {passed: checks.every(row => row.passed), checks, resolution: [width, height], detector_source: 'Explicit synthetic raster only',
        GPU: 'NOT_RUN', visual_quality_acceptance: 'NOT_RUN', webgl_context_attempts: globalThis.__terrainWebGLAttempts};
    }

    const plan = await (await fetch('/plan.json')).json(), scene = plan.scenes[0];
    if (plan.metadata?.terrain_infographic?.version !== 'v024' || scene.terrain_infographic?.version !== 'v024') throw Error('CPU_SELECTED_V024_PLAN_REQUIRED');
    const registry = await (await fetch('/registry.json')).json(), nativeProfile = await (await fetch('/native_profile.json')).json();
    if(typeof terrain.prepareTerrainInfographicGeometry!=='function')throw Error('ACTUAL_V024_GEOMETRY_PREPARER_REQUIRED');
    const manifest = await (await fetch('/manifest.json')).json();
    const fpsParts = String(scene.terrain_infographic.fps).split('/').map(Number), fps = fpsParts.length === 1 ? fpsParts[0] : fpsParts[0] / fpsParts[1];
    const single = new Function('THREE', 'SceneProductionEarthRenderer', strip(await get('/single.js'))
      + '\nreturn {singleCameraValues,installSingleCamera};')(THREE, class {});
    const returning = new Function('singleCameraValues', 'installSingleCamera', 'SceneSingleEventRenderer', strip(await get('/return.js'))
      + '\nreturn {returnCameraValues,installReturnCamera};')(single.singleCameraValues, single.installSingleCamera, class {});
    const second = new Function('THREE', 'returnCameraValues', 'installReturnCamera', 'SceneReturnWideRenderer', strip(await get('/second.js'))
      + '\nreturn {installSecondCamera,secondCameraState};')(THREE, returning.returnCameraValues, returning.installReturnCamera, class {});
    const camera = {scene: structuredClone(scene), camera: new THREE.PerspectiveCamera(64, width / height, .02, 30)};
    second.installSecondCamera(camera);
    const earthSource = await get('/earth.js'), projectSource = earthSource.match(/^ project\(point\)\{[^\n]+\}$/m)?.[0];
    if (!projectSource) throw Error('FROZEN_NATIVE_POINT_PROJECTION_CHANGED');
    const originalProject = new Function('return ({' + projectSource.trim() + '}).project;')();
    await document.fonts.load('400 72px "Noto Cinema"', '수에즈 CANAL CLOSED SINGAPORE');
    await document.fonts.load('700 72px "Noto Cinema"', '수에즈 CANAL CLOSED SINGAPORE');
    await document.fonts.ready;
    if (![400,700].every(weight => document.fonts.check(`${weight} 72px "Noto Cinema"`))) throw Error('ACTUAL_NATIVE_FONT_NOT_READY');
    const image = async url => {
      const img = new Image(); img.src = url; await img.decode(); const c = makeCanvas(img.width, img.height), ctx = c.getContext('2d', {willReadFrequently: true});
      ctx.drawImage(img, 0, 0); return {width: c.width, height: c.height, data: rgba(c)};
    };
    const day = await image('/day.jpg'), details = [await image('/detail_0.png'), await image('/detail_1.png')];
    const landMasks = [await image('/detail_0_land.png'), await image('/detail_1_land.png')];
    const detailRecords = manifest.textures.filter(row => row.role === 'regional_day_relief');
    function mapPixels(cam, factor = 1) {
      const out = new ImageData(width, height), land = new ImageData(width, height), coverage = new Uint8Array(width * height);
      const longitude=new Float32Array(width*height),latitude=new Float32Array(width*height),validRay=new Uint8Array(width*height);
      const position = cam.position, m = cam.matrixWorld.elements, scale = Math.tan(cam.fov * Math.PI / 360), aspect = width / height, C = position.lengthSq() - 1;
      for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
        const sx = (2 * (x + .5) / width - 1) * scale * aspect, sy = (1 - 2 * (y + .5) / height) * scale;
        let dx = m[0] * sx + m[4] * sy - m[8], dy = m[1] * sx + m[5] * sy - m[9], dz = m[2] * sx + m[6] * sy - m[10];
        const length = Math.hypot(dx, dy, dz); dx /= length; dy /= length; dz /= length;
        const b = position.x * dx + position.y * dy + position.z * dz, discriminant = b * b - C, index = (y * width + x) * 4;
        if (discriminant < 0) {out.data.set([6, 13, 22, 255], index); continue;}
        const at = -b - Math.sqrt(discriminant); if (at < 0) {out.data.set([6, 13, 22, 255], index); continue;}
        const xx = position.x + dx * at, yy = position.y + dy * at, zz = position.z + dz * at;
        const lon = Math.atan2(-zz, xx) * 180 / Math.PI, lat = Math.asin(Math.max(-1, Math.min(1, yy))) * 180 / Math.PI;
        longitude[y*width+x]=lon;latitude[y*width+x]=lat;validRay[y*width+x]=1;
        let source = day, u = (lon + 180) / 360, v = (90 - lat) / 180;
        for (let r = 0; r < detailRecords.length; r++) {
          const [left, bottom, right, top] = detailRecords[r].bounds;
          if (lon < left || lon > right || lat < bottom || lat > top) continue;
          const uu = (lon - left) / (right - left), vv = (top - lat) / (top - bottom), mask = landMasks[r];
          const mx = Math.min(mask.width - 1, Math.max(0, Math.floor(uu * mask.width))), my = Math.min(mask.height - 1, Math.max(0, Math.floor(vv * mask.height)));
          coverage[y * width + x] = 1; if (mask.data[(my * mask.width + mx) * 4] >= 128) land.data.set([255,255,255,255], index);
          if (cam.position.length() - 1 < .5) {source = details[r]; u = uu; v = vv;} break;
        }
        const tx = Math.min(source.width - 1, Math.max(0, Math.floor(u * source.width))), ty = Math.min(source.height - 1, Math.max(0, Math.floor(v * source.height))), sample = (ty * source.width + tx) * 4;
        for (let channel = 0; channel < 3; channel++) out.data[index + channel] = Math.round(source.data[sample + channel] * factor);
        out.data[index + 3] = 255;
      }
      return {image: out, land, land_mask_coverage: coverage,longitude,latitude,validRay};
    }
    function initializeOverlay(renderer, target, mode) {
      Object.assign(renderer, {w: width, h: height, camera: camera.camera, ctx: target.getContext('2d', {willReadFrequently: true}),
        project: originalProject, infographicReady: true, infographicFontsReady: true, infographicProfile: nativeProfile,
        infographicPrepared: new Map(scene.infographic.geometries.map(row => [row.id, infographic.prepareInfographicGeometry(row)]))});
      if (mode === 'V023') Object.assign(renderer, {boldReady: true, boldProfile,
        boldPrepared: new Map(scene.bold_infographic.geometries.map(row => [row.id, infographic.prepareInfographicGeometry(row)]))});
      if (mode === 'V024') Object.assign(renderer, {terrainReady: true, terrainProfile: profile,
        terrainPrepared: new Map(scene.bold_infographic.geometries.map(row => [row.id, terrain.prepareTerrainInfographicGeometry(row)]))});
      return renderer;
    }
    function withoutNativeAnnotationHeads(ctx){
      let arcPath=false;
      return new Proxy(ctx,{get(target,key){
        if(key==='fillText'||key==='strokeText')return ()=>undefined;
        if(key==='beginPath')return (...args)=>{arcPath=false;return target.beginPath(...args);};
        if(key==='arc')return (...args)=>{arcPath=true;return target.arc(...args);};
        if(key==='fill'||key==='stroke')return (...args)=>arcPath?undefined:target[key](...args);
        const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;
      },set(target,key,value){return Reflect.set(target,key,value,target);}});
    }
    const oldScene = structuredClone(scene); delete oldScene.terrain_infographic;
    const selections = [['WIDE',75,'COUNTRY_EGY'],['SUEZ_REGIONAL',135,'COUNTRY_EGY'],
      ['SUEZ_EVENT_VIEW',240,'COUNTRY_EGY'],['SINGAPORE_REGIONAL',570,'COUNTRY_SGP'],
      ['SINGAPORE_EVENT_VIEW',650,'COUNTRY_SGP'],['SUEZ_DARK_STRESS',240,'COUNTRY_EGY',.25],
      ['SUEZ_BRIGHT_STRESS',240,'COUNTRY_EGY',1.15]];
    for (const [name, frame, id, factor = 1] of selections) {
      const firstCaseCheck=checks.length;
      camera.update(frame / fps); const source = mapPixels(camera.camera, factor);
      canvas.getContext('2d').putImageData(source.image, 0, 0); capture(name + '_SOURCE');
      const before = makeCanvas(), after = makeCanvas();
      for (const c of [before, after]) c.getContext('2d').putImageData(source.image, 0, 0);
      const oldRenderer = initializeOverlay(bold.createBoldInfographicRenderer(oldScene, plan), before, 'V023');
      const newRenderer = initializeOverlay(terrain.createTerrainInfographicRenderer(scene, plan), after, 'V024');
      oldRenderer.overlay(frame / fps); newRenderer.overlay(frame / fps);
      capture(name + '_BEFORE_V023_INTEGRATED', before); capture(name + '_AFTER_V024_INTEGRATED', after);
      const annotationControls={};
      for(const [version,Renderer,mode,integrated] of [['V023',bold.createBoldInfographicRenderer,'V023',before],['V024',terrain.createTerrainInfographicRenderer,'V024',after]]){
        const control=makeCanvas();control.getContext('2d').putImageData(source.image,0,0);
        const renderer=initializeOverlay(Renderer(mode==='V024'?scene:oldScene,plan),control,mode);renderer.ctx=withoutNativeAnnotationHeads(renderer.ctx);renderer.overlay(frame/fps);
        const controlPixels=rgba(control),overlayPixels=rgba(integrated);
        annotationControls[version]={markers:renderer.infographicReceipt.markers.filter(row=>row.visible).map(row=>({id:row.id,geometry_id:row.geometry_id,
          pixels:metrics.annotationContrastPixels(controlPixels,overlayPixels,row.box,width,height)})),
          labels:renderer.infographicReceipt.labels.filter(row=>row.opacity>.01&&row.displayed_text).map(row=>({id:row.id,role:row.role,text:row.text,
            pixels:metrics.annotationContrastPixels(controlPixels,overlayPixels,row.box,width,height)}))};
      }
      check(name+'_MARKER_ACTUAL_LOCAL_CONTRAST',annotationControls.V024.markers.length>0&&annotationControls.V024.markers.every(row=>row.pixels.measured_ink_pixels>=24&&row.pixels.p90_rgb_contrast>=.12),{measured:annotationControls.V024.markers});
      check(name+'_TEXT_ACTUAL_LOCAL_CONTRAST',annotationControls.V024.labels.length>0&&annotationControls.V024.labels.every(row=>row.pixels.measured_ink_pixels>=24&&row.pixels.p90_rgb_contrast>=.10),{measured:annotationControls.V024.labels});
      const native = registry.geometries.find(row => row.id === id), prepared = terrain.prepareTerrainInfographicGeometry(native);
      const projected = infographic.projectInfographicGeometry(prepared, camera.camera, width, height), coverageCanvas=polygonMask(projected),mask = rgba(coverageCanvas),nativeEdges=nativeEdgeMask(projected);
      capture(name+'_NATIVE_V024_COVERAGE_MASK',coverageCanvas);
      const edgeCanvas=makeCanvas();edgeCanvas.getContext('2d').putImageData(new ImageData(nativeEdges,width,height),0,0);capture(name+'_NATIVE_SOURCE_EDGE_MASK',edgeCanvas);
      const coverage = metrics.interiorCoveragePixels(mask,nativeEdges,width,height);
      check(name+'_NO_INTERNAL_COVERAGE_SEAMS',coverage.partial_coverage_away_from_native_boundary_pixels===0,{measured:coverage});
      const fillOnBase = makeCanvas(); fillOnBase.getContext('2d').putImageData(source.image, 0, 0);
      const fillReceipt = draw(projected, 'PRIMARY', fillOnBase, {drawBoundary: false});
      const primary = metrics.terrainRegionPixels(source.image.data, rgba(fillOnBase), mask, width, height,
        {stride: 1, expectedLuminanceScale: fillReceipt.multiply_gray_factor});
      primary.local_tone = {requested_scale: fillReceipt.luminance_scale, browser_applied_scale: fillReceipt.multiply_gray_factor,
        browser_multiply_color: fillReceipt.multiply_color};
      const oldFill = makeCanvas(); oldFill.getContext('2d').putImageData(source.image, 0, 0);
      const oldProjection=infographic.projectInfographicGeometry(infographic.prepareInfographicGeometry(native),camera.camera,width,height);
      bold.drawBoldRegionLayer(oldFill.getContext('2d'), oldProjection, bold.boldRegionStyle(boldProfile, 'PRIMARY'), {drawBoundary: false, width, height});
      const independentMask=metrics.sourceGeometryMask(native,source.longitude,source.latitude,source.validRay,width,height);
      const sourceGeometryCoverage=metrics.sourceGeometryCoveragePixels(rgba(polygonMask(oldProjection,false)),mask,independentMask,nativeEdges,width,height);
      check(name+'_HEALED_SEAMS_INSIDE_SOURCE_GIS',sourceGeometryCoverage.healed_interior_outside_source_geometry_pixels===0,{measured:sourceGeometryCoverage});
      check(name+'_NO_SOURCE_GIS_INTERIOR_EXPANSION',sourceGeometryCoverage.new_coverage_outside_source_far_from_native_edges_pixels===0,{measured:sourceGeometryCoverage});
      const sourceMaskCanvas=makeCanvas();sourceMaskCanvas.getContext('2d').putImageData(new ImageData(independentMask,width,height),0,0);capture(name+'_INDEPENDENT_SOURCE_GIS_MASK',sourceMaskCanvas);
      const previous = metrics.terrainRegionPixels(source.image.data, rgba(oldFill), mask, width, height, {stride: 1});
      const coreCanvas = makeCanvas(); draw(projected, 'PRIMARY', coreCanvas, {drawFill: false, drawGlow: false});
      const core = metrics.boundaryPixelMetrics(rgba(coreCanvas), width, height, projected.segments, {brightCore: true});
      const haloCanvas = glowOnly(projected, 'PRIMARY'), halo = metrics.haloPixelMetrics(rgba(haloCanvas), width, height,
        projected.segments, {nativeEdgeMask:nativeEdges});
      const edge = makeCanvas(); edge.getContext('2d').putImageData(source.image, 0, 0); draw(projected, 'PRIMARY', edge, {drawFill: false});
      const edgeContrast = metrics.outlineContrastPixels(source.image.data, rgba(edge), width, height, projected.segments);
      const fill = makeCanvas(); draw(projected, 'PRIMARY', fill, {drawBoundary: false});
      const containment = metrics.containmentPixelMetrics(rgba(fill), mask, width, height);
      const off = makeCanvas(); off.getContext('2d').drawImage(before, 0, 0);
      terrain.drawTerrainRegionLayer(off.getContext('2d'), projected, null, {width, height});
      const offPixels = metrics.imageDifference(rgba(before), rgba(off), width, height);
      const activeSecondary = scene.bold_infographic.regions.filter(row => row.role === 'SECONDARY'
        && row.primary_geometry_ref === id && row.start_frame <= frame && frame < row.end_frame);
      const secondary = [];
      for (const selection of activeSecondary) {
        const record = registry.geometries.find(row => row.id === selection.geometry_ref);
        const p = infographic.projectInfographicGeometry(terrain.prepareTerrainInfographicGeometry(record), camera.camera, width, height);
        const c = makeCanvas(); c.getContext('2d').putImageData(source.image, 0, 0); const secondaryFill = draw(p, 'SECONDARY', c, {drawBoundary: false});
        const line = makeCanvas(); draw(p, 'SECONDARY', line, {drawFill: false});
        const secondaryMetrics = metrics.terrainRegionPixels(source.image.data, rgba(c), rgba(polygonMask(p)), width, height,
          {expectedLuminanceScale: secondaryFill.multiply_gray_factor});
        secondaryMetrics.local_tone = {requested_scale: secondaryFill.luminance_scale,
          browser_applied_scale: secondaryFill.multiply_gray_factor, browser_multiply_color: secondaryFill.multiply_color};
        secondary.push({geometry_id: record.id, geometry_sha256: record.sha256, visible: p.visible,
          metrics: secondaryMetrics,
          core: metrics.boundaryPixelMetrics(rgba(line), width, height, p.segments, {brightCore: true})});
      }
      const measurable = secondary.filter(row => row.metrics.interior_samples >= 32 && row.core.cross_sections > 0);
      const strongest = [...measurable].sort((a,b) => b.metrics.median_rgb_contrast - a.metrics.median_rgb_contrast)[0];
      const qc = metrics.evaluateTerrainPixels({primary, secondary: strongest?.metrics, core,
        secondaryCore: strongest?.core, halo, edgeContrast, containment, off: offPixels});
      for (const code of ['PRIMARY_NOT_MEASURABLE','PRIMARY_COLOR_NOT_VISIBLE','SOURCE_LUMINANCE_CHANGED',
        'TERRAIN_DETAIL_ATTENUATED','PRIMARY_CORE_NOT_READABLE','BOUNDARY_CONTRAST_WEAK','HALO_UNBOUNDED_OR_DOMINANT',
        'SECONDARY_NOT_VISIBLE','SECONDARY_SOURCE_LUMINANCE_CHANGED','SECONDARY_TERRAIN_DETAIL_ATTENUATED',
        'COLOR_HIERARCHY_REVERSED','BOUNDARY_HIERARCHY_REVERSED','COASTLINE_OR_HOLE_LEAK','OFF_V023_BASELINE_CHANGED']) {
        check(name + '_' + code, !qc.failures.includes(code));
      }
      const inherited = ['markers', 'labels', 'layout'].every(key => JSON.stringify(oldRenderer.infographicReceipt[key]) === JSON.stringify(newRenderer.infographicReceipt[key]));
      check(name + '_NATIVE_MARKER_TEXT_LAYOUT_UNCHANGED', inherited);
      // This independent existing raster coast is NOT inferred from ocean color.
      let coveredFill = 0, rasterOceanFill = 0;
      const fillPixels = rgba(fill);
      for (let pixel = 0; pixel < width * height; pixel++) {
        if (fillPixels[pixel * 4 + 3] < 3 || !source.land_mask_coverage[pixel]) continue;
        coveredFill++; if (!source.land.data[pixel * 4 + 3]) rasterOceanFill++;
      }
      const rasterCoast = {covered_fill_pixels: coveredFill, raster_ocean_or_hole_fill_pixels: rasterOceanFill,
        raster_mismatch_fraction: coveredFill ? rasterOceanFill / coveredFill : null,
        source: 'Existing v018 Natural Earth 1:50m rasterized country union masks',
        raster_texels_per_degree: 60, resolution: [1440,1680],
        scope: 'Separate native-vector versus existing raster coastline observation; pixel-center rasterization and spherical polygon projection differ. Not survey coastline, no ocean-color heuristic.'};
      rasterCoast.source_relative_pixels = metrics.existingLandMaskPixels(source.image.data, rgba(fillOnBase),
        source.land.data, source.land_mask_coverage, width, height);
      const landCanvas = makeCanvas(); landCanvas.getContext('2d').putImageData(source.land, 0, 0); capture(name + '_EXISTING_V018_LANDMASK', landCanvas);
      const allCaseFailures=checks.slice(firstCaseCheck).filter(row=>!row.passed).map(row=>row.id.slice(name.length+1));
      const caseAdmission={...qc,pixel_metric_failures:qc.failures,failures:allCaseFailures,passed:allCaseFailures.length===0};
      cases.push({name, frame, timestamp: frame / fps, preview_only_luminance_stress: factor, geometry_id: id,
        geometry_sha256: native.sha256, camera: {position: camera.camera.position.toArray(), quaternion: camera.camera.quaternion.toArray(), fov: camera.camera.fov},
        fill_tessellation:prepared.fill_tessellation,
        primary, previous_v023: previous, core, halo, edgeContrast, secondary, containment, coverage,sourceGeometryCoverage,annotations:annotationControls,rasterCoast, off: offPixels,
        native_infographic: {markers: newRenderer.infographicReceipt.markers, labels: newRenderer.infographicReceipt.labels, layout: newRenderer.infographicReceipt.layout},
        v024_draw_receipt: newRenderer.terrainInfographicReceipt, qc:caseAdmission});
    }
    camera.update(240 / fps);
    const high = {internal_resolution: [2160,3840], output_resolution: [width,height], roles: {}};
    for (const [role,id] of [['PRIMARY','COUNTRY_EGY'],['SECONDARY','COUNTRY_JOR']]) {
      const record = registry.geometries.find(row => row.id === id), prepared = terrain.prepareTerrainInfographicGeometry(record);
      const input = infographic.projectInfographicGeometry(prepared, camera.camera, 2160, 3840);
      const output = infographic.projectInfographicGeometry(prepared, camera.camera, width, height);
      const c = makeCanvas(2160,3840); draw(input, role, c, {drawFill: false, drawGlow: false});
      const down = makeCanvas(), ctx = down.getContext('2d'); ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high'; ctx.drawImage(c, 0, 0, width, height);
      const measured = metrics.boundaryPixelMetrics(rgba(down), width, height, output.segments, {brightCore: true});
      high.roles[role] = measured; capture('HIGH_DOWNSAMPLED_' + role + '_CORE', down);
      check('HIGH_2160_TO_1080_' + role + '_CORE_WIDTH', measured.cross_sections > 0
        && (role === 'PRIMARY' ? measured.width_px_median >= 6 && measured.width_px_median <= 12
          : measured.width_px_median >= 2 && measured.width_px_median < high.roles.PRIMARY.width_px_median));
    }
    const normal = ([lon,lat]) => new THREE.Vector3(Math.cos(lat*Math.PI/180)*Math.cos(lon*Math.PI/180),Math.sin(lat*Math.PI/180),-Math.cos(lat*Math.PI/180)*Math.sin(lon*Math.PI/180));
    const topologyCamera = coordinate => {const c = new THREE.PerspectiveCamera(40,width/height,.001,100); c.position.copy(normal(coordinate).multiplyScalar(1.6)); c.lookAt(0,0,0); c.updateMatrixWorld(true); return c;};
    const filledAt = (c, coordinate, cam) => {const q = normal(coordinate).multiplyScalar(1.00008).project(cam); return c.getContext('2d').getImageData(Math.round((q.x*.5+.5)*width),Math.round((.5-q.y*.5)*height),1,1).data[3]>3;};
    for (const row of [{id:'COUNTRY_ZAF',center:[27,-30],inside:[24,-30],outside:[28.25,-29.5],name:'REAL_LESOTHO_HOLE_EMPTY'},
      {id:'COUNTRY_IDN',center:[114,-4],inside:[110,-7],outside:[118.5,-6],name:'REAL_MULTIPOLYGON_OCEAN_GAP_EMPTY'}]) {
      const native = registry.geometries.find(record => record.id === row.id), cam = topologyCamera(row.center);
      const p = infographic.projectInfographicGeometry(terrain.prepareTerrainInfographicGeometry(native),cam,width,height), c = makeCanvas();
      draw(p,'PRIMARY',c,{drawBoundary:false}); check(row.name,filledAt(c,row.inside,cam)&&!filledAt(c,row.outside,cam)); capture(row.name,c);
    }
    const fiji = registry.geometries.find(row => row.id === 'COUNTRY_FJI'), prepared = terrain.prepareTerrainInfographicGeometry(fiji);
    const front = infographic.projectInfographicGeometry(prepared,topologyCamera([180,-17]),width,height), back = infographic.projectInfographicGeometry(prepared,topologyCamera([0,17]),width,height), seam = makeCanvas();
    draw(front,'PRIMARY',seam,{drawBoundary:false}); check('REAL_FIJI_SEAM_AND_HORIZON',front.visible&&front.bounds.width<width*.8&&!back.visible); capture('REAL_FIJI_SEAM',seam);
    check('ZERO_WEBGL_CONTEXT_ATTEMPTS',globalThis.__terrainWebGLAttempts===0);
    return {passed:checks.every(row=>row.passed),checks,cases:cases.slice(0,5),luminance_stress_cases:cases.slice(5),
      high_resolution_pixel_scale:high,snapshots,resolution:[width,height],webgl_context_attempts:globalThis.__terrainWebGLAttempts,
      GPU:'NOT_RUN',production_frame_render:'NOT_RUN',visual_quality_acceptance:'NOT_RUN',
      native_marker_text_layout:'Actual original overlay and actual deployed fonts executed; no authored replacement labels',
      scope:'CPU native frozen-camera source texture projection + exact production Canvas overlay. GPU shader/lighting/cloud/atmosphere absent; not CURRENT MP4 or GPU AFTER.'};
  }, {detectorOnly});

  for (const snapshot of receipt.snapshots || []) {
    const bytes = Buffer.from(snapshot.png.split(',')[1], 'base64');
    fs.writeFileSync(path.join(output, snapshot.name + '.png'), bytes);
    snapshot.file = snapshot.name + '.png'; snapshot.sha256 = sha(bytes); delete snapshot.png;
  }
  receipt.source_sha256s = Object.fromEntries(Object.entries(servedBytes).map(([url, bytes]) => [url, sha(bytes)]));
  receipt.executed_source_snapshots = sourceSnapshots;
  receipt.chromium_version = browser.version(); receipt.launch_flags = ['--no-sandbox','--disable-gpu','--disable-gpu-compositing'];
  if (detectorOnly) {
    console.log(JSON.stringify(receipt)); assert(receipt.passed, 'TERRAIN_DETECTOR_FAILED');
  } else {
    fs.writeFileSync(path.join(output,'scene-plan.json'),JSON.stringify(plan,null,2)+'\n');
    const escapeHTML = value => String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
    const sections = receipt.cases.map(row => `<section><h2>${escapeHTML(row.name)} — F${row.frame}</h2><div class="row"><figure><figcaption>CPU v023 BEFORE</figcaption><img src="${row.name}_BEFORE_V023_INTEGRATED.png"></figure><figure><figcaption>CPU v024 AFTER</figcaption><img src="${row.name}_AFTER_V024_INTEGRATED.png"></figure></div></section>`).join('');
    const contactHTML = `<!doctype html><meta charset="utf-8"><style>body{margin:24px;background:#e9edf1;color:#132230;font:16px sans-serif}h1{font-size:24px}h2{font-size:18px}figure{margin:0}.row{display:flex;gap:18px}img{display:block;width:270px;height:480px}figcaption{font-weight:bold;margin-bottom:8px}section{margin-bottom:26px}</style><h1>v024 CPU native overlay comparison</h1><p>Frozen native camera + real source textures + original marker/text/layout/fonts.<br>GPU shader lighting, cloud and atmosphere are absent. This is not CURRENT MP4 or a GPU AFTER.<br>Actual captured-pixel admission: ${receipt.checks.filter(row=>row.passed).length}/${receipt.checks.length}. Human target review and NVIDIA acceptance are separate.<br>Geometry-local tone: PRIMARY ${JSON.parse(servedBytes['/profile.json']).geometry.PRIMARY.luminance_scale}, SECONDARY ${JSON.parse(servedBytes['/profile.json']).geometry.SECONDARY.luminance_scale}; raw source/detail loss retained in metrics.json.</p>${sections}`;
    fs.writeFileSync(path.join(output,'contact-sheet.html'),contactHTML);
    const inlineContact = contactHTML.replace(/src="([^"]+\.png)"/g,(_,file)=>'src="data:image/png;base64,'+fs.readFileSync(path.join(output,file)).toString('base64')+'"');
    const contactPage = await browser.newPage({viewport:{width:900,height:1000}});
    await contactPage.setContent(inlineContact);await contactPage.evaluate(()=>Promise.all([...document.images].map(img=>img.decode())));
    await contactPage.screenshot({path:path.join(output,'contact-sheet.png'),fullPage:true});await contactPage.close();
    receipt.contact_sheet = {file:'contact-sheet.png',sha256:sha(fs.readFileSync(path.join(output,'contact-sheet.png'))),
      scope:'CPU source + native overlay only, not an uploaded MP4 analysis or actual GPU quality proof'};
    fs.writeFileSync(path.join(output,'metrics.json'),JSON.stringify(receipt,null,2)+'\n');
    console.log(JSON.stringify({passed:receipt.passed,checks:receipt.checks.length,frames:receipt.cases.length,output,GPU:'NOT_RUN'}));
    if (!args.includes('--review-iteration')) assert(receipt.passed,'TERRAIN_CANVAS_PIXEL_QC_FAILED');
  }
} catch(error){
  if(!detectorOnly){
    let progress={snapshots:[],checks:[],cases:[]};
    if(page)try{progress=await page.evaluate(()=>globalThis.__terrainCPUProgress??{snapshots:[],checks:[],cases:[]});}catch{}
    for(const snapshot of progress.snapshots){
      const bytes=Buffer.from(snapshot.png.split(',')[1],'base64');fs.writeFileSync(path.join(output,snapshot.name+'.png'),bytes);
      snapshot.file=snapshot.name+'.png';snapshot.sha256=sha(bytes);delete snapshot.png;
    }
    const failure={passed:false,GPU:'NOT_RUN',production_frame_render:'NOT_RUN',visual_quality_acceptance:'NOT_RUN',error:String(error),
      source_sha256s:Object.fromEntries(Object.entries(servedBytes).map(([url,bytes])=>[url,sha(bytes)])),executed_source_snapshots:sourceSnapshots,
      partial_progress:progress,scope:'Failure-safe native CPU preview records only. No failed run is admitted or presented as GPU output.'};
    fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify(failure,null,2)+'\n');
  }
  throw error;
} finally {
  if (browser) await browser.close(); await new Promise(resolve => server.close(resolve));
}
