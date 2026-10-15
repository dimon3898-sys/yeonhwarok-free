/** Standard-import-map decorator. Original field, triangles, GL and protection
 * code are reused unchanged; only the explicit material alpha profile changes.
 */
import {createTerritoryControlPass as createOriginal}
 from '/modules/territory_control_gpu_adapter_v1.mjs?baseline';
export * from '/modules/territory_control_gpu_adapter_v1.mjs?baseline';
import {applyQualityTerritoryStyle,validateQualityTerritoryProfile,QUALITY_TERRITORY_STYLE_VERSION}
 from './territory_style_core.mjs';
const selections=new WeakMap(),createdCanvases=new WeakSet();
let defaultSelection={enabled:false,profile:validateQualityTerritoryProfile()},defaultConfigured=false,factoryCreated=false;
/** One explicit opt-in before the unchanged boot creates its canvas/factory.
 * Module lifetime is one browser harness; there is no mid-frame style toggle.
 */
export function setQualityTerritoryProfile({enabled=false,profile={}}={}){
 if(defaultConfigured||factoryCreated)throw Error('QUALITY_TERRITORY_SELECTION_ALREADY_BOUND');
 if(typeof enabled!=='boolean')throw Error('QUALITY_TERRITORY_EXPLICIT_ENABLED_REQUIRED');
 defaultSelection={enabled,profile:validateQualityTerritoryProfile(profile)};defaultConfigured=true;
 return Object.freeze({enabled,version:QUALITY_TERRITORY_STYLE_VERSION});
}
export function configureQualityTerritoryForCanvas(canvas,{enabled=true,profile={}}={}){
 if(!canvas||typeof canvas.getContext!=='function'||typeof enabled!=='boolean')throw Error('QUALITY_TERRITORY_CANVAS_SELECTION_REQUIRED');
 if(selections.has(canvas)||createdCanvases.has(canvas))throw Error('QUALITY_TERRITORY_CANVAS_ALREADY_CONFIGURED');
 selections.set(canvas,{enabled,profile:validateQualityTerritoryProfile(profile)});
}
export function clearQualityTerritoryForCanvas(canvas){selections.delete(canvas);}
export function createTerritoryControlPass(options={}){
 factoryCreated=true;if(options.canvas)createdCanvases.add(options.canvas);
 const selection=selections.get(options.canvas)??defaultSelection;
 if(!selection?.enabled)return createOriginal(options);
 const originalStyle=structuredClone(options.style),style=applyQualityTerritoryStyle(options.style,selection.profile),
  pass=createOriginal({...options,style});
 const evidence={...pass.evidence,qualityTerritory:{version:QUALITY_TERRITORY_STYLE_VERSION,
  expressionChanged:true,profile:structuredClone(selection.profile),sourceStyle:originalStyle,effectiveStyle:structuredClone(style),
  classifier:'UNCHANGED_ORIGINAL_COMPLEMENTARY_FIELD',geometryChanged:false,timeChanged:false,
  sourceRgbHuesChanged:false,newLines:false,newArrows:false,backgroundRetentionExplicit:true}};
 return {evidence,draw(args){
  const diagnostic=pass.draw(args);
  return {...diagnostic,qualityTerritory:{...evidence.qualityTerritory,
   frame:args.controls.frame,boundaryKeyframeBinding:args.controls.boundaryKeyframeBinding,
   domainGeometryBinding:args.controls.domainGeometryBinding,originalProtectedReservationsRetained:true}};
 },dispose(){pass.dispose();}};
}
