/** New material-only decorator around the preserved F territory factory.
 * The explicit query is a baseline edge; the new harness must allow only this
 * exact alias and serve the unchanged, hash-bound quality_territory source.
 */
import {createTerritoryControlPass as createQualityTerritory}
 from '/quality/quality_territory.mjs?baseline';
export * from '/quality/quality_territory.mjs?baseline';
import {applyReferenceTerritoryStyle,describeReferenceGainStyle,validateReferenceTerritoryProfile}
 from './gain_style_core.mjs';
export {REFERENCE_GAIN_STYLE_VERSION,DEFAULT_REFERENCE_TERRITORY_PROFILE,validateReferenceTerritoryProfile}
 from './gain_style_core.mjs';
let selected=validateReferenceTerritoryProfile(),configured=false,factoryCreated=false;

export function setReferenceTerritoryProfile(profile={}){
 if(configured||factoryCreated)throw Error('REFERENCE_GAIN_PROFILE_ALREADY_BOUND');
 selected=validateReferenceTerritoryProfile(profile);configured=true;
 return Object.freeze(structuredClone(selected));
}

export function createTerritoryControlPass(options={}){
 factoryCreated=true;
 // Returning the original pass directly preserves the exact disabled F path,
 // including its diagnostics, allocation, draw call count and disposal.
 if(!selected.enabled)return createQualityTerritory(options);
 const sourceStyle=structuredClone(options.style),style=applyReferenceTerritoryStyle(options.style,selected),
  pass=createQualityTerritory({...options,style}),
  actualStyle=pass.evidence?.qualityTerritory?.effectiveStyle??pass.evidence?.material;
 if(!actualStyle){pass.dispose();throw Error('REFERENCE_GAIN_ACTUAL_STYLE_EVIDENCE_REQUIRED');}
 const gainTerritory={...describeReferenceGainStyle(sourceStyle,actualStyle,selected),actualFactorySelected:true},
  evidence={...pass.evidence,gainTerritory};
 return {evidence,draw(args){
  const diagnostic=pass.draw(args);
  return {...diagnostic,gainTerritory:{...structuredClone(gainTerritory),
   frame:args.controls.frame,boundaryKeyframeBinding:args.controls.boundaryKeyframeBinding,
   domainGeometryBinding:args.controls.domainGeometryBinding,
   actualFactorySelected:true,originalProtectedReservationsRetained:true}};
 },dispose(){pass.dispose();}};
}
