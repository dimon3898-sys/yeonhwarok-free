/** Serialization adapter only. The frozen Planner V1 validator compares
 * JSON.stringify geometry records, so Python-sorted JSON must restore that
 * validator's property order without repairing, reordering or replacing data.
 * Raw Scene SHA is checked BEFORE calling this helper by long_adapter.mjs. */
export function normalizePlannerGeometryKeys(scene){
 if(!scene||typeof scene!=='object'||Array.isArray(scene)||!Array.isArray(scene.geometries))
  throw Error('UNIVERSAL_PLANNER_GEOMETRY_RECORDS_REQUIRED');
 const normalized=structuredClone(scene),allowed=new Set(['id','geometry','source_id','note']);
 normalized.geometries=scene.geometries.map(row=>{
  if(!row||typeof row!=='object'||Array.isArray(row)||Object.keys(row).some(key=>!allowed.has(key))
   ||!Object.hasOwn(row,'id')||!Object.hasOwn(row,'geometry')||!Object.hasOwn(row,'source_id'))
   throw Error('UNIVERSAL_PLANNER_GEOMETRY_KEYS_REQUIRED');
  const geometry=row.geometry;
  if(!geometry||typeof geometry!=='object'||Array.isArray(geometry)
   ||Object.keys(geometry).some(key=>!['type','coordinates'].includes(key))
   ||!Object.hasOwn(geometry,'type')||!Object.hasOwn(geometry,'coordinates'))
   throw Error('UNIVERSAL_PLANNER_GEOMETRY_PAYLOAD_KEYS_REQUIRED');
  // Coordinates keep the same value, order and precision. The existing
  // validator remains responsible for geometry type, ring and source checks.
  return {id:row.id,geometry:{type:geometry.type,coordinates:structuredClone(geometry.coordinates)},
   source_id:row.source_id,...(Object.hasOwn(row,'note')?{note:row.note}:{})};
 });return normalized;
}
