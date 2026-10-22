/** Minimal source-field orchestration. Every pixel owner is an existing engine. */
import * as THREE from '/three.js';
import {createMapInfographicRenderer} from '/modules/renderer.mjs';
import {createAreaOverlayPass} from '/modules/area_overlay_pass_v3.mjs';
import {compileAreaLinePrimitive} from '/modules/area_core_v3.mjs';
import {evaluateMinimumContextCameraFrame} from '/modules/camera_director_v5.mjs';
import {createAreaAnnotation} from '/modules/area_annotation_v3.mjs';
import {createMovingGraphicPass} from '/modules/graphic_motion_pass_v4.mjs';

export const UNIVERSAL_SOURCE_RUNTIME_VERSION='WORLD_ENGINE_UNIVERSAL_SOURCE_RUNTIME_V2';
const clone=x=>structuredClone(x),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const bounds=b=>Array.isArray(b)&&b.length===4&&b.every(Number.isFinite)&&b[0]<b[2]&&b[1]<b[3];
const rgb=c=>Array.isArray(c)&&c.length===3&&c.every(n=>Number.isFinite(n)&&n>=0&&n<=1);
const notEmpty=g=>g&&Array.isArray(g.coordinates)&&g.coordinates.length>0;
function roleStyle(color,fill=0,width=0,alpha=0,halo=0,gain=0){return{fillColor:[...color,fill],coreColor:[...color,alpha],width,glowColor:[...color,1],glowRadius:halo,glowGain:gain};}
function styleFor(area,front){return{version:'SOURCE_FIELD_EXISTING_AREA_STYLE_V2',AREA:area,FRONT:front,IMPACT:area,PROPAGATION:front};}
function maskItems(mask,prefix,field){
 const rows=Array.isArray(mask)?mask:mask?[mask]:[];
 return rows.filter(row=>notEmpty(row.geometry)).map((row,index)=>({id:row.id??prefix+'-'+index,geometry:clone(row.geometry),alpha:1,coverage:1,coverageOrigin:null,
  fieldId:field.fieldId,frame:field.frame}));
}
function validate(inputs){
 const {canvas,nativePlan,frames,cameraPlan,cameraSchedule,actors,eventLocation,annotations=[],profile={}}=inputs;
 if(!canvas||canvas.width!==1080||canvas.height!==1920||!nativePlan||!bounds(nativePlan.framing?.bounds))throw Error('UNIVERSAL_CANONICAL_NATIVE_PLAN_REQUIRED');
 if(!Array.isArray(frames)||frames.length<2||frames.length>240||!Array.isArray(cameraSchedule)||cameraSchedule.length!==frames.length)throw Error('UNIVERSAL_BOUNDED_SOURCE_FRAME_SEQUENCE_REQUIRED');
 if(cameraPlan?.directorVersion!=='CAMERA_DIRECTOR_V5'||cameraPlan.fps!==30||!same(cameraPlan.intent.finalExtent,nativePlan.framing.bounds))throw Error('UNIVERSAL_ACTUAL_V5_CAMERA_BINDING_REQUIRED');
 if(!Array.isArray(actors)||actors.length<1||actors.length>8||new Set(actors.map(a=>a.actor_id)).size!==actors.length||actors.some(a=>typeof a.actor_id!=='string'||!rgb(a.actor_color)))throw Error('UNIVERSAL_EXPLICIT_ACTOR_PALETTE_REQUIRED');
 if(!Array.isArray(eventLocation)||eventLocation.length!==2||!eventLocation.every(Number.isFinite)||!same(eventLocation,nativePlan.anchor.coordinates))throw Error('UNIVERSAL_EXPLICIT_EVENT_LOCATION_REQUIRED');
 if(!Array.isArray(annotations)||annotations.length)throw Error('UNIVERSAL_CUSTOM_ANNOTATIONS_NOT_IMPLEMENTED');
 const allowed=['fillOpacity','frontWidth','frontOuterWidth','frontHaloPixels'];
 if(Object.keys(profile).some(k=>!allowed.includes(k)))throw Error('UNIVERSAL_UNKNOWN_RENDER_PROFILE_FIELD');
 const actorIDs=new Set(actors.map(a=>a.actor_id));
 for(let i=0;i<frames.length;i++){
  const field=frames[i],clock=cameraSchedule[i];
  if(field?.frame!==i||typeof field.fieldId!=='string'||!Array.isArray(field.ownerMasks)||!field.sharedFront||field.sharedFront.fieldId!==field.fieldId||field.sharedFront.frame!==i)throw Error('UNIVERSAL_SOURCE_FIELD_CLOCK_MISMATCH');
  if(field.ownerMasks.some(row=>!actorIDs.has(row.factionId)||row.fieldId!==field.fieldId||row.frame!==i))throw Error('UNIVERSAL_SOURCE_OWNER_FIELD_MISMATCH');
  if(clock?.frame!==i||!Number.isSafeInteger(clock.sourceFrame)||clock.sourceFrame<0||clock.sourceFrame>=cameraPlan.totalFrames)throw Error('UNIVERSAL_CAMERA_SOURCE_CLOCK_REQUIRED');
  const actual=evaluateMinimumContextCameraFrame(cameraPlan,clock.sourceFrame);
  if(actual.admission.localUsed||!same(actual.camera.flatBounds,clock.flatBounds))throw Error('UNIVERSAL_CAMERA_STATE_NOT_ACTUAL_V5');
 }
 return true;
}
/**
 * The caller's authenticated source contract admits the immutable field package.
 * This consumer never invents coordinates, closes a partial front, selects a
 * country or creates a paid GPU authorization. It is the explicit software lane.
 */
export async function createUniversalSourceRuntime(inputs={}){
 validate(inputs);
 const {canvas,nativePlan,cameraPlan,cameraSchedule,frames,actors,eventLocation,
  contextGeometries=[],contextTerrain=null,heightSource=null,profile={}}=inputs;
 const fillOpacity=profile.fillOpacity??.44,frontWidth=profile.frontWidth??4.4,
  outerWidth=profile.frontOuterWidth??8.4,halo=profile.frontHaloPixels??5;
 if(!Number.isFinite(fillOpacity)||fillOpacity<.15||fillOpacity>.55||!Number.isFinite(frontWidth)||frontWidth<2||frontWidth>7
  ||!Number.isFinite(outerWidth)||outerWidth<frontWidth||outerWidth>12||!Number.isFinite(halo)||halo<0||halo>8)throw Error('UNIVERSAL_RENDER_PROFILE_RANGE');
 const protectedBinding=JSON.stringify({nativePlan,cameraPlan,cameraSchedule,frames,actors,eventLocation,contextGeometries,contextTerrain,heightSource,profile});
 const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
 if(!gl)throw Error('UNIVERSAL_WEBGL2_REQUIRED');
 const renderer=new THREE.WebGLRenderer({canvas,context:gl,antialias:false});
 renderer.setPixelRatio(1);renderer.setSize(1080,1920,false);renderer.autoClear=false;
 renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
 let factory,caption,graphics,disposed=false,last=null,nativeDrawCount=0;
 const passes=[];
 try{
  factory=await createMapInfographicRenderer({canvas,plan:nativePlan,layoutPlan:nativePlan,width:1080,height:1920,
   contextGeometries,contextTerrain,heightSource,outputRenderer:renderer,outputTarget:null,terrainTreatment:'BAKED_RELIEF_V1'});
  graphics=await createMovingGraphicPass({renderer,factory,width:1080,height:1920});
  const empty=roleStyle([1,1,1]);
  const actorPass=new Map(actors.map(actor=>{
   const pass=createAreaOverlayPass({canvas,style:styleFor(roleStyle(actor.actor_color,fillOpacity),empty)});passes.push(pass);return[actor.actor_id,pass];}));
  const unknown=createAreaOverlayPass({canvas,style:styleFor(roleStyle([.55,.57,.6],.12),empty)}),
   contested=createAreaOverlayPass({canvas,style:styleFor(roleStyle([.95,.75,.23],.2),empty)}),
   gold=createAreaOverlayPass({canvas,style:styleFor(empty,roleStyle([1,.72,.2],0,outerWidth,.88,halo,.22))}),
   white=createAreaOverlayPass({canvas,style:styleFor(empty,roleStyle([1,.98,.9],0,frontWidth,1,.8,.06))});
  passes.push(unknown,contested,gold,white);
  const source={source_type:'SYNTHETIC_TEST',source_reference:'Source-qualified authored non-historical observation-zone technical fixture',verification_status:'SYNTHETIC_TEST'};
  caption=createAreaAnnotation({renderer,labels:[{id:'demo',display_value:'SYNTHETIC',unit:'DEMO',source,anchor:eventLocation}],
   dataMode:'SYNTHETIC_TEST',geographicAnchor:eventLocation,safeArea:nativePlan.layout.safe,width:1080,height:1920});
  const safe=nativePlan.layout.safe,captionPlacement=caption.place({anchor:[540,safe[1]+26],anchorCandidates:[],safeArea:safe,protectedGraphics:[],boundarySegments:[]}),
   captionReservation=captionPlacement.reservation,baseGraphics=clone(factory.evidence.layout),marker=baseGraphics.find(r=>r.role==='MARKER');
  if(!marker||marker.kind!=='MARKER')throw Error('UNIVERSAL_EXISTING_MARKER_ART_REQUIRED');
  const getProjectedFront=(field,project)=>{
   const geometry=field.sharedFront.geometry;
   if(!notEmpty(geometry))return[];
   const paths=geometry.type==='LineString'?[geometry.coordinates]:geometry.type==='MultiLineString'?geometry.coordinates:null;
   if(!paths)throw Error('UNIVERSAL_SOURCE_SHARED_FRONT_TYPE');
   return paths.filter(p=>p.length>=2).map((coordinates,index)=>{
    const geometry={type:'LineString',coordinates:clone(coordinates)};
    return{id:'shared-'+index,geometry,alpha:1,revealFraction:1,linePrimitive:compileAreaLinePrimitive({geometry,source,data_mode:'SYNTHETIC_TEST'},{project})};
   });
  };
  function drawFrame(frame,{controlEnabled=true,frontEnabled=true,captionEnabled=true}={}){
   if(disposed||!Number.isSafeInteger(frame)||frame<0||frame>=frames.length)throw Error('UNIVERSAL_FRAME_OUTSIDE_APPROVED_SEQUENCE');
   for(const value of [controlEnabled,frontEnabled,captionEnabled])if(typeof value!=='boolean')throw Error('UNIVERSAL_ABLATION_BOOLEAN_REQUIRED');
   const field=frames[frame],clock=cameraSchedule[frame],camera=evaluateMinimumContextCameraFrame(cameraPlan,clock.sourceFrame),bounds=camera.camera.flatBounds;
   factory.updateCamera(bounds);factory.setTerrainLod(1);
   const native=factory.renderFrame({mode:1,graphics:false,boundaries:false,glow:false,dem:heightSource!==null,primaryMaterial:1,
    reveal:{primary:1,marker:0,location:0,country:0,title:0,disclosure:0}});nativeDrawCount++;
   if(native.glError)throw Error('UNIVERSAL_NATIVE_GL_ERROR');
   const projected=factory.screen(eventLocation),size=marker.box[2],items=clone(baseGraphics);
   for(const item of items)if(item.role==='MARKER')item.box=[projected[0]-size/2,projected[1]-size/2,size,size];
   const markerReservation={kind:'MARKER',role:'EXPLICIT_SYNTHETIC_EVENT_POINT',box:[projected[0]-size/2-2,projected[1]-size/2-2,projected[0]+size/2+2,projected[1]+size/2+2]},
    reservations=[markerReservation,captionReservation],project=point=>factory.screen(point),drawResults=[];
   const draw=(pass,controls)=>pass.draw({controls,project,safeArea:safe,protectedGraphics:reservations,primaryMaterialColor:nativePlan.theme.primary,boundarySegments:[]});
   if(controlEnabled){
    for(const actor of actors){const owned=field.ownerMasks.filter(row=>row.factionId===actor.actor_id);drawResults.push({actor_id:actor.actor_id,graphics:draw(actorPass.get(actor.actor_id),{areas:maskItems(owned,actor.actor_id,field)})});}
    drawResults.push({kind:'unknown',graphics:draw(unknown,{areas:maskItems(field.unknownMask,'unknown',field)})});
    drawResults.push({kind:'contested',graphics:draw(contested,{areas:maskItems(field.contestedMask,'contested',field)})});
   }
   const front=getProjectedFront(field,project),frontDraws=[];
   if(frontEnabled&&controlEnabled&&front.length){frontDraws.push(draw(gold,{fronts:front}),draw(white,{fronts:front}));}
   graphics.draw({items,reveal:{marker:1,location:0,country:0,title:0,disclosure:0}});
   const annotation=captionEnabled?caption.draw({id:'demo',placement:captionPlacement}):null;
   gl.finish();const error=gl.getError();if(error)throw Error('UNIVERSAL_COMPOSITION_GL_ERROR_'+error);
   if(JSON.stringify({nativePlan,cameraPlan,cameraSchedule,frames,actors,eventLocation,contextGeometries,contextTerrain,heightSource,profile})!==protectedBinding)throw Error('UNIVERSAL_BOUND_SOURCE_MUTATED');
   last={version:UNIVERSAL_SOURCE_RUNTIME_VERSION,frame,timeSeconds:frame/30,classification:'SYNTHETIC_DEMO_NOT_HISTORY',
    fieldId:field.fieldId,ownerMasks:clone(field.ownerMasks),sharedFront:clone(field.sharedFront),unknownMask:clone(field.unknownMask),contestedMask:clone(field.contestedMask),
    sourceControlFrame:field.frame,sharedFieldClock:true,actualCamera:clone(factory.evidence.cameraFrame),camera:{...clone(camera),sourceFrame:clock.sourceFrame,clockDirection:clock.clockDirection,globalDerivativeClaimed:false},
    projectEventPoint:projected,fillDraws:drawResults,frontDraws,annotation,marker:{position:projected,source:'UNCHANGED_NATIVE_MARKER_ART_EXPLICIT_EVENT_LOCATION',safeArea:projected[0]-size/2>=safe[0]&&projected[0]+size/2<=safe[2]&&projected[1]-size/2>=safe[1]&&projected[1]+size/2<=safe[3]},
    nativeDrawCount,glError:0,sourceGeometryUnchanged:true,finishedFrameReuse:false,framePixelsNewlyDrawn:true,
    sourceTerrainFallback:'UNCHANGED_NATIVE_NE1_REGIONAL_AND_GLOBAL_RGB_COVERAGE',astraOutsideSupportUsed:false,
    unqualifiedReferenceV4SourceClampingUsed:false,nvidiaVerified:false,visualQualityApproved:false};
   return last;
  }
  const debug=gl.getExtension('WEBGL_debug_renderer_info');
  return{drawFrame,readPixels:factory.readPixels,png:()=>canvas.toDataURL('image/png'),project:point=>factory.screen(point),get diagnostic(){return last;},
   evidence:{version:UNIVERSAL_SOURCE_RUNTIME_VERSION,native:factory.evidence,areaEngine:'UNCHANGED_AREA_OVERLAY_PASS_V3',cameraEngine:'UNCHANGED_CAMERA_DIRECTOR_V5',
    sourceField:'ONE_SUPPLIED_FRAME_OWNER_UNKNOWN_CONTESTED_AND_SHARED_FRONT',sharedFrontStroke:'EXISTING_AREA_LINE_PASS_WHITE_CORE_GOLD_OUTER_NO_SCALAR_INFERENCE',
    nationSpecificBranches:false,fullRendererCopied:false,g1SourceOrArtifactsChanged:false,syntheticCaption:'UNCHANGED_EVENT_METRIC_GLYPH_LAYOUT_GPU_PASS',
    backend:debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),softwareOnly:true,productionEligible:false,visualQualityApproved:false},
   dispose(){if(disposed)return;caption?.dispose();graphics?.dispose();passes.forEach(p=>p.dispose());factory?.dispose();renderer.dispose();disposed=true;}};
 }catch(error){caption?.dispose();graphics?.dispose();passes.forEach(p=>p.dispose());factory?.dispose();renderer.dispose();throw error;}
}
