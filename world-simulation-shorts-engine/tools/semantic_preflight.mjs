/**
 * Canvas-free forecast of the frozen renderer's semantic draw eligibility.
 * This is a pre-render gate, never proof that pixels were rendered or watched.
 * Usage: node tools/semantic_preflight.mjs --plan PLAN [--output NEW_JSON]
 */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';

const appRoot=path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const legacyRoot=path.resolve(appRoot, '../cinematic-world-map');
const options={};
for(let i=2;i<process.argv.length;i++) {
  if(!process.argv[i].startsWith('--')) throw Error('Expected named argument');
  options[process.argv[i].slice(2)]=process.argv[++i];
}
if(!options.plan) throw Error('Required: --plan PLAN_JSON');
const planFile=path.resolve(options.plan), planBytes=fs.readFileSync(planFile);
const input=JSON.parse(planBytes), plan=input.plan||input.scene_plan||input;
if(!Array.isArray(plan.scenes)||!plan.scenes.length) throw Error('Scene Plan is empty');
const fps=30, width=2160, height=3840;
const THREE=await import(pathToFileURL(path.join(legacyRoot,'node_modules/three/build/three.module.js')));
const {createAircraftV3}=await import(pathToFileURL(path.join(legacyRoot,'src/aircraft_v3.js')));
const geo=(lon,lat,r=1)=>new THREE.Vector3(Math.cos(lat*Math.PI/180)*Math.cos(lon*Math.PI/180),Math.sin(lat*Math.PI/180),-Math.cos(lat*Math.PI/180)*Math.sin(lon*Math.PI/180)).multiplyScalar(r);
const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const smooth=v=>{v=clamp(v);return v*v*(3-2*v);};
const adapterFile=path.join(appRoot,'web/earth_adapter.js'), adapterBytes=fs.readFileSync(adapterFile);
const adapterSource=adapterBytes.toString().replace(/^import .*;$/gm,'').replace(/^export /gm,'');
const original=fs.readFileSync(path.join(legacyRoot,'src/renderer_v3.js'),'utf8');
const routeClass=original.match(/export class RouteGraphics\{([\s\S]*?)\n\}\nexport class EffectsEngine/);
if(!routeClass) throw Error('Original MASTER V3 RouteGraphics could not be loaded');
const RouteGraphics=new Function('THREE','return class RouteGraphics {'+routeClass[1]+'\n}')(THREE);
// Evaluate only reviewed local class definitions, stripping imports and exports.
// No browser, renderer constructor, network access, or original auto-start executes.
const classes=new Function('THREE','Renderer','RouteGraphics','createAircraftV3','geo','clamp','smooth',
  adapterSource+';return {SceneRoutes,GenericCamera,GenericEntities,GenericEffects,GenericRouteGraphics,SceneEarthRenderer,REPRESENTED_EVENT_KINDS};'
)(THREE,class {},RouteGraphics,createAircraftV3,geo,clamp,smooth);
const {SceneRoutes,GenericCamera,GenericEntities,GenericEffects,GenericRouteGraphics,SceneEarthRenderer,REPRESENTED_EVENT_KINDS}=classes;
const productionBytes=plan.scenes.some(scene=>scene.production_defaults?.version==='v1')?fs.readFileSync(path.join(appRoot,'web/production_visual_adapter.js')):null;
const production=productionBytes?new Function('THREE','SceneFlatEntitySeparationPolishRenderer','SceneEarthPolishRenderer','flatClamp','flatNumber','flatSmooth','flatCameraEase','flatWindow','flatCoordinate',
 productionBytes.toString().replace(/^import .*;$/gm,'').replace(/^export /gm,'')+';return {productionLabelScene,productionCameraIntervals,productionFlatCameraValues,productionUsesRouteHeadAnchor,SceneProductionEarthRenderer};'
)(THREE,class {},SceneEarthRenderer,clamp,(value,fallback=0)=>Number.isFinite(Number(value))?Number(value):fallback,smooth,
 (value,kind='smootherstep')=>{const p=clamp(value);if(kind==='smootherstep')return p*p*p*(p*(p*6-15)+10);if(kind==='quintic_out')return 1-(1-p)**5;if(kind==='linear')return p;if(kind==='ease_in')return p*p;if(kind==='ease_out')return 1-(1-p)**2;return smooth(p);},
 (time,start,end,fade=.24,hold=false)=>time<start||time>end?0:smooth((time-start)/Math.min(fade,Math.max(.01,(end-start)/3)))*(hold?1:1-smooth((time-end+fade)/fade)),
 value=>{const q=value?.coordinates||value;return {lon:Number(q.lon??q.longitude??q[0]),lat:Number(q.lat??q.latitude??q[1])};}):null;
// Optional additive component clock: the same installer is used by the native
// rhythm renderer. No canvas, shader or inherited production path is changed.
const rhythmBytes=plan.scenes.some(scene=>scene.rhythm_visual)?fs.readFileSync(path.join(appRoot,'web/rhythm_visual_adapter.js')):null;
const rhythm=rhythmBytes?new Function('SceneProductionFlatRenderer','productionCameraIntervals','productionFlatCameraValues',
 rhythmBytes.toString().replace(/^import .*;$/gm,'').replace(/^export /gm,'')+';return {installRhythmOnFlatCore};'
)(class {},production.productionCameraIntervals,production.productionFlatCameraValues):null;
const python=`import json,sys,subprocess,textwrap,math
from fontTools.ttLib import TTFont
from engine.retention import MEANINGFUL
from engine.assets import validate_clip_requirements,resolve_user_asset,sha256_file
data=json.load(sys.stdin)
plan=data['plan'];result={'meaningful':sorted(MEANINGFUL),'fonts':{},'clips':{}}
for name,p in data['fonts'].items():
 f=TTFont(p);cmap=f.getBestCmap();units=f['head'].unitsPerEm;metrics=f['hmtx'].metrics
 result['fonts'][name]={'units_per_em':units,'advances':{c:metrics[cmap[ord(c)]][0]/units for c in data['characters'] if ord(c) in cmap},'missing':sorted(c for c in data['characters'] if not c.isspace() and ord(c) not in cmap)}
for scene in plan['scenes']:
 if scene.get('scene_type')!='CINEMATIC_CLIP':continue
 check=validate_clip_requirements(scene,{s['id'] for s in plan.get('sources',[])},{c['id']:c['status'] for c in plan.get('story',{}).get('claims',[])})
 clip=scene.get('cinematic_clip',scene.get('clip',{}));check['overlays']=[]
 try:
  source=resolve_user_asset(clip.get('path',scene.get('clip_path','')))
  if not clip.get('license') and not clip.get('user_owned'):raise ValueError('CLIP_LICENSE_REQUIRED')
  probe=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,width,height','-of','json',str(source)],capture_output=True,text=True,timeout=10,check=True)
  media=json.loads(probe.stdout);length=float(media['format']['duration']);start=float(clip.get('trim_start',0))
  if not math.isfinite(length) or start<0 or start+float(scene['duration'])>length+.03:raise ValueError('CLIP_TOO_SHORT')
  if not any(s.get('codec_type')=='video' for s in media.get('streams',[])):raise ValueError('CLIP_VIDEO_STREAM_REQUIRED')
  check['source']={'path':str(source),'sha256':sha256_file(source),'duration':length,'license':clip.get('license','USER_OWNED')}
 except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
  check['errors'].append({'code':'CLIP_SOURCE_PREFLIGHT_FAILED','detail':str(error),'scene_id':scene['scene_id']})
 annotations=sorted(check['annotations'],key=lambda a:a.get('time',0))
 for index,annotation in enumerate(annotations):
  try:
   start=float(annotation['time']);end=min(float(scene['duration']),start+float(annotation['duration']))
   if index+1<len(annotations):end=min(end,float(annotations[index+1]['time']))
   if end-start<=.10:raise ValueError('CLIP_ANNOTATION_TOO_SHORT_OR_OVERLAPPING')
   event=next(e for e in scene['visual_events'] if e['id']==annotation['event_id'])
   text=str(annotation['text']).replace('{','').replace('}','').replace(chr(92),'/')
   wrapped=textwrap.wrap(text,width=25 if any(chr(0xac00)<=c<=chr(0xd7a3) for c in text) else 37)
   if len(wrapped)>3:raise ValueError('CLIP_ANNOTATION_EXCEEDS_MOBILE_SAFE_LINES')
   check['overlays'].append({**annotation,'end':end,'kind':event['kind'],'lines':wrapped,'font_size':42})
  except (ValueError,TypeError,KeyError,StopIteration) as error:
   check['errors'].append({'code':'CLIP_ANNOTATION_LAYOUT_FAILED','event_id':annotation.get('event_id'),'detail':str(error)})
 if scene.get('start_time')==0:
  hook=scene.get('hook') or plan.get('story',{}).get('hook')
  if hook:
   text=str(hook).replace('{','').replace('}','').replace(chr(92),'/')
   wrapped=textwrap.wrap(text,width=25 if any(chr(0xac00)<=c<=chr(0xd7a3) for c in text) else 37)
   if len(wrapped)>3:check['errors'].append({'code':'CLIP_HOOK_EXCEEDS_MOBILE_SAFE_LINES'})
   check['overlays'].append({'event_id':None,'time':0,'end':min(3,float(scene['duration'])),'text':text,'kind':'hook_reveal','lines':wrapped,'font_size':54})
 check['passed']=not check['errors'];result['clips'][scene['scene_id']]=check
print(json.dumps(result,ensure_ascii=False))
`;
const strings=[plan.story?.hook||plan.story_plan?.hook||plan.hook||''];
for(const scene of plan.scenes) {
  strings.push(scene.hook||'');
  for(const annotation of (scene.cinematic_clip||scene.clip||{}).annotations||[])strings.push(annotation.text||'');
  for(const item of [...(scene.labels||[]),...(scene.visual_events||[]),...(scene.text_events||[])])
    strings.push(item.text||item.label||item.description||'',String(item.value??''),String(item.unit??''));
}
strings.push('0123456789,. KM世界 항로 서울');
const fonts={OpenSans:path.join(legacyRoot,'assets/v3/fonts/OpenSans-Light.ttf'),Noto:path.join(appRoot,'web/fonts/NotoSansCJKkr-Regular.otf')};
const fontResult=spawnSync(options.python||'python',['-c',python],{
  cwd:appRoot,input:JSON.stringify({plan,fonts,characters:[...new Set(strings.join(''))]}),encoding:'utf8',maxBuffer:4*1024*1024,
});
if(fontResult.status!==0) throw Error('Installed font/retention metadata failed: '+fontResult.stderr);
const metadata=JSON.parse(fontResult.stdout), meaningful=new Set(metadata.meaningful);
class MetricsContext {
  constructor(){this.font='300 92px Open Sans';this.stack=[];}
  save(){this.stack.push(this.font);}
  restore(){this.font=this.stack.pop();}
  fillText(){} // No canvas pixels: the original method still emits its label boxes.
  measureText(text){
    const font=this.font.includes('Noto Cinema')?metadata.fonts.Noto:metadata.fonts.OpenSans;
    const size=Number(this.font.match(/([\d.]+)px/)[1]);
    let advance=0;
    for(const ch of String(text)) {
      if(ch==='\n')continue;
      if(font.advances[ch]===undefined)throw Error('MISSING_INSTALLED_FONT_GLYPH '+ch);
      advance+=font.advances[ch];
    }
    // Individual glyph advances exactly match city labels. Whole-string widths
    // reserve 3% for shaping/kerning variation: this is a conservative layout gate.
    return {width:advance*size*(String(text).length>1?1.03:1)};
  }
}
const allowances={information:.25,world_label:.4,'3D_entity':.24,route_head:0,route_barrier:0,network:0,clip_information:.09};
const physical={route_start:new Set(['route_head']),entity_departure:new Set(['3D_entity']),route_blocked:new Set(['route_barrier']),network_expand:new Set(['network']),arrival:new Set(['geographic_pulse','world_label'])};
let flatCertify=null,flatSourceHash=null;
let productionFlatCertify=null;
const flatScenes=plan.scenes.some(scene=>scene.render_mode==='FLAT_MAP_PREMIUM');
if(flatScenes){
 const file=path.join(appRoot,'web/flat_semantics.js'),bytes=fs.readFileSync(file);
 const source=bytes.toString().replace(/^import .*;$/gm,'').replace(/^export /gm,'');
 flatCertify=new Function('THREE',source+';return flatSceneEligibility;')(THREE);
 if(production){
  const FlatSceneCore=new Function('THREE',source+';return FlatSceneCore;')(THREE);
  const createProductionCore=(scene,plan,options)=>{
   const adapted=production.productionLabelScene(scene),core=new FlatSceneCore(adapted,plan,options);
   core.cam.values=time=>production.productionFlatCameraValues(core.cam,time);
   const originalLabels=core.overlayLabels.bind(core);
   core.overlayLabels=time=>{
    if(scene.text_density==='NONE')return [];
    const original=core.sceneSpec;
    core.sceneSpec={...original,labels:(original.labels||[]).map(label=>{const route=production.productionUsesRouteHeadAnchor(label)?core.route(label.route_id):null;return route?{...label,coordinates:{...label.coordinates,...route.coordinate(core.routeProgress(route,time))}}:label;})};
    try{return originalLabels(time).filter(label=>scene.production_defaults.large_titles===true||!label.information);}
    finally{core.sceneSpec=original;}
   };
   if(scene.rhythm_visual)rhythm.installRhythmOnFlatCore(core);
   return core;
  };
  const needle='const core=new FlatSceneCore(scene,plan,options),observed=';
  if(!source.includes(needle))throw Error('PRODUCTION_SEMANTIC_CORE_CONTRACT_CHANGED');
  productionFlatCertify=new Function('THREE','createProductionCore',source.replace(needle,'const core=createProductionCore(scene,plan,options),observed=')+';return flatSceneEligibility;')(THREE,createProductionCore);
 }
 flatSourceHash=createHash('sha256').update(bytes).digest('hex');
}
const {mapTransitionOpacity}=await import(pathToFileURL(path.join(appRoot,'web/map_transition.js')));
const flatCountries=flatScenes?JSON.parse(fs.readFileSync(path.join(legacyRoot,'assets/gis/countries_50m.geojson'),'utf8')):null;
const results=[], failures=[], scopeScenes=options.scene?new Set(options.scene.split(',')):null;
if(scopeScenes)for(const id of scopeScenes)if(!plan.scenes.some(scene=>scene.scene_id===id))
  failures.push({code:'UNKNOWN_SCOPED_SCENE',scene_id:id});
let hookEligible=false;
for(const scene of plan.scenes) {
  if(scopeScenes&&!scopeScenes.has(scene.scene_id))continue;
  if(scene.render_mode==='FLAT_MAP_PREMIUM'){
    try{
      const productionScene=scene.production_defaults?.version==='v1';
      const certified=(productionScene?productionFlatCertify:flatCertify)(scene,plan,fps,{width,height,context:new MetricsContext(),countries:flatCountries,visibilityFilter:time=>productionScene&&scene.visual_polish?.version==='v004'||mapTransitionOpacity(scene,time)<=.4});
      if(productionScene&&Number(scene.start_time)===0){
       const hook=scene.hook||plan.story?.hook||plan.story_plan?.hook;
       certified.opening_hook_eligible=Boolean(hook&&certified.events.some(event=>event.first_eligible_local_time!==null&&event.first_eligible_local_time<Math.min(3,scene.duration)));
       certified.opening_hook_scope='Story/narration question plus actual eligible early geographic/event primitive; generated title banner not required';
      }
      hookEligible ||= certified.opening_hook_eligible;
      failures.push(...(certified.failures||[]));
      if(!certified.numeric?.finite||certified.numeric.maxCameraAngleDegreesPerFrame>2.5)
        failures.push({code:'FLAT_CAMERA_PREFLIGHT_FAILED',scene_id:scene.scene_id});
      for(const result of certified.events){
        if(!meaningful.has(result.kind))continue;
        const event=scene.visual_events.find(e=>e.id===result.event_id);
        const required=result.kind==='route_reroute'?new Set(['route_head']):physical[result.kind];
        if(required&&result.eligible_primitives.some(p=>!required.has(p)))
          failures.push({code:'PHYSICAL_EVENT_REQUIRES_PHYSICAL_PRIMITIVE',scene_id:scene.scene_id,event_id:event.id});
        if(result.first_eligible_local_time===null){
          failures.push({code:['city_reveal','country_reveal','arrival','destination_preview','region_reveal'].includes(event.kind)?'GEOGRAPHIC_EVENT_NOT_VISIBLE':'MEANINGFUL_EVENT_NOT_ELIGIBLE',event_id:event.id,scene_id:scene.scene_id,kind:event.kind,coordinates:event.coordinates||null,projection_at_scheduled_time:result.projection_at_scheduled_time});
        }else{
          const primitive=result.first_primitive;
          const allowance=(primitive==='geographic_pulse'?.04*Number(event.duration??1.25):(['country_highlight','map_vfx'].includes(primitive)?.15:(allowances[primitive]??0)))+1/fps;
          result.onset_latency_seconds=result.first_eligible_local_time-Number(event.time);result.allowed_onset_delay_seconds=allowance;
          if(result.onset_latency_seconds>allowance+.00001)failures.push({code:'MEANINGFUL_EVENT_ELIGIBLE_LATE',event_id:event.id,scene_id:scene.scene_id,latency_seconds:result.onset_latency_seconds,allowed_seconds:allowance});
          if(result.visible_seconds<.1-1e-6)failures.push({code:'MEANINGFUL_EVENT_ELIGIBLE_TOO_BRIEFLY',event_id:event.id,scene_id:scene.scene_id,visible_seconds:result.visible_seconds});
        }
        results.push({...result,render_mode:'FLAT_MAP_PREMIUM',projection:certified.numeric?.projection});
      }
    }catch(error){failures.push({code:'FLAT_SEMANTIC_CERTIFICATION_FAILED',scene_id:scene.scene_id,detail:String(error.stack||error)});}
    continue;
  }
  if(scene.scene_type==='CINEMATIC_CLIP') {
    const check=metadata.clips[scene.scene_id];
    if(!check?.passed)failures.push(...(check?.errors||[{code:'CINEMATIC_CLIP_REQUIRES_CLIP_PREFLIGHT'}]).map(error=>({...error,scene_id:scene.scene_id})));
    for(const overlay of check?.overlays||[]) {
      // The existing FFmpeg ASS pipeline fixes Noto typography and coordinates.
      // Forecast its exact 90ms/100ms fades; actual encoded-frame proof remains mandatory.
      const font=metadata.fonts.Noto,lines=overlay.lines||[];
      const layoutEligible=lines.length>0&&lines.length<=3&&lines.every(line=>[...line].every(ch=>font.advances[ch]!==undefined)&&[...line].reduce((w,ch)=>w+font.advances[ch]*overlay.font_size+.4,0)*1.03<=770);
      if(!layoutEligible)failures.push({code:'CLIP_FONT_LAYOUT_UNCERTIFIED',scene_id:scene.scene_id,event_id:overlay.event_id});
      let eligibleFrames=0,firstEligible=null;
      for(let frame=0;frame<Math.round(scene.duration*fps);frame++) {
        const time=frame/fps,opacity=Math.max(0,Math.min(1,(time-overlay.time)/.09,(overlay.end-time)/.10));
        if(check.passed&&layoutEligible&&opacity>.1){eligibleFrames++;firstEligible??=time;if(!overlay.event_id&&Number(scene.start_time)+time<3)hookEligible=true;}
      }
      if(!overlay.event_id)continue;
      const result={event_id:overlay.event_id,scene_id:scene.scene_id,kind:overlay.kind,scheduled_local_time:overlay.time,first_eligible_local_time:firstEligible,eligible_frames:eligibleFrames,visible_seconds:eligibleFrames/fps,eligible_primitives:['clip_information'],source:check.source,projection_at_scheduled_time:null,renderer_supported:true};
      if(firstEligible===null)failures.push({code:'CLIP_INFORMATION_NOT_ELIGIBLE',scene_id:scene.scene_id,event_id:overlay.event_id});
      else {
        result.onset_latency_seconds=firstEligible-overlay.time;result.allowed_onset_delay_seconds=.09+1/fps;
        if(result.onset_latency_seconds>result.allowed_onset_delay_seconds+.00001)failures.push({code:'MEANINGFUL_EVENT_ELIGIBLE_LATE',scene_id:scene.scene_id,event_id:overlay.event_id});
        if(result.visible_seconds<.1-1e-6)failures.push({code:'MEANINGFUL_EVENT_ELIGIBLE_TOO_BRIEFLY',scene_id:scene.scene_id,event_id:overlay.event_id});
      }
      results.push(result);
    }
    continue;
  }
  for(const event of scene.visual_events||[])if(event.meaningful!==false&&!REPRESENTED_EVENT_KINDS.has(String(event.kind).toLowerCase()))
    failures.push({code:'UNSUPPORTED_SEMANTIC_EVENT',event_id:event.id,scene_id:scene.scene_id,kind:event.kind});
  const productionScene=scene.production_defaults?.version==='v1';
  const renderedScene=productionScene?production.productionLabelScene(scene):scene;
  const expected=(scene.visual_events||[]).filter(e=>e.meaningful!==false&&meaningful.has(e.kind));
  const camera=new THREE.PerspectiveCamera(44,9/16,.02,30),routes=new SceneRoutes(renderedScene),cam=new GenericCamera(camera,renderedScene,routes);
  if(productionScene){const originalValues=cam.values.bind(cam);cam.values=time=>{const {travel,zoom}=production.productionCameraIntervals(scene,3);const value=originalValues(Math.min(scene.duration,time/travel*scene.duration)),z=originalValues(Math.min(scene.duration,time/zoom*scene.duration));value.height=z.height;value.fov=z.fov;value.p=clamp(time/scene.duration);return value;};}
  const map={groups:{routes:new THREE.Group(),effects:new THREE.Group(),entities:new THREE.Group()}};
  const graphics=new GenericRouteGraphics(map,routes),effects=new GenericEffects(map,scene,routes),entities=new GenericEntities(scene,routes,map.groups.entities);
  const context={sceneSpec:renderedScene,plan,duration:scene.duration,camera,cam,routes,graphics,effects,entities,w:width,h:height,ctx:new MetricsContext(),labels:[]};
  context.project=SceneEarthRenderer.prototype.project.bind(context);
  context.drawStoryInformation=(productionScene?production.SceneProductionEarthRenderer:SceneEarthRenderer).prototype.drawStoryInformation.bind(context);
  const observed=new Map(expected.map(event=>[event.id,{event_id:event.id,scene_id:scene.scene_id,kind:event.kind,target_id:event.target_id,coordinates:event.coordinates||null,scheduled_local_time:event.time,eligible_frames:0,eligible_primitives:new Set(),first_eligible_local_time:null,projection_at_scheduled_time:null}]));
  for(let frame=0;frame<Math.round(scene.duration*fps);frame++) {
    const time=frame/fps;
    cam.update(time);entities.update(time,camera);graphics.update(time,camera);effects.update(time);
    try {
      const actualScene=context.sceneSpec;
      if(productionScene)context.sceneSpec={...actualScene,labels:(actualScene.labels||[]).map(label=>{const route=production.productionUsesRouteHeadAnchor(label)?routes.byId(label.route_id):null;if(!route)return label;const point=route.curve.getPoint(routes.progress(time,route)).normalize();return {...label,coordinates:{...label.coordinates,lon:Math.atan2(-point.z,point.x)*180/Math.PI,lat:Math.asin(clamp(point.y,-1,1))*180/Math.PI}};})};
      SceneEarthRenderer.prototype.overlay.call(context,time);
      context.sceneSpec=actualScene;
      (productionScene?production.SceneProductionEarthRenderer:SceneEarthRenderer).prototype.dispatchEventAudit.call(context,time);
    } catch(error) {
      failures.push({code:'SEMANTIC_LAYOUT_UNCERTIFIED',scene_id:scene.scene_id,time,detail:String(error.message)});
      break;
    }
    const veil=mapTransitionOpacity(scene,time);
    if(veil>.4&&!productionScene)context.eventAudit=[];
    if(Number(scene.start_time)+time<3&&veil<=.4&&context.labels.some(l=>l.kind==='hook_reveal'&&l.text&&l.opacity>.1))hookEligible=true;
    for(const event of expected) {
      const result=observed.get(event.id);
      if(result.projection_at_scheduled_time===null&&time+1e-8>=Number(event.time)&&event.coordinates) {
        const c=event.coordinates.coordinates||event.coordinates;
        const p=context.project(geo(Number(c.lon??c.longitude??c[0]),Number(c.lat??c.latitude??c[1]),1.0004));
        result.projection_at_scheduled_time={x:p.x/width,y:p.y/height,earth_occluded:p.occluded,depth_visible:p.visible,inside_event_safe_area:p.visible&&p.x>=width*.06&&p.x<=width*.91&&p.y>=height*.08&&p.y<=height*.85};
      }
    }
    for(const event of context.eventAudit) {
      const result=observed.get(event.event_id);
      if(!result)continue;
      if(physical[result.kind]&&!physical[result.kind].has(event.rendered_primitive))continue;
      // A zero-strength pulse is geometrically eligible in the old audit but has
      // no luminous pixels; refuse it here instead of silently counting it.
      if(event.rendered_primitive==='geographic_pulse') {
        const pulse=effects.items.find(e=>e.event.id===event.event_id);
        if(!pulse||pulse.mat.uniforms.uStrength.value<=.01)continue;
      }
      if(result.first_eligible_local_time===null)result.first_eligible_local_time=time;
      result.eligible_frames++;result.eligible_primitives.add(event.rendered_primitive);
      result.first_primitive??=event.rendered_primitive;
    }
  }
  for(const event of expected) {
    const result=observed.get(event.id);
    result.visible_seconds=result.eligible_frames/fps;
    result.eligible_primitives=[...result.eligible_primitives].sort();
    result.renderer_supported=REPRESENTED_EVENT_KINDS.has(String(event.kind).toLowerCase());
    if(result.first_eligible_local_time===null) {
      failures.push({code:['city_reveal','country_reveal','arrival','destination_preview','region_reveal'].includes(event.kind)?'GEOGRAPHIC_EVENT_NOT_VISIBLE':'MEANINGFUL_EVENT_NOT_ELIGIBLE',event_id:event.id,scene_id:scene.scene_id,kind:event.kind,coordinates:event.coordinates||null,projection_at_scheduled_time:result.projection_at_scheduled_time});
    } else {
      const allowance=(result.first_primitive==='geographic_pulse'?.04*Number(event.duration??1.25):(allowances[result.first_primitive]??0))+1/fps;
      result.onset_latency_seconds=result.first_eligible_local_time-Number(event.time);
      result.allowed_onset_delay_seconds=allowance;
      if(result.onset_latency_seconds>allowance+.00001)failures.push({code:'MEANINGFUL_EVENT_ELIGIBLE_LATE',event_id:event.id,scene_id:scene.scene_id,latency_seconds:result.onset_latency_seconds,allowed_seconds:allowance});
      if(result.visible_seconds<.1-1e-6)failures.push({code:'MEANINGFUL_EVENT_ELIGIBLE_TOO_BRIEFLY',event_id:event.id,scene_id:scene.scene_id,visible_seconds:result.visible_seconds});
    }
    results.push(result);
  }
  for(const group of Object.values(map.groups))group.traverse(object=>{object.geometry?.dispose();if(object.material)for(const material of Array.isArray(object.material)?object.material:[object.material])material.dispose();});
}
if(!scopeScenes&&!hookEligible)failures.push({code:'OPENING_HOOK_NOT_ELIGIBLE'});
const hash=data=>createHash('sha256').update(data).digest('hex');
const sourceHashes={flat_semantics:flatSourceHash,map_transition:hash(fs.readFileSync(path.join(appRoot,'web/map_transition.js'))),adapter:hash(adapterBytes),legacy_renderer:hash(original),aircraft:hash(fs.readFileSync(path.join(legacyRoot,'src/aircraft_v3.js'))),OpenSans:hash(fs.readFileSync(fonts.OpenSans)),Noto:hash(fs.readFileSync(fonts.Noto)),certifier:hash(fs.readFileSync(fileURLToPath(import.meta.url)))};
if(productionBytes)sourceHashes.production_visual_adapter=hash(productionBytes);
if(rhythmBytes)sourceHashes.rhythm_visual_adapter=hash(rhythmBytes);
const report={schema_version:1,created_at_utc:new Date().toISOString(),passed:failures.length===0,plan_path:planFile,plan_sha256:hash(planBytes),renderer_sha256:hash(adapterBytes),source_hashes:sourceHashes,fps,resolution:[width,height],scoped_scene_ids:scopeScenes?[...scopeScenes]:null,opening_hook_eligible:hookEligible,events:results,failures,scope:'Shared selected-renderer pose, Earth occlusion or projected-map geography, atmospheric handoff visibility, event primitive eligibility and installed-font advance layout at every 30fps pose. No canvas/WebGL, shader brightness, texture visibility, aesthetic assessment or actual rendered-pixel/QC claim.',font_layout_policy:'Installed OpenSans/Noto glyph advances; whole strings reserve3% for shaping uncertainty. Final browser font/rasterization QC remains required.'};
if(options.output)fs.writeFileSync(path.resolve(options.output),JSON.stringify(report,null,2),{flag:'wx'});
process.stdout.write(JSON.stringify(report)+'\n');
if(!report.passed)process.exitCode=2;
