import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {validateNationalFlagProfiles,validateNationalUnitBadgeFixture,evaluateNationalUnitBadgeLayout,
 measureNationalUnitBadge} from '../../web/map_infographic_v1/national_unit_badge_v1.mjs';
import {compileUnitParticipationPolicy,validateHistoricalFlagProfile} from '../../web/map_infographic_v1/unit_participation_policy_v1.mjs';
const root=path.dirname(fileURLToPath(import.meta.url));
const fixture=JSON.parse(fs.readFileSync(path.join(root,'fixtures/NATIONAL_FLAG_PROFILES.json')));
const profiles=fixture.profiles;
const units=[{id:'GENERIC_A',profile_id:'US_MODERN_50_STAR',role:'GROUND',
 anchor_frames:[[127,37],[127.001,37]],size_frames:[104,104],rotation_frames:[11,11.1]}];

test('modern and historical flag datasets remain distinct with the correct star counts',()=>{
 assert.equal(validateNationalFlagProfiles(profiles).profiles,7);
 assert.equal(profiles.US_MODERN_50_STAR.flag_geometry.filter(s=>s.type==='star').length,50);
 assert.equal(profiles.US_1950_48_STAR.flag_geometry.filter(s=>s.type==='star').length,48);
 assert.equal(profiles.PRC_1949.flag_geometry.filter(s=>s.type==='star').length,5);
 assert.equal(profiles.DPRK_1948.flag_geometry.filter(s=>s.type==='star').length,1);
 assert.equal(profiles.USSR_1936.traits.hammer_sickle,true);
 assert.equal(profiles.USSR_1936.traits.modern_tricolor,false);
 assert.equal(profiles.RUS_MODERN_TRICOLOR.traits.modern_tricolor,true);
 assert.equal(profiles.ROK_1949_TAEGEUK.traits.trigram_count,4);
 assert.equal(profiles.USSR_1936.private_only,true);
});
test('original tablet artwork support stays inside the unchanged layout envelope at every rotation',()=>{
 for(let rotation=-180;rotation<180;rotation+=3){
  const measured=measureNationalUnitBadge({sizePx:104,rotationDegrees:rotation,aspectRatio:1.9});
  assert.equal(measured.conservativeSupportWithinReusedOctagon,true);
  assert.equal(measured.flagWidthPx,66.56);
  assert.ok(Math.abs(measured.flagHeightPx-35.03157894736842)<1e-8);
 }
});
test('renderer uses explicit profiles and resolved frame positions without applying historical gates',()=>{
 const before=JSON.stringify({units,profiles});
 assert.equal(validateNationalUnitBadgeFixture(units,profiles).units,1);
 const layout=evaluateNationalUnitBadgeLayout(units,0,{project:()=>[540,900],safeArea:[48,72,1032,1848]});
 assert.deepEqual(layout.units[0].position,[540,900]);
 assert.equal(layout.historicalPolicyApplied,false);assert.equal(layout.noRenderedText,true);
 assert.equal(layout.criticalCollisions.length,0);assert.equal(layout.units[0].actualArtworkInsideProtectedFootprint,true);
 assert.equal(JSON.stringify({units,profiles}),before);
});
test('existing protected graphics are reported without being moved by the artwork pass',()=>{
 const protectedGraphics=[{id:'OLD_MARKER',bounds:[520,870,560,930]}];
 const before=JSON.stringify(protectedGraphics);
 const layout=evaluateNationalUnitBadgeLayout(units,0,{project:()=>[540,900],safeArea:[48,72,1032,1848],protectedGraphics});
 assert.equal(layout.criticalCollisions.length,1);assert.equal(JSON.stringify(protectedGraphics),before);
});
test('source portrait and pixel textures are rejected rather than quietly copied',()=>{
 const invalid=structuredClone(profiles);invalid.US_MODERN_50_STAR.face_portrait='SOURCE';
 assert.throws(()=>validateNationalFlagProfiles(invalid),/DATA_PROFILE_REQUIRED/);
 const invalidRole=structuredClone(units);invalidRole[0].role='SOVIET_GROUND_INVASION';
 assert.throws(()=>validateNationalUnitBadgeFixture(invalidRole,profiles),/PROFILE_ROLE_REQUIRED/);
});
test('private historical policy checks actual authored profiles without changing modern public profiles',()=>{
 const policy=compileUnitParticipationPolicy(JSON.parse(fs.readFileSync(path.join(root,'fixtures/HISTORICAL_UNIT_POLICY.json'))));
 for(const [country_id,id] of [['ROK','ROK_1949_TAEGEUK'],['US','US_1950_48_STAR'],
  ['DPRK','DPRK_1948'],['PRC','PRC_1949'],['USSR','USSR_1936']]) {
  const actual=validateHistoricalFlagProfile(policy,{country_id,date:'1951-01-04',flag_profile:profiles[id]});
  assert.equal(actual.status,'ELIGIBLE',id);
  assert.equal(actual.validation_scope,'DECLARED_DESIGN_TRAITS_NOT_PIXEL_CERTIFICATION');
 }
 assert.equal(validateHistoricalFlagProfile(policy,{country_id:'US',date:'1951-01-04',
  flag_profile:profiles.US_MODERN_50_STAR}).status,'NOT_ELIGIBLE');
 assert.equal(validateHistoricalFlagProfile(policy,{country_id:'USSR',date:'1951-01-04',
  flag_profile:profiles.RUS_MODERN_TRICOLOR}).status,'NOT_ELIGIBLE');
 assert.equal(profiles.US_MODERN_50_STAR.traits.star_count,50);
 assert.equal(profiles.RUS_MODERN_TRICOLOR.traits.modern_tricolor,true);
});
