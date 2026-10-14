/** PRIVATE: actual canvas flag/tablet review, not a scene or historical proof. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
const root=path.dirname(fileURLToPath(import.meta.url)),engine=path.resolve(root,'../..'),repo=path.resolve(engine,'..');
const require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
assert.equal(process.version,'v24.19.0');assert.equal(require('playwright/package.json').version,'1.62.1');
const allowed=new Map([
 ['/modules/national_unit_badge_v1.mjs',path.join(engine,'web/map_infographic_v1/national_unit_badge_v1.mjs')],
 ['/modules/reference_combat_overlay_v2.mjs',path.join(engine,'web/map_infographic_v1/reference_combat_overlay_v2.mjs')],
 ['/fixtures/NATIONAL_FLAG_PROFILES.json',path.join(root,'fixtures/NATIONAL_FLAG_PROFILES.json')],
]);
const output=path.join(root,'evidence/national_units');fs.mkdirSync(output,{recursive:true});
const browser=await require('playwright').chromium.launch({executablePath:'/usr/bin/chromium',headless:true,
 args:['--no-sandbox','--disable-dev-shm-usage']});
try{
 assert.equal(browser.version(),'154.0.8037.57');
 const page=await browser.newPage({viewport:{width:1440,height:940},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.route('http://127.0.0.1:8799/**',async route=>{
  const pathname=new URL(route.request().url()).pathname;
  if(pathname==='/')return route.fulfill({status:200,contentType:'text/html',body:'<!doctype html><html><body><canvas id="sheet" width="1440" height="940"></canvas></body></html>'});
  const file=allowed.get(pathname);if(!file)return route.fulfill({status:404,body:'NOT_IN_PRIVATE_FLAG_SHEET_ALLOWLIST'});
  return route.fulfill({status:200,contentType:pathname.endsWith('.json')?'application/json':'text/javascript',body:fs.readFileSync(file)});
 });
 await page.goto('http://127.0.0.1:8799/');
 const result=await page.evaluate(async()=>{
  const {createNationalUnitBadgeArtwork,measureNationalUnitBadge}=await import('/modules/national_unit_badge_v1.mjs');
  const fixture=await(await fetch('/fixtures/NATIONAL_FLAG_PROFILES.json')).json();
  const canvas=document.querySelector('canvas'),context=canvas.getContext('2d');
  context.fillStyle='#111d23';context.fillRect(0,0,canvas.width,canvas.height);
  context.font='25px sans-serif';context.fillStyle='#dbe2d3';context.fillText('PRIVATE — ORIGINAL WORLD ENGINE NATIONAL TABLETS / NO VIDEO TEXT',28,38);
  const rows=[],artwork=[];
  Object.entries(fixture.profiles).forEach(([id,profile],index)=>{
   const x=24+(index%4)*356,y=60+Math.floor(index/4)*410;
   context.fillStyle=index<4?'#643925':'#432b67';context.fillRect(x,y,340,390);
   context.fillStyle='#e7e9e0';context.font='17px sans-serif';context.fillText(id,x+12,y+25);
   const image=createNationalUnitBadgeArtwork(profile,256);
   context.drawImage(image,x+60,y+38,220,220);
   context.drawImage(image,x+30,y+258,104,104);context.drawImage(image,x+186,y+269,96,96);
   context.fillStyle='#d7dfd8';context.font='14px sans-serif';context.fillText('104px actual output',x+20,y+375);
   context.fillText('96px candidate',x+173,y+375);
   const sample=document.createElement('canvas');sample.width=sample.height=104;
   const sampleContext=sample.getContext('2d');sampleContext.drawImage(image,0,0,104,104);
   const pixels=sampleContext.getImageData(0,0,104,104).data;
   let opaque=0,visible=0,min=[104,104],max=[-1,-1];
   for(let pixel=0;pixel<104*104;pixel++)if(pixels[pixel*4+3]>=8){
    visible++;if(pixels[pixel*4+3]>=240)opaque++;
    const px=pixel%104,py=Math.floor(pixel/104);min[0]=Math.min(min[0],px);min[1]=Math.min(min[1],py);
    max[0]=Math.max(max[0],px);max[1]=Math.max(max[1],py);
   }
   const measurement=measureNationalUnitBadge({sizePx:104,aspectRatio:profile.aspect_ratio});
   const full=image.getContext('2d'),flagHeight=.64/profile.aspect_ratio,
    flagLeft=128-.32*256,flagTop=128+(-.245-(flagHeight-.36)/2)*256;
   const sampleFlag=(x,y)=>Array.from(full.getImageData(Math.floor(flagLeft+x*flagHeight*256),
    Math.floor(flagTop+y*flagHeight*256),1,1).data);
   const colorSamples=profile.traits.taegeuk?{upperTaegeuk:sampleFlag(.75,.3),lowerTaegeuk:sampleFlag(.75,.7)}:{};
   rows.push({id,country_id:profile.country_id,traits:profile.traits,default_role:profile.default_role,colorSamples,
    measured_support:[...min,...max],visible_pixels:visible,opaque_pixels:opaque,
    actual_visible_width_px:max[0]-min[0]+1,actual_visible_height_px:max[1]-min[1]+1,
    flag_width_px:measurement.flagWidthPx,flag_height_px:measurement.flagHeightPx,
    reused_layout_support_contains_art:measurement.conservativeSupportWithinReusedOctagon});
   artwork.push({id,png:image.toDataURL('image/png')});
  });
  context.font='20px sans-serif';context.fillStyle='#d2ddd6';
  context.fillText('Modern public: ROK / US50 / DPRK / PRC / RUS. Historical-only: US48 / USSR with aviation role.',28,908);
  return {png:canvas.toDataURL('image/png'),rows,artwork};
 });
 assert.deepEqual(errors,[]);
 const save=(name,data)=>fs.writeFileSync(path.join(output,name),Buffer.from(data.split(',')[1],'base64'));
 save('PRIVATE_NATIONAL_FLAG_TABLETS.png',result.png);
 for(const item of result.artwork)save(item.id+'.png',item.png);
 const report={schema:'PRIVATE_NATIONAL_FLAG_ARTWORK_PROBE_V1',method:'ACTUAL_PINNED_CHROMIUM_CANVAS',
  profiles:result.rows,sourceIconArtworkCopied:false,noVideoText:true,historicalPolicyCertificate:false,
  technicalResult:'PASS',visualQualityResult:'PENDING_ACTUAL_IMAGE_REVIEW'};
 fs.writeFileSync(path.join(output,'ARTWORK_PROBE.json'),JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify(report));
}finally{await browser.close();}
