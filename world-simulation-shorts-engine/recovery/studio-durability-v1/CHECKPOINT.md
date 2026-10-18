# Studio durability implementation checkpoint

Baseline: `f983adc247363b06e8e0f29bd7d5b2e74d73e8c0`.

The user authorized CPU development of data-loss prevention before another paid GPU job. Existing FINAL, renderers, admission, authentication/CSRF/Origin, claims, cache formats and private-root rules remain frozen. `/world-storage` is never substituted for authoritative private state.

Existing scene MP4 export is reused. The missing piece is authenticated private recovery material after private state loss. This additive namespace will provide bounded authenticated encryption of Scene/audio and verified reusable completed cache artifacts, immutable content-addressed checkpoints, independent remote readback, explicit fresh-private-tree restoration, and a fail-closed production gate before further rendering.

Selected external path: a dedicated encrypted Dropbox API backup namespace; existing `/world-storage` public result export stays unchanged. A separately retained approved 32-byte backup key and scoped Dropbox credential are prerequisites. No key is generated silently for production or exported alongside backups. Mounted-only CPU tests cannot establish actual remote durability.

Work division: `vault.py`/`stores.py` protect bounded encrypted objects; `checkpoint.py` selects and restores only verified plan-derived cache files; independent Studio backend/coordinator/server entrypoints retain frozen production execution and add pre-render/per-scene barriers. CPU tests use explicit test provenance; `_test_components` is never used to inject a production backup.

Current state: implementation in progress. Resume at focused CPU validation, then integration packaging. Paid GPU, live render, deployment/stop/delete and SSH recovery remain forbidden. Do not mark actual Dropbox persistence or NVIDIA video quality PASS without the corresponding execution evidence.
