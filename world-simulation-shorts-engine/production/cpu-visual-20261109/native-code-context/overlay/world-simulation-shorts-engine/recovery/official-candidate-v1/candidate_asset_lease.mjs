/** Server-owned single-window memory lease. No HTTP listener or renderer. */
import path from 'node:path';import {createHash} from 'node:crypto';
import {readPinnedServerFile,verifyServerRoot} from './candidate_asset_snapshot.mjs';
import {prepareRegisteredFrameWindow,WINDOWS} from './candidate_frame_window.mjs';
import {preparePartialPngRoute,PNG_ROUTE_MODE} from '../../production/reference-reproduction-v18/source-candidate-contract/partial_png_route_adapter.mjs';
const check=(v,c)=>{if(!v)throw Error(c);},sha=b=>createHash('sha256').update(b).digest('hex');
const freeze=v=>{if(v&&typeof v==='object'){Object.values(v).forEach(freeze);Object.freeze(v);}return v;};
export const PNG_RETAINED_CAP=67108864,BINARY_RETAINED_CAP=71000064;
async function pinned(pin){check(pin&&typeof pin.sourcePath==='string'&&path.isAbsolute(pin.sourcePath),'LEASE_SERVER_PIN_REQUIRED');return readPinnedServerFile(path.dirname(pin.sourcePath),path.basename(pin.sourcePath),pin);}
export function createCandidateAssetLeaseManager(registry){
 check(registry instanceof Map,'LEASE_SERVER_REGISTRY_REQUIRED');const registered=freeze(Object.fromEntries([...registry].map(([k,v])=>[k,structuredClone(v)])));
 let state=null,epoch=0,pending=false,closed=false;
 const invalidate=()=>{epoch++;state=null;};
 return Object.freeze({
  get status(){return Object.freeze({state:closed?'CLOSED':pending?'PREPARING':state?'ACTIVE':'EMPTY',ownedPngBytes:state?.pngBytes??0,ownedBinaryBytes:state?.window.binarySnapshotBytes??0,pngCap:PNG_RETAINED_CAP,binaryCap:BINARY_RETAINED_CAP,processPeakBounded:false,gpuPeakBounded:false});},
  release(){invalidate();},dispose(){closed=true;invalidate();},
  async transition(request){
   check(!closed,'LEASE_MANAGER_CLOSED');check(!pending,'LEASE_TRANSITION_BUSY');const input=freeze(structuredClone(request));
   // Explicit transition always evicts first, even when new input later fails.
   invalidate();const ticket=epoch;pending=true;
   try{
    const r=registered[input?.registrationId];check(r&&Object.keys(r).sort().join(',')==='png,textureDescriptor,window','LEASE_REGISTRATION_INVALID');
    const w=WINDOWS.find(x=>x.id===input.windowId);check(w,'LEASE_WINDOW_UNKNOWN');
    const window=await prepareRegisteredFrameWindow({request:input,registry:new Map([[input.registrationId,r.window]])});
    await verifyServerRoot(r.png.partial.root);await verifyServerRoot(r.png.png.root);
    // Keep all existing strict/partial/PNG validator dependencies; no copied policy shortcut.
    const prepared=await preparePartialPngRoute(r.png,{mode:PNG_ROUTE_MODE,segment:w.segment});
    const descriptorBytes=await pinned(r.textureDescriptor),descriptor=JSON.parse(descriptorBytes.toString('utf8'));
    check(descriptor.schema==='WORLD_ENGINE_CPU_TEXTURE_INTEGRATION_DESCRIPTOR_V1'&&descriptor.renderAllowed===false&&descriptor.productionAdmitted===false,'LEASE_TEXTURE_DESCRIPTOR_INVALID');
    const matches=descriptor.layers.filter(x=>x.layerId===input.layerId);check(matches.length===1,'LEASE_LAYER_NOT_UNIQUE');const layer=matches[0];
    const role=w.layerId.endsWith('_regional')?'regional':'overview',image=prepared.images.find(x=>x.role===role);check(image,'LEASE_COMPOSITE_NOT_VALIDATED');
    const packIndexBytes=await pinned(descriptor.sourceMetadata.packIndex),packIndex=JSON.parse(packIndexBytes.toString('utf8')),packBytes=await pinned(descriptor.sourceMetadata.packReceipt),pack=JSON.parse(packBytes.toString('utf8'));
    check(packIndex.files['PACK_RECEIPT.json'].sha256===sha(packBytes)&&pack.compositeIndexSha256===r.png.png.generationIndexSha256&&pack.atlasIndexSha256===r.png.partial.originalGenerationIndexSha256&&pack.productionAdmitted===false&&pack.actualGpuFootprintVerified===false,'LEASE_PACK_PROVENANCE_UNBOUND');
    const packRows=pack.layers.filter(x=>x.segment===w.segment&&x.role===role);check(packRows.length===1,'LEASE_PACK_LAYER_REQUIRED');const packLayer=packRows[0];
    const validatedLayer=prepared.layers.find(x=>x.role===role);check(validatedLayer,'LEASE_VALIDATED_RAW_LAYER_REQUIRED');
    for(const[packKey,rawKey]of [['baselineAsset','baseline'],['selectionAsset','opticalSelection'],['knownLandAsset','knownLand']]){
     const asset=prepared.serverAssets[validatedLayer[rawKey].assetKey];check(asset&&asset.sha256===packLayer[packKey].sha256&&asset.bytes===packLayer[packKey].bytes,'LEASE_RAW_PACK_BINDING_MISMATCH');
    }
    check(layer.knownLandSourceManifestSha256===packLayer.sourceManifestSha256&&packLayer.crs===image.crs&&JSON.stringify(packLayer.bounds)===JSON.stringify(image.bounds)&&JSON.stringify(packLayer.dimensions)===JSON.stringify(image.dimensions),'LEASE_COLOR_GRID_UNBOUND');
    const png=new Map(),assets={};let pngBytes=0;
    for(const role of ['composite','baseline','materialMask']){
     const a=layer.assets[role];check(a?.format==='PNG_RGB8'&&a.rowOrder==='NORTH_TO_SOUTH'&&a.flipY===false&&a.automaticColorDecode===false&&a.width===image.dimensions[0]&&a.height===image.dimensions[1]&&JSON.stringify(a.grid.bounds)===JSON.stringify(image.bounds),'LEASE_PNG_POLICY_MISMATCH');
     if(role==='composite')check('sha256/'+a.sha256===image.imageKey&&a.bytes===prepared.serverImages[image.imageKey].bytes,'LEASE_COMPOSITE_UNBOUND');
     else{const output=packLayer.outputs.find(o=>o.role===(role==='baseline'?'baseline':'selection_land_water')),d=packIndex.files[path.basename(a.sourcePath)];check(output&&d&&d.sha256===a.sha256&&d.bytes===a.bytes&&output.sha256===a.sha256&&output.bytes===a.bytes&&output.exactCpuRoundTrip===true,'LEASE_PACK_PNG_UNBOUND');}
     const key='sha256/'+a.sha256;if(!png.has(key)){pngBytes+=a.bytes;check(pngBytes<=PNG_RETAINED_CAP,'LEASE_PNG_CAP');png.set(key,await pinned(a));}
     const decodedHash=role==='composite'?image.rawAssetKey.slice('sha256/'.length):packLayer.outputs.find(o=>o.role===(role==='baseline'?'baseline':'selection_land_water')).decodedRgbSha256;
     check(/^[a-f0-9]{64}$/.test(decodedHash),'LEASE_DECODED_RGB_PIN_REQUIRED');
     assets[role]={key,sha256:a.sha256,bytes:a.bytes,mimeType:'image/png',width:a.width,height:a.height,grid:a.grid,decodedRgbSha256:decodedHash,decodedRgbBytes:a.width*a.height*3};
    }
    check(window.binarySnapshotBytes<=BINARY_RETAINED_CAP,'LEASE_BINARY_CAP');
    for(const[role,a]of Object.entries(window.binaryAssets))assets[role]={key:a.assetKey,sha256:a.sha256,bytes:a.bytes,mimeType:'application/octet-stream',format:a.format,width:a.width,height:a.height,grid:a.grid};
    check(!closed&&ticket===epoch,'LEASE_TRANSITION_CANCELLED');
    state={window,png,pngBytes,assets:freeze(assets)};
    // Leases capture only manager+ticket+metadata, never buffers or private snapshots.
    const metadata=freeze({windowId:input.windowId,layerId:input.layerId,assets,windowQualificationSha256:window.sourceQualificationSHA256,textureDescriptorSha256:sha(descriptorBytes),pngBytes,binaryBytes:window.binarySnapshotBytes,renderAllowed:false,productionAdmitted:false,cacheReuseAllowed:false,executingCodeIdentity:'UNVERIFIED'});
    return Object.freeze({metadata,assertCurrent(){check(state&&ticket===epoch&&!closed,'LEASE_INVALIDATED');},read(key){check(state&&ticket===epoch&&!closed,'LEASE_INVALIDATED');const role=Object.keys(state.assets).find(role=>state.assets[role].key===key);check(role,'LEASE_ASSET_NOT_REGISTERED');if(state.png.has(key))return Buffer.from(state.png.get(key));return state.window.binarySnapshot.read(role);}});
   }finally{pending=false;}
  }
 });
}
