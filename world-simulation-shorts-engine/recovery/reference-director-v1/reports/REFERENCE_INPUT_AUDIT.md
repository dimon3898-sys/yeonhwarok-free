# Reference input audit — original 64306 available

The uploaded `lv_0_20261008074313.mp4` is the exact reference source identified by the supplied package: SHA-256 `853ce5be22dc95c95e0c4b3eddbd603930e499bc88ee40cb4e59b50aad1187bc`. The filename differs; the bytes do not. It was decoded directly, rather than treating the supplied analysis as a substitute for an unavailable video.

## Actual verification

- FFprobe counted 635 H.264 video frames, 822×1920, nominal 30/1 fps, duration 21.166666 s. First/last presentation timestamps are 0/21.133333 s. The average-framerate rational in this phone recording is slightly different from nominal 30/1 and is not silently rewritten as an encoder property.
- All 635 frames were sequentially decoded to BGR24 with FFmpeg. Every decoded-frame SHA-256 matches the supplied `REFERENCE_FRAME_LOG_635.csv` OpenCV pixel hash. No missing, extra, reordered, or byte-different decoded frame was found.
- All 635 supplied timestamps match actual decoded presentation timestamps within 0.000001 s.
- All 546 authored plan rows are contiguous: reference `[29,575)`, core `[0,546)`. Their local/global mapping and authored hero-pop, boundary reveal, label/metric onset-count, metric-settled state were checked against the target JSON.
- Review windows are exactly A `[29,209)`/180, B `[209,389)`/180, C `[389,575)`/186. They partition one continuous source timeline. A window boundary is not an editorial cut or a state reset.
- Camera-estimate rows are 0..574; hero-pin estimate rows are 347..574; boundary-estimate rows are 457..574. Every hero-pin normalized coordinate matches the provided x/822, (y−160)/1464 formula.
- The source has AAC stereo at 48 kHz, audio duration 19.050667 s. Audio was not listened to, transcribed, copied, or used to infer SFX. Target review clips remain silent.

The machine-readable evidence and exact input-file hashes are in `REFERENCE_INPUT_AUDIT.json`. These checks verify the source and authored plan; they do not verify a newly rendered frame.

## What was inspected visually

Actual source map-ROI frames 30, 170, 270, 332, 350, 390, 420, 455, 485, 505, 540, 574 were extracted and visually inspected as a private 12-frame contact sheet. It shows:

- f30 → f170: the yellow primary-country shape shrinks substantially while surrounding land and country boundaries enter the view.
- f270 → f332: two yellow pins precede the two Korean place labels; blue-glow labels are readable by f332.
- f350 → f390: a separate larger hollow pin is present, with rapid map enlargement underneath and little tip displacement.
- f420 → f455: a small irregular yellow coastal shape becomes visible and larger. This observation is not a verified identification or surveyed outline of the location.
- f485 → f574: a yellow boundary becomes near-horizontal as the map rotates; `85 m` is visible in later frames and the final close-up is retained.

This manual scope is 12 selected frames, not a claim that a human independently reviewed all 635 full-size source frames. The full 635-frame check is a decoded-pixel/timestamp audit. Exact event start frames and easing in the target remain authored approximations, as the supplied MASTER states; observing `85 m` does not independently authenticate an 85 m geographic measurement.

The phone interface, lower narration subtitles, engagement controls, watermark, and editor ending are excluded from target production. The approximately x=[0,822), y=[160,1624) map ROI still contains occluding platform elements; these were not reconstructed as hidden geographic data.

## Lightweight ZIP omissions

The delivered ZIP contains 11 files. Although its README and analysis refer to 22 `all_frames/*.jpg` sheets and seven event-zoom evidence images, the actual ZIP has no `all_frames/` directory and its `evidence/` directory contains only `REFERENCE_KEYFRAMES.jpg`. It also does not contain the referenced package `SHA256SUMS`. Those missing attachments were not reported as present or inspected. Actual input hashes were computed independently.

The original MP4 makes source inspection possible despite those omissions. Only the 12 requested keyframes and one contact sheet were regenerated privately; no fictitious renderer output or video was made from those images.

## Publication and gate limits

The original video and extracted source images remain outside Git in a private analysis directory. The task authorizes analysis but does not establish a new redistribution license. Neither the source MP4 nor all decoded images is copied into public review artifacts. The public report contains hashes, frame references, and findings only.

`REFERENCE_VISUAL_MATCH = NOT_EVALUATED_NO_RENDER_OUTPUT` for this audit. It produces no actual WORLD ENGINE frame, no A/B render comparison, and no replacement MP4. Renderer capability and precise source/geometry gates are separate. This audit cannot lift those gates or claim NVIDIA, Android hardware, geographic precision, or final visual quality PASS.

## Reproduction command

Run from the new namespace, substituting the local uploaded paths; outputs containing source imagery must remain private:

```sh
PYTHONDONTWRITEBYTECODE=1 python -B tools/audit_reference.py \
  --input-dir /path/to/extracted-input \
  --video /path/to/user-supplied-video.mp4 \
  --private-output /path/to/private/reference-audit \
  --report reports/REFERENCE_INPUT_AUDIT.json
```

The tool is sequential and bounded in memory to a small number of raw frames/keyframe thumbnails. It does not alter any reference input, existing renderer, Scene, asset, cache, or protected file.
