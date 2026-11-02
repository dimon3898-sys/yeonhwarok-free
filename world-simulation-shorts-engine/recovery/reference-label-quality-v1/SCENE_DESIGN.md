# 10-second geographic quality candidate

`QUALITY_LABELS_10S.json` is a new candidate. The successful `GENERIC_LABELS_10S.json`, its MP4 and its image are unchanged. The existing two 150-frame segments, Studio input contract and 300-frame NVIDIA route are retained.

| Frames / seconds | Map and camera | Labels |
| --- | --- | --- |
| 0–17 / 0–0.6 s | Reveal the real Namibia outline and warm country fill. Hold overview. | Larger white Namibia card with a context pin. |
| 18–59 / 0.6–2 s | Existing cubic camera moves toward the supplied Windhoek context. Country emphasis grows without changing its polygon. | Country card remains geographically anchored. |
| 60–89 / 2–3 s | Arrive at the admitted regional zoom; preserve the full country footprint. | Windhoek appears per grapheme with a blue halo and hero pin. |
| 90–149 / 3–5 s | Hold geographic emphasis. | Read Windhoek, then dismiss it before the seam. Country card stays opaque. |
| 150–184 / 5–6.17 s | Exact camera/color/geometry continuity. Brief wider view begins the coast beat. | Country card and context pin remain full size; no repeated entry. |
| 185–239 / 6.17–8 s | Pan toward the coast while country emphasis changes from warm orange to cyan. | “대서양 해안” appears with a blue halo, grapheme reveal and hero pin. |
| 240–299 / 8–10 s | Return to the admitted country framing and hold. | Coast label exits by frame 270; Namibia card remains for the ending. |

The country polygon is the preserved 235-point `COUNTRY_NAM` ring, unchanged from the original input (canonical geometry SHA256 `dce5948b914856654d0018bf361bbb581a8a4cc39b43fca4bdb457ce0f8bedd8`). `NAM_BOUNDARY` is the same ring as a LineString. The coast anchor `[14.40332,-22.968066]` is an exact ring vertex. Windhoek retains `[17.083546,-22.570006]`. The country-name anchor is a cartographic placement point inside the country, not a claimed city or surveyed center.

`GENERAL` with `SYNTHETIC_TEST` data mode denotes authored presentation states, colors and ordered dates under the existing source policy. It does **not** claim that geography is invented, or that state dates describe war, sovereignty, occupation or observed border change. The existing generic area-state backend is named `WAR`; no engine or fact-admission policy is changed for this geographic showcase.

Only one actual country polygon is colored. No rectangular synthetic territory, invented numeric count, unsupported local detail, false 85 m measurement, count-up effect or new region dataset is introduced. Local reference zoom cannot be promised from this regional source and the unchanged full-country safety constraint. The candidate aims to test the missing visible styling and coordinated sequence first.

## Focused evidence

Run `node recovery/reference-label-quality-v1/tests/test_quality_scene.mjs` for the changed input's structural checks. With the real existing assets checked out, add `--private-root=<owned-0700-root> --public-root=<separate-existing-root> --output=<fresh-evidence-directory>` to use the existing source qualifier and NVIDIA preparation function without launching a browser. That produces `REQUEST.json`, `PREPARED.json`, `CPU_FRAME_AUDIT.json` and `SCENE_RESULT.json` for the separate free software pixel harness.

The CPU audit checks every new candidate frame for source coverage, real-country safe footprint, geographic label anchors and camera seam. It does not declare label-pixel readability or reference-video parity; those require the measured-font pixel harness and a later separately authorized GPU video review.
