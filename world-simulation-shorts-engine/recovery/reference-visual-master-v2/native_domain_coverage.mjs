/** Exact native role/domain binding. No geography, projection or contour is
 * inferred from source colour, depth sign or an arbitrary country name. */
const bindings=new WeakMap(),frames=new WeakMap(),clone=value=>structuredClone(value);
const check=(ok,code)=>{if(!ok)throw Error(code);};
const box=value=>Array.isArray(value)&&value.length===4&&value.every(Number.isFinite)&&value[0]<value[2]&&value[1]<value[3];
const digest=async value=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(value))))]
 .map(v=>v.toString(16).padStart(2,'0')).join('');
function coordinateArray(value,depth=0){
 check(Array.isArray(value)&&value.length>0&&depth<12,'REFERENCE_DOMAIN_COORDINATES_REQUIRED');
 for(const item of value){if(Array.isArray(item))coordinateArray(item,depth+1);
  else check(typeof item==='number'&&Number.isFinite(item),'REFERENCE_DOMAIN_FINITE_COORDINATES_REQUIRED');}
}
/** Pass ORIGINAL bootstrap regional records and ORIGINAL control domain.
 * The returned opaque token cannot be substituted with a caller-supplied SHA. */
export async function createNativeDomainBinding({primary,secondary,geometries,domain,eventStartFrame=0}={}){
 check(typeof primary==='string'&&primary&&Array.isArray(secondary)&&secondary.every(x=>typeof x==='string'&&x)
  &&Array.isArray(geometries)&&Array.isArray(domain)&&domain.length>0,'REFERENCE_DOMAIN_INPUT_RECORDS_REQUIRED');
 check(Number.isSafeInteger(eventStartFrame)&&eventStartFrame>=0,'REFERENCE_DOMAIN_START_FRAME_REQUIRED');
 const ids=[primary,...secondary];check(new Set(ids).size===ids.length,'REFERENCE_DOMAIN_DUPLICATE_ROLE');
 check(domain.every(item=>item&&typeof item.id==='string')&&new Set(domain.map(item=>item.id)).size===domain.length
  &&JSON.stringify([...ids].sort())===JSON.stringify(domain.map(item=>item.id).sort()),'REFERENCE_ROLE_DOMAIN_ID_MISMATCH');
 const selected=ids.map(id=>{
  const records=geometries.filter(item=>item.id===id);check(records.length===1,'REFERENCE_DOMAIN_GEOMETRY_SELECTION_REQUIRED');
  const record=records[0],match=domain.find(item=>item.id===id);
  check(['Polygon','MultiPolygon'].includes(record.geometry_type)&&record.geometry_type===match.geometry?.type,'REFERENCE_ROLE_DOMAIN_TYPE_MISMATCH');
  coordinateArray(record.coordinates);coordinateArray(match.geometry.coordinates);
  check(JSON.stringify(record.coordinates)===JSON.stringify(match.geometry.coordinates),'REFERENCE_ROLE_DOMAIN_COORDINATE_MISMATCH');
  return {id:record.id,geometry_type:record.geometry_type,coordinates:clone(record.coordinates)};
 });
 const metadata={schema:'REFERENCE_NATIVE_ROLE_DOMAIN_BINDING_V2',primary,secondary:clone(secondary),
  eventStartFrame,domainSHA256:await digest(domain),sourceGeometrySHA256:await digest(selected),
  selectedRoleIds:ids,coverageChannels:{land:0,secondary:1,primary:2},
  union:'PRIMARY_PLUS_SECONDARY_FRACTIONAL_NATIVE_COVERAGE',geometryCoordinatesExactlyMatched:true};
 const handle=Object.freeze({schema:metadata.schema,domainSHA256:metadata.domainSHA256});bindings.set(handle,metadata);return handle;
}
export function describeNativeDomainBinding(handle){
 const value=bindings.get(handle);check(value,'REFERENCE_OPAQUE_DOMAIN_BINDING_REQUIRED');return clone(value);
}
/** Called only by the new source-factory wrapper immediately after that SAME
 * frame's unchanged material draw. Its input is the native factory's coverage. */
export function publishNativeDomainCoverage(canvas,handle,{coverage,bounds,frame,width,height}={}){
 const binding=bindings.get(handle);check(binding,'REFERENCE_OPAQUE_DOMAIN_BINDING_REQUIRED');
 check(canvas&&typeof canvas==='object'&&Number.isSafeInteger(width)&&Number.isSafeInteger(height)&&width>0&&height>0
  &&width*height<=4*1024*1024&&box(bounds)&&Number.isSafeInteger(frame)&&frame>=0,'REFERENCE_NATIVE_FRAME_REQUIRED');
 check(coverage instanceof Uint8Array&&coverage.length===width*height*4,'REFERENCE_NATIVE_ROLE_COVERAGE_SHAPE');
 const domainCoverage=new Uint8Array(width*height);let fractional=0,nonzero=0;
 for(let i=0;i<domainCoverage.length;i++){
  const r=coverage[i*4],union=coverage[i*4+1]+coverage[i*4+2];
  // Separate MSAA byte rounding can differ by at most two LSB. Coverage is
  // neither blurred nor repaired; impossible role/land relations fail closed.
  check(union<=257&&union<=r+2,'REFERENCE_NATIVE_ROLE_COVERAGE_INCONSISTENT');
  domainCoverage[i]=Math.min(255,union);if(domainCoverage[i])nonzero++;
  if(domainCoverage[i]>0&&domainCoverage[i]<255)fractional++;
 }
 const record={schema:'REFERENCE_SAME_FRAME_DOMAIN_COVERAGE_V2',frame:binding.eventStartFrame+frame,nativeFrame:frame,
  width,height,bounds:clone(bounds),rowZero:'SOUTH',domainSHA256:binding.domainSHA256,
  sourceGeometrySHA256:binding.sourceGeometrySHA256,roleIds:clone(binding.selectedRoleIds),domainCoverage,
  source:'UNCHANGED_NATIVE_FACTORY_ROLE_COVERAGE_RGBA8_BOTTOM_LEFT',
  union:'EXACT_BOUND_PRIMARY_PLUS_SECONDARY_GEOMETRIES',fractionalPixels:fractional,nonzeroPixels:nonzero,
  sourceGeometryChanged:false,nativeCoastCoverageFiltered:false,sourceColourThresholdUsed:false};
 frames.set(canvas,record);return {frame:record.frame,nativeFrame:frame,domainSHA256:record.domainSHA256,
  nonzeroPixels:nonzero,fractionalPixels:fractional,rowZero:'SOUTH',nativeCoastCoverageFiltered:false};
}
export function getNativeDomainCoverage(canvas,{frame,domainSHA256,bounds}={}){
 const value=frames.get(canvas);check(value,'REFERENCE_NATIVE_DOMAIN_FRAME_UNAVAILABLE');
 check(Number.isSafeInteger(frame)&&value.frame===frame,'REFERENCE_NATIVE_DOMAIN_FRAME_MISMATCH');
 check(typeof domainSHA256==='string'&&value.domainSHA256===domainSHA256,'REFERENCE_NATIVE_DOMAIN_SHA_MISMATCH');
 if(bounds!==undefined)check(JSON.stringify(bounds)===JSON.stringify(value.bounds),'REFERENCE_NATIVE_DOMAIN_BOUNDS_MISMATCH');
 return clone(value);
}
export function clearNativeDomainCoverage(canvas){frames.delete(canvas);}
