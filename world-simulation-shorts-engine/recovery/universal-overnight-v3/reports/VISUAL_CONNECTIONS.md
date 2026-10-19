# Optional advanced visual owners: source-bound CPU connection

This report concerns the new `visual_extensions.mjs` adapter only. It does not
change the protected camera, Area, Flow, Event, map renderer, shaders, historical
source files, FINAL, old candidates, images, or claims. CPU instrumentation below
is not a rendered output or NVIDIA verification.

## Connected existing owners

| Feature IDs | Existing implementation called | New connection | Current historical 80-second data |
|---|---|---|---|
| `TERRITORY.COMPLEMENTARY_SCALAR_CONTROL` | `compileTerritoryControlPlan`, `evaluateTerritoryControlFrame` in `territory_control_adapter_v1.mjs` | Exact canonical source plan, absolute-frame evaluation, original complementary classifier | `DATA_BLOCKED`: no verified bilateral monotone ownership plan. Eight partial front records cannot supply this contract. |
| `TERRITORY.GAIN_STYLE` | `applyReferenceTerritoryStyle`, `describeReferenceGainStyle` | Bounded material selection passed to original `createTerritoryControlPass` | Conditional on the same missing scalar source. No gained area is generated here. |
| `FRONTIER.MOVING_SCALAR_LIGHT` | `compileControlFrontierLightMotion`, `evaluateControlFrontierLightMotion`, `createControlFrontierLightPassV3` | Same source control boundary drives motion, stop response, original core and halo | Conditional on scalar source plus native composition slot; existing parent fill/front must be absent before an added scalar pass is allowed. |
| `FRONTIER.TERRAIN_DESTINATION_LIGHT` | Existing `createControlFrontierLightPassV3` destination-light consumer | Requires a genuine same-frame, pre-territory native terrain texture. GPU owner also checks `gl.isTexture`. | Native texture slot is not supplied by the protected current historical path; not silently replaced with a finished screenshot. |
| `FRONTIER.OUTER_DOMAIN_GOLD` | `createNativeDomainBinding`, `publishNativeDomainCoverage`, `assertOuterDomainContext`, `createCoverageOuterGlowPass` | Actual native primary/secondary role coverage, exact source domain and frame/projection checks | Requires source-matched native role coverage. General land coverage or RGB thresholds cannot substitute. |
| `UNITS.NATIONAL_TABLETS` | `validateNationalUnitBadgeFixture`, `evaluateNationalUnitBadgeLayout`, `createNationalUnitBadgeOverlay` | Authoritative per-frame anchors/roles/profiles; current layout checked before drawing | `DATA_BLOCKED`: no authoritative historical per-frame troop-position source. City anchors or modern hypothetical units are not relabelled as historical troops. |
| `UNITS.SAFE_STATIC_SCALE` | `selectReferenceUnitScale` | Existing all-frame search chooses a single bounded scale; current actual projection/protected layout is checked again | Conditional on a verified national-unit scene. No animated size pumping or anchor repair is added. |

The generic adapters now have explicit source-to-evaluator-to-real-factory paths.
That statement does not mean these optional owners are applied to the historical
80-second image. The production trusted catalog currently has zero
`SCALAR_CONTROL_PLAN` and zero `NATIONAL_UNIT_SCENE` records. Selecting a missing
source fails before rendering; default null selections create no extra GPU pass.

## Safe exact request

The default is deliberately a no-op:

```json
{
  "schema": "WORLD_ENGINE_OVERNIGHT_VISUAL_V1",
  "scalarTerritory": null,
  "nationalUnits": null
}
```

Only an existing server-admitted source ID and SHA can select an optional owner.
The public request cannot supply trusted-source payloads or change their
verification status. Unsupported keys are rejected. Synthetic records are
accepted only with the explicit internal CPU-test option, never by the production
`--admit` entry point.

`scalarTerritory`, when selected, has exactly `sourceId`, `sha256`, `gain`, and
`frontier`. Existing bounded gain/frontier validators own those profiles.
`frontier: null` disables the optional frontier consumer. `nationalUnits`, when
selected, has exactly `sourceId`, `sha256`, and `markerScale` (1–1.25).

The source roles are exact and are never converted from a generic `GEOMETRY`:

* `SCALAR_CONTROL_PLAN`: a canonical original plan, original territory/light
  styles, and optional original native role/domain binding. Fact-based production
  mode must agree with the backend verification status.
* `NATIONAL_UNIT_SCENE`: verified resolved per-frame national-unit data with its
  existing camera/layout context. Frame counts and FPS must match the video.

## Deliberately unexposed protected contracts

`MAP.REFERENCE_PRESENTATION_ROLL` remains blocked in the historical Studio path.
The existing presentation pass rotates a genuinely rendered geographic layer;
it needs native overscan, a slot before screen-fixed graphics, and the presented
projection in every layout owner. Applying it as an arbitrary final-image
rotation would also rotate protected text and can crop geography. No roll knob
is accepted by this adapter.

`DETAIL.POST_ARRIVAL_APPROACH` remains blocked when fresh native 1080×1920 visual
admission and source-bound candidate layout are missing. The preserved detail
adapter is not replaced with an unadmitted tighter crop. Lack of survey-grade
certification is not the blocker: the missing contracts are actual visual
evidence and camera-floor compatibility.

Terrain and ocean material quality, signed bathymetry, NoData, ASTRA support
feathering, and golden illumination remain owned by the existing material path.
This adapter adds no fabricated height, depth, masks, material shaders, or new
terrain style claims.

## Focused free verification

Command:

```text
node --test --test-isolation=none recovery/universal-overnight-v3/tests/test_visual_extensions.mjs
```

15 tests pass against the actual imported original CPU compilers, evaluators,
material transforms, motion/stop logic, national all-frame scale/layout owner,
and explicitly instrumented draw consumers. Tests cover exact source SHA/role,
canonicality, clock, source mutation rejection, synthetic/production separation,
southern/western generic coordinates, parent layer protection, stale terrain,
same-frame role coverage, native projection, current protected layout, invalid
scales, failed factory cleanup, and disposal.

No WebGL context is created by these tests. GPU draw consumers are spies labelled
`cpuInstrumentation: true`; output evidence is always `gpuOutputVerified: false`.
Separate free-software render evidence, if produced by the parent task, must be
reported under its own actual renderer and cannot promote these missing
historical inputs to `APPLIED`.

## Next exact integration action

The optional factory must be called by the new Studio runtime wrapper before
capture, using the original global frame. With no optional historical sources,
the default request remains null/null. Adding scalar ownership or national troops
later requires immutable source-catalog records and the native same-frame
composition contracts above. No existing claim or completed result may be reset
to force an optional selection.
