/** Browser-only alias over the unchanged Area factory and prior five knobs. */
import {createProductionAreaPass as originalFactory} from '/integration-v1/parent_production_area_pass.mjs';
import {loadIntegrationRuntimeConfig,bindProductionFactory} from '/integration-v1/presentation.mjs';
import {bindFrontierProductionFactory} from '/completion-v2/frontier_extension.mjs';
import {readFrameContext} from '/completion-v2/frame_context.mjs';
const response=await fetch('/runtime-config.json',{cache:'no-store',redirect:'error'});
if(!response.ok)throw Error('COMPLETION_FRONTIER_RUNTIME_CONFIG_REQUIRED');
const config=await response.json(),completion=config.completionV2;
if(completion?.schema!=='WORLD_ENGINE_UNIVERSAL_COMPLETION_V2'||completion.profile!=='VISUAL_UNIFIED_COMPLETION_V2')
 throw Error('COMPLETION_FRONTIER_EXPLICIT_PROFILE_REQUIRED');
const oldBinding=await loadIntegrationRuntimeConfig(),parentFactory=bindProductionFactory(originalFactory,oldBinding,'AREA');
export const createProductionAreaPass=bindFrontierProductionFactory(parentFactory,{
 profile:completion.frontier,readFrameContext,motionPlan:config.completionFrontierMotion??null});
