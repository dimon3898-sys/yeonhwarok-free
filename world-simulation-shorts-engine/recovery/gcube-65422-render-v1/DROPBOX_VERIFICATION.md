# Dropbox preservation and independent retrieval

This procedure is prepared, not executed against an actual Dropbox account. Mounted-view write/readback is already supported by the storage adapter; this task does not equate it with remote upload, durability or external HTTP download.

## Identify exactly this completed run

Preserve the foreground render command's nonzero/zero exit status and safe stdout/stderr in a **private** operator log. The existing structured `WORLD_ENGINE_EXPORT_LOCATION_V1` identifies the generated export directory, capture directory, seven public files, byte counts and SHA256 values. Use that exact record, not the latest directory by timestamp or a broad wildcard.

For this run the completed tree is:

```text
/world-storage/world-engine-export-<24hex>/capture-<signature12>-<24hex>/
  EXPORT_COMPLETE.json
  public-review/
    WORLD_ENGINE_RTX_GPU_65422_5S_SILENT.mp4
    01_START.png
    02_ADVANCE.png
    03_TRACKING.png
    04_CONTINUOUS_CONTROL.png
    05_END.png
    SHA256SUMS
```

The completion receipt is written only after the source manifest/hash checks, destination copies and mounted readback pass. `EXPORT_COMPLETE.json` is **outside** public-review. Do not publicize it, original REPORT.json, raw frames, admission files, source, environment or internal logs. Only the seven public files are for public review.

The SHA of SHA256SUMS must be taken from the successful source-side export log or its completion receipt and preserved independently. A manifest downloaded alongside modified files is not an independent trust anchor. Preserve the anchor and exact generated capture identity privately before leaving the container.

## Confirm remote Dropbox materialization

1. Keep the GPU workload running while required private logs and public artifacts are being recovered. A local directory or mount listing does not certify remote sync.
2. In the authorized Dropbox web/app account, locate the exact generated export/capture names from the source log. Wait for upload/synchronization to finish according to the actual provider UI; this preparation cannot certify that provider state.
3. Confirm the sibling completion receipt and all seven files are present. Compare their byte counts with the export log. Reopen the Dropbox location from a separate client/session where available.
4. Download MP4, five PNG and SHA256SUMS through the authorized Dropbox client or direct shared-download links. Public sharing, if permitted, applies only to these seven files. Do not share the entire capture/export parent.
5. Use a fresh destination folder on the reviewing device/computer. Do not overwrite an older Candidate. A failed or partial transfer must remain incomplete; do not re-encode the MP4 or regenerate PNGs to make verification pass.

No Dropbox credentials are configured in this Codex runtime, and the task did not authorize creating credentials or changing visibility. Use the existing authorized account. Do not paste token/password/share-key values into GitHub or diagnostic logs. If Codex later verifies private shared URLs, transmit them through the appropriate private channel; reports must avoid access-bearing query strings.

## Verify original versus downloaded bytes

The prepared standalone `verify_artifacts.py` works on a local public directory or fresh HTTPS Dropbox downloads. Use its `--help` for exact options. It requires the independently preserved source SHA of SHA256SUMS. The report distinguishes artifact integrity from GPU or visual approval.

For a prepared verifier on the downloaded directory, set PUBLIC_DIR to that exact new folder and SOURCE_SUMS_SHA to the independently preserved source SHA256SUMS SHA:

```sh
python3 -B world-simulation-shorts-engine/recovery/gcube-65422-render-v1/verify_artifacts.py \
  --public-dir "$PUBLIC_DIR" --sha256sums-sha256 "$SOURCE_SUMS_SHA" \
  --receipt /private/new-local-receipt.json --decode
```

For actual independent Dropbox GETs, create a **private** local JSON object mapping each exact filename above to its authorized direct HTTPS URL. Keep it out of Git/public review; no token generation is required. The helper validates Dropbox hosts/redirects, HTTP200, source-anchored sums and media facts. Its download destination and receipt must be fresh paths; the receipt remains outside public-review:

```sh
python3 -B world-simulation-shorts-engine/recovery/gcube-65422-render-v1/verify_artifacts.py \
  --urls-file /private/dropbox-urls.json --download-dir /private/fresh-download-dir \
  --sha256sums-sha256 "$SOURCE_SUMS_SHA" \
  --receipt /private/new-download-receipt.json --decode
```

Run the verifier on an authorized client with FFmpeg/FFprobe and network access. The current Codex runtime has no Dropbox binding or supplied media URL; do not interpret the prepared command or mocked network tests as completed retrieval. The tool records no access-bearing URL. Its receipt always keeps hardware verification false and visual quality UNREVIEWED; externalDownloadVerified becomes true only after actual GETs and anchored checks.

For a manual verification on the downloaded directory:

```sh
cd /path/to/newly-downloaded-public-review
sha256sum SHA256SUMS
# Compare this one digest with the independently preserved source-side anchor.
sha256sum --strict --check SHA256SUMS
ffprobe -v error -count_frames -show_streams -show_format -of json \
  WORLD_ENGINE_RTX_GPU_65422_5S_SILENT.mp4
ffmpeg -v error -xerror -nostdin -i WORLD_ENGINE_RTX_GPU_65422_5S_SILENT.mp4 \
  -map 0:v:0 -f null -
```

Required ffprobe facts: exactly one video stream and zero audio, codec h264, width1080, height1920, average rate30/1,150 decoded frames, duration5.000seconds. Full decode must finish without error. PNGs must decode at1080×1920. These checks do not establish that an RTX GPU generated the frames or that the scene looks good.

For actual shared-URL validation, every exact file requires HTTPS GET returning **HTTP200**, complete body and matching original SHA. A Dropbox HTML preview page, HEAD200, folder ZIP, response206, or a successful mount read is insufficient. Standard Dropbox shared links may use `dl=1` for direct download; retain any required existing share key privately, preserve TLS validation, and validate redirects and the final body. Do not invent links. No actual media URL or HTTP200/SHA result is reported by this preparation.

## Playback and reference comparison

Open the downloaded original MP4 in the target phone's real player. Review its full5seconds with the five checkpoints, the preserved65422 Candidate and the reference65379. Inspect moving frontier/glow synchronization, camera motion, terrain/ocean rendering, territory-color distinction, icon readability, unexpected lines/arrows and corruption. Confirm the soundtrack is absent. Preserve approved styles and timing; this task does not tune them.

Record separately:

- Technical artifact validity: PASS/FAIL from ffprobe, decoding and anchored hashes.
- Source GPU/native draw evidence: exact original safe native report, not inferred from video existence.
- Dropbox upload/persistence: observed remote state, not inferred from mounted readback.
- External download: actual URL/body HTTP200 and downloaded SHA equality, with access-bearing URLs kept private where needed.
- Phone playback and reference quality: USER_VIDEO_REVIEW_REQUIRED until actually reviewed.

Only after all required public artifacts and safe logs have been recovered, remote Dropbox presence confirmed, externally downloaded bytes verified, and playback checked should an authorized operator stop the paid workload. Stopping/deleting the container before that can irreversibly lose private local evidence. A successful encode, exit0 or completion receipt alone does not authorize a durability/download PASS.

## On failure

- Missing completion receipt, nonzero launcher exit or IN_PROGRESS/BLOCKED report: keep safe first stage/code and do not report successful export.
- Download SHA mismatch: preserve the verified source anchor, reject the downloaded copy, retry only the transfer after resolving incomplete sync/wrong-file selection; do not re-render to hide a transfer failure.
- Missing remote files: resolve provider sync/quota/permission status before terminating; do not chmod/chown existing Dropbox contents or delete older results.
- No authenticated Dropbox/terminal path: stop that operation and obtain the exact authorized access method. Do not claim external recovery succeeded.
