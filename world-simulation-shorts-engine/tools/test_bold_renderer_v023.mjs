/** Reuse the frozen v022 native camera/material fixture without editing it.
 * Canvas records operations, not NVIDIA pixels. Actual pixel QC is separate.
 */
import fs from 'node:fs';
import path from 'node:path';
const root=path.resolve('.');
const original=fs.readFileSync(path.join(root,'tools/test_infographic_v022.mjs'),'utf8');
const marker='\ntry{\n const baselineScene=structuredClone(inputScene);';
const cut=original.indexOf(marker);if(cut<0)throw Error('FROZEN_NATIVE_HARNESS_SETUP_CHANGED');
const setup=original.slice(0,cut);
const test=String.raw`
const bold=new Function('SceneInfographicRenderer','SceneProductionInfographicRenderer','createInfographicRenderer','validateInfographicGeometry','prepareInfographicGeometry','projectInfographicGeometry','digestBytes','trustedStaticURL',strip('web/bold_infographic_adapter.js')+';return {createBoldInfographicRenderer,validateBoldProfile,validateBoldSelection,boldRegionStyle,drawBoldRegionLayer,withoutLegacyCountryDraw,containsNativeCountryPoint};')(infographic.SceneInfographicRenderer,infographic.SceneProductionInfographicRenderer,infographic.createInfographicRenderer,infographic.validateInfographicGeometry,infographic.prepareInfographicGeometry,infographic.projectInfographicGeometry,quality.digestBytes,quality.trustedStaticURL);
buffers['/static/infographic/v023/bold_profile.json']=fs.readFileSync(path.join(root,'web/infographic/v023/bold_profile.json'));
try{
 assert.equal(inputScene.bold_infographic?.version,'v023');
 const source=JSON.stringify(inputScene),baseScene=structuredClone(inputScene);delete baseScene.bold_infographic;
 const legacy=infographic.createInfographicRenderer(baseScene,plan);await legacy.init();const legacyRequests=requests.splice(0);
 const off=bold.createBoldInfographicRenderer(baseScene,plan);await off.init();const offRequests=requests.splice(0);
 const on=bold.createBoldInfographicRenderer(inputScene,plan);await on.init();const onRequests=requests.splice(0);
 const selected=inputScene.infographic,fps=String(selected.fps).includes('/')?Number(selected.fps.split('/')[0])/Number(selected.fps.split('/')[1]):Number(selected.fps),total=selected.total_frames;
 assert.equal(off.constructor,legacy.constructor);assertRequestInventory(offRequests,legacyRequests);
 assertRequestInventory(onRequests.filter(url=>!url.startsWith('/static/infographic/v023/')&&url!=='/static/infographic/v022/registry.json'),legacyRequests.filter(url=>url!=='/static/infographic/v022/registry.json'));
 assert.equal(onRequests.filter(url=>url==='/static/infographic/v022/registry.json').length,2);
 assert.equal(onRequests.filter(url=>url==='/static/infographic/v023/bold_profile.json').length,1);
 const materialValue=value=>value?.isTexture?{image:value.image,colorSpace:value.colorSpace,wrapS:value.wrapS,wrapT:value.wrapT,minFilter:value.minFilter,magFilter:value.magFilter,anisotropy:value.anisotropy,generateMipmaps:value.generateMipmaps}:value?.toArray?value.toArray():value;
 const trajectory=[],regions=[],coverage={},stateCoverage={},markerCoverage={};let visiblePrimary=0,visibleSecondary=0,suppressed=0;
 for(let frame=0;frame<total;frame++){
  const t=frame/fps;for(const renderer of [legacy,off,on]){renderer.ctx.reset();renderer.actx.reset();renderer.frame(t);}
  const before=legacy.audit(t),inactive=off.audit(t),after=on.audit(t),receipt=after.infographic,child=after.bold_infographic;
  assert.deepEqual(off.ctx.commands,legacy.ctx.commands);assert.deepEqual(off.actx.commands,legacy.actx.commands);
  for(const renderer of [off,on]){
   assert.deepEqual(renderer.camera.position.toArray(),legacy.camera.position.toArray());assert.deepEqual(renderer.camera.quaternion.toArray(),legacy.camera.quaternion.toArray());assert.equal(renderer.camera.fov,legacy.camera.fov);assert.deepEqual(renderer.cam.values(t),legacy.cam.values(t));assert.equal(renderer.shaderTime,legacy.shaderTime);
   assert.equal(renderer.map.surface.fragmentShader,legacy.map.surface.fragmentShader);assert.deepEqual(Object.keys(renderer.map.surface.uniforms),Object.keys(legacy.map.surface.uniforms));
   for(const [name,uniform] of Object.entries(renderer.map.surface.uniforms))assert.deepEqual(materialValue(uniform.value),materialValue(legacy.map.surface.uniforms[name].value));
  }
  assert.deepEqual(on.actx.commands,legacy.actx.commands);assert.equal(JSON.stringify(inputScene),source);assert.equal(on.ctx.stack.length,0);
  // Real projected compact-country obstacles and measured label layout must
  // match, including Singapore. Country suppression must not erase them.
  assert.deepEqual(receipt.labels,before.infographic.labels);assert.deepEqual(receipt.markers,before.infographic.markers);assert.deepEqual(receipt.layout,before.infographic.layout);
  assert.deepEqual(on.ctx.commands.filter(command=>['fillText','strokeText'].includes(command[0])),legacy.ctx.commands.filter(command=>['fillText','strokeText'].includes(command[0])));
  assert.equal(receipt.primary_motion_effect_count,before.infographic.primary_motion_effect_count);
  assert.equal(child.frame,frame);assert.equal(child.version,'v023');assert.equal(child.added_texture_uploads,0);assert.equal(child.added_routes,0);assert.equal(child.added_entities,0);assert.equal(child.added_sfx,0);
  for(const geometry of receipt.geometry){
   const old=before.infographic.geometry.find(value=>value.geometry_id===geometry.geometry_id);
   assert(old);assert.equal(geometry.state,old.state);assert.equal(geometry.event_id,old.event_id);assert.equal(geometry.visible,old.visible);assert.deepEqual(geometry.bounds,old.bounds);
   (stateCoverage[geometry.geometry_id]||=new Set()).add(geometry.state_after);
   if(geometry.visual_profile){assert.equal(geometry.visual_role,'PRIMARY');assert.equal(geometry.legacy_draw_suppressed,true);assert.equal(geometry.drawn_by,'BOLD_NATIVE_COUNTRY_LAYER');assert.equal(geometry.line_width_px_1080,8);assert.equal(geometry.fill_alpha,.5);}
   else assert.deepEqual(geometry,old);
  }
  for(const region of child.regions){assert(selected.total_frames>=region.end_frame);assert.equal(region.source_sha256,on.boldPrepared.get(region.geometry_id).record.sha256);coverage[region.id]=(coverage[region.id]||0)+1;if(region.visible){if(region.role==='PRIMARY')visiblePrimary++;else visibleSecondary++;}}
  for(const marker of receipt.markers)markerCoverage[marker.id]=(markerCoverage[marker.id]||0)+1;
  assert(child.primary_regions<=1);visiblePrimary+=0;suppressed+=child.legacy_country_draw_groups_suppressed;
  trajectory.push({frame,position:on.camera.position.toArray(),quaternion:on.camera.quaternion.toArray(),FOV:on.camera.fov,target:on.cam.values(t)});
  if(child.regions.length)regions.push(structuredClone(child));
 }
 assert.equal(trajectory.length,total);assert(visiblePrimary>0);assert(visibleSecondary>0);assert(suppressed>0);
 for(const region of inputScene.bold_infographic.regions)assert.equal(coverage[region.id],region.end_frame-region.start_frame);
 for(const marker of selected.markers)assert.equal(markerCoverage[marker.id],marker.end_frame-marker.start_frame);
 const profile=JSON.parse(buffers['/static/infographic/v023/bold_profile.json']);
 const inverted=structuredClone(profile);inverted.geometry.SECONDARY.fill_alpha=.8;assert.throws(()=>bold.validateBoldProfile(inverted),/HIERARCHY/);
 const changed=structuredClone(inputScene);changed.bold_infographic.regions[0].geometry_ref='LOCATION_SUEZ_CANAL';assert.throws(()=>bold.validateBoldSelection(changed),/REGION/);
 const ghost=structuredClone(inputScene);ghost.bold_infographic.regions[0].source_event_id='MADE_UP_EVENT';assert.throws(()=>bold.validateBoldSelection(ghost),/STORY_TARGET/);
 // Inject a real inherited stroke failure after the BOLD fill/edge groups.
 // The country draw proxy and native context stack must be restored.
 const failFrame=selected.events.find(event=>event.primary_role==='EVENT_TITLE')?.start_frame??selected.events[0].start_frame;
 const originalDraw=on.ctx.stroke,context=on.ctx,spec=on.sceneSpec;let calls=0;
 const activeRegions=inputScene.bold_infographic.regions.filter(region=>failFrame>=region.start_frame&&failFrame<region.end_frame),visibleEdges=activeRegions.filter(region=>infographic.projectInfographicGeometry(on.boldPrepared.get(region.geometry_ref),on.camera,on.w,on.h).segments.length).length;
 on.frame(failFrame/fps);calls=0;const boldStrokeCalls=on.boldInfographicReceipt.regions.filter(region=>region.segment_count>0).length*2;
 on.ctx.stroke=function(){calls++;if(calls>boldStrokeCalls)throw Error('INJECTED_INHERITED_STROKE_FAILURE');return originalDraw.apply(this,arguments);};
 try{assert.throws(()=>on.overlay(failFrame/fps),/INJECTED_INHERITED/);assert.equal(on.ctx,context);assert.equal(on.sceneSpec,spec);assert.equal(on.ctx.stack.length,0);}finally{on.ctx.stroke=originalDraw;on.ctx.reset();}
 const registry=JSON.parse(buffers['/static/infographic/v022/registry.json']);
 const country=id=>registry.geometries.find(record=>record.id===id);
 assert(bold.containsNativeCountryPoint(country('COUNTRY_ZAF'),[24,-30]));assert.equal(bold.containsNativeCountryPoint(country('COUNTRY_ZAF'),[28.25,-29.5]),false);
 assert(bold.containsNativeCountryPoint(country('COUNTRY_FJI'),[178.1,-17.8]));assert.equal(bold.containsNativeCountryPoint(country('COUNTRY_FJI'),[0,0]),false);
 const {frameEvidence}=await import(pathToFileURL(path.join(root,'tools/scene_diagnostic_journal.mjs')));
 on.frame(failFrame/fps);const audit=on.audit(failFrame/fps),captured=frameEvidence({sceneId:inputScene.scene_id,frameIndex:failFrame,t:failFrame/fps,audit,errors:[],renderer:{},failedInvariants:[],decoded:[1080,1920],decodeError:false});assert.deepEqual(captured.infographic.bold_visual_profile,audit.bold_infographic);
 const result={passed:true,checks:18,frames:total,parent_renderer_family:family,camera_trajectory:'UNCHANGED',material:'UNCHANGED',wide:'UNCHANGED',marker:'UNCHANGED',text_layout:'UNCHANGED',canal_event_state:'UNCHANGED',overlay_off:'EXACT_V022',source_scene_immutable:true,primary_visible_frames:visiblePrimary,secondary_visible_region_frames:visibleSecondary,legacy_country_draw_suppressed:suppressed,geometry_state_coverage:Object.fromEntries(Object.entries(stateCoverage).map(([id,states])=>[id,[...states]])),region_coverage:coverage,marker_coverage:markerCoverage,additional_texture_uploads:0,scope:'Actual native Three camera/material/overlay execution with recording Canvas2D; CPU pixel QC separate',GPU:'NOT_RUN',pixel_quality:'NOT_RUN'};
 if(process.argv[3]){fs.mkdirSync(process.argv[3],{recursive:true});fs.writeFileSync(path.join(process.argv[3],'native-result.json'),JSON.stringify(result,null,2)+'\n');fs.writeFileSync(path.join(process.argv[3],'camera-720.json'),JSON.stringify(trajectory,null,2)+'\n');fs.writeFileSync(path.join(process.argv[3],'bold-draw-receipts.json'),JSON.stringify(regions,null,2)+'\n');}
 console.log(JSON.stringify(result));
}finally{globalThis.fetch=oldFetch;globalThis.document=oldDocument;}
`;
await import('data:text/javascript;base64,'+Buffer.from(setup+test).toString('base64'));
