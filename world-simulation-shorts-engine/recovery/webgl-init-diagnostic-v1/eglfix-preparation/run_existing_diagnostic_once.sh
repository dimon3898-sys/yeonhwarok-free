#!/usr/bin/env bash
(
set -eu
trap 'rc=$?; printf "DIAG_OPERATION_EXIT=%s\n" "$rc"' EXIT
cd /opt/world-engine-storage-fix
[ "$(id -u)" -eq 0 ]
src=/world-storage/webgl-eglfix-inputs-20261102-a1
dst=/tmp/world-engine-webgl-eglfix-20261102-a1
out=/world-storage/webgl-init-eglfix-20261102-a1
[ ! -e "$out" ]
[ ! -L "$out" ]
mkdir -m 0755 "$dst"
for f in capture_environment_runner_v2.py diagnose_webgl_once.mjs; do
  [ -f "$src/$f" ]
  [ ! -L "$src/$f" ]
  install -m 0644 "$src/$f" "$dst/$f"
done
cd "$dst"
printf '%s\n' \
'9242a57d6136976b217588fe61f37a9f7b8c64053344516794e287e265c4a886  capture_environment_runner_v2.py' \
'28b190f20c0621153f4ef00e442764655c35b8b0b6588b05c100bbc71d215e00  diagnose_webgl_once.mjs' | sha256sum -c -
cd /opt/world-engine-storage-fix
mapfile -t wpids < <(pgrep -u 1000 -f 'studio-cold-start-v2/worker\.py([[:space:]]|$)')
[ "${#wpids[@]}" -eq 1 ]
printf '%s\n' DIAG_TRANSFER_PASS
if python3 -I -B "$dst/capture_environment_runner_v2.py" --worker-pid "${wpids[0]}" --runner "$dst/diagnose_webgl_once.mjs" --runner-sha256 28b190f20c0621153f4ef00e442764655c35b8b0b6588b05c100bbc71d215e00 --output "$out" --approved-single-diagnostic; then rc=0; else rc=$?; fi
exit "$rc"
)
