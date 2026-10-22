/** Actual browser raster COMPONENT tests only: no native map, Studio or movie. */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {authoredPinSvg} from '../director_events.mjs';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../../..'),ns=path.resolve(here,'..');
const output=process.env.RD_COMPONENT_OUTPUT ?? '/workspace/reference-director-v1-private-20261022/event-components';
fs.mkdirSync(output,{recursive:true});fs.mkdirSync(path.join(ns,'assets'),{recursive:true});
const require=createRequire('/workspace/universal-data-pipeline-v1-private-20261022/node-deps/package.json');
const {chromium}=require('playwright');
const font=path.join(root,'web/fonts/NotoSansCJKkr-Bold.otf'),glyph=path.join(root,'web/map_infographic_v1/glyph_atlas.mjs');
const eventContract=path.join(root,'web/map_infographic_v1/event_contract_v1.mjs');
const dataModule=(file)=>`data:text/javascript;base64,${fs.readFileSync(file).toString('base64')}`;
const directorCode=fs.readFileSync(path.join(ns,'director_events.mjs'),'utf8').replace("'../../web/map_infographic_v1/event_contract_v1.mjs'",JSON.stringify(dataModule(eventContract))).replace("'../../web/map_infographic_v1/glyph_atlas.mjs'",JSON.stringify(dataModule(glyph)));
const svgs=['HERO','CONTEXT'].map(size=>({size,svg:authoredPinSvg(size)}));
for(const {size,svg} of svgs)fs.writeFileSync(path.join(ns,'assets',`reference-pin-${size.toLowerCase()}.svg`),svg);
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
try{
 const page=await browser.newPage({viewport:{width:1080,height:900}});
 await page.goto('about:blank');
 const report=await page.evaluate(async({svgs,fontBase64,glyphCode,directorCode})=>{
  const face=new FontFace('Gate1Bold',`url(data:font/otf;base64,${fontBase64})`);await face.load();document.fonts.add(face);await document.fonts.ready;
  const {createMeasuredGlyph}=await import(`data:text/javascript;base64,${glyphCode}`);
  const {measureDirectorWord,labelPlacement}=await import(`data:text/javascript;base64,${directorCode}`);
  const results=[];
  const title=document.createElement('h2');title.textContent='COMPONENT UNIT DRAW ONLY — NOT STUDIO / MAP OUTPUT';document.body.append(title);
  for(const {size,svg} of svgs){
   const image=new Image();image.src=`data:image/svg+xml;base64,${btoa(svg)}`;await image.decode();
   const canvas=document.createElement('canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;const c=canvas.getContext('2d',{willReadFrequently:true});c.drawImage(image,0,0);
   canvas.style.background='repeating-conic-gradient(#294458 0% 25%, #476278 0% 50%) 0 0 / 16px 16px';canvas.style.display='block';
   const pixels=c.getImageData(0,0,canvas.width,canvas.height).data,w=canvas.width,h=canvas.height;
   const cx=w/2,cy=56*h/151,centerIndex=(Math.floor(cy)*w+Math.floor(cx))*4;
   let alphaPixels=0,x0=w,y0=h,x1=-1,y1=-1,outlinePixels=0;
   for(let y=0;y<h;y++)for(let x=0;x<w;x++){
    const i=(y*w+x)*4;if(!pixels[i+3])continue;alphaPixels++;x0=Math.min(x0,x);x1=Math.max(x1,x);y0=Math.min(y0,y);y1=Math.max(y1,y);
    if(pixels[i]<200&&pixels[i+1]<200&&pixels[i+2]<40)outlinePixels++;
   }
   let left=Math.floor(cx),right=left;while(left>0&&pixels[(Math.floor(cy)*w+left-1)*4+3]===0)left--;while(right<w-1&&pixels[(Math.floor(cy)*w+right+1)*4+3]===0)right++;
   const declaredHole=size==='HERO'?68:29,transparentRun=right-left+1,centerAlpha=pixels[centerIndex+3],pass=centerAlpha===0&&Math.abs(transparentRun-declaredHole)<=2&&alphaPixels>100&&outlinePixels>0;
   results.push({component:size,width:w,height:h,alphaBounds:[x0,y0,x1+1,y1+1],alphaPixels,centerAlpha,transparentRunPixels:transparentRun,declaredHolePixels:declaredHole,outlinePixels,strokeWidthAttribute:1.5,pass});
   const caption=document.createElement('p');caption.textContent=`${size}: ${w}×${h}, transparent hole, bottom-tip anchor`;document.body.append(caption,canvas);
  }
  const words=['세우타','멜리야','85 m'];
  const glyphs=words.map(word=>{
   const fontSize=word==='85 m'?52:48,glyph=createMeasuredGlyph(word,{fontSize,fontFamily:'Gate1Bold',outlineRadius:word==='85 m'?2:16,maxLines:1});
   const caption=document.createElement('p');caption.textContent=`Existing pinned-font glyph raster: ${word}`;glyph.canvas.style.background='#294458';glyph.canvas.style.display='block';document.body.append(caption,glyph.canvas);
   const measured=measureDirectorWord(word,{fontPx:fontSize,haloRadiusPx:word==='85 m'?2:16}),placement=labelPlacement(measured,[400,800]);
   const [l,,r,d]=measured.fullWordInkBounds,inkCenter=(placement.left+l+placement.left+r)/2,actualBottom=placement.baseline+d;
   return {text:word,fontSize,fontFamily:glyph.fontFamily,alphaBounds:glyph.alphaBounds,alphaPixels:glyph.alphaPixels,atlasDimensions:glyph.atlasDimensions,lines:glyph.lines,alphaTouchesEdge:glyph.alphaTouchesEdge,fullWordInkBounds:measured.fullWordInkBounds,fullWordCenteredAt:inkCenter,actualInkBottom:actualBottom,pass:glyph.fits&&!glyph.alphaTouchesEdge&&glyph.lines.length===1&&inkCenter===400&&actualBottom===724};
  });
  return {status:'COMPONENT_UNIT_DRAW_ONLY',nativeMapRendered:false,studioPathExecuted:false,nvidiaVerified:false,pins:results,glyphs,pass:results.every(r=>r.pass)&&glyphs.every(r=>r.pass)};
 },{svgs,fontBase64:fs.readFileSync(font).toString('base64'),glyphCode:fs.readFileSync(glyph).toString('base64'),directorCode:Buffer.from(directorCode).toString('base64')});
 report.font={path:'web/fonts/NotoSansCJKkr-Bold.otf',sha256:crypto.createHash('sha256').update(fs.readFileSync(font)).digest('hex'),licensePath:'web/fonts/LICENSE_Noto_CJK.txt',licenseSha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'web/fonts/LICENSE_Noto_CJK.txt'))).digest('hex'),originalReferenceFontRecovered:false};
 report.command='node recovery/reference-director-v1/tools/check_event_components.mjs';
 fs.writeFileSync(path.join(output,'EVENT_COMPONENT_DRAW.json'),JSON.stringify(report,null,2)+'\n');
 await page.screenshot({path:path.join(output,'EVENT_COMPONENT_DRAW.png'),fullPage:true});
 console.log(JSON.stringify(report,null,2));
 if(!report.pass)process.exitCode=1;
}finally{await browser.close();}
