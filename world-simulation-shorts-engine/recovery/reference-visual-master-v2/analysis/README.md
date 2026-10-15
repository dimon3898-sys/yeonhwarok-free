# Stage A — complete reference decode and numerical inspection

The authoritative attachment is `WORLD_ENGINE_REFERENCE_65379_COMPRESSED.mp4`, SHA-256 `5bfe11c8d034a6681bd1ce1ca81fa66c142d58c18a1ea8d2f1c80c903a8476a6`. A user alias does not substitute a different reference. The uploaded original is unchanged; no fresh video or uncropped phone UI is copied into this directory, runtime assets or Public Review.

`analyze_reference.py` decoded **all 958 native 1080×2520 RGB frames** through FFmpeg with error-fatal decoding, without writing raw frames. FFprobe supplies each source PTS; the VFR sequence remains unchanged. The source hash is checked before and after. `FULL_REFERENCE_METRICS.json` records every PTS and decoded full-frame RGB SHA, with map-only display statistics. `NATIVE_DECODE_CROSSCHECK.json` compares all 958 native hashes and PTS with the already saved audit: every value matches.

The analysis mask starts at source y=212, one row inside the visually/numerically observed map start y=211. It excludes the right phone controls, variable central subtitle band, and the entire identity/caption/comment footer from y=1840 onward. Mask geometry and retained sample count are explicit in the JSON. It is a conservative measurement mask, not an inpainted clean map or a final framing prescription. Optional privately saved previews are masked and remain outside the repository.

Orange/purple hue fractions are screen-pixel proxies, **not geographic territory areas**. Camera motion, original unit graphics and the final national-flag transition can affect them. Gold brightness near both hue classes is a heuristic, not an exact frontier measurement. The visually observed moving internal front is predominantly white; the broad static country/coast halo is gold, so those two effects must remain conceptually separate.

The consecutive camera translation proxy uses static-looking, non-faction texture from a left/top map ROI. At this analysis resolution, displacement is quantized to 4 source pixels. Zero displacement does not prove a static camera; scale, roll, occlusion and translation are not independently solved. The prior source-bound focused tracking evidence remains useful for the selected five-second interval.

The container duration is **31.813189 seconds**, with the final source PTS **31.781784 seconds**. There are no exact adjacent native-frame duplicates, no low-motion run of at least 0.15 seconds under the declared strict thresholds, and no equal first/last frame. This supports continuous changing visual content; it does not turn the national-flag ending into territorial animation or prove semantic loop absence. The visual storyboard determines event phases.

Reproduce against an approved private local copy:

```sh
python3 -B analyze_reference.py --input /approved/private/reference.mp4 --output /new/output/FULL_REFERENCE_METRICS.json
python3 -B summarize_reference.py --metrics /new/output/FULL_REFERENCE_METRICS.json --saved-audit /approved/repo/world-simulation-shorts-engine/recovery/reference-reproduction-v1/evidence/reference_audit/FRAMES.json --output /new/output/FULL_REFERENCE_SUMMARY.json
```

Both output commands require a new file. This stage performs no renderer implementation, GPU execution, image build, paid operation, video production, quality PASS or FINAL promotion.
