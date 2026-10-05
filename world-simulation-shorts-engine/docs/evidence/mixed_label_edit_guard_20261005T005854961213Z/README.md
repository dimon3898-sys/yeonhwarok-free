# Mixed label edit guard — R05

This narrow correction rejects recognized label-appearance requests combined with explicit supported camera, lighting, route-addition, ship-addition, or aircraft-removal commands. It returns `UNSUPPORTED_COMBINED_LABEL_EDIT` and asks for separate requests before reading the project, applying an advanced edit, changing any Scene, or writing a revision record. Existing lighting edits already adjust dependent place/status colors.

Command grammar is bounded. Korean clause-ending camera/day/night requests and English `Faster camera.` are included. Readability explanations such as bright ground, night backdrop, fast camera movement, zoom-out in progress, or already-added routes remain accepted. This is not unrestricted language understanding.

The focused regression run completed once: **18 tests passed in 73.273 seconds**; the wrapper measured **73.891146 seconds**. No source bytes changed during the run. Its three added tests exercise 21 blocked mixed requests without revision/approval/base-byte changes, 10 allowed context explanations with exact appearance-only changes, and the existing camera-plus-two-ships and camera-plus-two-routes workflows with actual passing proposal gates. Prior label contrast, source verification, duplicate-event rejection, font width, and lighting-dependent palette tests also passed.

Exact originals are in `SOURCE_BEFORE_R05/`; tested source bytes are in `SOURCE_AFTER_R05/`. Their SHA-256 and byte counts are in the adjacent manifests. `SOURCE_DIFF_R05.patch` records the only code/test changes. The planner, schema, frozen renderer adapter, and exact production-derived test fixture stayed byte-identical. No server restart, production-plan edit, rendering, WebGL, approval, or Git operation was performed.

Reproduce the focused check from `world-simulation-shorts-engine/`:

```sh
PYTHONPYCACHEPREFIX=/tmp/wss_mixed_label_r05_recheck .venv/bin/python -m unittest discover -s tests -p test_place_label_readability.py -v
```

The parent owns the next combined suite, expected to discover 175 tests after these three additions. This evidence does not claim that later suite has run. The previously reported 172-test combined PASS and native 4K/375-pixel contrast review are preserved historical evidence at `../final_core_status_labels_clean_runtime_20261005T005017814324Z/` and `../shipping75_status_candidate_native_stills_20261005T005330Z/`; no new pixel-render claim is made here.

Full-suite command for the existing isolated runtime, from the same directory:

```sh
/tmp/world-engine-clean-runtime-20261004T182155Z/bin/python -m unittest discover -s tests -v
```
