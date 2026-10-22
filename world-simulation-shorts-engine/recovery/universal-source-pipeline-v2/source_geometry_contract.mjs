/** Recognize explicit provider EMPTY only; never simplify nonempty geometry. */
export function sourcePolygonHasCoverage(geometry){
 if(geometry==null)return false;
 if(!['Polygon','MultiPolygon'].includes(geometry.type)||!Array.isArray(geometry.coordinates))throw Error('UNIVERSAL_SOURCE_POLYGON_GEOMETRY_REQUIRED');
 const coordinates=geometry.coordinates;
 if(coordinates.length===0)return false;
 // GEOS/GeoJSON mappings can serialize POLYGON EMPTY as either [] or [[]].
 if(geometry.type==='Polygon'&&coordinates.length===1&&Array.isArray(coordinates[0])&&coordinates[0].length===0)return false;
 return true;
}
