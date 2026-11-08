# Worker launch-state publication repair

The running worker can load `state.json` before its parent has published `pid`
and `processStart`. It waits for `launch.json`, but previously kept the stale
state object. Its first CAPTURE save then removes the published identity.
The unchanged status method consequently reports
`HANDOFF_UNRESOLVED_WORKER_OR_DESCENDANTS` even though the worker is alive.

The actual v14 worker `_run`, actual backend `studio_status`, frozen PrivateTree
and real `/proc` identity reproduced this interleaving on CPU. The fixture stops
at the capture-launch boundary; no renderer, encoder or GPU is invoked. The
`captureLaunches` counter counts intercepted boundary calls, not real launches.
The simulated 158 progress count is not a newly rendered frame count.

After the parent's launch receipt exists, the patch reloads published state and
validates both receipt and state against the current process PID/start ticks.
It also requires unchanged initial state, matching job ID and UID before lease
acquisition. Six new checks pass: both startup orders, plus mismatched receipt
PID, receipt start ticks, state identity and job ID. No previous PASS was rerun.
The status liveness guard, GPU lease, supervisor, cleanup, source/approval
verification, compiler, renderer, encoder, input data and JSON size fix are
unchanged. Source/startup hashes must be updated together for packaging.

## What this establishes and does not establish

The launch race is a confirmed code bug with the same observed error. It is not
proven to be the cause of job `studio-b5687598139382feecef4973b903f86a`: its original
state and launch files were unavailable after the user's stop. Worker exit,
signals and platform faults remain unconfirmed, not asserted. No provider
response is needed to fix this reproducible code defect.

Previous evidence is retained: `68819.mp4` is an existing 10-second/300-frame
technical PASS (SHA256 `762fcb76c4174fb5a65e528fe1d52b5083322724a39fcd1ddf0a422d2f6ceb62`).
The identical Korean War PART_01 previously captured all 300 frames with exit 0
and verified cleanup; its later `JSON_SIZE_INVALID` is a separate validation
boundary repaired in v13. The v14 startup pin repair is retained. Neither a
rollback to the unpatched v11 nor a new renderer is appropriate.

## Gates

Only the newly changed worker identity handoff and dependent package pins are
being checked. Historical success, data, terrain and renderer suites are SKIP.
The additive image must pass installed manifest/source and actual CPU
ENTRYPOINT checks before publication. Those checks stop at intentionally absent
owner configuration, before service or GPU admission. The old image/tag is
preserved and the new image backed up. GPU rendering and final MP4 remain user
actions and unverified. No automatic retry is added.
