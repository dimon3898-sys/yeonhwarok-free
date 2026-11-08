/** Reuse the already validated V8 viewport/contour changes verbatim.
 * Source: production/korean-war-20s-viewport-v8/create_overlay.py.
 * No geographic point, camera, source raster, label or timing is changed.
 */
function once(source,before,after){if(source.split(before).length!==2)throw Error('V8_RESTORE_UNIQUE_ANCHOR_REQUIRED');return source.replace(before,after);}
export function restoreRuntime(source){
 source=once(source,'style.AREA.coreColor[3]=0;style.AREA.glowGain=0;','style.AREA.coreColor=[1,.97,.78,.94];style.AREA.width=3.2;style.AREA.glowColor=[1,.85,.03,1];style.AREA.glowRadius=3.5;style.AREA.glowGain=.22;');
 source=once(source,'coreColor:accent?[.08,.95,1,1]:[1,.87,.1,.2]','coreColor:accent?[.08,.95,1,1]:[1,.87,.1,0]');
 source=once(source,'for(const area of controls.areas)if(area.alpha>0)presentationAreaViewport({geometry:area.geometry,project,safeArea:safe,presentation:p});',"const visibleAreas=[],culledAreaIds=[];for(const area of controls.areas){const visibility=area.alpha>0?presentationAreaViewport({geometry:area.geometry,project,safeArea:safe,presentation:p,allowOffscreenComponents:true}):{visible:true};if(visibility.visible!==false)visibleAreas.push(area);else culledAreaIds.push(area.id);}for(const id of groups)if(controls.areas.some(a=>(a.state_id??'__DEFAULT__')===id&&a.alpha>0&&a.coverage>0))assert(visibleAreas.some(a=>(a.state_id??'__DEFAULT__')===id&&a.alpha>0&&a.coverage>0),'UP2_ACTIVE_STATE_ENTIRELY_OUTSIDE_VIEWPORT');");
 source=once(source,"areas:controls.areas.filter(a=>(a.state_id??'__DEFAULT__')===id)","areas:visibleAreas.filter(a=>(a.state_id??'__DEFAULT__')===id)");
 source=once(source,'for(const item of controls.areas)if(item.alpha>0&&item.coverage>0)','for(const item of visibleAreas)if(item.alpha>0&&item.coverage>0)');
 source=once(source,'sourceFronts:controls.fronts.map','culledAreaIds,sourceFronts:controls.fronts.map');return source;
}
export function restorePlan(source){
 source=once(source,'export function presentationAreaViewport({geometry,project,safeArea,presentation,width=1080,height=1920})','export function presentationAreaViewport({geometry,project,safeArea,presentation,width=1080,height=1920,allowOffscreenComponents=false})');
 return once(source,"ok(visible,'UP2_AREA_SOURCE_OUTSIDE_VIEWPORT');","if(!visible&&allowOffscreenComponents===true)return{safeArea:viewport,clipped:true,visible:false,sourceGeometryChanged:false};ok(visible,'UP2_AREA_SOURCE_OUTSIDE_VIEWPORT');");
}
