/** New orchestration only: every map, polygon, line, motion and glyph pixel is
 * drawn by an existing engine. This lane is explicitly free software proof. */
import * as THREE from '/three.js';
import {createMapInfographicRenderer} from '/modules/renderer.mjs';
import {compileExistingEnginePlan} from '/modules/planner_engine_adapter_v1.mjs';
import {validateScenePlan} from '/modules/planner_scene_v1.mjs';
import {evaluateMinimumContextCameraFrame} from '/modules/camera_director_v5.mjs';
import {evaluateAreaFrame} from '/modules/area_core_v3.mjs';
import {createAreaOverlayPass} from '/modules/area_overlay_pass_v3.mjs';
import {compileFlowRoute,evaluateFlowFrame} from '/modules/flow_core_v2.mjs';
import {createFlowGraphicPass} from '/modules/flow_graphic_pass_v2.mjs';
import {selectEventLineStyle} from '/modules/event_style_v1.mjs';
import {createMovingGraphicPass} from '/modules/graphic_motion_pass_v4.mjs';
import {auditRuntimeLayout} from '/modules/graphic_layout.mjs';

export const GENERIC_RUNTIME_SCHEMA='WORLD_ENGINE_UNIVERSAL_DATA_RUNTIME_V1';
const copy=value=>structuredClone(value);
const inside=(point,box)=>point[0]>=box[0]&&point[0]<=box[2]&&point[1]>=box[1]&&point[1]<=box[3];
const assert=(condition,code)=>{if(!condition)throw Error(code);};

export async function createGenericRuntime({canvas,scene,nativePlan,cameraPlan,sourceStyle,inputTrace=null}={}){
 validateScenePlan(scene);
 assert(['WAR','TRANSPORT'].includes(scene.event_type),'UDP_RENDER_FAMILY_UNSUPPORTED');
 assert(scene.metadata.output.width===1080&&scene.metadata.output.height===1920&&scene.timing.fps===30,'UDP_CANONICAL_OUTPUT_REQUIRED');
 assert(scene.timing.total_frames>=2&&scene.timing.total_frames<=240,'UDP_SOFTWARE_CLIP_LIMIT');
 assert(canvas?.width===1080&&canvas?.height===1920,'UDP_CANONICAL_CANVAS_REQUIRED');
 assert(sourceStyle?.styleId==='NE1_SOURCE_NATIVE_COVERAGE'&&sourceStyle.terrainAsset?.sha256===nativePlan.assets.terrain.sha256,'UDP_STYLE_BINDING_REQUIRED');
 assert(cameraPlan?.directorVersion==='CAMERA_DIRECTOR_V5','UDP_ACTUAL_V5_REQUIRED');
 const engines=compileExistingEnginePlan(scene),immutable=JSON.stringify({scene,nativePlan,cameraPlan,sourceStyle}),safe=copy(nativePlan.layout.safe);
 const cameraSourceFrame=cameraPlan.totalFrames-1,camera=evaluateMinimumContextCameraFrame(cameraPlan,cameraSourceFrame);
 assert(camera.cameraLocked&&camera.settle.locked&&!camera.admission.localUsed,'UDP_ACTUAL_LOCKED_REGIONAL_CAMERA_REQUIRED');
 const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
 assert(gl,'UDP_WEBGL2_REQUIRED');
 const debug=gl.getExtension('WEBGL_debug_renderer_info'),backend=String(gl.getParameter(debug?debug.UNMASKED_RENDERER_WEBGL:gl.RENDERER));
 assert(backend.includes('SwiftShader'),'UDP_FREE_SOFTWARE_BACKEND_REQUIRED');
 const renderer=new THREE.WebGLRenderer({canvas,context:gl,antialias:false});renderer.setPixelRatio(1);renderer.setSize(1080,1920,false);renderer.autoClear=false;
 renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
 let factory,graphics,last=null,lastBasePixels=null,disposed=false;const passes=[];
 try{
  factory=await createMapInfographicRenderer({canvas,plan:nativePlan,layoutPlan:nativePlan,outputRenderer:renderer,terrainTreatment:'BAKED_RELIEF_V1'});
  graphics=await createMovingGraphicPass({renderer,factory,width:1080,height:1920});
  const source=sourceStyle.terrainAsset,spacing=source.pixelSpacing,b=camera.camera.flatBounds;
  const gutter=Math.min((b[0]-source.bounds[0])/spacing[0],(b[1]-source.bounds[1])/spacing[1],(source.bounds[2]-b[2])/spacing[0],(source.bounds[3]-b[3])/spacing[1]);
  assert(gutter>=1-1e-9,'UDP_NATIVE_SOURCE_SUPPORT_REQUIRED');
  factory.updateCamera(b);factory.setTerrainLod(1);
  const layoutAudit=auditRuntimeLayout({plan:nativePlan,screen:factory.screen});
  assert(layoutAudit.validation.valid,'UDP_NATIVE_LAYOUT_ADMISSION_FAILED');
  const baseline=copy(graphics.baseline),nativeMarker=baseline.find(item=>item.kind==='MARKER');
  assert(nativeMarker,'UDP_NATIVE_MARKER_DESIGN_REQUIRED');
  const markerRows=(scene.markers??[]).map(item=>{
   const p=factory.screen(item.anchor),size=nativeMarker.box[2],box=[p[0]-size/2-2,p[1]-size/2-2,p[0]+size/2+2,p[1]+size/2+2];
   assert(inside([box[0],box[1]],safe)&&inside([box[2],box[3]],safe),'UDP_SUPPLIED_MARKER_OUTSIDE_SAFE_AREA');
   return{id:item.id,anchor:copy(item.anchor),position:p,box,kind:'MARKER'};
  });
  const bindings=engines.plans.map(binding=>{
   if(binding.engine==='EXISTING_AREA_V3'){
    const pass=createAreaOverlayPass({canvas});passes.push(pass);return{...binding,pass};
   }
   if(binding.engine==='EXISTING_FLOW_V2'){
    const style=selectEventLineStyle({role:'PRIMARY',theme:nativePlan.theme,primaryMaterialColor:nativePlan.theme.primary}),pass=createFlowGraphicPass({canvas,style});
    passes.push(pass);return{...binding,pass,style};
   }
   throw Error('UDP_ENGINE_DRAW_UNSUPPORTED_'+binding.engine);
  });
  const project=point=>factory.screen(point);
  function drawFrame(frame){
   assert(!disposed&&Number.isSafeInteger(frame)&&frame>=0&&frame<scene.timing.total_frames,'UDP_FRAME_RANGE');
   renderer.resetState();factory.updateCamera(b);
   const native=factory.renderFrame({mode:1,graphics:false,boundaries:false,glow:false,dem:false,primaryMaterial:0,
    reveal:{primary:0,marker:0,location:0,country:0,title:0,disclosure:0}});
   const basePixels=factory.readPixels(),localFrame=frame-engines.globalEventStartFrame,features=[];lastBasePixels=basePixels;
   if(localFrame>=0)for(const binding of bindings){
    assert(localFrame<binding.plan.totalFrames,'UDP_ENGINE_FRAME_BINDING_REQUIRED');
    if(binding.engine==='EXISTING_AREA_V3'){
     const controls=evaluateAreaFrame(binding.plan,binding.plan.startFrame+localFrame,{project});
     const draw=binding.pass.draw({controls,project,safeArea:safe,protectedGraphics:markerRows,primaryMaterialColor:nativePlan.theme.primary,boundarySegments:[]});
     features.push({id:binding.id,engine:binding.engine,stateId:controls.stateId,state:controls.state,activeFeatures:controls.activeFeatures,
      sourceAreas:controls.areas.map(a=>({id:a.id,stateId:a.state_id,geometry:copy(a.geometry),alpha:a.alpha,coverage:a.coverage})),
      sourceFronts:controls.fronts.map(f=>({id:f.id,geometry:copy(f.geometry),alpha:f.alpha,revealFraction:f.revealFraction})),draw});
    }else{
     const primitive=compileFlowRoute(binding.plan.intent,{project}),controls=evaluateFlowFrame(binding.plan,binding.plan.startFrame+localFrame,
      {primitive,eventContext:{cameraState:camera,project,safeArea:safe,scalePlan:nativePlan,heightSource:null,protectedBoxes:markerRows.map(m=>m.box)}});
     const draw=binding.pass.draw({primitive,controls,safeArea:safe,protectedGraphics:markerRows,flowIntent:binding.plan.intent});
     assert(!controls.objectVisible||draw.object?.drawn===true,'UDP_FLOW_OBJECT_NOT_DRAWN');
     assert(controls.routeFraction===0||draw.route?.drawn===true,'UDP_FLOW_ROUTE_NOT_DRAWN');
     features.push({id:binding.id,engine:binding.engine,state:controls.state,routeFraction:controls.routeFraction,objectFraction:controls.objectFraction,
      objectPosition:controls.objectPosition,heading:controls.heading,departurePulse:controls.departurePulse,arrivalPulse:controls.arrivalPulse,
      geometry:copy(binding.plan.intent.route_geometry),projectedRoute:copy(primitive.screenCoordinates),draw});
    }
   }
   const featurePixels=factory.readPixels();let featureChangedPixels=0;
   for(let i=0;i<featurePixels.length;i+=4)if(featurePixels[i]!==basePixels[i]||featurePixels[i+1]!==basePixels[i+1]||featurePixels[i+2]!==basePixels[i+2]||featurePixels[i+3]!==basePixels[i+3])featureChangedPixels++;
   const visibleFlow=features.some(feature=>feature.engine==='EXISTING_FLOW_V2'&&feature.routeFraction>0);
   assert(!visibleFlow||featureChangedPixels>0,'UDP_FEATURE_PIXELS_MISSING');
   renderer.resetState();
   for(const marker of markerRows){
    const items=copy(baseline),item=items.find(i=>i.kind==='MARKER'),size=item.box[2];item.box=[marker.position[0]-size/2,marker.position[1]-size/2,size,size];
    graphics.draw({items,reveal:{marker:1,location:0,country:0,title:0,disclosure:0}});
   }
   gl.finish();assert(gl.getError()===gl.NO_ERROR,'UDP_DRAW_GL_ERROR');
   assert(JSON.stringify({scene,nativePlan,cameraPlan,sourceStyle})===immutable,'UDP_IMMUTABLE_SOURCE_CHANGED');
   last={schema:GENERIC_RUNTIME_SCHEMA,frame,timeSeconds:frame/30,localEventFrame:localFrame,sourceGeometryBinding:engines.sourceGeometryBinding,
    camera:{sourceFrame:cameraSourceFrame,state:camera,actualFactory:copy(factory.evidence.cameraFrame),profile:'EXPLICIT_REGION_PROFILE_ACTUAL_LOCKED_V5',motionClaimed:false},
    layout:{valid:layoutAudit.validation.valid,locationRecovery:layoutAudit.validation.locationRecovery,visibleNativeLabels:false},
    material:{styleId:sourceStyle.styleId,terrainSHA256:source.sha256,bounds:copy(source.bounds),cameraBounds:copy(b),minimumSourceGutterPixels:gutter,fullViewportCovered:true,demEnabled:false,defaultCountryTintEnabled:false},
    suppliedLocations:scene.locations.map(location=>({id:location.id,anchor:copy(location.anchor),projected:project(location.anchor),inSafe:inside(project(location.anchor),safe)})),
    suppliedCameraAnchor:{geographic:copy(scene.camera_intent.anchor),projected:project(scene.camera_intent.anchor),inSafe:inside(project(scene.camera_intent.anchor),safe)},
    markers:copy(markerRows),markerLabelRendering:'SEMANTIC_LABEL_METADATA_ONLY_NO_VISIBLE_TEXT_REQUEST_SUPPORTED',features,featureChangedPixels,
    featurePixelComparison:'ACTUAL_NATIVE_MAP_READPIXELS_BEFORE_AND_AFTER_FEATURE_PASSES_BEFORE_MARKERS',inputTrace:copy(inputTrace),nativeDraw:frame+1,glError:native.glError,backend,nvidiaVerified:false,qualityApproved:false};
   return last;
  }
  return{drawFrame,readPixels:factory.readPixels,readBasePixels:()=>{assert(lastBasePixels,'UDP_FRAME_NOT_DRAWN');return lastBasePixels;},png:()=>canvas.toDataURL('image/png'),project,
   evidence:{schema:GENERIC_RUNTIME_SCHEMA,backend,sceneFamily:scene.event_type,existingEngines:engines.plans.map(p=>p.engine),
    nativeFactory:factory.evidence,layoutAudit,materialSource:copy(sourceStyle),countrySpecificBranches:false,finishedFrameBlit:false,
    actualGPUVerified:false,nvidiaVerified:false,visualQualityApproved:false,softwareOnly:true},
   get diagnostic(){return last;},dispose(){if(disposed)return;passes.forEach(p=>p.dispose());graphics?.dispose();factory?.dispose();renderer.dispose();disposed=true;}};
 }catch(error){passes.forEach(p=>p.dispose());graphics?.dispose();factory?.dispose();renderer.dispose();throw error;}
}
