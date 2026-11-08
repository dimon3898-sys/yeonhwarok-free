/** Additive measured glyph layer. The existing camera and renderer own projection.
 * No browser/GPU is created here; a caller supplies its already verified renderer.
 */
import {validateLabelText,REFERENCE_LABEL_STYLE} from './presentation_labels.mjs';
import {authoredPinSvg,popScale,graphemes} from '../reference-director-v1/director_events.mjs';
export const LABEL_LAYER_SCHEMA='WORLD_ENGINE_PRESENTATION_LABEL_LAYER_V1';
export const LABEL_FONT_FAMILY='Gate1Bold';
const roles=Object.freeze({EVENT:3,NUMERIC:2,COUNTRY:1});
const check=(value,code)=>{if(!value)throw Error(code);};
const copy=value=>structuredClone(value);
const point=value=>Array.isArray(value)&&value.length===2&&value.every(Number.isFinite);
const box=value=>Array.isArray(value)&&value.length===4&&value.every(Number.isFinite)&&value[0]<value[2]&&value[1]<value[3];
const within=(p,b)=>p[0]>=b[0]&&p[0]<=b[2]&&p[1]>=b[1]&&p[1]<=b[3];
const overlap=(a,b,gap=0)=>a[0]<b[2]+gap&&a[2]>b[0]-gap&&a[1]<b[3]+gap&&a[3]>b[1]-gap;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const order=(a,b)=>roles[b.role]-roles[a.role]||b.priority-a.priority||(a.id<b.id?-1:a.id>b.id?1:0);
const font=(size)=>`${size}px "${LABEL_FONT_FAMILY}"`;

function alphaAt(item,frame){
 if(frame<item.startFrame||frame>=item.endFrame)return 0;
 return Math.min(1,(frame-item.startFrame+1)/item.revealFrames,(item.endFrame-frame)/item.exitFrames);
}
function validateItem(item){
 check(item&&typeof item==='object'&&Object.hasOwn(roles,item.role)&&typeof item.id==='string'&&typeof item.text==='string'
  &&typeof item.locationId==='string'&&point(item.anchor)&&Math.abs(item.anchor[0])<=180&&Math.abs(item.anchor[1])<=90
  &&Number.isSafeInteger(item.startFrame)&&item.startFrame>=0&&Number.isSafeInteger(item.endFrame)&&item.endFrame>item.startFrame&&item.endFrame<=300
  &&Number.isSafeInteger(item.revealFrames)&&item.revealFrames>=1&&item.revealFrames<=30
  &&Number.isSafeInteger(item.exitFrames)&&item.exitFrames>=1&&item.exitFrames<=30
  &&item.revealFrames+item.exitFrames<item.endFrame-item.startFrame
  &&Number.isSafeInteger(item.priority)&&item.priority>=0&&item.priority<=100,'UP2_LABEL_NORMALIZED_ITEM_REQUIRED');
 validateLabelText(item.text);
 check(item.style===undefined||item.style===REFERENCE_LABEL_STYLE,'UP2_LABEL_STYLE_UNSUPPORTED');
 check(item.style===REFERENCE_LABEL_STYLE||item.pin===undefined&&item.reveal===undefined,'UP2_LABEL_REFERENCE_STYLE_REQUIRED');
 check(item.pin===undefined||['CONTEXT','HERO','NONE'].includes(item.pin),'UP2_LABEL_PIN_UNSUPPORTED');
 check(item.reveal===undefined||item.reveal==='GRAPHEME_POP','UP2_LABEL_REVEAL_UNSUPPORTED');
}
function measuredSize(item,width,height,measure){
 const scale=Math.min(width/1080,height/1920),reference=item.style===REFERENCE_LABEL_STYLE,
  preferred=(reference?{COUNTRY:48,EVENT:56,NUMERIC:52}:{COUNTRY:36,EVENT:44,NUMERIC:52})[item.role]*scale;
 const min=Math.max(10,18*scale),paddingX=(reference?24:16)*scale,paddingY=(reference?24:10)*scale,maxWidth=Math.min(width*.48,width-64*scale);
 let size=Math.max(min,preferred),advance;
 for(let i=0;i<4;i++){
  const result=measure(item.text,font(size),item.role);advance=typeof result==='number'?result:result?.width;
  check(Number.isFinite(advance)&&advance>0,'UP2_LABEL_ACTUAL_GLYPH_METRICS_REQUIRED');
  if(advance+2*paddingX<=maxWidth)break;
  size=Math.max(min,size*(maxWidth-2*paddingX)/advance);
 }
 check(advance+2*paddingX<=maxWidth+1e-6,'UP2_LABEL_TEXT_DOES_NOT_FIT');
 return{width:Math.ceil(advance+2*paddingX),height:Math.ceil(size*1.4+2*paddingY),fontSize:size,font:font(size),scale,paddingX};
}
function candidateOffsets(role,w,h,s,referencePinHeight=null){
 if(referencePinHeight!==null)return[[-w/2,-h-referencePinHeight-12*s],[70*s,-h-40*s],[-w-70*s,-h-40*s],[-w/2,44*s],[70*s,44*s],[-w-70*s,44*s]];
 const gap=44*s;
 if(role==='COUNTRY')return[[-w/2,-h-100*s],[gap,-h-100*s],[-w-gap,-h-100*s],[-w/2,100*s],[gap,100*s],[-w-gap,100*s]];
 if(role==='NUMERIC')return[[gap,44*s],[-w-gap,44*s],[gap,-h-gap],[-w-gap,-h-gap],[-w/2,100*s]];
 return[[gap,-h-gap],[-w-gap,-h-gap],[gap,gap],[-w-gap,gap],[-w/2,-h-100*s]];
}
function closestBoundary(rect,p){return[clamp(p[0],rect[0],rect[2]),clamp(p[1],rect[1],rect[3])];}
// Liang-Barsky entry time, including endpoints. No invented geographic anchor.
function entryTime(a,b,rect){
 let lo=0,hi=1;const dx=b[0]-a[0],dy=b[1]-a[1];
 for(const[p,q]of [[-dx,a[0]-rect[0]],[dx,rect[2]-a[0]],[-dy,a[1]-rect[1]],[dy,rect[3]-a[1]]]){
  if(p===0){if(q<0)return null;continue;}
  const r=q/p;if(p<0)lo=Math.max(lo,r);else hi=Math.min(hi,r);if(lo>hi)return null;
 }
 return lo;
}
function connectorFor(rect,anchor,protectedBoxes,placed,clearance){
 const start=closestBoundary(rect,anchor);let cutoff=1;
 for(const obstacle of protectedBoxes){
  const t=entryTime(start,anchor,obstacle);
  if(t!==null){
   if(!within(anchor,obstacle))return null;
   const length=Math.hypot(anchor[0]-start[0],anchor[1]-start[1]);
   const stop=Math.max(0,t-clearance/Math.max(1,length));
   cutoff=Math.min(cutoff,stop);
  }
 }
 const end=[start[0]+(anchor[0]-start[0])*cutoff,start[1]+(anchor[1]-start[1])*cutoff];
 if(placed.some(row=>entryTime(start,end,row.box)!==null))return null;
 return[start,end];
}

/** Deterministic current-camera layout. Hysteresis retains a valid prior slot;
 * it never retains an old projected point or ignores a new primary obstruction.
 */
export function layoutLabels({items,frame,project,width=1080,height=1920,safeArea,protectedBoxes=[],measureText,previousLayout=null}={}){
 check(Array.isArray(items)&&items.length<=16&&new Set(items.map(x=>x?.id)).size===items.length,'UP2_LABEL_ITEM_CAPACITY');
 check(Number.isSafeInteger(frame)&&frame>=0&&frame<300&&typeof project==='function'&&typeof measureText==='function','UP2_LABEL_FRAME_PROJECTION_REQUIRED');
 check(Number.isSafeInteger(width)&&Number.isSafeInteger(height)&&width>=240&&height>=240&&width<=4096&&height<=4096,'UP2_LABEL_CANVAS_REQUIRED');
 const scale=Math.min(width/1080,height/1920),margin=32*scale,requested=safeArea??[0,0,width,height];
 check(box(requested)&&requested[0]>=0&&requested[1]>=0&&requested[2]<=width&&requested[3]<=height,'UP2_LABEL_SAFE_VIEWPORT_REQUIRED');
 const safe=[Math.max(margin,requested[0]),Math.max(margin,requested[1]),Math.min(width-margin,requested[2]),Math.min(height-margin,requested[3])];
 check(box(safe),'UP2_LABEL_SAFE_VIEWPORT_REQUIRED');
 check(Array.isArray(protectedBoxes)&&protectedBoxes.length<=128,'UP2_LABEL_PROTECTED_BOXES_REQUIRED');
 const protectedRects=protectedBoxes.map(row=>Array.isArray(row)?row:row?.box);
 check(protectedRects.every(box),'UP2_LABEL_PROTECTED_BOXES_REQUIRED');
 items.forEach(validateItem);
 const previous=previousLayout?.frame<=frame?previousLayout:null,slots={},drawn=[],suppressed=[],pins=new Set();
 for(const item of [...items].sort(order)){
  const alpha=alphaAt(item,frame);
  if(alpha<=0){suppressed.push({id:item.id,reason:'OUTSIDE_EVENT_TIMING'});continue;}
  let projected;try{projected=project(item.anchor);}catch{throw Error('UP2_LABEL_PROJECTION_UNSUPPORTED');}
  check(point(projected),'UP2_LABEL_PROJECTION_UNSUPPORTED');
  if(!within(projected,safe)){suppressed.push({id:item.id,reason:'ANCHOR_OUTSIDE_SAFE_VIEWPORT'});continue;}
  const reference=item.style===REFERENCE_LABEL_STYLE,pinStyle=reference?(item.pin??'CONTEXT'):null,
   pinWidth=(pinStyle==='HERO'?116:49)*scale,pinHeight=(pinStyle==='HERO'?151:64)*scale;
  const size=measuredSize(item,width,height,measureText),offsets=candidateOffsets(item.role,size.width,size.height,scale,reference?(pinStyle==='NONE'?0:pinHeight):null);
  if(size.width>safe[2]-safe[0]||size.height>safe[3]-safe[1]){suppressed.push({id:item.id,reason:'LABEL_DOES_NOT_FIT_SAFE_VIEWPORT'});continue;}
  const prior=previous?.slots?.[item.id],indices=offsets.map((_,i)=>i);
  if(Number.isSafeInteger(prior)&&prior>=0&&prior<indices.length)indices.splice(indices.indexOf(prior),1),indices.unshift(prior);
  const pinBox=reference?[projected[0]-pinWidth/2-2*scale,projected[1]-pinHeight-2*scale,projected[0]+pinWidth/2+2*scale,projected[1]+2*scale]:[projected[0]-13*scale,projected[1]-34*scale,projected[0]+13*scale,projected[1]+scale];
  const higherPins=drawn.filter(row=>row.pinDrawn).map(row=>row.pinBox),protectedAndPins=[...protectedRects,...higherPins];
  let selected;
  for(const slot of indices){
   const offset=offsets[slot],x=clamp(projected[0]+offset[0],safe[0],safe[2]-size.width),y=clamp(projected[1]+offset[1],safe[1],safe[3]-size.height);
   const rect=[x,y,x+size.width,y+size.height],gap=10*scale;
   if(within(projected,rect)||(pinStyle!=='NONE'&&overlap(rect,pinBox,4*scale))||protectedAndPins.some(other=>overlap(rect,other,gap))||drawn.some(other=>overlap(rect,other.box,gap)))continue;
   let connector=connectorFor(rect,projected,protectedAndPins,drawn,2+2*scale);if(!connector)continue;
   const pinDrawn=pinStyle!=='NONE'&&!pins.has(item.locationId)&&within(pinBox.slice(0,2),safe)&&within(pinBox.slice(2),safe)
    &&!protectedAndPins.some(other=>overlap(pinBox,other))&&!drawn.some(other=>overlap(pinBox,other.box));
   if(reference&&pinDrawn){connector=connectorFor(rect,projected,[...protectedAndPins,pinBox],drawn,2+2*scale);if(!connector)continue;}
   selected={id:item.id,role:item.role,text:item.text,locationId:item.locationId,eventId:item.eventId??null,anchor:copy(item.anchor),projected:[...projected],box:rect,connector,
    pinDrawn,pinBox:pinDrawn?pinBox:null,alpha,fontSize:size.fontSize,font:size.font,slot,priority:item.priority,
    ...(reference?{style:item.style,pin:pinStyle,reveal:item.reveal??null,startFrame:item.startFrame,pinScale:item.revealFrames===1?1:popScale(frame,item.startFrame,15)}:{})};
   break;
  }
  if(!selected){suppressed.push({id:item.id,reason:'OVERLAP_WITH_HIGHER_PRIORITY_OR_PRIMARY_EVENT'});continue;}
  slots[item.id]=selected.slot;if(selected.pinDrawn)pins.add(item.locationId);drawn.push(selected);
 }
 return{schema:LABEL_LAYER_SCHEMA,enabled:true,frame,width,height,safeArea:safe,visibleCount:drawn.length,drawn,suppressed,slots,
  projectionOwner:'EXISTING_CURRENT_CAMERA_PROJECT_FUNCTION',layoutPolicy:'PRIORITY_THEN_STABLE_SLOT_HYSTERESIS',gpuVerified:false};
}

const referencePinPaths=new Map();
function paintReferencePin(context,row,s){
 check(typeof globalThis.Path2D==='function','UP2_LABEL_REFERENCE_PIN_PATH_REQUIRED');
 let paths=referencePinPaths.get(row.pin);
 if(!paths){
  // Reuse the existing authored pin outline and actual even-odd transparent hole.
  const svg=authoredPinSvg(row.pin),data=[...svg.matchAll(/<path d="([^"]+)"/g)].map(match=>match[1]);
  check(data.length===2,'UP2_LABEL_REFERENCE_PIN_ASSET_REQUIRED');
  paths=data.map(value=>new Path2D(value));referencePinPaths.set(row.pin,paths);
 }
 const w=row.pin==='HERO'?116:49,h=row.pin==='HERO'?151:64,k=s*row.pinScale;
 if(k<=0)return;
 context.save();context.translate(row.projected[0],row.projected[1]);context.scale(k,k);context.translate(-w/2,-h);
 context.fillStyle='#FEE901';context.fill(paths[0],'evenodd');context.strokeStyle='#8C8200';context.lineWidth=1.5;context.stroke(paths[1]);context.restore();
}
function paintReferenceText(context,row,layout,cx,cy,s){
 context.fillStyle=row.role==='COUNTRY'?'#191c22':'#fff';
 context.strokeStyle='#2368ff';context.lineWidth=2*s;
 context.shadowColor='#1764ff';context.shadowBlur=row.role==='COUNTRY'?0:16*s;
 const draw=(text,x,y)=>{if(row.role!=='COUNTRY')context.strokeText(text,x,y);context.fillText(text,x,y);};
 if(row.reveal!=='GRAPHEME_POP'){draw(row.text,cx,cy);return;}
 // Same ease-out and four-frame glyph beats as reference-director. Local Scene
 // frame replaces its hardcoded reference-movie frame; full word stays reserved.
 const parts=graphemes(row.text),total=context.measureText(row.text).width;let prefix='',beat=0;
 for(const part of parts){
  const advance=context.measureText(prefix).width,next=context.measureText(prefix+part).width;prefix+=part;
  if(/^\s+$/u.test(part))continue;
  const progress=clamp((layout.frame-row.startFrame-beat++*4)/4,0,1),k=1-(1-progress)**3;
  if(k<=0)continue;
  const x=cx-total/2+(advance+next)/2;
  context.save();context.globalAlpha=row.alpha*k;context.translate(x,cy);context.scale(k,k);draw(part,0,0);context.restore();
 }
}

/** Paint only new label glyphs/plates/pins to a transparent surface. */
export function paintLabels(context,layout){
 check(context&&typeof context.clearRect==='function'&&layout?.schema===LABEL_LAYER_SCHEMA,'UP2_LABEL_CANVAS_CONTEXT_REQUIRED');
 const s=Math.min(layout.width/1080,layout.height/1920);
 context.save();context.setTransform(1,0,0,1,0,0);context.clearRect(0,0,layout.width,layout.height);
 // Round caps/outlines can extend beyond their mathematical centerline. Clip
 // actual alpha coverage to the admitted viewport without moving the anchor.
 const[x0,y0,x1,y1]=layout.safeArea;context.beginPath();context.rect(x0,y0,x1-x0,y1-y0);context.clip();
 context.lineCap='round';context.lineJoin='round';
 for(const row of layout.drawn){
  context.globalAlpha=row.alpha;context.strokeStyle='#22252b';context.lineWidth=Math.max(1,2*s);
  context.beginPath();context.moveTo(...row.connector[0]);context.lineTo(...row.connector[1]);context.stroke();
 }
 for(const row of layout.drawn)if(row.pinDrawn){
  if(row.style===REFERENCE_LABEL_STYLE){context.globalAlpha=row.alpha;paintReferencePin(context,row,s);continue;}
  const[x,y]=row.projected,r=12*s;context.globalAlpha=row.alpha;context.fillStyle='#ffd329';context.strokeStyle='#1f2228';context.lineWidth=Math.max(1,2*s);
  context.beginPath();context.moveTo(x,y);context.bezierCurveTo(x-r*1.2,y-r*1.2,x-r,y-r*2.7,x,y-r*2.7);context.bezierCurveTo(x+r,y-r*2.7,x+r*1.2,y-r*1.2,x,y);context.closePath();context.fill();context.stroke();
  context.beginPath();context.arc(x,y-r*1.75,r*.38,0,Math.PI*2);context.fillStyle='#24262c';context.fill();
 }
 for(const row of layout.drawn){
  const[x0,y0,x1,y1]=row.box,cx=(x0+x1)/2,cy=(y0+y1)/2;context.globalAlpha=row.alpha;context.font=row.font;context.textAlign='center';context.textBaseline='middle';
  if(row.role==='COUNTRY'){
   context.fillStyle='#fff';context.fillRect(x0,y0,x1-x0,y1-y0);context.strokeStyle='#24262c';context.lineWidth=Math.max(1,1.5*s);context.strokeRect(x0+.75*s,y0+.75*s,x1-x0-1.5*s,y1-y0-1.5*s);
   if(row.style===REFERENCE_LABEL_STYLE){context.save();paintReferenceText(context,row,layout,cx,cy,s);context.restore();}
   else{context.fillStyle='#191c22';context.fillText(row.text,cx,cy);}
  }else{
   if(row.style===REFERENCE_LABEL_STYLE){context.save();paintReferenceText(context,row,layout,cx,cy,s);context.restore();}
   else{context.lineWidth=Math.max(2,6*s);context.strokeStyle='#171a20';context.strokeText(row.text,cx,cy);context.fillStyle='#fff';context.fillText(row.text,cx,cy);}
  }
 }
 context.restore();return{paintedLabels:layout.drawn.length,paintedPins:layout.drawn.filter(row=>row.pinDrawn).length};
}

function defaultCanvas(width,height){
 check(globalThis.document?.createElement&&document.fonts,'UP2_LABEL_BROWSER_CANVAS_REQUIRED');
 const loaded=[...document.fonts].some(face=>face.family.replace(/^['"]|['"]$/g,'')===LABEL_FONT_FAMILY&&face.status==='loaded');
 check(loaded&&document.fonts.check(`36px "${LABEL_FONT_FAMILY}"`,'한글'),'UP2_LABEL_PINNED_FONT_REQUIRED');
 const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;return canvas;
}
/** Same native framebuffer, transparent glyph texture only. No source-map blit. */
export function createPresentationLabelPass({renderer,THREE,width=1080,height=1920,canvasFactory=defaultCanvas}={}){
 check(renderer&&THREE&&typeof renderer.render==='function'&&typeof canvasFactory==='function','UP2_LABEL_EXISTING_RENDERER_REQUIRED');
 check(renderer.autoClear===false,'UP2_LABEL_ADDITIVE_RENDERER_REQUIRED');
 const canvas=canvasFactory(width,height);check(canvas?.width===width&&canvas?.height===height,'UP2_LABEL_CANVAS_REQUIRED');
 const context=canvas.getContext('2d');check(context,'UP2_LABEL_CANVAS_CONTEXT_REQUIRED');
 const texture=new THREE.CanvasTexture(canvas);texture.minFilter=THREE.LinearFilter;texture.magFilter=THREE.LinearFilter;texture.generateMipmaps=false;
 // The compositor camera is y-down, matching factory.screen and Canvas2D.
 texture.flipY=false;
 // Existing presentation output uses LinearSRGBColorSpace; retain authored
 // Canvas RGB values just like its other direct graphic passes.
 if(THREE.NoColorSpace!==undefined)texture.colorSpace=THREE.NoColorSpace;
 const geometry=new THREE.PlaneGeometry(width,height),material=new THREE.MeshBasicMaterial({map:texture,transparent:true,depthTest:false,depthWrite:false,toneMapped:false,side:THREE.DoubleSide});
 const mesh=new THREE.Mesh(geometry,material);mesh.position.set(width/2,height/2,0);mesh.frustumCulled=false;
 const scene=new THREE.Scene();scene.add(mesh);const camera=new THREE.OrthographicCamera(0,width,0,height,.1,10);camera.position.z=5;camera.updateMatrixWorld();
 let previous=null,prepared=null,disposed=false;
 function prepare({labels,scene:sourceScene,frame,project,safeArea,protectedBoxes=[]}={}){
   check(!disposed&&labels?.enabled===true&&Array.isArray(labels.items),'UP2_LABEL_ENABLED_CONTRACT_REQUIRED');
   check(renderer.autoClear===false,'UP2_LABEL_ADDITIVE_RENDERER_REQUIRED');
   check(Array.isArray(sourceScene?.locations),'UP2_LABEL_LOCATION_BINDING_REQUIRED');
   for(const item of labels.items){const location=sourceScene.locations.find(row=>row.id===item.locationId);check(location&&point(location.anchor)&&point(item.anchor)&&location.anchor.every((v,i)=>v===item.anchor[i]),'UP2_LABEL_LOCATION_BINDING_REQUIRED');}
   prepared=layoutLabels({items:labels.items,frame,project,width,height,safeArea,protectedBoxes,previousLayout:previous,
    measureText:(text,fontValue)=>{context.font=fontValue;return context.measureText(text);}});
   return prepared;
 }
 function drawPrepared(layout){
   check(!disposed&&layout===prepared&&layout?.schema===LABEL_LAYER_SCHEMA,'UP2_LABEL_PREPARED_LAYOUT_REQUIRED');
   check(renderer.autoClear===false,'UP2_LABEL_ADDITIVE_RENDERER_REQUIRED');
   paintLabels(context,layout);previous=layout;prepared=null;
   if(layout.visibleCount){check(renderer.getRenderTarget?.()==null,'UP2_LABEL_CURRENT_FRAMEBUFFER_REQUIRED');texture.needsUpdate=true;renderer.resetState();renderer.render(scene,camera);}
   return layout;
 }
 return{
  // Runtime marker ownership is decided from actual admitted pins. Preparing is
  // CPU-only and does not paint or commit hysteresis; the same result is drawn.
  prepare,drawPrepared,
  draw(args={}){return drawPrepared(prepare(args));},
  dispose(){if(disposed)return;texture.dispose();material.dispose();geometry.dispose();disposed=true;previous=null;prepared=null;}
 };
}
