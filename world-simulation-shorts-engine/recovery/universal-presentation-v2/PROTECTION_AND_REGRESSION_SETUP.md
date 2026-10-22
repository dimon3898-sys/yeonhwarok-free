# Preserved baseline and unchanged regression execution

The actual checked-out baseline is `b0d013832ee38571f9d3dfe685ce63f7083ba90f`, on the separate branch `development/universal-presentation-v2-20261022`. All new work is confined to `world-simulation-shorts-engine/recovery/universal-presentation-v2/`.

Before implementation, the original307 protection manifest was verified against actual bytes:306 repository files and the existing canonical PLAN. The original manifest SHA is `cc09c9dca0262b800387df1d27e6ac91d0fd18d2c5c582862cc600baf843ce3e`; the existing external PLAN SHA is `33596c97b433887afb7ced6847d4ef63d099a9b6633546d541890a45c9c6289e`. Neither was restored or replaced by this task.

The new baseline contains actual SHA-256, byte size and original Git blob identity for all **6,439** files tracked at b0d0138. It therefore protects the whole prior universal-data-pipeline implementation, reports, artifacts and test results, in addition to G1/G2/FINAL. Both old worktrees are recorded with their HEAD and clean status. Metadata for565 entries in three existing private cache roots was also captured. Cache checks compare existence, inode, mtime, size, permissions and kind; they do not read secret contents or pretend to establish old machine metadata that was never recorded.

`tools/protection.py` imports the unchanged previous SHA verifier. It relocates new reports and adds the b0d0138 snapshot/cache checks, without modifying the imported file or old reports. Run it with `--output PROTECTION_FINAL.json` for a final verification. `--acquire` is exclusive and must only run before the first task commit.

`tools/run_baseline_298.py` executes the original143 commands through the preserved runner with its report destination relocated in memory, then the original109 prompt,14schema,22Studio and10capture tests. No prior PASS results are reused. Every original test file, assertion and expected count remains unchanged. Full stdout/stderr and command/exit/count summaries are stored under the new `reports/regressions/` tree. The old runner is not executed in a way that overwrites its old result file.

Existing exact neutral fixtures, original918KB GovInfo PDF and pinned Playwright1.62.1 dependencies were already retained in the workspace and are reused read-only. No new data collection, dependency reinstall or full renderer audit is needed for these regression runs. Studio's real localhost HTTP checks require the supported execution permission path; this does not grant GPU or paid-provider authority.

This setup does not declare any new rendering feature or visual quality PASS. Actual test outcomes are recorded separately after execution, and failed tests must stop subsequent production gates.
