/** Explicit runtime alias; the actual preserved Area factory owns shaders, projection and masks. */
import {createProductionAreaPass as originalFactory} from '/integration-v1/parent_production_area_pass.mjs';
import {loadIntegrationRuntimeConfig,bindProductionFactory} from '/integration-v1/presentation.mjs';
const binding=await loadIntegrationRuntimeConfig();
export const createProductionAreaPass=bindProductionFactory(originalFactory,binding,'AREA');
