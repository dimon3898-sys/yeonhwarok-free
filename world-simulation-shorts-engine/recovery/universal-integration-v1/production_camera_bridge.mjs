/** Existing conservative V3 focus consumes approachFrames; V5/layout/detail remain unchanged. */
import {createProductionNativeCamera as originalFactory,nativeGraphicReservations,nativeBoundarySupport}
 from '/integration-v1/parent_production_native_camera.mjs';
import {loadIntegrationRuntimeConfig,bindProductionFactory} from '/integration-v1/presentation.mjs';
const binding=await loadIntegrationRuntimeConfig();
export const createProductionNativeCamera=bindProductionFactory(originalFactory,binding,'CAMERA');
export {nativeGraphicReservations,nativeBoundarySupport};
