# v022 actual-video baseline and source evidence

This report compares the actual uploaded REFERENCE 64306 and CURRENT 64558 pixels. It does not identify the source revision of CURRENT, does not contain an AFTER NVIDIA render, and does not transfer reference story, geography, words, colors, fonts or map assets into World Engine.

## Input identity and scope

| Input | SHA-256 | Native frame grid | Analysis scope |
| --- | --- | --- | --- |
| REFERENCE 64306 | `853ce5be22dc95c95e0c4b3eddbd603930e499bc88ee40cb4e59b50aad1187bc` | 822×1920; 30 fps; 635 decoded frames | Actual content F000–574; phone outro F575–634 excluded |
| CURRENT 64558 | `1fc3e4bdc8f393e0363dde259649337633bfad752e15a41660f65eae2581d7c4` | 1080×1920; 30 fps; 720 decoded frames | F000–719; 24 seconds |

CURRENT image digest/revision, actual runtime Scene JSON, page hash, font hash and render environment are UNKNOWN: its original Diagnostic ZIP was not supplied. Existing checkout `b88ec3e26d45c1709bf7496cbaed4e220a14628c` is a repository audit baseline, not proof that it generated CURRENT. RTX4080S success is user-reported for CURRENT; no new GPU or Workload was run for this review. Candidate AFTER pixels are NOT_RUN.

Every frame of both files was decoded again on CPU. `INPUT_CAPTURE_RECEIPTS.json` records input metadata and individual raw RGB frame receipts. Reference content viewport `[x=0,y=160,w=822,h=1463]` was converted to RGB before the odd-height crop and normalized to 1080×1920 with Lanczos for comparisons. This is analysis normalization, not enhancement. Extracted forensic screenshots retain original phone platform controls. `REFERENCE_MAP_ONLY_*` comparison copies mask the right-hand platform UI and lower platform author/footer regions; masked pixels are never described as rendered map pixels. Local text/geometry measurements exclude that UI. Coarse full-viewport luminance inventory is not a geography readability certification.

## Directly observed reference grammar

| Frames / time | Actual observation | Evidence and permissible conclusion |
| --- | --- | --- |
| About F029 onward / 0.97s onward | Highlighted geographic region is opaque enough to read, with a strong perimeter and retained terrain underneath | Region highlight and geographic attachment are established. Exact alpha, shader, GIS provenance and stroke method are unavailable. |
| F176–185 / 5.87–6.17s | Location pins grow, settle and remain after introduction | Intro animation and marker lifetime are separate. Persistent marker is established; a repeated pulse is not. |
| About F201–230 / 6.70–7.67s | A second geographic focus receives its own fill/perimeter and remains visible | Region/state emphasis rather than a continuously repeating effect. Reference colors and region content are not templates. |
| F289–306 then F311–328 / 9.63–10.93s | Location text appears in steps; stable colored text halo is visible after the introduction | `REFERENCE_TEXT_PERSISTENCE.jpg`, F305/F328/F343 distinguish retained halo from intro flare. Treat steady halo as contrast support, not an endlessly animated glow. |
| F333–343 / 11.10–11.43s | Central marker grows and settles; remains through F574 | Approximately eight seconds of retained geographic anchor after the settled marker. |
| F351–450 / 11.70–15.00s | View moves toward a local feature; geography and labels remain associated with the map | Reference itself contains additional local movement. This does not authorize changing the strict 720-frame QA camera fixture. |
| F449–500 / 14.97–16.67s | Local region edge already exists. A short junction/feature becomes progressively brighter around F455–483 and then persists | `REFERENCE_JUNCTION_SEQUENCE.jpg` is dense local evidence. The pixels do **not** establish whole-country sequential boundary creation. Existing v020/v021 wording “boundary draw” was too broad. Call this LOCAL_FEATURE_EMPHASIS; default to authored fade/state change unless a separately evidenced draw is selected. |
| About F487–510 / 16.23–17.00s | A numeric measurement is introduced and then remains unchanged through F574 | A numeric annotation is established. Count-up behavior is not. No reference number is imported into QA or Production. |

The local feature may brighten in a directional order, but video alone cannot distinguish a stroke-progress renderer from a mask, opacity or gradient change. No full sequential boundary draw, repeated pulse, particle, explosion, screen flash, persistent animated glow, or traffic route/trail behavior is established. No isolated SFX stems exist, so audio onset evidence cannot prove that a particular sound is an event-only effect rather than voice/music. New copied sounds are not supported by this review.

## CURRENT actual information progression

| Frames / time | What viewers actually receive |
| --- | --- |
| F000–059 / 0–2s | Wide geography with no primary event fact yet. The strict QA fixture retains this certified camera/timing; separately versioned Production can have different authored speech/beat pacing. |
| About F061–089 / 2.03–2.97s | SUEZ location reveal and short marker intro. F069 marker circle is small, around 24 output pixels across. |
| F090–149 / 3–4.97s | First certified zoom toward Suez. |
| F180–197 / 6–6.57s | CANAL CLOSED text reveal. The event connection to geography remains primarily a point, not an evidenced canal polygon or line. |
| F197–319 / 6.57–10.63s | Full CLOSED message stays for roughly 123 frames / 4.10s, with little new authored information. This is retained perception time, not proof of a missing real event. Do not invent traffic, damage, numbers, reroutes or objects to fill it. |
| F320–329 then about F330–347 / 10.67–11.57s | CLOSED is cleared, OPEN is introduced. The actual text state replacement is available to visualize; it is QA hypothetical, not sourced historical news. |
| F360–420 / 12–14s | Existing zoom-out. |
| F420–450 / 14–15s | Existing adaptive-wide lock/context. |
| About F450–465 / 15–15.5s | Singapore location reveal. |
| F495–585 / 16.5–19.5s | Existing second zoom. |
| F585–704 / 19.5–23.47s | Location-only Singapore view remains about four seconds. No distinct Singapore event/result is visible in the supplied sample. Do not add an arrival result as fact unless authored data supplies it. |

CURRENT's event text is visually thin and has an unusually broad neutral gray shadow around the title. The dark shadow footprint obscures more geography than the actual glyphs. Geographic attachment, real weight/contrast, information role and retained marker/region state are the evidence-based gaps; “make all text much bigger” alone does not explain the difference.

## Raster text measurements

`PIXEL_MEASUREMENTS.json` retains exact ROIs and threshold definitions. These are threshold-dependent raster estimates, not point sizes, font weights, alpha, WCAG ratios or certified readability.

| Actual frame | Measured ink definition | Height at 1080px output width | Equivalent at 360px display width |
| --- | --- | --- | --- |
| REFERENCE F305 | White location glyph core | 50px | 16.7px |
| REFERENCE F328 | White location glyph core | 50px | 16.7px |
| CURRENT F197 CLOSED | White positive-difference glyph core | 47px | 15.7px |
| CURRENT F197 SUEZ | Neutral dark stroke threshold | 43px | 14.3px |
| CURRENT F347 OPEN | Neutral dark stroke threshold | 52px | 17.3px |

Definitions differ between white core and dark outline, with about ±2–4px threshold uncertainty. They do not establish a large size gap. CURRENT F180→197 adds a broad neutral negative-difference region at least 600×128px inside the tested ROI; left/right ROI edges are censored, so this is a lower-bound extent, not the full shadow width. Outline and small lighting/texture clock differences can contribute; the visible broad gray shadow is also directly inspected.

## Existing fonts, textures and licenses

`FONT_TEXTURE_SOURCE_AUDIT.json` records hashes, true font weights, dimensions, coverage and license files. All inspected manifest hashes match actual local files. No external source was downloaded.

- Shipped Noto Sans CJK KR Regular is real weight 400 with no variable weight axis. SHA `91a6b21a427d1a5982e19e8875bfd6af620d0a372cd84967a0c225b90f342f6c`; 16,433,088 bytes; SIL OFL 1.1; Korean/Latin QA glyphs present. Declaring 500/600 in CSS would not supply actual 500/600 font files.
- Existing system Noto CJK Bold TTC contains real **Noto Sans CJK KR weight 700 at face index 1**. It is a legal local candidate covered by existing Noto OFL. Mono face index 6 is distinct and must not be substituted accidentally. Its extraction/bundling and GPU raster result belong to implementation validation, not this baseline audit.
- Existing Open Sans Light is real weight 300, SHA `cf5f5184c1441a1660aa52526328e9d5c2793e77b6d8d3a3ad654bdb07ab8424`, 222,412 bytes, Apache 2.0. It does not cover Korean, as expected.
- Natural Earth source TIFF really exists locally: 21600×10800 RGB, 699,969,932 bytes, SHA `b47bdddd1336b07f498c50eba5d70699ec57dd726a7ea0a85d2dca243236c9eb`, matching the v018 manifest. A missing tracked-tree listing is not evidence of filesystem absence. This audit does not establish full TIFF presence in a deployment container.
- Existing v018 regional DayRelief/LandMask PNGs retain their manifested native crops and hashes. Global Day/Night/Cloud assets remain 8192×4096. Existing relief is 2048×1024; regional color detail must not be represented as a new high-resolution elevation model.
- Existing Natural Earth/public-domain, SOLSYSTEMSCOPE CC BY 4.0, Noto OFL and Open Sans Apache licenses/credit sources remain present. Reference assets are never licensing substitutes.

## Before / After contract

`BEFORE_AFTER_FIXTURES.json` records exact actual source frame SHA values and five reference/current comparison pairs. The pairs compare hierarchy, persistence and geographic attachment across different locations, content and colors; they are not identical-camera map-quality comparisons. AFTER entries are null/NOT_RUN. A future authorized RTX4080S output must supply its actual MP4, Diagnostic ZIP, image revision and the corresponding camera-locked frames before an output-quality pass can be claimed.

The implementation should retain strict QA 720-frame camera/timing and baseline visual materials; version new graphic/state layers independently. Any Production solver, new real geometry source, measured TTS, font extraction or new LOD requires its own provenance/contract checks. This baseline review neither fabricates missing event geometry nor promotes QA CLOSED/OPEN into a historical claim.
