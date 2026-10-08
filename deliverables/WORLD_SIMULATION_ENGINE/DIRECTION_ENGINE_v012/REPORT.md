# Reference-informed common Direction Engine v012

## Evidence and limits

BEFORE is the attached `final (2).mp4`, SHA256 dbb5f2dc021b5270043c0eaf751d493a47e2c1077dcae36a1866b8f372c2cc11: 12 seconds, all 360 frames decoded. REFERENCE is `lv_0_20261008074313.mp4`, SHA256 853ce5be22dc95c95e0c4b3eddbd603930e499bc88ee40cb4e59b50aad1187bc: all 635 frames decoded. Phone/YouTube UI is excluded from geographic feature matching; the CapCut slate after 18.8 seconds is excluded from map statistics. File contents establish their roles despite different user-facing numeric names.

Metrics in COMPARISON.json and metrics0/1.json are 2D image-flow/affine proxies, not recovered 3D camera angles or FOV. Mixed AAC transient candidates cannot identify isolated SFX from narration/music. Reliable all-frame text collisions and entity bounding boxes cannot be recovered from these MP4s alone; no fabricated precision is reported.

## Actual observed problems

| BEFORE time | Observation | New rule |
|---|---|---|
| 0–2.4s | Location, question and distance compete despite a long opening hold | One primary, geographic opening hook, factual support subdued |
| 2.967–3.600s | Moving camera and destination cue compete | Early arrival entry read gate; dominant motion axis |
| 5.800–6.833s | Suez pullback/rotation while status and distance compete | Stop independent follow/orbit oscillation; preserve current location |
| 7.433–9.133s | 1.700s continuous high motion, weak night geography/entity tracking | Transported camera up, bounded motion, fill floor and entity pixel target |
| 10.300–11.333s | Result pullback with simultaneous city labels | Context/result framing, one current location and primary result |
| 11.400–12.000s | Final settle only 0.600s | Adaptive RESULT_HERO settle >=1.05s |

The current upload already fills about 97% of frame width with Earth at its end: its connected nonblack body proxy occupies 41.54% of the full portrait frame, including halo. It is not the earlier tiny-Earth result. The remaining problem is vertical black margin, competing labels and short final read time. New adaptive framing mildly crops the lateral limb when geography allows and centers the result; actual GPU aesthetics remain unverified.

Reference settles include 0.800s, 0.700s, 0.967s and 1.333s. Its 2D rotation p95 is 14.10deg/s versus BEFORE 21.55deg/s; its scale-change p95 is actually higher, 1.505/s versus 0.567/s. Therefore slowing every move is unsupported. We extract move/settle/information hierarchy rather than copying velocities, story, countries, colors, labels or assets.

## Common versioned implementation

Newly authored FAST_PLUS plans select direction_v012. Existing saved plans continue their own source hashes and renderer selection. FAST/NORMAL/CINEMATIC and legacy preset remain available. No city name or scene ID selects a special implementation.

- Adaptive minimum read time: normal 0.62–0.90s; important 0.82–1.20s; result 1.05–1.50s. Language, characters, information count, movement and zoom affect the budget. QA does not scale these minima down.
- A bounded integral velocity ramp accelerates, decelerates, then becomes exactly stationary. Strong pan and zoom use distinct intervals. Camera FOV is continuous; geographic up is parallel-transported to avoid pole/roll flips, with gentle long-scene roll correction.
- Early already-visible arrival has an entry read gate. Later results align their authored visual event, factual text and SFX after movement. Physical routes/entities stay on the authored scene clock, with no global timewarp.
- One primary text at each moment; location/event/data priority is explicit. Current location outranks redundant cities; existing safe-area/collision placement and strict text clipping remain active. No invented slogan.
- Current route retains priority over faint context. The approved geometry/occlusion overlay uses zoom-adjusted primary stroke width. Entity display size targets 18px at output width1080 with bounded model scale, preserving ground clearance.
- Existing V3 shader is retained with bounded ocean specular reduction, cloud cap, exposure and surface fill. Night/city lights remain present. No new texture or renderer design.
- RESULT_HERO protects the final read interval and frames critical result nodes; no unsupported world zoom-out requirement.
- Existing structural/numeric/semantic gates remain critical. Direction excess motion, label density, contrast or mild readability problems are warnings, not a new reason to abort valid GPU frames. New-version label reveal fade is capped at0.16s using the identical draw/layout function in runtime and native preflight. Final info/SFX times land on the actual30fps grid. Synthetic full-pipeline QC caught support-label fades causing SFX to precede semantic visibility by2frames; the fix changes actual drawing and keeps the original one-frame QC tolerance. Actual GPU frame audits add measured Earth occupancy/luma and route-head contrast; local planning reports those pixel checks NOT_RUN.
- FLAT↔Earth registered projection handoff remains on its actual transition clock.
- Direction beat decisions and QC are embedded in the existing diagnostic preflight.json, while actual Scene JSON, FAILED_INVARIANT, stdout/stderr, checkpoint, GPU records, ZIP download and retry remain unchanged.

## Verification scope

Four native, canvas-free scenarios cover shipping12s, aviation12s, country/region12s, global network20s. Shipping75s is planning-only to verify independent production reading budgets; no 75-second video is generated. Native checks sample all scenes, actual approved camera/route/entity geometry, clipping, projection, causality and source contracts. Real GPU frame quality is NOT_RUN here. The shipping12 plan retains one CAMERA_MOTION_OVERLOAD warning on S004 at the planning threshold, and the country12 plan one TEXT_DURING_HIGH_MOTION warning on its initial geographic label. Both pass the unchanged native critical gates; these warnings are disclosed, not suppressed or treated as proof of comfortable actual playback. The protected settles and dominant axes still apply. Final visual comfort must be judged on the single actual GPU QA.

The container pipeline additionally validates required installed graphics libraries, asset manifest, UID1000 storage writes, 360 valid JPEG synthetic frames, FFmpeg, concat, audio, QC, checkpoint/retry, login, proxy/security, 61-second persistence, fail-closed GPU admission and anonymous GHCR pull. Final numeric results and image digest are recorded in RELEASE_VERIFICATION.json after CI completion.

Protected source hashes: PRESERVED_SOURCES.json. Full input metrics: COMPARISON.json / metrics0.json / metrics1.json. Exact scene/beat plans and native reports: fixtures/. Reference media is not packaged into the runtime.

## Next actual GPU check

One authorized RTX4080 SUPER run: same Suez topic, QA12s, HIGH, FAST_PLUS, TTS/subtitle OFF, BGM/SFX ON. Check dizziness, location/route comprehension, Suez/Singapore settle, labels, entity tracking, night geography, final result and event/SFX timing. Download both MP4 and Diagnostic ZIP before stopping the workload. No GPU run was initiated for this task.

TODO only: PWA standalone, brighter web UI, web redesign. None implemented here.

## Published and verified release

- Image: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v012-direction`
- Digest: `sha256:20f48cc67db9eecd233f788c6c04ba4cc94fc5d8ee6aa0a1f7def82d6db88ce7`
- Code revision: `eb4ab3cca89d8b13d65a3bc8a864e178ae5a7749`
- [Successful container workflow](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37705257707)
- Core529 + proxy/GPU-logic206 + unchanged diagnostic31 =766PASS,0FAIL,0SKIP.
- Container64 required assets, UID1000 paths and graphics packages PASS.
- Synthetic360frames/12s JPEG→FFmpeg→Concat→Audio→QC PASS; actual GPU map rendering NOT_RUN.
- Anonymous pull, OCI revision match, foreground boot, owner login and61s persistence PASS. No physical-GPU readiness claim in the CPU container: GPU-required admission correctly fails closed.
- Strict frame-sound QC originally rejected3 delayed labels; the final actual mixer/native-visibility comparison passes without loosening its1-frame tolerance. PREPUBLICATION_QC_FAILURE.json and media-sync-final.json retain before/after evidence.

Generate a **new QA plan** when comparing the new version; reopening or retrying a saved old plan intentionally keeps its old direction version. Actual visual comfort, route contrast, Earth occupancy and mobile playback/download still require the single authorized RTX4080S12s QA.
