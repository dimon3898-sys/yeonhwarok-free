/** Keep the measured motion data; author a separate, original visual profile. */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {validateWorldEngineUnitFixture} from '../../web/map_infographic_v1/world_engine_unit_overlay_v3.mjs';

const root = path.dirname(fileURLToPath(import.meta.url));
const engine = path.resolve(root, '../..');
const sourcePath = path.join(engine, 'recovery/reference-quality-rework-v2/fixtures/COMBAT_PROFILE.json');
const sourceBytes = fs.readFileSync(sourcePath);
const source = JSON.parse(sourceBytes);
const digest = value => crypto.createHash('sha256').update(typeof value === 'string' ? value : JSON.stringify(value)).digest('hex');
// Affiliation assignment is fixture data. The generic unit renderer has no
// nation, coordinate, source-ID or scenario-specific color branch.
const assignments = {
 north_01: 'WORLD_ENGINE_WARM_INFANTRY', north_02: 'WORLD_ENGINE_WARM_INFANTRY', north_03: 'WORLD_ENGINE_WARM_INFANTRY',
 south_01: 'WORLD_ENGINE_COOL_INFANTRY', south_02: 'WORLD_ENGINE_COOL_INFANTRY', south_03: 'WORLD_ENGINE_COOL_INFANTRY',
 south_04: 'WORLD_ENGINE_COOL_INFANTRY', south_05: 'WORLD_ENGINE_COOL_INFANTRY',
};
const profile = (faction, highlight) => ({role: 'INFANTRY', artwork: 'ORIGINAL_FULL_BODY_ISOMETRIC_INFANTRY',
 faction_color: faction, faction_highlight: highlight, metal_palette: ['#b7cbc2', '#708b8d', '#344e55'],
 base_size_px: 72, authorship: 'WORLD_ENGINE_ORIGINAL_AUTHORED_VECTOR',
 faction_encoding: 'SMALL_UNBRANDED_SHOULDER_AND_CHEST_PANELS', ground_contact: 'SUBDUED_SOFT_SHADOW',
 no_national_insignia: true, no_source_icon_copy: true});
const profiles = {WORLD_ENGINE_WARM_INFANTRY: profile('#e95e37', '#ffb77e'),
 WORLD_ENGINE_COOL_INFANTRY: profile('#a67aef', '#d7b6ff')};
const units = source.units.map(unit => {
 if (!assignments[unit.id] || !Number.isFinite(unit.size_frames[0])) throw Error('ORIGINAL_UNIT_FIXTURE_SOURCE_ASSIGNMENT_REQUIRED');
 return {id: unit.id, profile_id: assignments[unit.id], anchor_frames: structuredClone(unit.anchor_frames),
  rotation_frames: [...unit.rotation_frames], size_frames: unit.size_frames.map(size => size / unit.size_frames[0] * 72)};
});
validateWorldEngineUnitFixture(units, profiles);
const coordinates = value => value.map(unit => ({id: unit.id, anchor_frames: unit.anchor_frames, rotation_frames: unit.rotation_frames}));
const originalBinding = digest(coordinates(source.units)), newBinding = digest(coordinates(units));
if (source.units.length !== 8 || originalBinding !== newBinding) throw Error('ORIGINAL_UNIT_ANCHOR_ROTATION_BINDING_CHANGED');
const result = {version: 'WORLD_ENGINE_ORIGINAL_UNIT_PROFILE_V3', units, profiles,
 source_semantics: source.source_semantics, source_visible_unit_count: source.source_visible_unit_count,
 motion_owner: source.motion_owner, interpolation: source.interpolation,
 artwork: 'ORIGINAL_FULL_BODY_ISOMETRIC_INFANTRY', source_icon_artwork_copied: false,
 source_motion: {path: 'recovery/reference-quality-rework-v2/fixtures/COMBAT_PROFILE.json',
  sha256: crypto.createHash('sha256').update(sourceBytes).digest('hex'),
  anchor_rotation_binding_sha256: originalBinding, anchors_and_rotations_unchanged: true,
  temporal_size_ratio_unchanged: true, role_base_size_px: 72},
 excluded: ['NATIONAL_FLAGS', 'INSIGNIA', 'FACE_PORTRAIT', 'VISIBLE_OCTAGON_BADGE', 'NEON_RING',
  'ARROWS', 'ROUTE_TRACES', 'SPECULATIVE_EXPLOSIONS', 'AIRCRAFT', 'SHIP', 'TANK']};
fs.mkdirSync(path.join(root, 'fixtures'), {recursive: true});
fs.writeFileSync(path.join(root, 'fixtures/ORIGINAL_UNIT_PROFILE.json'), JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify({status: 'PASS', units: units.length, frames: units[0].anchor_frames.length,
 nominal_sprite_range_px: [Math.min(...units.flatMap(unit => unit.size_frames)), Math.max(...units.flatMap(unit => unit.size_frames))],
 anchors_and_rotations_unchanged: true, temporal_size_ratio_unchanged: true, original_artwork: true,
 national_flags: 0, speculative_combat_effects: 0}));
