# Studio Scene serialization recovery

The first actual Studio job failed before its first draw with `PLANNER_SCENE_NON_CANONICAL_GEOMETRY`. The original private cache serializes every object using sorted keys. The protected Scene validator reconstructs geometry records and compares `JSON.stringify` values, which also compares member order. Numbers and coordinates were not changed; the wire contract was lost between compile and capture.

The new Studio adapter retains the existing compiler Scene as an immutable `sceneWireJSON` string before private persistence. Sorted private storage leaves that string intact. `sceneSHA256` retains the canonical semantic Scene hash; new `sceneWireSHA256` separately binds exact bytes. The worker validates both hashes and verifies that parsing the wire yields the same bound Scene, then writes and renders those exact bytes. No protected validator, geometry, source or equality check is changed.

The focused test reproduces the original failure and verifies the repaired compiler → private persistence → strict validator → runtime-build path for all three actual nonhistorical examples. All 22 Studio tests passed (`reports/STUDIO_WIRE_FIX_TEST_RESULTS.json`). No frames were rendered in these focused tests. The failed job and its report remain untouched.

The runner accepts `--attempt=02` and creates new suffixed execution reports instead of replacing the first failure evidence. Actual videos retain their canonical review filenames. A new checkpoint and unchanged A–E gates are required before the next full Studio attempt.
