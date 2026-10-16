/** Reuse the existing protected polygon/front GPU pass with an explicit style contract. */
import {createAreaOverlayPass} from '/modules/area_overlay_pass_v3.mjs';
import {productionAreaStyle} from '/production-v3/production_visual_profile.mjs';
export function createProductionAreaPass({canvas,profile,bindings,probeVariant='AFTER'}){
 const owners=new Map(bindings.map(row=>[row.areaId,row])),passes=new Map(),baseline=probeVariant==='BEFORE'?createAreaOverlayPass({canvas}):null;
 const front=probeVariant==='AFTER'?createAreaOverlayPass({canvas,style:productionAreaStyle(profile)}):null;
 // Allocate one original GPU pass per bounded, explicitly supplied color, never per frame.
 for(const row of bindings){const key=JSON.stringify(row.color);if(!passes.has(key))passes.set(key,createAreaOverlayPass({canvas,style:productionAreaStyle(profile,row.color)}));}
 function draw(input){
  if(baseline){const result=baseline.draw(input);return{...result,productionVisual:{variant:'BEFORE',originalAreaStyle:true,noComplementOwnership:true}};}
  const groups=new Map();for(const item of input.controls.areas){const owner=owners.get(item.id);if(!owner)throw Error('PRODUCTION_UNBOUND_AREA_OWNER_'+item.id);
   const key=JSON.stringify(owner.color);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(item);}
  const areaResults=[];for(const [key,areas]of groups){areaResults.push(passes.get(key).draw({...input,controls:{...input.controls,areas,fronts:[],impacts:[],propagations:[]}}));}
  const frontResult=front.draw({...input,controls:{...input.controls,areas:[],impacts:[],propagations:[]}});
  return{...frontResult,areas:areaResults.flatMap(result=>result.areas),productionVisual:{variant:'AFTER',
   version:profile.version,territoryOpacity:profile.territoryOpacity,frontCoreWidthPixels:profile.frontCoreWidthPixels,
   frontCoreColor:[...profile.frontCoreColor],frontGlowColor:[...profile.frontGlowColor],
   frontGlowRadiusPixels:profile.frontGlowRadiusPixels,frontGlowGain:profile.frontGlowGain,
   actualSuppliedOwnership:true,noComplementOwnership:true,newFrontGeometry:false,
   nativeBoundaryAndReservationsMasked:true,sourceBeforeTerritoryBeforeFront:true,
   originalAreaEngine:true,scalarV2ClassifierReused:false,roleStyleOnly:true,
   areaBindings:input.controls.areas.map(item=>({areaId:item.id,factionId:owners.get(item.id).factionId,sourceId:owners.get(item.id).sourceId}))}};
 }
 return{draw,evidence:{version:'PRODUCTION_AREA_STYLE_ADAPTER_V3',originalAreaPassReused:true,
  originalShadersChanged:false,actualSuppliedPolygonOnly:true,complementOwnershipInvented:false,
  originalV2ScalarClassifierApplicable:false,originalFrontGeometryRetained:true,
  rolePassCount:passes.size+1,probeVariant},dispose(){baseline?.dispose();front?.dispose();for(const pass of passes.values())pass.dispose();}};
}
