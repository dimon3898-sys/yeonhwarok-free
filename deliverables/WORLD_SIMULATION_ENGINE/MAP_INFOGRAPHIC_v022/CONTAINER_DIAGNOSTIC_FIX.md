# v022 container bootstrap before/after proof

The actual container contract stage passed after its CI bootstrap selected the
UID 1000 account's HOME before dropping privileges. Production startup already
uses this account HOME. Production source, renderer flags and image user were
unchanged. This resolves the reported Canvas launch failure in this CI stage;
full regression and publication admission remain pending.

| Actual CI evidence | Before | After |
| --- | --- | --- |
| Source commit | `2d094020ad6e940e5fb60d0a8a586da3ab566077` | `bbb3d15f057797c7894c796d1eb444e9990d90dc` |
| Run | [37933662885](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37933662885/job/113830424838) | [37935004783](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37935004783/job/113835034826) |
| Step 8 start, UTC | 2026-10-09 13:00:56 | 2026-10-09 13:13:01 |
| Step 8 completion, UTC | 2026-10-09 13:04:37 | 2026-10-09 13:15:37 |
| Result | `INFOGRAPHIC_CANVAS_CRASHPAD_DATABASE_REQUIRED` | PASS |

The BEFORE completion time comes from reviewer public polling, as reported by
the release owner. The initial cached job page predates that completion. The
failure category is preserved in the public run overview annotation. The AFTER
times and PASS result come from the cached public job page. These provenance
details are retained in [CONTAINER_DIAGNOSTIC_FIX.json](CONTAINER_DIAGNOSTIC_FIX.json).

The bootstrap now resolves `pwd.getpwuid(1000).pw_dir`, then verifies the UID,
account HOME, directory access and a real temporary-file write after the UID
change. Its notice contains only `HOME_matches_account` and `writable` booleans.
Unknown diagnostic values, commands, environments, raw browser stderr and local
paths are not forwarded. A failed admission still fails the stage.

The recorded commits also differ in fail-fast CI sequencing and safe structured
diagnostic forwarding. All 39 other frozen runtime/source records and all 27
protected parent records are identical. The anonymous OCI audit independently
matched those 27 protected files in the immutable v021 parent; see
[PROTECTED_PARENT_SOURCE_AUDIT.json](PROTECTED_PARENT_SOURCE_AUDIT.json).
The exact pinned-base local HOME comparison passed both variants and therefore
does not independently reproduce the CI failure.

The successful stage includes the full immutable v021 preflight, the 720-frame
QA OFF/ON source, camera, material and static checks, real measured offline speech
and cached audio/subtitle handoff, synthetic AAC/MP4 technical checks, and all 16
CPU Canvas2D checks with 10 snapshots. It verifies the 111-file container asset
union. These are technical CPU/container results.

The final source manifest is
`573efa6adf8759073668eebd4f2cd20c8f1c8a024d0f3da7257d3a29ac1a0682`.
Its targets remain 57 new tests and 1,061 unique tests: 824 core, 206 independent
proxy and 31 independent diagnostic tests. Isolated reruns do not add unique
tests. This record does not claim the full suite has passed or that an image has
been published.

Actual NVIDIA rendering, map MP4 quality, GPU memory/render-time measurements and
listening remain NOT_RUN. The future sequence is documented in
[GPU_TEST_METHOD.md](GPU_TEST_METHOD.md).
