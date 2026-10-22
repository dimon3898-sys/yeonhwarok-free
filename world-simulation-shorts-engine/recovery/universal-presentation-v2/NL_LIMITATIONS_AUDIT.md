# Natural-language and presentation connection audit

Baseline: `b0d013832ee38571f9d3dfe685ce63f7083ba90f`. The findings below are read from actual preserved code. No existing file or validation rule is changed by this audit.

| Finding | Actual code | Consequence |
|---|---|---|
| Current data prompt accepts JSON or one JSON fence | `universal-data-pipeline-v1/prompt_pipeline.mjs:268`, `parsePrompt` | Free prose returns `FREE_NATURAL_LANGUAGE_NOT_SUPPORTED`; the parser does not extract facts from prose. |
| Earlier offline natural-language wrapper extracts output settings | `universal-auto-video-v2/planner.py:40`, `parse_request` | Duration, fps, resolution and aspect intent are parsed without an LLM, but this is a bounded grammar rather than unrestricted language understanding. |
| Earlier topic planning requires an existing catalog match | `universal-auto-video-v2/planner.py:114`, `_entry` | An unknown supplied subject cannot pass that wrapper, even though the generic native Planner has broader feature contracts. |
| Earlier long timing allocator is WAR-only | `universal-auto-video-v2/planner.py:130`, `_timing` | It is not an arbitrary transport-topic planner. Reusing it as universal natural-language interpretation would be misleading. |
| Five-region admission is an explicit old profile rule | `universal-data-pipeline-v1/prompt_pipeline.mjs:11,320` | The preserved profile cannot admit an unregistered region. A new opt-in source provider must independently verify coverage; a fake registered-region fallback would be wrong. |
| Existing generic Planner is reusable | `web/map_infographic_v1/planner_scene_v1.mjs`, `validateFactDataset/compileScenePlan/validateScenePlan` | Provided facts can compile to the existing Scene format without reimplementing a renderer or inventing geometry. |
| Old preview camera deliberately remains locked | `universal-data-pipeline-v1/generic_runtime.mjs:30,68,103` | The actual V5 final camera state is reused every frame. Scene camera references are projected, but they do not cause motion. |
| Native motion and area engines are connected | `generic_runtime.mjs:71-86` | The old preview already uses real Flow/Area controls and pixels; these engines must be reused rather than replaced. |
| Unconnected features are rejected explicitly | `prompt_pipeline.mjs:136,143` | LINE_METRIC/DISASTER and undrawn optional categories are not implemented merely because their Planner contracts exist. |

The existing Python wrapper states `externalAIConnected: false` and `plannerMode: OFFLINE_CONSTRAINED_FACT_CATALOG`. No paid or existing external LLM is invoked by these paths. The new free implementation is therefore a **bounded Korean/English intent grammar with supplied-data entity linking**, not complete natural-language understanding or historical research.

The new input adapter will distinguish the original text and extracted spans from authoritative attached facts. Explicit dates, durations, locations already present in the supplied dataset, route references and supported presentation intent can be extracted. Missing coordinates, historical boundaries, factual source evidence and ambiguous references remain clarification requirements. Natural language cannot silently overwrite supplied facts.

The new profile keeps the old profile's result as an audit observation. Only its old region-availability restriction may be delegated to a new real source-coverage gate. All other relevant validation failures remain failures, and the unchanged native validators and compiler still run on the original supplied facts. No sentinel region is selected and no source is relabelled as covered.

The implementation and its focused tests are added only under this new namespace. Source-qualified map coverage, animated presentation, authenticated Studio execution and actual pixel validation are separate gates owned by their respective modules. This audit alone establishes none of their PASS results and no video-quality or NVIDIA claim.
