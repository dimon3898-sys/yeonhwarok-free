# Reference analysis — implementation prerequisite

Source: user supplied `lv_0_20261004072746.mp4`. Studied the complete frame sequence using FFmpeg extraction and three 0.5-second contact sheets, including the final export card. No instructions embedded in the footage are treated as user instructions. No footage, script, screenshots, audio or proprietary graphics are reused in the output.

## Measurements and method

- 822×1920, approximately 30 fps, 449 frames, 14.9667 s. A recorded mobile Shorts interface occupies substantial screen area. Map content ends around 12.8 s; the remainder is a black CapCut export card.
- Stereo AAC 48 kHz, audio duration 12.8213 s. Decoded peak −0.88 dBFS, full-track RMS −18.78 dBFS. These are signal measurements, not integrated loudness.
- The visual observations below are from frame inspection. Approximate event times have ±0.25 s uncertainty from the initial contact-sheet sampling. Subtitles changing alone are excluded from the main visual-event cadence.
- Content event onsets: 0.0 (moving camera/path), 0.9 (North America reveal), 1.5 (arrival), 2.0 (rings), 2.7 (impact growth), 3.2 (aftermath), 3.8 (East Asia cut), 4.3 (photo icon), 5.5 (icon caption), 7.4 (new identifier), 9.9 (range region), 10.7 (route/zoom), 12.8 (export card).
- Content-only onset intervals: mean **0.97 s**, median **0.70 s**, maximum **2.50 s**, based on 11 intervals between the 12 onsets before the export card. Including the 12.8 s export-card transition gives a mean of **1.07 s** across the complete recorded edit. This is an approximate editorial measurement, not an exact automated event detector. Continuous camera and entity motion often run between onsets.

## Visual findings

| Requirement | Observation / principle extracted |
|---|---|
| First second | Starts inside the action: East Asia/Alaska, bright warm moving heads and an already moving camera. No logo introduction. |
| First three seconds | Movement crosses the Pacific, orange destination territory enters frame, then three arrival rings expand. Cause → destination → consequence. |
| Map / satellite / terrain | Satellite-like green/tan land, textured mountains, dark navy sea. Raster detail gives recognisable geography. Data provider cannot be established from the recording. |
| Country colours | Orange destination, red source, later broad translucent red coverage. Strong contrast but flat fills hide some terrain. |
| Borders / coast | Geographic outlines are clear at overview level. Country emphasis relies mainly on fill; no consistently distinct border glow is visible. |
| Glow | Warm yellow route heads are very bright, with broad bloom and short streaks. Impacts use bright rings. Extract a controlled luminous focal point, not this extreme brightness. |
| Zoom / pan / speed | Initial continuous west-to-east geographic travel, settling at destination; abrupt return to East Asia around 3.8 s; large range pull-out around 10 s. Different shot speeds signal importance. |
| Tracking | Camera broadly follows the luminous heads in the first shot, not a rigidly locked central icon. Later it frames the origin and expands the map. |
| Scene duration | First sequence ≈3.8 s; East Asia explanation ≈6.1 s with overlays changing; range expansion ≈2.9 s. The explanatory segment holds its map view longest, though overlays and slight map drift continue. |
| Icon design / scale | Three luminous entities initially; later rectangular photographic cutout ≈one quarter of map width. It pops in with a slight rotation. Not a coherent vector icon system. |
| Icon movement | Initial heads translate with streaks; later photo stays anchored on a country and scales down during zoom-out. |
| Routes / trails / arrows | First trajectory is a thin luminous streak with fading fragments; later a long yellow range line grows across the map. No convincing arrowhead system or geodesic specification can be verified. |
| Radar / impact | Three expanding circular arrivals turn into clustered impact/aftermath shapes. Later a large translucent range disk creates scale. |
| New countries / information | Camera reveals the destination first; colour identifies it; arrival effects follow. A return to the origin precedes a photo, name, then range reveal. |
| Curiosity | Each action creates an unanswered geographic question, answered by the next camera movement. The late pull-out changes perceived scale. |
| Captions | White Korean text near the lower map area. Coloured cyan/yellow object labels near the photo. Recorded app UI interferes with typography and safe areas. |
| Mobile readability | High contrast focal objects are easy to find; small lower captions and stacked photo labels are less clear. Original map detail is constrained by screen recording and overlays. |
| Transitions | Mostly continuous pan/zoom with one abrupt geographic cut. The output will use uninterrupted spherical camera travel, avoiding teleportation. |

## Audio findings and limits

The decode covers all 12.8213 s of audio. 50 ms RMS-envelope analysis locates prominent maxima near 0.40, 1.15, 2.10, 2.70, 4.45, 5.45, 7.35, 10.00, 11.05 and 12.05 s. The loudest sustained second is 2–3 s (−13.9 dBFS RMS), coinciding with the expanding impact effects; 9–10 s is quieter (−24.4 dBFS RMS), immediately before the late range reveal. Peaks can include speech and are **not** proof that each is an effect hit. A separate BGM stem and effect identities cannot be established from the mixed file. The tool environment does not expose playable audio to the assistant; therefore direct listening, exact BGM character and psychoacoustic mix assessment are not claimed.

For the new sample use original procedural audio: restrained low harmonic tension, filtered zoom whooshes, precise route pulses, stereo pass-bys, soft arrival transients and a deep final impact. Avoid copying the reference audio. Leave the speech-frequency region relatively open.

## Production decisions

Neutral fictional cargo-air itinerary: **Singapore → Seoul → Tokyo**, with a maritime network hint at the end. Geographic coordinates and actual GIS country boundaries; no predictions, military imagery or conflict story. A curved 3D globe with terrain raster sourced from real GIS and vector borders; cyan and warm ivory/gold accents, restrained bloom, dark ocean, original dimensional aircraft silhouette. Continuously interpolated camera, geodesic elevated routes with progressive heads and fading tails. Original typography and bilingual restrained labels.

20 s edit: 0–1.5 moving globe hook; 1.5–4 Singapore approach/highlight/aircraft; 4–7 northbound tracked flight; 7–10 pull-out and Seoul reveal; 10–13 second leg; 13–16 low-angle curved-Earth shot; 16–18 Tokyo arrival/network reveal; 18–20 widening final composition. Visible authored events at least every 1–2.5 s, with one dominant focal point.

This file was written before application implementation. The current repository's original README and HTML have a recoverable complete archive under `/workspace/preserved-originals/` and remain unchanged.
