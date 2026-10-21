/** Same preserved module instance owns settings, upload and composed materials. */
import {createReferenceTerrainMaterialPassV4 as createParent} from '/reference/director_parent_source_material.mjs';
import {trackDirectorMaterialPass} from '/astra-director-v2/material_context.mjs';
export {REFERENCE_TERRAIN_MATERIAL_V4_VERSION,DEFAULT_REFERENCE_TERRAIN_PROFILE_V4,
 validateReferenceTerrainProfileV4,createNativeDomainBinding,describeNativeDomainBinding,
 getNativeDomainCoverage,setReferenceSourceProfile,setQualityMaterialProfile,
 configureAstraMaterialForCanvas,clearAstraMaterialForCanvas}
 from '/reference/director_parent_source_material.mjs';
export async function createReferenceTerrainMaterialPassV4(options={}){
 const parent=await createParent(options);
 try{return trackDirectorMaterialPass({canvas:options.canvas,pass:parent});}
 catch(error){parent.dispose();throw error;}
}
export const createMapTerrainMaterialPassV4=createReferenceTerrainMaterialPassV4;
