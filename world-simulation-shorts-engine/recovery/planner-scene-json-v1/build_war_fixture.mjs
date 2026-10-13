/** Fixture authoring only: historical state sketches never become engine/topic branches. */
import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {dirname, resolve} from 'node:path';
import {validateAreaGeometry} from '../../web/map_infographic_v1/area_core_v3.mjs';

const folder = dirname(fileURLToPath(import.meta.url));
const engine = resolve(folder, '../..');
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const serialize = value => JSON.stringify(value, null, 2) + '\n';
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const round = value => Number(value.toFixed(9));

const historicalReferences = [
 {id: 'HISTORY_START', source_type: 'GOVERNMENT_HISTORICAL_REFERENCE',
  source_reference: 'https://history.state.gov/milestones/1945-1952/korean-war-2',
  title: 'U.S. Department of State, Office of the Historian: The Korean War, 1950–1953',
  verification_status: 'VERIFIED', verification_basis: 'CURATED_ESTABLISHED_HISTORICAL_FACT_REVIEW',
  live_access: 'REFERENCE_ONLY_RETRIEVAL_BLOCKED', retrieval_date: '2026-10-13',
  retrieval_http_status: 403, retrieval_failure: 'Managed network proxy denied HTTPS CONNECT; no source body retrieved.',
  original_body_sha256: null, license: 'Government historical reference; event facts are not copyrighted.',
  note: 'Verified here means review of established chronology supplied to the fixture, not live retrieval or surveyed front geometry.'},
 {id: 'HISTORY_CAMPAIGNS', source_type: 'GOVERNMENT_HISTORICAL_REFERENCE',
  source_reference: 'https://history.army.mil/html/reference/army_flag/kw.html',
  title: 'U.S. Army Center of Military History: Korean War campaigns',
  verification_status: 'VERIFIED', verification_basis: 'CURATED_ESTABLISHED_HISTORICAL_FACT_REVIEW',
  live_access: 'REFERENCE_ONLY_RETRIEVAL_BLOCKED', retrieval_date: '2026-10-13',
  retrieval_http_status: 403, retrieval_failure: 'Managed network proxy denied HTTPS CONNECT; no source body retrieved.',
  original_body_sha256: null, license: 'Government historical reference; event facts are not copyrighted.',
  note: 'Campaign chronology provides contextual reference only. This fixture does not claim to reproduce an archival situation map.'},
 {id: 'HISTORY_OVERVIEW', source_type: 'PUBLISHED_HISTORICAL_REFERENCE',
  source_reference: 'https://www.britannica.com/event/Korean-War',
  title: 'Encyclopaedia Britannica: Korean War',
  verification_status: 'VERIFIED', verification_basis: 'CURATED_ESTABLISHED_HISTORICAL_FACT_REVIEW',
  live_access: 'REFERENCE_ONLY_RETRIEVAL_BLOCKED', retrieval_date: '2026-10-13',
  retrieval_http_status: 403, retrieval_failure: 'Managed network proxy denied HTTPS CONNECT; no source body retrieved.',
  original_body_sha256: null, license: 'Reference citation only; no copyrighted article text is copied.',
  note: 'Public historical overview citation; authored labels and schematic coordinates below are independent fixture data.'},
 {id: 'SCHEMATIC_STATES', source_type: 'SCHEMATIC_HISTORICAL_STATE',
  source_reference: 'HISTORY_START; HISTORY_CAMPAIGNS; HISTORY_OVERVIEW',
  verification_status: 'VERIFIED', verification_basis: 'CURATED_SEMANTIC_AND_CHRONOLOGY_REVIEW',
  license: 'Newly authored fixture data in this repository.', crs: 'EPSG:4326',
  resolution: 'Illustrative mainland state/front sketches; not surveyed or reconstructed military control lines.',
  note: 'The highlighted mainland region denotes a simplified Republic of Korea/UN-held core area. Fronts omit isolated units, pockets, islands, and exact day-by-day territorial control. Coastline comes from the existing Native Natural Earth data. Changes show southward advance, northward counter-advance, withdrawal, and final stalemate in the historically correct order.'}
];

/** Remove the exact reciprocal current-border arc, preserving the two native coastline arcs. */
export function joinNativeMainland(kor, prk) {
 const south = kor.coordinates[0][0].slice(0, -1);
 const north = prk.coordinates[0][0].slice(0, -1);
 const matches = south.map((point, i) => ({i, j: north.findIndex(other => equal(point, other))})).filter(x => x.j >= 0);
 if (matches.length < 2 || matches.some((x, i) => i && (x.i !== matches[i - 1].i + 1 || x.j !== matches[i - 1].j - 1)))
  throw Error('FIXTURE_NATIVE_SHARED_BORDER_MUST_BE_ONE_REVERSED_CONTIGUOUS_ARC');
 const first = matches[0], last = matches.at(-1);
 if (first.i !== 0 || last.j !== 0) throw Error('FIXTURE_NATIVE_RING_ORDER_NOT_EXPECTED');
 const ring = [...south.slice(last.i), ...south.slice(0, first.i + 1), ...north.slice(first.j + 1), north[0]];
 const geometry = {type: 'Polygon', coordinates: [ring]};
 validateAreaGeometry(geometry);
 return {geometry, removedSharedBorderVertexCount: matches.length,
  sourceCoastlineVerticesPreserved: true, operations: ['Remove exact reciprocal shared border arc', 'Join untouched outer coastline arcs']};
}

/** Ordinary GeoJSON clipping for this authored fixture, not a new runtime Geometry engine. */
function clipHalfPlane(inputRing, plane) {
 const points = inputRing.slice(0, -1);
 const signed = ([x, y]) => plane[0] * x + plane[1] * y + plane[2];
 const output = [];
 for (let i = 0; i < points.length; i++) {
  const a = points[i], b = points[(i + 1) % points.length], da = signed(a), db = signed(b);
  const ain = da >= -1e-10, bin = db >= -1e-10;
  if (ain) output.push([...a]);
  if (ain !== bin) {
   const t = da / (da - db);
   output.push([round(a[0] + (b[0] - a[0]) * t), round(a[1] + (b[1] - a[1]) * t)]);
  }
 }
 const deduplicated = output.filter((point, i) => !i || !equal(point, output[i - 1]));
 if (deduplicated.length && equal(deduplicated[0], deduplicated.at(-1))) deduplicated.pop();
 if (deduplicated.length < 3) throw Error('FIXTURE_CLIPPING_EMPTY_AREA');
 deduplicated.push([...deduplicated[0]]);
 return deduplicated;
}

function clipMainland(mainland, planes) {
 let ring = mainland.coordinates[0];
 for (const plane of planes) ring = clipHalfPlane(ring, plane);
 const geometry = {type: 'Polygon', coordinates: [ring]};
 validateAreaGeometry(geometry);
 return geometry;
}

function authoredFront(coordinates) {
 if (coordinates.length < 2 || coordinates.length > 129) throw Error('FIXTURE_FRONT_CAPACITY');
 return {type: 'LineString', coordinates};
}

function trimFrontToMainland(coordinates, mainland) {
 const coast = mainland.coordinates[0], inside = ([x, y]) => {
  let result = false;
  for (let i = 0; i < coast.length - 1; i++) {
   const a = coast[i], b = coast[i + 1];
   if ((a[1] > y) !== (b[1] > y) && x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]) result = !result;
  }
  return result;
 };
 const groups = []; let current = [];
 const finish = () => {if (current.length > 1) groups.push(current); current = [];};
 const cross = (a, b) => a[0] * b[1] - a[1] * b[0];
 for (let i = 0; i < coordinates.length - 1; i++) {
  const a = coordinates[i], b = coordinates[i + 1], r = [b[0] - a[0], b[1] - a[1]], cuts = [0, 1];
  for (let k = 0; k < coast.length - 1; k++) {
   const c = coast[k], d = coast[k + 1], s = [d[0] - c[0], d[1] - c[1]], den = cross(r, s);
   if (Math.abs(den) < 1e-14) continue;
   const ca = [c[0] - a[0], c[1] - a[1]], t = cross(ca, s) / den, u = cross(ca, r) / den;
   if (t > 1e-10 && t < 1 - 1e-10 && u >= -1e-10 && u <= 1 + 1e-10) cuts.push(t);
  }
  const ts = cuts.sort((x, y) => x - y).filter((t, n, all) => !n || t - all[n - 1] > 1e-10);
  const point = t => [round(a[0] + r[0] * t), round(a[1] + r[1] * t)];
  for (let k = 0; k < ts.length - 1; k++) {
   if (!inside(point((ts[k] + ts[k + 1]) / 2))) {finish(); continue;}
   const first = point(ts[k]), last = point(ts[k + 1]);
   if (current.length && !equal(current.at(-1), first)) finish();
   if (!current.length) current.push(first);
   if (!equal(current.at(-1), last)) current.push(last);
  }
 }
 finish();
 const length = points => points.slice(1).reduce((sum, p, i) => sum + Math.hypot(p[0] - points[i][0], p[1] - points[i][1]), 0);
 groups.sort((a, b) => length(b) - length(a));
 if (!groups.length) throw Error('FIXTURE_FRONT_DOES_NOT_INTERSECT_MAINLAND');
 return groups[0];
}

export function buildWarFacts() {
 const nativePath = 'recovery/event-area-propagation-v3/fixtures/REGIONAL-plan.json';
 const nativeBytes = readFileSync(resolve(engine, nativePath));
 const native = JSON.parse(nativeBytes);
 const sourceCountries = Object.fromEntries(['COUNTRY_KOR', 'COUNTRY_PRK'].map(id => {
  const record = native.geometries.find(item => item.id === id);
  if (!record) throw Error('FIXTURE_NATIVE_COUNTRY_MISSING');
  return [id, {type: record.geometry_type, coordinates: structuredClone(record.coordinates)}];
 }));
 const mainland = joinNativeMainland(sourceCountries.COUNTRY_KOR, sourceCountries.COUNTRY_PRK);
 const definitions = [
  {id: 'START', date: '1950-06-25', label: '국군 방어선',
   front: [[125.62, 38], [126.3, 38], [127.2, 38], [128.03, 38], [128.71, 38]],
   planes: [[0, -1, 38]], fact: 'North Korean forces invaded south across the 38th parallel on 25 June 1950.'},
  {id: 'BUSAN', date: '1950-09-01', label: '국군·유엔군 부산 교두보',
   front: [[128.05, 34.9], [128.05, 35.7], [128.28, 36.2], [128.6, 36.63], [129.42, 36.1]],
   planes: [[1, 0, -128.05], [.5, -.23, -.5 * 128.05 + .23 * 35.7],
    [.43, -.32, -.43 * 128.28 + .32 * 36.2], [-.53, -.82, .53 * 128.6 + .82 * 36.63]],
   fact: 'By early September 1950, Republic of Korea and UN forces defended the southeastern Busan perimeter.'},
  {id: 'NORTH_ADVANCE', date: '1950-11-24', label: '국군·유엔군 북진',
   front: [[124.96, 40.16], [125.8, 40.56], [126.67, 40.87], [128.02, 41.09], [129.3, 41.25]],
   planes: [[0.28, -1, 5.11]],
   fact: 'After the Incheon landing and counteroffensive, Republic of Korea and UN forces advanced far north before the major Chinese counteroffensive in late November 1950. The line is an intentionally simplified mainland core-front view, not a continuous archival battlefield front.'},
  {id: 'SEOUL_WITHDRAWAL', date: '1951-01-04', label: '국군·유엔군 후퇴',
   front: [[126.4, 37.02], [127.08, 37.03], [127.83, 37.13], [128.62, 37.29], [129.32, 37.30]],
   planes: [[0.085, -1, 26.29]],
   fact: 'Chinese and North Korean forces recaptured Seoul on 4 January 1951; UN and Republic of Korea forces withdrew south before recovering ground later in 1951.'},
  {id: 'ARMISTICE', date: '1953-07-27', label: '정전선 · 국군·유엔군',
   front: sourceCountries.COUNTRY_KOR.coordinates[0][0].slice(0, 23).map(point => [...point]),
   area: {type: 'Polygon', coordinates: structuredClone(sourceCountries.COUNTRY_KOR.coordinates[0])},
   fact: 'The armistice signed on 27 July 1953 ended active fighting with a front near the 38th parallel. The existing simplified present inter-Korean boundary is used as a visual approximation of the final stalemate, not the surveyed Military Demarcation Line.'}
 ];
 const geometries = [
  {id: 'COUNTRY_KOR', geometry: sourceCountries.COUNTRY_KOR, source_id: 'NATIVE_COUNTRIES'},
  {id: 'COUNTRY_PRK', geometry: sourceCountries.COUNTRY_PRK, source_id: 'NATIVE_COUNTRIES'}
 ];
 const stages = definitions.map(stage => {
  const areaId = 'HELD_CORE_' + stage.id, frontId = 'FRONT_' + stage.id;
  const area = stage.area ?? clipMainland(mainland.geometry, stage.planes);
  validateAreaGeometry(area);
  geometries.push({id: areaId, geometry: area, source_id: 'SCHEMATIC_STATES'},
   {id: frontId, geometry: authoredFront(trimFrontToMainland(stage.front, mainland.geometry)), source_id: 'SCHEMATIC_STATES'});
  return {id: stage.id, date: stage.date, label: stage.label, area_refs: [areaId], front_refs: [frontId],
   fact: stage.fact, semantic_role: 'SIMPLIFIED_REPUBLIC_OF_KOREA_UN_HELD_MAINLAND_CORE'};
 });
 const nativeSource = native.geometries.find(item => item.id === 'COUNTRY_KOR');
 const source_notes = [...historicalReferences, {id: 'NATIVE_COUNTRIES', source_type: 'PUBLIC_DOMAIN_VECTOR_DATA',
  source_reference: 'https://www.naturalearthdata.com/downloads/50m-cultural-vectors/50m-admin-0-countries-2/',
  verification_status: 'VERIFIED', verification_basis: 'EXISTING_VERIFIED_PROJECT_NATIVE_GIS',
  license: 'Natural Earth public domain', crs: 'EPSG:4326', resolution: '1:50,000,000 scale vector dataset',
  version: nativeSource.source_version, original_sha256: nativeSource.source_file_sha256,
  source_wrapper_sha256: sha(nativeBytes), source_wrapper_path: nativePath,
  note: 'Existing project source geometry is reused byte for byte. Only new illustrative event polygons are clipped to its mainland coastline; native country geometry and boundaries remain unchanged.'}];
 const facts = {version: 'PLANNER_FACTS_V1', data_mode: 'PRODUCTION',
  semantic_mode: 'ILLUSTRATIVE_FACT_BASED_VISUAL',
  subject: {id: 'KOREAN_WAR', label: '한국전쟁의 전선', aliases: ['한국전쟁', 'Korean War', '6.25 전쟁'], event_family: 'WAR'},
  locations: [{id: 'SEOUL', label: '서울', anchor: [126.978, 37.5665]},
   {id: 'BUSAN_LOCATION', label: '부산', anchor: [129.0756, 35.1796]},
   {id: 'PYONGYANG', label: '평양', anchor: [125.7625, 39.0392]}],
  time_range: {start: '1950-06-25', end: '1953-07-27'}, source_notes, geometries, stages,
  markers: [{id: 'SEOUL_MARKER', label: '서울', anchor: [126.978, 37.5665], source_id: 'NATIVE_COUNTRIES'}],
  text: [{id: 'TITLE', content: '한국전쟁의 전선', role: 'TITLE'}],
  camera: {anchor: [126.978, 37.5665], target_geometry_refs: geometries.map(item => item.id),
   minimum_context_geometry_refs: ['COUNTRY_KOR', 'COUNTRY_PRK'], detail_policy: 'FACT_BASED_VISUAL_GRADE'},
  scale: {preferred: 'REGIONAL'},
  native_context: {country_ids: ['COUNTRY_KOR', 'COUNTRY_PRK'], primary_country_id: 'COUNTRY_KOR',
   secondary_country_ids: ['COUNTRY_PRK'], context_location_ids: ['SEOUL']},
  native_labels: [{text: '남한', coordinates: [127.42, 36.05], geometry_ref: 'COUNTRY_KOR'},
   {text: '북한', coordinates: [126.87, 40.1], geometry_ref: 'COUNTRY_PRK'}],
  authoring: {quality_policy: 'FACT_BASED_VISUAL_GRADE', historical_control_accuracy: 'SCHEMATIC_NOT_ARCHIVAL',
   simulation: 'NONE', territory_meaning: 'SIMPLIFIED_ALLIED_HELD_MAINLAND_CORE',
   uncertainty: ['No claim of precise military unit positions or uninterrupted line of battle.',
    'Simplified state sketches omit pockets, islands, and detailed local terrain.',
    'Historical source bodies were not retrieved because the managed proxy denied access.'],
   build_recipe: 'node recovery/planner-scene-json-v1/build_war_fixture.mjs'}};
 return {facts, references: {version: 'WAR_FIXTURE_SOURCES_V1', retrieval_date: '2026-10-13', sources: source_notes},
  native: {version: 'NATIVE_PENINSULA_DERIVATIVE_V1', crs: 'EPSG:4326', license: 'Natural Earth public domain',
   source_path: nativePath, source_sha256: sha(nativeBytes), countries: sourceCountries, mainland,
   derivative_sha256: sha(serialize(mainland.geometry))},
  provenance: {version: 'WAR_FIXTURE_PROVENANCE_V1', status: 'PASS', quality_policy: 'FACT_BASED_VISUAL_GRADE',
   stage_count: stages.length, geography: 'Korean peninsula', selection_reason: 'Publicly established chronology with clear southward advance, northern counter-advance, renewed withdrawal, and final stalemate; readable without adding military simulation or transport primitives.',
   original_country_geometry_unchanged: true, new_geometry_scope: 'Illustrative authored event state polygons/fronts only',
   historical_reference_live_access: 'REFERENCE_ONLY_RETRIEVAL_BLOCKED',
   renderer_changes: false, camera_core_changes: false, required_temp_only_files: 0,
   source_native_sha256: sha(nativeBytes), fact_data_sha256: sha(serialize(facts))}};
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
 const result = buildWarFacts();
 mkdirSync(resolve(folder, 'data'), {recursive: true});
 for (const [file, value] of Object.entries({'FACT_DATA.json': result.facts, 'SOURCE_REFERENCES.json': result.references,
  'NATIVE_PENINSULA.json': result.native, 'FACT_PROVENANCE.json': result.provenance}))
  writeFileSync(resolve(folder, 'data', file), serialize(value));
 console.log(JSON.stringify({status: 'PASS', stageCount: result.facts.stages.length,
  factSha256: sha(serialize(result.facts)), sourcesLiveAccess: 'REFERENCE_ONLY_RETRIEVAL_BLOCKED'}));
}
