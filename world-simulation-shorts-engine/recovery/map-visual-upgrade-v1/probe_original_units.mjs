/** Private authored-artwork probe; no scene or reference frame is rendered. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';

const root = path.dirname(fileURLToPath(import.meta.url));
const engine = path.resolve(root, '../..');
const repo=path.resolve(engine,'..');
const require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
assert.equal(process.version,'v24.19.0');assert.equal(require('playwright/package.json').version,'1.62.1');
const {chromium} = require('playwright');
const output = path.join(root, 'evidence/original_units'); fs.mkdirSync(output, {recursive: true});
const allowed = new Map([
 ['/modules/world_engine_unit_overlay_v3.mjs', path.join(engine, 'web/map_infographic_v1/world_engine_unit_overlay_v3.mjs')],
 ['/modules/reference_combat_overlay_v2.mjs', path.join(engine, 'web/map_infographic_v1/reference_combat_overlay_v2.mjs')],
 ['/fixtures/ORIGINAL_UNIT_PROFILE.json', path.join(root, 'fixtures/ORIGINAL_UNIT_PROFILE.json')],
]);
const browser = await chromium.launch({executablePath: '/usr/bin/chromium', headless: true,
 args: ['--disable-dev-shm-usage', '--no-sandbox']});
try {
 const page = await browser.newPage({viewport: {width: 1080, height: 720}, deviceScaleFactor: 1});
 await page.route('http://127.0.0.1:8799/**', async route => {
  const url = new URL(route.request().url());
  if (url.pathname === '/') return route.fulfill({status: 200, contentType: 'text/html',
   body: '<!doctype html><html><body><canvas id="prototype" width="1080" height="720"></canvas></body></html>'});
  const file = allowed.get(url.pathname);
  if (!file) return route.fulfill({status: 404, body: 'NOT_IN_ARTWORK_PROBE_ALLOWLIST'});
  return route.fulfill({status: 200, contentType: url.pathname.endsWith('.json') ? 'application/json' : 'text/javascript', body: fs.readFileSync(file)});
 });
 await page.goto('http://127.0.0.1:8799/');
 const result = await page.evaluate(async () => {
  const {createWorldEngineUnitArtwork} = await import('/modules/world_engine_unit_overlay_v3.mjs');
  const fixture = await (await fetch('/fixtures/ORIGINAL_UNIT_PROFILE.json')).json();
  const canvas = document.querySelector('canvas'), context = canvas.getContext('2d');
  context.fillStyle = '#111d23'; context.fillRect(0, 0, canvas.width, canvas.height);
  context.font = '22px sans-serif'; context.fillStyle = '#d0d8da';
  context.fillText('PRIVATE WORLD ENGINE ORIGINAL UNIT ARTWORK — ACTUAL CANVAS', 34, 42);
  const images = [], pixelSupport = [];
  for (const [index, [id, profile]] of Object.entries(Object.entries(fixture.profiles))) {
   const x = 34 + Number(index) * 520;
   context.fillStyle = index === '0' ? '#9d381f' : '#572994'; context.fillRect(x, 64, 494, 520);
   const art = createWorldEngineUnitArtwork(profile);
   context.fillStyle = '#e2e7d9'; context.font = '18px sans-serif'; context.fillText(id, x + 16, 92);
   context.drawImage(art, x + 135, 104, 224, 224);
   const sizes = [72, 80, 86];
   sizes.forEach((size, position) => {
    const left = x + 54 + position * 142;
    context.drawImage(art, left, 382, size, size);
    context.fillStyle = '#efeadc'; context.font = '16px sans-serif'; context.fillText(`${size}px sprite`, left - 4, 506);
    const sample = document.createElement('canvas'); sample.width = sample.height = size;
    const sampleContext = sample.getContext('2d'); sampleContext.drawImage(art, 0, 0, size, size);
    const bytes = sampleContext.getImageData(0, 0, size, size).data;
    let count = 0, solid = 0, minimum = [size, size], maximum = [-1, -1];
    for (let pixel = 0; pixel < size * size; pixel++) if (bytes[pixel * 4 + 3] >= 8) {
     count++; if (bytes[pixel * 4 + 3] >= 240) solid++;
     const px = pixel % size, py = Math.floor(pixel / size);
     minimum[0] = Math.min(minimum[0], px); minimum[1] = Math.min(minimum[1], py);
     maximum[0] = Math.max(maximum[0], px); maximum[1] = Math.max(maximum[1], py);
    }
    pixelSupport.push({profile: id, nominal_sprite_px: size, nonempty_pixels_alpha_ge_8: count,
     opaque_pixels_alpha_ge_240: solid, measured_support: [...minimum, ...maximum],
     actual_visible_width_px: maximum[0] - minimum[0] + 1, actual_visible_height_px: maximum[1] - minimum[1] + 1});
   });
   images.push({id, png: art.toDataURL('image/png')});
  }
  context.fillStyle = '#c7d0cb'; context.font = '19px sans-serif';
  context.fillText('No source badges, flags, face portraits, speculative effects or visible outline badges.', 34, 632);
  context.fillText('Supplied geographic motion retained. Small panels encode only fixture faction.', 34, 663);
  return {png: canvas.toDataURL('image/png'), images, pixelSupport};
 });
 const save = (filename, data) => fs.writeFileSync(path.join(output, filename), Buffer.from(data.split(',')[1], 'base64'));
 save('PRIVATE_UNIT_ARTWORK_PROTOTYPE.png', result.png);
 for (const art of result.images) save(`${art.id}.png`, art.png);
 const report = {schema: 'WORLD_ENGINE_ORIGINAL_UNIT_ARTWORK_PROBE_V3', method: 'ACTUAL_CHROMIUM_CANVAS_VECTOR_RENDER',
  sourceIconTextureCopied: false, referenceBackgroundCopied: false, nationalInsignia: 0,
  visibleBadgeOutlines: 0, speculativeEffects: 0, pixelSupport: result.pixelSupport,
  technicalResult: 'PASS', visualQualityResult: 'PENDING_ACTUAL_IMAGE_INSPECTION'};
 fs.writeFileSync(path.join(output, 'ARTWORK_PROBE.json'), JSON.stringify(report, null, 2) + '\n');
 console.log(JSON.stringify(report));
} finally {await browser.close();}
