/** Test-only trace of the actual immutable original pipeline. No visual repair claim. */
import {bootLongRuntime as bootOriginal} from '/universal/reconciliation_parent_adapter.mjs';
import {configureObservation,beginObservation,finishObservation} from '/reconciliation/pass_observer.mjs';
export async function bootLongRuntime(options={}){
 const response=await fetch('/runtime-config.json',{cache:'no-store',redirect:'error'});
 if(!response.ok)throw Error('RECONCILIATION_TRACE_CONFIG_REQUIRED');
 const config=await response.json(),binding=config.reconciliationObservation;
 if(options.testOnlySoftwareProbe!==true||config.testOnlySoftwareProbe!==true
  ||binding?.schema!=='WORLD_ENGINE_SOURCE_BOUND_OBSERVATION_V1'
  ||binding.productionRenderAllowed!==false)throw Error('RECONCILIATION_TEST_ONLY_TRACE_REQUIRED');
 configureObservation({sampleFrames:binding.sampleFrames});
 const info=await bootOriginal(options),pipeline=window.longVideoProof?.pipeline;
 if(!pipeline)throw Error('RECONCILIATION_ORIGINAL_PIPELINE_REQUIRED');
 const draw=pipeline.drawFrame.bind(pipeline);
 pipeline.drawFrame=async frame=>{
  beginObservation(frame);const diagnostic=await draw(frame),actual=await finishObservation();
  for(const kind of ['ASTRA_REFERENCE_SOURCE','SUPPLIED_AREA_FRONT','PRESERVED_V5_CAMERA'])
   if(actual.instantiatedFactories[kind]!==1||actual.executedDraws[kind]!==1)
    throw Error('RECONCILIATION_EXPECTED_ACTUAL_CONSUMER_NOT_EXECUTED');
  const visual=diagnostic.overnightV3?.visualExtensions;
  if(visual?.scalar!==null||visual?.national!==null)
   throw Error('RECONCILIATION_DEFAULT_SOURCE_SELECTION_CHANGED');
  return {...diagnostic,reconciliation:{...actual,sourceBinding:binding,
   originalGlobalFrame:frame,importPresenceIsNotExecution:true,
   scalarSelected:false,nationalUnitsSelected:false,full80Rendered:false}};
 };
 return {...info,reconciliation:{sourceBinding:binding,originalPipelineReused:true,
  softwareTraceOnly:true,physicalNvidiaVerified:false,visualQualityApproved:false}};
}
