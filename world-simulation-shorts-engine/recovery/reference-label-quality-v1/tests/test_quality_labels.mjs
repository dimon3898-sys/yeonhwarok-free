/** New opt-in consumer tests only; no capture, browser, GPU or old suite run. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {validateLabelSpec} from '../../universal-presentation-v2/presentation_labels.mjs';
import {layoutLabels,paintLabels,createPresentationLabelPass} from '../../universal-presentation-v2/presentation_label_layer.mjs';

const scene={timing:{fps:30,total_frames:150},locations:[{id:'WINDHOEK',anchor:[17.083546,-22.570006]}]};
const highlights=[{id:'CITY',locationId:'WINDHOEK',startFrame:0,endFrame:150}];
const base={id:'city',role:'EVENT',text:'빈트후크',locationId:'WINDHOEK',eventId:'CITY',startFrame:10,endFrame:145,revealFrames:8,exitFrames:8,priority:100};
const normalized=extra=>validateLabelSpec({enabled:true,items:[{...base,...extra}]},{scene,highlights}).items;
const measure=(text,font)=>({width:[...text].length*Number.parseFloat(font)*.75});
const layout=(items,frame=40,extra={})=>layoutLabels({items,frame,project:()=>[540,960],width:1080,height:1920,measureText:measure,...extra});

function recorder(){
 const calls=[],stack=[];
 const context={globalAlpha:1,font:'',shadowBlur:0,shadowColor:'',fillStyle:'',strokeStyle:'',lineWidth:1,textAlign:'',textBaseline:'',
  save(){stack.push(Object.fromEntries(Object.entries(this).filter(([,v])=>typeof v!=='function')));},
  restore(){Object.assign(this,stack.pop());},
  measureText(text){return{width:[...text].length*42};},
 };
 for(const method of ['setTransform','clearRect','beginPath','rect','clip','moveTo','lineTo','stroke','fill','bezierCurveTo','closePath','arc','fillRect','strokeRect','translate','scale'])context[method]=(...args)=>calls.push({method,args,alpha:context.globalAlpha});
 for(const method of ['fillText','strokeText'])context[method]=(...args)=>calls.push({method,args,alpha:context.globalAlpha,shadowBlur:context.shadowBlur,shadowColor:context.shadowColor,fillStyle:context.fillStyle});
 return{context,calls};
}
globalThis.Path2D=class Path2D{constructor(data){this.data=data;}};

test('legacy normalized contract and layout do not acquire reference effects',()=>{
 const items=normalized({});
 assert.deepEqual(items,[{...base,anchor:[...scene.locations[0].anchor]}]);
 const row=layout(items).drawn[0];
 assert.equal(row.fontSize,44);assert.equal(row.style,undefined);assert.equal(row.pinScale,undefined);
 assert.deepEqual(row.pinBox,[527,926,553,961]);
 const {context,calls}=recorder();paintLabels(context,layout(items));
 assert.equal(calls.filter(x=>x.method==='fillText').length,1);
 assert.equal(calls.some(x=>x.shadowBlur>0),false);
 assert.equal(calls.some(x=>x.method==='fill'&&x.args[1]==='evenodd'),false);
});

test('reference style is explicit, closed and must hold after final glyph',()=>{
 for(const extra of [{pin:'HERO'},{reveal:'GRAPHEME_POP'},{style:'OTHER'},{style:'REFERENCE_V1',pin:'URL'},{style:'REFERENCE_V1',reveal:'COUNT_UP'}])assert.throws(()=>normalized(extra));
 assert.throws(()=>normalized({style:'REFERENCE_V1',reveal:'GRAPHEME_POP',endFrame:30,revealFrames:1,exitFrames:5}),/GLYPH_REVEAL_HOLD_REQUIRED/);
 const [row]=normalized({style:'REFERENCE_V1'});assert.equal(row.pin,'CONTEXT');assert.equal(row.reveal,undefined);
});

test('full-size hero footprint is reserved while its existing pop curve plays',()=>{
 const items=normalized({style:'REFERENCE_V1',pin:'HERO',reveal:'GRAPHEME_POP'}),start=layout(items,10).drawn[0],mid=layout(items,15).drawn[0],end=layout(items,30).drawn[0];
 assert.deepEqual(start.box,end.box);assert.deepEqual(start.pinBox,[480,807,600,962]);
 assert.deepEqual(start.pinBox,end.pinBox);assert.equal(start.pinScale,0);assert.ok(mid.pinScale>0&&mid.pinScale<1);assert.equal(end.pinScale,1);
 assert.ok(end.connector[1][1]<end.pinBox[1]);
 assert.equal(end.fontSize,56);
});

test('current camera projection moves reference pin and full word together',()=>{
 const items=normalized({style:'REFERENCE_V1',pin:'HERO'}),a=layout(items),b=layout(items,41,{project:()=>[600,1000],previousLayout:a});
 assert.deepEqual(b.drawn[0].projected,[600,1000]);
 assert.deepEqual(b.drawn[0].box.map((v,i)=>v-a.drawn[0].box[i]),[60,40,60,40]);
 assert.equal(b.drawn[0].slot,a.drawn[0].slot);
});

test('actual reference SVG path and even-odd hole reach the new canvas consumer',()=>{
 const state=layout(normalized({style:'REFERENCE_V1',pin:'HERO'})),{context,calls}=recorder();paintLabels(context,state);
 const pinFill=calls.find(x=>x.method==='fill'&&x.args[1]==='evenodd');
 assert.ok(pinFill.args[0].data.includes('A34 34'));assert.ok(pinFill.args[0].data.includes('151'));
 assert.equal(calls.some(x=>x.method==='arc'),false); // Old painted dark pin hole is not reused.
});

test('per-glyph beats reach canvas calls, reserve full word and attach blue halo',()=>{
 const items=normalized({style:'REFERENCE_V1',pin:'NONE',reveal:'GRAPHEME_POP'}),early=layout(items,12),late=layout(items,30);
 assert.deepEqual(early.drawn[0].box,late.drawn[0].box);
 const a=recorder(),b=recorder();paintLabels(a.context,early);paintLabels(b.context,late);
 assert.deepEqual(a.calls.filter(x=>x.method==='fillText').map(x=>x.args[0]),['빈']);
 assert.deepEqual(b.calls.filter(x=>x.method==='fillText').map(x=>x.args[0]),['빈','트','후','크']);
 assert.ok(b.calls.filter(x=>x.method==='fillText').every(x=>x.shadowBlur===16&&x.shadowColor==='#1764ff'));
 assert.equal(a.calls.some(x=>x.method==='fill'&&x.args[1]==='evenodd'),false);
 assert.ok(a.calls.some(x=>x.method==='scale'&&x.args[0]===.875));
});

test('one-frame country reveal preserves visible card and pin across scene seam',()=>{
 const item={id:'country',role:'COUNTRY',text:'나미비아',locationId:'WINDHOEK',startFrame:0,endFrame:150,revealFrames:1,exitFrames:1,priority:30,style:'REFERENCE_V1',pin:'CONTEXT'};
 const items=validateLabelSpec({enabled:true,items:[item]},{scene,highlights}).items;
 const end=layout(items,149).drawn[0],start=layout(items,0).drawn[0];
 assert.equal(end.alpha,1);assert.equal(start.alpha,1);assert.equal(end.pinScale,1);assert.equal(start.pinScale,1);assert.deepEqual(end.box,start.box);
});

test('overlap reservations and safe viewport still suppress impossible quality placement',()=>{
 const items=normalized({style:'REFERENCE_V1',pin:'HERO'});
 const state=layout(items,40,{protectedBoxes:[[32,32,1048,1888]]});
 assert.equal(state.visibleCount,0);assert.equal(state.suppressed[0].reason,'OVERLAP_WITH_HIGHER_PRIORITY_OR_PRIMARY_EVENT');
 const offscreen=layout(items,40,{project:()=>[5,5]});assert.equal(offscreen.visibleCount,0);assert.equal(offscreen.suppressed[0].reason,'ANCHOR_OUTSIDE_SAFE_VIEWPORT');
});

test('exit timing still clears all reference label and pin pixels after endFrame',()=>{
 const items=normalized({style:'REFERENCE_V1',pin:'HERO',reveal:'GRAPHEME_POP'}),last=layout(items,144),gone=layout(items,145);
 assert.equal(last.drawn[0].alpha,1/8);assert.equal(gone.visibleCount,0);
 const {context,calls}=recorder();paintLabels(context,gone);assert.equal(calls.filter(x=>x.method==='fillText'||x.method==='fill').length,0);
});

test('runtime can decide marker fallback from actual prepared pins before one paint',()=>{
 const {context,calls}=recorder();let renders=0;
 class Resource{dispose(){}}
 class Positioned extends Resource{position={set(){}};updateMatrixWorld(){}}
 const THREE={CanvasTexture:Resource,PlaneGeometry:Resource,MeshBasicMaterial:Resource,Mesh:Positioned,Scene:class{add(){}},OrthographicCamera:Positioned};
 const renderer={autoClear:false,render(){renders++;},resetState(){},getRenderTarget(){return null;}};
 const pass=createPresentationLabelPass({renderer,THREE,canvasFactory:(width,height)=>({width,height,getContext:()=>context})});
 const args={labels:{enabled:true,items:normalized({style:'REFERENCE_V1',pin:'HERO'})},scene,frame:40,project:()=>[540,960]};
 const admitted=pass.prepare(args);assert.equal(admitted.drawn[0].pinDrawn,true);assert.equal(calls.length,0);assert.equal(renders,0);
 const blocked=pass.prepare({...args,protectedBoxes:[[32,32,1048,1888]]});assert.equal(blocked.visibleCount,0);
 assert.throws(()=>pass.drawPrepared(admitted),/PREPARED_LAYOUT_REQUIRED/);
 assert.equal(pass.drawPrepared(blocked),blocked);assert.equal(renders,0);
 const final=pass.prepare(args);assert.equal(pass.drawPrepared(final),final);assert.equal(renders,1);
 assert.throws(()=>pass.drawPrepared(final),/PREPARED_LAYOUT_REQUIRED/);pass.dispose();
 assert.throws(()=>pass.prepare(args),/ENABLED_CONTRACT_REQUIRED/);
});

// Optional local CPU raster evidence. This deliberately checks the new pixel
// consumer with an ASCII fixture, not production Korean font quality or WebGL.
test('CPU raster: hollow hero pin, blue text halo and staggered glyph pixels',{skip:!process.env.QUALITY_CANVAS_MODULE},async()=>{
 const {createRequire}=await import('node:module'),require=createRequire(import.meta.url),{createCanvas,Path2D,GlobalFonts}=require(process.env.QUALITY_CANVAS_MODULE),fs=await import('node:fs/promises');
 const fontPath=process.env.QUALITY_PINNED_FONT??new URL('../../../web/fonts/NotoSansCJKkr-Bold.otf',import.meta.url);
 let fontBytes;try{fontBytes=await fs.readFile(fontPath);}catch(error){if(error.code!=='ENOENT'||process.env.QUALITY_PINNED_FONT_REQUIRED==='1')throw error;}
 if(fontBytes){
  const{createHash}=await import('node:crypto');assert.equal(createHash('sha256').update(fontBytes).digest('hex'),'da1f44844b4d65fc6eef82a0979404a38c78a4a5639b8e9ecf3590dc4cb880b0');
  assert.ok(GlobalFonts.register(fontBytes,'Gate1Bold'));
 }
 globalThis.Path2D=Path2D;
 const actual=await import('../../universal-presentation-v2/presentation_label_layer.mjs?cpu-raster');
 const canvas=createCanvas(1080,1920),context=canvas.getContext('2d');
 const items=normalized({text:fontBytes?'빈트후크':'WIND',style:'REFERENCE_V1',pin:'HERO',reveal:'GRAPHEME_POP'});
 const state=actual.layoutLabels({items,frame:40,project:()=>[540,960],measureText:(text,font)=>{context.font=font;return context.measureText(text);}});
 // Make the CPU fixture font explicit; no substitute production font is claimed.
 if(!fontBytes)state.drawn[0].font='56px sans-serif';actual.paintLabels(context,state);
 const pixel=(x,y)=>[...context.getImageData(x,y,1,1).data];
 assert.equal(pixel(540,865)[3],0);assert.ok(pixel(491,865)[3]>240);
 assert.ok(pixel(491,865)[0]>200&&pixel(491,865)[1]>180&&pixel(491,865)[2]<50);
 const row=state.drawn[0],x=Math.floor(row.box[0]),y=Math.floor(row.box[1]),w=Math.ceil(row.box[2])-x,h=Math.ceil(row.box[3])-y,data=context.getImageData(x,y,w,h).data;
 let blue=0,white=0;for(let i=0;i<data.length;i+=4){if(data[i+2]>data[i]+50&&data[i+2]>data[i+1]+30&&data[i+3]>10)blue++;if(data[i]>220&&data[i+1]>220&&data[i+2]>220&&data[i+3]>150)white++;}
 assert.ok(blue>100);assert.ok(white>100);
 const early=actual.layoutLabels({items,frame:16,project:()=>[540,960],measureText:(text,font)=>{context.font=font;return context.measureText(text);}});if(!fontBytes)early.drawn[0].font='56px sans-serif';
 actual.paintLabels(context,early);
 const earlyData=context.getImageData(x,y,w,h).data;let earlyWhite=0;for(let i=0;i<earlyData.length;i+=4)if(earlyData[i]>220&&earlyData[i+1]>220&&earlyData[i+2]>220&&earlyData[i+3]>20)earlyWhite++;
 assert.ok(earlyWhite>0&&earlyWhite<white);
 if(process.env.QUALITY_PIXEL_OUTPUT){actual.paintLabels(context,state);await fs.writeFile(process.env.QUALITY_PIXEL_OUTPUT,await canvas.encode('png'));}
 let legacyPixelEquivalent=null;
 if(process.env.QUALITY_BASELINE_LABEL_LAYER){
  const {pathToFileURL}=await import('node:url'),old=await import(pathToFileURL(process.env.QUALITY_BASELINE_LABEL_LAYER)),{createHash}=await import('node:crypto');
  const legacy=normalized({text:fontBytes?'빈트후크':'WIND'}),args={items:legacy,frame:40,project:()=>[540,960],measureText:(text,font)=>{context.font=font;return context.measureText(text);}},before=old.layoutLabels(args),after=actual.layoutLabels(args);
  assert.deepEqual(after,before);old.paintLabels(context,before);const beforeHash=createHash('sha256').update(context.getImageData(0,0,1080,1920).data).digest('hex');
  actual.paintLabels(context,after);const afterHash=createHash('sha256').update(context.getImageData(0,0,1080,1920).data).digest('hex');assert.equal(afterHash,beforeHash);legacyPixelEquivalent=true;
 }
 console.log(JSON.stringify({scope:fontBytes?'CPU_COMPONENT_PIXELS_PINNED_KOREAN_FONT':'CPU_COMPONENT_PIXELS_ASCII_FIXTURE_ONLY',blueHaloPixels:blue,settledWhiteGlyphPixels:white,earlyWhiteGlyphPixels:earlyWhite,heroHoleAlpha:0,pinnedKoreanFontVerified:!!fontBytes,legacyPixelEquivalent,GPU:false}));
});
