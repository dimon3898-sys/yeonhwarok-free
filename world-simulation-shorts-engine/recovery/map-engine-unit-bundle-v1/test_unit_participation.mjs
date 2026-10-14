import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import {compileUnitParticipationPolicy, evaluateUnitParticipation, validateHistoricalFlagProfile} from '../../web/map_infographic_v1/unit_participation_policy_v1.mjs';

const source = JSON.parse(readFileSync(new URL('./fixtures/HISTORICAL_UNIT_POLICY.json', import.meta.url), 'utf8'));
const policy = compileUnitParticipationPolicy(source);
const FLAGS = {
  ROK: {id: 'ROK_1949_TAEGEUK', country_id: 'ROK', traits: {taegeuk: true, trigram_count: 4}},
  US: {id: 'US_1950_48_STAR', country_id: 'US', traits: {star_count: 48, star_rows: 6, star_columns: 8}},
  DPRK: {id: 'DPRK_1948', country_id: 'DPRK', traits: {star_count: 1}},
  PRC: {id: 'PRC_1949', country_id: 'PRC', traits: {star_count: 5}},
  USSR: {id: 'USSR_1936', country_id: 'USSR', traits: {hammer_sickle: true, outlined_star: true, modern_tricolor: false}},
};
const evaluate = (country_id, date, options = {}) => evaluateUnitParticipation(policy, {
  scene_semantics: 'HISTORICAL_FACT_BASED_VISUAL', event_id: 'KOREAN_WAR',
  country_id, date, role: 'GROUND_COMBAT', location_scope: 'KOREAN_PENINSULA',
  location_evidence: 'PRIVATE_AUTHORED_SCHEMATIC_LOCATION_NOT_EXACT_UNIT_POSITION',
  flag_profile: FLAGS[country_id], ...options,
});
const codes = result => result.reasons.map(item => item.code);

test('Private historical rules do not alter or block the modern counterfactual scene', () => {
  const request = {scene_semantics: 'COUNTERFACTUAL_REFERENCE_VISUAL_STUDY_NOT_KOREAN_WAR_HISTORY', country_id: 'RUS'};
  const before = JSON.stringify(request);
  const result = evaluateUnitParticipation(policy, request);
  assert.equal(result.status, 'OUT_OF_SCOPE');
  assert.equal(result.eligible, false);
  assert.deepEqual(codes(result), ['HISTORICAL_POLICY_NOT_APPLIED_TO_SCENE']);
  assert.equal(JSON.stringify(request), before);
});

test('US ground arrival and first combat are not conflated; air involvement has its own gate', () => {
  assert.equal(evaluate('US', '1950-07-01').eligible, false);
  assert.ok(codes(evaluate('US', '1950-07-04')).includes('OUTSIDE_ROLE_PARTICIPATION_INTERVAL'));
  assert.equal(evaluate('US', '1950-07-05').eligible, true);
  assert.equal(evaluate('US', '1950-06-26', {role: 'AVIATION', location_scope: 'KOREAN_AIRSPACE'}).eligible, false);
  assert.equal(evaluate('US', '1950-06-27', {role: 'AVIATION', location_scope: 'KOREAN_AIRSPACE'}).eligible, true);
  assert.equal(evaluate('US', '1950-06-27').eligible, false);
});

test('Chinese border crossing does not prematurely enable PVA ground combat', () => {
  assert.equal(evaluate('PRC', '1950-10-19').eligible, false);
  assert.equal(evaluate('PRC', '1950-10-24').eligible, false);
  assert.equal(evaluate('PRC', '1950-10-25').eligible, true);
});

test('Soviet aviation and rear support cannot become ordinary ground occupation', () => {
  assert.equal(evaluate('USSR', '1951-01-04').eligible, false);
  assert.ok(codes(evaluate('USSR', '1951-01-04')).includes('ROLE_NOT_ADMITTED'));
  assert.equal(evaluate('USSR', '1950-06-25', {role: 'SUPPORT', location_scope: 'EXTERNAL_SUPPORT_BASE'}).eligible, true);
  assert.equal(evaluate('USSR', '1950-10-31', {role: 'AVIATION', location_scope: 'KOREAN_AIRSPACE'}).eligible, false);
  const air = evaluate('USSR', '1950-11-15', {role: 'AVIATION', location_scope: 'KOREAN_AIRSPACE'});
  assert.equal(air.eligible, true);
  assert.equal(air.participation_date_precision, 'MONTH');
  assert.equal(evaluate('USSR', '1951-01-04', {role: 'SUPPORT'}).eligible, false);
});

test('1950–1953 US flag requires 48 stars; modern 50-star flag is rejected', () => {
  assert.equal(evaluate('US', '1950-07-05').eligible, true);
  const incorrectArt = evaluate('US', '1950-07-05', {flag_profile: {...FLAGS.US, traits: {...FLAGS.US.traits, star_count: 50}}});
  assert.ok(codes(incorrectArt).includes('FLAG_TRAITS_MISMATCH'));
  const modern = {id: 'US_MODERN_50_STAR', country_id: 'US', traits: {star_count: 50, star_rows: 9}};
  assert.ok(codes(evaluate('US', '1950-07-05', {flag_profile: modern})).includes('FLAG_OUTSIDE_DATE_VALIDITY'));
  assert.equal(validateHistoricalFlagProfile(policy, {country_id: 'US', date: '1960-07-04', flag_profile: modern}).eligible, true);
});

test('Historical Soviet identity cannot use a modern Russian tricolor', () => {
  const modern = {id: 'RUS_MODERN_TRICOLOR', country_id: 'RUS', traits: {modern_tricolor: true}};
  const result = evaluate('USSR', '1951-01-04', {role: 'AVIATION', location_scope: 'KOREAN_AIRSPACE', flag_profile: modern});
  assert.ok(codes(result).includes('FLAG_COUNTRY_MISMATCH'));
  assert.ok(codes(result).includes('FLAG_OUTSIDE_DATE_VALIDITY'));
  assert.equal(evaluate('RUS', '1951-01-04', {flag_profile: modern}).eligible, false);
});

test('Nation flag contracts remain distinct; all five are not admitted at outbreak', () => {
  assert.equal(evaluate('ROK', '1950-06-25').eligible, true);
  assert.equal(evaluate('DPRK', '1950-06-25').eligible, true);
  assert.equal(evaluate('US', '1950-06-25').eligible, false);
  assert.equal(evaluate('PRC', '1950-06-25').eligible, false);
  assert.equal(evaluate('USSR', '1950-06-25').eligible, false);
  assert.ok(codes(evaluate('ROK', '1950-06-25', {flag_profile: FLAGS.DPRK})).includes('FLAG_COUNTRY_MISMATCH'));
});

test('Unspecified historical dates and invalid calendar days cannot imply participation', () => {
  for (const date of [undefined, '1950-02-30', '1950-13-01', '1950-7-5']) {
    assert.ok(codes(evaluate('US', date)).includes('INVALID_OR_MISSING_DATE'));
  }
  assert.ok(codes(evaluate('US', '1953-07-28')).includes('OUTSIDE_EVENT_DATE_RANGE'));
  assert.ok(codes(evaluate('US', '1950-07-05', {event_id: 'UNRELATED_EVENT'})).includes('EVENT_MISMATCH'));
});

test('Country eligibility is not evidence of exact geographic unit placement', () => {
  assert.ok(codes(evaluate('ROK', '1950-06-25', {location_evidence: ''})).includes('LOCATION_EVIDENCE_REQUIRED'));
  assert.ok(codes(evaluate('ROK', '1950-06-25', {claims_exact_unit_position: true})).includes('EXACT_UNIT_POSITION_NOT_VERIFIED'));
  assert.equal(evaluate('ROK', '1950-06-25').does_not_verify_historical_unit_coordinates, true);
  assert.equal(evaluate('ROK', '1950-06-25').does_not_modify_public_scene, true);
});

test('Country/date/role behavior comes from data, not engine country-name branches', () => {
  const other = structuredClone(source);
  other.event_id = 'OTHER_EVENT';
  other.countries = [{country_id: 'TEST_NATION', aliases: ['TEST_ALIAS'], role_rules: [{role: 'SUPPORT', start_date: '1951-01-01', location_scopes: ['TEST_REAR']}]}];
  other.flag_profiles = [{id: 'TEST_FLAG', country_id: 'TEST_NATION', valid_from: '1950-01-01', required_traits: {design: 'INDEPENDENT'}}];
  const compiled = compileUnitParticipationPolicy(other);
  const result = evaluateUnitParticipation(compiled, {scene_semantics: 'HISTORICAL_FACT_BASED_VISUAL', event_id: 'OTHER_EVENT', country_id: 'TEST_ALIAS', date: '1951-01-01', role: 'SUPPORT', location_scope: 'TEST_REAR', location_evidence: 'PRIVATE_TEST_DATA', flag_profile: {id: 'TEST_FLAG', country_id: 'TEST_NATION', traits: {design: 'INDEPENDENT'}}});
  assert.equal(result.eligible, true);
  assert.equal(result.country_id, 'TEST_NATION');
  assert.equal(evaluate('KOR', '1950-06-25', {flag_profile: FLAGS.ROK}).eligible, true);
});

test('Compilation preserves its input and rejects ambiguous role/date specifications', () => {
  const before = JSON.stringify(source);
  compileUnitParticipationPolicy(source);
  assert.equal(JSON.stringify(source), before);
  assert.equal(Object.isFrozen(policy.countries[0].role_rules[0]), true);
  const malformed = structuredClone(source);
  malformed.countries[0].role_rules[0].start_date = '1950-02-30';
  assert.throws(() => compileUnitParticipationPolicy(malformed), /role rule/);
  const duplicate = structuredClone(source);
  duplicate.countries[0].role_rules.push({...duplicate.countries[0].role_rules[0]});
  assert.throws(() => compileUnitParticipationPolicy(duplicate), /role rule/);
});
