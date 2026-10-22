# Change manifest

All changes are additive inside `world-simulation-shorts-engine/recovery/universal-data-pipeline-v1/`. No baseline source was edited.

## New entry points

- `PROMPT_INPUT.schema.json`
- `capture_generic.mjs`
- `generic_runtime.mjs`
- `prompt_pipeline.mjs`
- `run_studio_demos.py`
- `software_worker.py`
- `studio_adapter.py`

The prompt compiler and schema select existing Planner/Area/Flow functions. Studio adapters reuse authentication, private state and detached claims. The capture wrapper uses existing map/camera/layout functions. A wire-string bridge preserves legacy canonical geometry serialization without changing the old validator. New tools restore exact neutral fixtures, execute unchanged tests, audit real pixels/video, scan public files and package/verify downloads.

`examples/` and `evidence/` contain versioned test inputs with explicit illustrative/history limits. `tests/` and `reports/` record executed checks, including preserved failures. `public-review/` contains new real Studio movies and actual frame images. `review-package/` is a selective mobile review ZIP, not a standalone replacement renderer. Its BUNDLE_MANIFEST.json records every bundled file hash.

Protection evidence: original307 and all6268baseline tracked files actualSHA match; originalcheckout unchanged; differences outside this namespace=0. Existing FINAL, scenes/assets, videos, renderers and old caches were not overwritten or deleted.
