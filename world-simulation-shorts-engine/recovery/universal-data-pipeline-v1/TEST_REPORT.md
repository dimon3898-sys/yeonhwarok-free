# Actual test results

All results below were executed in this working environment. None is a reused PASS count or a claim of NVIDIA validation.

| Suite | Actual result | Command / evidence |
|---|---:|---|
| Preserved G2 suites | 143 PASS, 0 FAIL, 0 SKIP | `tools/run_g2_regressions.py`; all ten original commands and full logs in `reports/regressions/actual-143-01/RESULTS.json` |
| New prompt and Scene adapter | 109 PASS | `node tests/test_prompt_pipeline.mjs`; `reports/PROMPT_PIPELINE_TEST_RESULTS.json` |
| New JSON Schema | 14 PASS | `python -B tests/test_prompt_schema.py`; `reports/PROMPT_SCHEMA_TEST.log` |
| New Studio and persistence | 22 PASS | `python -B -m unittest discover -s tests -p test_studio_adapter.py -v`; `reports/STUDIO_WIRE_FIX_TEST_RESULTS.json` |
| New render contract | 10 PASS | `node tests/test_capture_generic.mjs`; `reports/RENDER_CONTRACT_TEST_RESULTS.json` |
| Independent adversarial inputs | 20 PASS | `tools/independent_adversarial.mjs`; `reports/INDEPENDENT_ADVERSARIAL_PROBES.json` |
| Five subjects and error/partial cases | 13 expected decisions matched | `reports/FIVE_TOPIC_INPUT_RESULTS.json`; expected history rejections are not rendered-history successes |
| Actual changed-input WebGL proof | PASS | Same basemap/camera, altered route changes actual pixels; `reports/paired-input-probe/PAIRED_PIXEL_PROOF.json` |
| Actual authenticated Studio movies | 3 completed | `reports/STUDIO_DEMOS_02.json`; actual browser authentication, CSRF/Origin rejection, duplicate touch and disconnected service/controller reconstruction |
| Actual data-to-pixel audit | 270/270 frames | `tools/audit_data_pixels.mjs`; `reports/DATA_TO_PIXEL_AUDIT.json` |
| Whole MP4 decoding and timestamps | 270/270 frames | `tools/audit_videos.py`; `reports/video-audit/VIDEO_AUDIT.json` |
| Original protection | 307/307 SHA match | `reports/PROTECTION_FINAL.json`; all 6,268 baseline tracked files also match |

The preserved143 plus final new109+14+22+10 suites total **298 passing tests**. Independent probes and example-matrix decisions are reported separately rather than inflated into that total. Earlier20-test Studio runs are superseded by the final22-test run and are not counted twice.

The initial real Studio job failed before its first frame because sorted persisted JSON conflicted with the original strict Scene member-order check. That failure remains in `reports/STUDIO_SERIALIZATION_FAILURE.json` and the unsuffixed execution report. The corrected wire-preservation path was tested before the second bounded free attempt. It produced all three movies without changing the protected Scene validator or renderer.

Loopback execution initially required the supported sandbox permission path; `listen EPERM` is recorded as an environment permission observation, not a graphics or source-code defect. No network/TLS/security check was disabled to solve it.

The Korean War and Roman Empire examples do not contain full verified historical ownership extents; the correct test outcome is `NEEDS_INPUT`. The partial-front line has an explicitly unconnected new pixel family. No exact historical film, unrestricted natural-language AI, arbitrary-region rendering, NVIDIA hardware, production image deployment or Dropbox external synchronization is marked PASS.
