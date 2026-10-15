# B — camera/source audit, read-only

A separate Scene-owned camera extension can reuse the protected camera and presentation compilers. No core change is required for an optional short camera read pause. This is a design finding, not an implemented Stage G feature or a visual-quality approval.

The protected `compileReferenceCameraTrack` accepts ordered frame keyframes with repeated equal bounds. It interpolates center and log extent with the existing C1 monotone cubic. The presentation compiler independently interpolates roll. A genuine pose pause therefore needs equal center, extent **and roll**; stopping translation while roll continues would not meet that definition.

The event clock is separate. The unchanged GPU adapter evaluates territory at `control.startFrame + frame` and national units at `frame`. A camera-only read pause can preserve all 150 event/object frame indices while introducing an explicitly declared short pause in camera pose. Changing territory timing, object timing, capture duration or FFmpeg frame rate is outside this interface.

`assessReferenceCameraMotion` returns `fakeLockCount: 0` as a literal field. It is not a numerical plateau detector. Existing frame diagnostics also declare `cameraLocked: false`, referring to the absence of an arrival/detail lock. Neither protected field should be rewritten or disabled to accommodate a readability pause. A future extension must add a separate sampled cadence audit, call the phase a **camera read pause**, and retain the distinction from DETAIL LOCK.

For the proposed parameter contract:

- `CameraSmoothing` can control a bounded new Scene-owned cadence through the existing C1 interpolators. Disabled/zero must preserve the original F camera exactly. C2 acceleration continuity and a new V5 algorithm are not supported claims.
- `HoldDuration` can mean an optional camera-only pause of zero or 9–12 displayed frames. Its unit must be pinned explicitly in Stage G. It cannot silently retime the story, stop territory change, pause objects or manufacture event completion.
- An N-frame pause must be measured from N displayed samples. Two equal keyframes separated by N indices can accidentally produce N+1 identical samples; the future implementation must test the actual output.

The matching reference phase moves and changes scale. A long static camera lock or global slowdown is not supported by the observed five-second window. A short readability pause would be a new controlled visual choice, rather than a claimed transcription of a measured reference freeze.

The smallest later implementation is a pure planner in the new namespace: accept the current F Scene, existing plans and source guards; emit camera keyframes plus a cadence audit; preserve control intent, object arrays and the original output clock. Select a candidate pause after a meaningful evaluated change rather than from country names or fixed coordinates. Keep the current first/final framing, test the whole 150-frame native envelope and inherited framing floor, and reject any candidate that introduces unsafe front/unit placement or critical collisions. If none pass, retain exact F framing and report the unsupported pause explicitly.

The original F regression variant must compare all 150 sampled camera poses, not only its five keyframes. Actual GPU motion, frame cost and reference-level visual quality remain unverified until a real video is available.

[B_CAMERA_SOURCE_AUDIT.json](B_CAMERA_SOURCE_AUDIT.json) pins the source SHA values, API locations, constraints and pending Stage G checks. Existing source, data and output modifications: **0**. No implementation was started in this audit.
