/** Cartographic pullback through a short atmospheric layer, never a clip dissolve.
 * Both independently rendered backends use the same absolute-clock veil.
 */
const clamp=value=>Math.max(0,Math.min(1,value));
const ease=value=>{const v=clamp(value);return v*v*(3-2*v);};
export function mapTransitionOpacity(scene,time){
 const duration=Math.max(.15,Math.min(1.5,Number(scene.map_transition?.duration||scene.flat_map?.transition_duration||.42)));
 const incoming=['FLAT_TO_EARTH','EARTH_TO_FLAT'].includes(scene.transition_in);
 const outgoing=['FLAT_TO_EARTH','EARTH_TO_FLAT'].includes(scene.transition_out);
 return Math.max(incoming?1-ease(time/duration):0,outgoing?ease((time-scene.duration+duration)/duration):0);
}
export function drawAtmosphericVeil(ctx,width,height,opacity,absoluteTime){
 if(!(opacity>0))return;
 const x=width*(.45+Math.sin(absoluteTime*.31)*.11),y=height*(.46+Math.cos(absoluteTime*.23)*.07);
 ctx.save();ctx.globalCompositeOperation='source-over';ctx.globalAlpha=opacity;
 const background=ctx.createLinearGradient(0,0,width,height);
 background.addColorStop(0,'#142738');background.addColorStop(.48,'#456578');background.addColorStop(1,'#173448');
 ctx.fillStyle=background;ctx.fillRect(0,0,width,height);
 const light=ctx.createRadialGradient(x,y,0,x,y,height*.8);
 light.addColorStop(0,'rgba(163,192,204,.52)');light.addColorStop(.28,'rgba(123,156,170,.30)');light.addColorStop(1,'rgba(23,52,72,0)');
 ctx.fillStyle=light;ctx.fillRect(0,0,width,height);
 // Large soft bands travel through space; their shared clock matches the boundary.
 for(let i=0;i<4;i++){
  const center=height*(.14+i*.23)+Math.sin(absoluteTime*.53+i)*height*.025;
  const band=ctx.createLinearGradient(0,center-height*.12,0,center+height*.12);
  band.addColorStop(0,'rgba(161,185,195,0)');band.addColorStop(.5,'rgba(161,185,195,.08)');band.addColorStop(1,'rgba(161,185,195,0)');
  ctx.fillStyle=band;ctx.fillRect(0,center-height*.12,width,height*.24);
 }
 ctx.restore();
}
export function transitionAuditVisibility(audit,opacity){
 return {...audit,labels:(audit.labels||[]).map(label=>({...label,opacity:Number(label.opacity??1)*(1-opacity)})),
  meaningfulEventsRendered:opacity>.4?[]:(audit.meaningfulEventsRendered||[]),
  projectionTransition:{kind:opacity>0?'ATMOSPHERIC_PROJECTION_HANDOFF':'NONE',veil_opacity:opacity,
   shared_clock:true,not_clip_crossfade:true,aesthetic_review_required:true}};
}
