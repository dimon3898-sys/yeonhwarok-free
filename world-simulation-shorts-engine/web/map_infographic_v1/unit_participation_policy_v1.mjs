/**
 * Data-driven participation/flag checks for private historical fixtures.
 * This optional validator never reinterprets a counterfactual scene as history,
 * modifies an actor, or owns projection, motion, artwork, or rendering.
 */
const COMPILED = new WeakSet();
const nonempty = value => typeof value === 'string' && value.length > 0;
const immutable = value => {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    for (const item of Object.values(value)) immutable(item);
    Object.freeze(value);
  }
  return value;
};
const calendarDay = value => {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const date = new Date(`${value}T00:00:00.000Z`);
  if (!Number.isFinite(date.valueOf()) || date.toISOString().slice(0, 10) !== value) return null;
  return date.valueOf();
};
const inRange = (day, start, end) => day >= calendarDay(start) && (!end || day <= calendarDay(end));
const traitMismatches = (expected, actual, prefix = 'traits') => {
  const failures = [];
  for (const [key, value] of Object.entries(expected || {})) {
    const path = `${prefix}.${key}`;
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      failures.push(...traitMismatches(value, actual?.[key], path));
    } else if (JSON.stringify(value) !== JSON.stringify(actual?.[key])) failures.push(path);
  }
  return failures;
};
const reason = (code, detail) => detail === undefined ? {code} : {code, detail};
const output = (status, reasons, details = {}) => immutable({status, eligible: status === 'ELIGIBLE', reasons, ...details});
const assertCompiled = policy => {
  if (!COMPILED.has(policy)) throw new TypeError('Use compileUnitParticipationPolicy before evaluation.');
};

export function compileUnitParticipationPolicy(input) {
  const policy = structuredClone(input);
  if (policy?.version !== 'UNIT_PARTICIPATION_POLICY_V1' || !nonempty(policy.semantic_mode) || !nonempty(policy.event_id)) {
    throw new TypeError('Invalid unit participation policy contract.');
  }
  if (!Array.isArray(policy.accepted_scene_semantics) || !policy.accepted_scene_semantics.length ||
      !policy.accepted_scene_semantics.every(nonempty)) throw new TypeError('Historical scene semantics must be explicit.');
  const eventStart = calendarDay(policy.event_time_range?.start_date);
  const eventEnd = calendarDay(policy.event_time_range?.end_date);
  if (eventStart === null || eventEnd === null || eventEnd < eventStart) throw new TypeError('Invalid event date range.');
  if (!Array.isArray(policy.countries) || !policy.countries.length || !Array.isArray(policy.flag_profiles)) {
    throw new TypeError('Country and flag data are required.');
  }
  const aliases = {};
  for (const country of policy.countries) {
    if (!nonempty(country.country_id) || !Array.isArray(country.role_rules) || !country.role_rules.length) {
      throw new TypeError('Country entries require data-driven role rules.');
    }
    for (const alias of [country.country_id, ...(country.aliases || [])]) {
      if (!nonempty(alias) || aliases[alias]) throw new TypeError('Country identifiers must be unique.');
      aliases[alias] = country.country_id;
    }
    const roles = new Set();
    for (const rule of country.role_rules) {
      if (!nonempty(rule.role) || roles.has(rule.role) || calendarDay(rule.start_date) === null ||
          (rule.end_date && (calendarDay(rule.end_date) === null || calendarDay(rule.end_date) < calendarDay(rule.start_date))) ||
          !Array.isArray(rule.location_scopes) || !rule.location_scopes.length || !rule.location_scopes.every(nonempty)) {
        throw new TypeError('Invalid or ambiguous participation role rule.');
      }
      roles.add(rule.role);
    }
  }
  const ids = new Set();
  for (const profile of policy.flag_profiles) {
    if (!nonempty(profile.id) || ids.has(profile.id) || !nonempty(profile.country_id) ||
        calendarDay(profile.valid_from) === null ||
        (profile.valid_to && (calendarDay(profile.valid_to) === null || calendarDay(profile.valid_to) < calendarDay(profile.valid_from))) ||
        !profile.required_traits || typeof profile.required_traits !== 'object') {
      throw new TypeError('Invalid flag profile specification.');
    }
    ids.add(profile.id);
  }
  policy.country_aliases = aliases;
  COMPILED.add(policy);
  return immutable(policy);
}

export function validateHistoricalFlagProfile(policy, {country_id, date, flag_profile} = {}) {
  assertCompiled(policy);
  const day = calendarDay(date);
  if (day === null) return output('NOT_ELIGIBLE', [reason('INVALID_OR_MISSING_DATE')]);
  const expected = policy.flag_profiles.find(profile => profile.id === flag_profile?.id);
  if (!expected) return output('NOT_ELIGIBLE', [reason('UNKNOWN_FLAG_PROFILE')]);
  const canonicalCountry = policy.country_aliases[country_id] || country_id;
  const providedCountry = policy.country_aliases[flag_profile.country_id] || flag_profile.country_id;
  const reasons = [];
  if (expected.country_id !== canonicalCountry || providedCountry !== canonicalCountry) reasons.push(reason('FLAG_COUNTRY_MISMATCH'));
  if (!inRange(day, expected.valid_from, expected.valid_to)) reasons.push(reason('FLAG_OUTSIDE_DATE_VALIDITY'));
  const mismatches = traitMismatches(expected.required_traits, flag_profile.traits);
  if (mismatches.length) reasons.push(reason('FLAG_TRAITS_MISMATCH', mismatches));
  return output(reasons.length ? 'NOT_ELIGIBLE' : 'ELIGIBLE', reasons, {profile_id: expected.id, validation_scope: 'DECLARED_DESIGN_TRAITS_NOT_PIXEL_CERTIFICATION'});
}

export function evaluateUnitParticipation(policy, request = {}) {
  assertCompiled(policy);
  if (!policy.accepted_scene_semantics.includes(request.scene_semantics)) {
    return output('OUT_OF_SCOPE', [reason('HISTORICAL_POLICY_NOT_APPLIED_TO_SCENE')], {policy_scope: policy.semantic_mode});
  }
  if (request.event_id !== policy.event_id) return output('NOT_ELIGIBLE', [reason('EVENT_MISMATCH')]);
  const day = calendarDay(request.date);
  if (day === null) return output('NOT_ELIGIBLE', [reason('INVALID_OR_MISSING_DATE')]);
  if (!inRange(day, policy.event_time_range.start_date, policy.event_time_range.end_date)) {
    return output('NOT_ELIGIBLE', [reason('OUTSIDE_EVENT_DATE_RANGE')]);
  }
  const canonicalCountry = policy.country_aliases[request.country_id];
  const country = policy.countries.find(item => item.country_id === canonicalCountry);
  if (!country) return output('NOT_ELIGIBLE', [reason('UNKNOWN_COUNTRY')]);
  const role = country.role_rules.find(item => item.role === request.role);
  if (!role) return output('NOT_ELIGIBLE', [reason('ROLE_NOT_ADMITTED')], {country_id: canonicalCountry});
  const reasons = [];
  if (!inRange(day, role.start_date, role.end_date)) reasons.push(reason('OUTSIDE_ROLE_PARTICIPATION_INTERVAL'));
  if (!role.location_scopes.includes(request.location_scope)) reasons.push(reason('LOCATION_SCOPE_NOT_ADMITTED'));
  if (policy.require_location_evidence && !nonempty(request.location_evidence)) reasons.push(reason('LOCATION_EVIDENCE_REQUIRED'));
  if (request.claims_exact_unit_position && !request.exact_unit_position_verified) reasons.push(reason('EXACT_UNIT_POSITION_NOT_VERIFIED'));
  const flag = validateHistoricalFlagProfile(policy, {country_id: canonicalCountry, date: request.date, flag_profile: request.flag_profile});
  reasons.push(...flag.reasons);
  return output(reasons.length ? 'NOT_ELIGIBLE' : 'ELIGIBLE', reasons, {
    country_id: canonicalCountry,
    role: request.role,
    date: request.date,
    profile_id: flag.profile_id || null,
    policy_scope: policy.semantic_mode,
    evidence_status: policy.evidence_status,
    participation_date_precision: role.date_precision || 'DAY',
    does_not_verify_historical_unit_coordinates: true,
    does_not_modify_public_scene: true,
  });
}
