import {SceneEarthRenderer} from '/static/earth_adapter.js';
import {drawAtmosphericVeil,mapTransitionOpacity,transitionAuditVisibility} from '/static/map_transition.js';
/** Original V3 Earth pixels with an independently versioned projection handoff. */
export class SceneEarthTransitionRenderer extends SceneEarthRenderer{
 frame(time,samples=1){
  const canvas=super.frame(time,samples);
  this.transitionOpacity=mapTransitionOpacity(this.sceneSpec,time);
  drawAtmosphericVeil(this.ctx,this.w,this.h,this.transitionOpacity,Number(this.sceneSpec.render_time_offset??this.sceneSpec.start_time)+time);
  return canvas;
 }
 audit(time){
  return {...transitionAuditVisibility(super.audit(time),mapTransitionOpacity(this.sceneSpec,time)),
   render_mode:'MASTER_V3_EARTH',transition_backend:'PRESERVED_V3_ATMOSPHERIC_HANDOFF'};
 }
}
