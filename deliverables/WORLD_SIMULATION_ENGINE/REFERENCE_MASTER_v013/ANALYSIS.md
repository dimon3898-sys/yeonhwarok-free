# Reference-first evidence, prior to code changes

Current: final (3).mp4 = logical 64313, 12s, 360 decoded frames. Reference: lv_0_20261008074313.mp4 = logical 64306, 635 frames; map content 0–18.8s. File hashes and every-frame records accompany this report. Reference upload matches the earlier reference by SHA256.

Current observed problems:
- 0.20–0.60: faint distance competes with ROTTERDAM; ship cannot be confidently identified in the sampled whole-globe composition. Do not infer its pixel size without actual audit.
- 2.40–3.57: TO SINGAPORE and ROTTERDAM share the same European composition, without the destination geographically visible. Static camera does not itself give coherent information.
- 4.80–5.50: SUEZ CANAL then ARRIVED appear in succession; small thin route and faint ship do not explain the closure.
- 6.65–7.30: location, HOLD, and 14,482 km compete. High-motion resumes at 7.367. Reveal-to-next-major-motion is about 0.72s for the HOLD/metric information (onset bracket ±0.1s), although prior static segment was 1.533s.
- 7.70–8.60: SINGAPORE label appears while the globe is still turning quickly. It is not a protected reveal.
- 9.77–10.93: globe moves again while arrival/result messages replace each other.
- 11.00–12.00: final +6,460 km has about 1s before end. Earlier camera settle cannot be counted as time to read this later result.
- Late Earth geography ROI luma is 41.14/255 vs overall median74.49. This ROI includes black space: not a physical surface luminance measurement or proof every dark region is unreadable. Inspect sheet confirms the dark sea dominates the route neighborhood.

Reference observations: location detail reveals near9.8s and11.23s are followed by major movements near11.23s and13.4s respectively. Local marker context stabilizes12.033–13.367 (1.333s). Context is established before detailed markers. The final reference still zooms slowly; we will improve result locking rather than claim it is perfectly static.

Current motion proxy p95 rotation11.20deg/s vs reference14.10; current log-scale speed .185/s vs reference1.505. The current is NOT universally faster. The failure is exposure order, competing information, a fixed five-scene clock and missing event-relative holds. 2D flow is a proxy, not calibrated angular velocity. Mixed audio transients are preserved but cannot honestly be called isolated SFX onsets because the reference contains narration/music.

Proposed QA event budget: four core beats, with one primary at a time; minor physical departure and location acknowledgments stay subordinate. New profile planned before geometry/scene compilation. Adaptive minimums cannot be shrunk to fit; optional information/beat count is reduced instead. Reference geography and graphics are never imported.


## Measurement limits and reference timing

Every frame was decoded: 635 reference frames, 360 current frames. Optical flow uses the geographic viewport only, excluding recorded mobile controls. It measures 2D apparent movement, not calibrated 3D camera speed. Manual reveal onsets are bracketed by approximately ±0.1 s. Audio novelty peaks are mixed narration/music/effects and cannot establish isolated SFX onset. The reference profile leaves those SFX times null.

| Reference interval | Observed structure | Information-to-next-new-move | Stationary portion after reveal |
|---|---|---:|---:|
| 0.000–0.833 | Initial context, static | 0.833 s | 0.833 s |
| 0.867–6.033 | Broad geographic travel and context reveal | 5.066 s | 0.866 s |
| 6.033–9.800 | Regional relationship and approach | 3.533 s | 0.733 s |
| 9.800–11.233 | First detailed location marker, approach then settle | 1.433 s | 1.000 s |
| 11.233–13.400 | Next marker, travel then local lock | 2.167 s | 1.367 s |
| 13.400–15.800 | New context and local information | 1.733 s | 0.733 s |
| 15.800–18.800 | Final information during continuing zoom | 2.533 s to end | NOT_LOCKED |

These durations are distinct: an early reveal during travel is not a multi-second perception hold. The final reference is not fully locked. v013 improves final locking rather than inventing a locked reference ending. The final CapCut slate after 18.8 s is excluded from direction targets.

## v013 reference-first implementation

New profile `reference_master_v013` is compiled before sourced geographic content. Event budget, minimum recognition time and information budget allocate beat clocks before Scene JSON construction. Old `FAST_PLUS_LEGACY` remains v012, with five QA scenes and original source hashes. Existing saved project plans do not migrate automatically.

Four shared scenarios pass native collect-all projection and planning QC: maritime logistics, aviation, country reveal, world network. 75-second production was planned and checked only; no production video was rendered. The profile contains no reference graphic/story assets and no Suez-specific direction override.

Adaptive hold starts from independently justified design floors: location 0.8 s, event 1.1 s, route change 1.3 s, result 1.5 s. Text reading load, route complexity, entities, zoom, density and previous motion add time. If protected time cannot fit, optional information/beat count is reduced. These floors are design margins from the reference observations, not claims the reference obeys every target.

### Sourced shipping QA timeline (12 s)

| Beat | Bounds | Deceleration starts | Camera lock | Primary reveal | Primary reveal→next major move/end | Primary SFX insertion |
|---|---|---:|---:|---:|---:|---:|
| Departure / ROTTERDAM | 0.000–2.133 | 0.240 | 0.300 | 0.400 | 1.733 s | 0.433 |
| Suez closure / CANAL CLOSED | 2.133–5.067 | 2.853 | 3.033 | 3.633 | 1.433 s | 3.667 |
| Route change / ALTERNATE ROUTE | 5.067–8.167 | 5.787 | 5.967 | 6.567 | 1.600 s | 6.600 |
| Singapore result / +6,460 km | 8.167–12.000 | 9.127 | 9.367 | 9.967 | 2.033 s to end | 10.000 |

Location appears first after camera lock; primary event follows after 0.6 s on subsequent core beats. Route change preserves the blocked prior route and reveals the alternative separately. Display prominence is different from the unchanged physical route clock. Final camera remains locked to the end. SFX insertion is one frame after the corresponding authored reveal, preserving strict existing audio/rhythm QC.

The underlying Scene JSON remains geographic/model-based. Event distance metadata is calculated using frozen route helpers and physical path progress; it is not invented from elapsed fractions. Ship/aircraft display scale is bounded separately from the physical route. Native posed geometry checks enforce clipping, grounding and tracking eligibility.

### Comparison: observed versus planned

| Metric | 64306 reference, observed | 64313 current, observed | v013 planned/native, not GPU pixels |
|---|---|---|---|
| Longest continuous high apparent motion | 2.133 s | 1.233 s | Major travel ≤1.200 s on shipping QA; no travel during hold |
| Relevant recognition interval | Local marker 1.433 / 2.167 s to next new move; some travel overlaps | Late Suez information ≈0.72 s before movement | Closure 1.433 s / route change 1.600 s |
| Settle after local reveal | 1.000 / 1.367 s | Depends on reveal; earlier 1.533 s settle precedes later message | Exact pose/FOV lock through protected hold |
| Text during travel | Present in reference; marker context established first | Singapore appears during 7.7–8.6 s turn | Core primary appears after lock; projection timing QC PASS |
| Concurrent information | Context→location→detail sequence | Late location / HOLD / distance competition | One primary, at most one subordinate location; support omitted |
| Route / entity | Visually trackable detail markers | Thin route / faint vessel in globe composition | Zoom-aware route widths, entity ≥18 px projected bound; actual contrast NOT_RUN |
| Result | ≈2.533 s exposure but continuous final zoom | Final metric ≈1 s to end | 2.033 s protected primary hold; final camera locked |
| Earth occupancy | Flat geographic reference: not comparable Earth metric | Globe roughly 90–97% of frame width, with vertical black space | Final ray-projected area 39.34%; actual image segmentation NOT_RUN |
| Luma proxy | Overall geographic ROI median83.59; final97.70 | Median74.49; final41.14 | Beat-specific readability floor; real surface luma NOT_RUN |
| SFX alignment | Isolated timing unavailable from mixed audio | Mixed audio only; no invented onset | Real synthetic audio/rhythm QC within one frame |

Current p95 apparent rotation11.20°/s is lower than reference14.10°/s. Current p95 log-scale speed0.185/s is also lower than reference1.505/s. This disproves a blanket “all camera speed is too high” diagnosis. v012 counted settle before the late event; it did not reserve a complete post-reveal interval. Late competing text and subsequent movement make the information feel rushed despite lower global motion metrics.

## Output diagnostic metrics and quality boundary

The new renderer records actual camera quaternion/position/FOV changes, label visibility receipts and observed primary reveal intervals into the existing frame-audit/Diagnostic ZIP path. Real GPU draws additionally record Earth pixel-mask occupancy/luma/dark fraction, projected entity size and route-head pixel contrast. First samples are explicitly NO_PRIOR_FRAME, not zero-motion success. Pixel warning policy remains separate from hard technical invariants.

Native preflight uses the real Three.js posed models and projection math, without WebGL. Ray masks are geometry measurements, not pixel/luminance proof. Synthetic JPEG tests encode 360 valid frames at HIGH 2160×3840 internal /1080×1920 output, with real FFmpeg, concat, audio, QC and controlled checkpoint retry. They do not render maps and cannot certify final GPU aesthetics.

The final image must pass CI container gates before publication. Final source revision, container test counts and anonymous image digest are recorded separately in FINAL_REPORT.md after release verification.


## Container-only frame-clock defect found before publication

The immutable Bookworm runtime rejected variable 64/88/93/115-frame beat assembly with FPS_MISMATCH while the host FFmpeg 7.1.5 synthetic pipeline passed. The release was blocked. The v013-only concat now declares each offset from validated frame count/FPS rather than container-rounded format duration. It requires compatible H264 parameter sets, uses stream copy without automatic bitstream conversion, and verifies all packet payload hashes and sequential presentation timestamps. No frame is dropped, duplicated, re-encoded or accepted by weakening QC. Legacy concat is unchanged. A completed proof and file hash are required before an assembled file can be reused on retry. The corrected container synthetic/audio/QC/retry gate passed on revision eb3c33d; final-revision full validation follows. The exact same inputs' pre/post container clocks are preserved in release evidence.


Verified same-input container comparison: original average frame rate276480/9217 (29.996745 fps), stream duration12.001302 s, format duration12.002 s,360 frames. Frame-clock concat:30/1 fps, stream/format duration12.000000 s,360 frames. Individual source format durations are2.134/2.934/3.100/3.834 s, although stream durations are2.133333/2.933333/3.100000/3.833333 s. This confirms millisecond format-duration rounding accumulating across unequal beat joins. CONTAINER_FRAME_CLOCK_BEFORE_AFTER.json contains the exact report, workflow and source revision. That intermediate run was deliberately superseded by the final assembly-reuse proof guard; it was not published.
