# Actual Studio movie and frame audit

Three separate structured prompts produced three actual authenticated Studio jobs. Each output is H.264, 1080×1920,30fps,3seconds,90frames,silent. All270 encoded frames were decoded and checked against their requested frame budgets and monotonic30fps presentation timestamps. Black/empty-frame checks passed. The original movies and capture PNGs are retained under `public-review/`.

`reports/video-audit/VIDEO_AUDIT.json` records full-decode and media results. CSV files alongside it contain every decoded frame's image statistics and thumbnail SHA. Consecutive identical frames in an intentional hold are measured and reported; they are not silently removed or mistaken for a missing timestamp.

`reports/DATA_TO_PIXEL_AUDIT.json` independently re-evaluates the existing engine plans for every frame. Original prompt and Scene identities, wire and semantic hashes, source geometries, geographic projections, camera state, input trace, Flow position/heading/pulses and Area state/alpha/front controls match the actual capture evidence. These checks distinguish real drawn feature pixels from an unchanged basemap.

For aviation and trade, route pixels were drawn in88frames, moving objects in82frames, with51 object-position changes. The fictional Area case drew supplied area controls in89frames and used exactly the two supplied states. Every movie's actual basemap readback stayed constant under its explicitly locked camera. Source-native material coverage has a positive native-pixel gutter; no missing tile or invented outside coverage was used.

Manual visual inspection covered the original full-resolution middle frames for all three movies, the start/middle/end comparison sheet (nine actual frames), and the paired original/modified route proof. No obvious basemap material seam or rectangular source tile was seen in that inspected scope. The whole270-frame pixel/data audit is automatic, not a claim that every full-resolution pixel was manually inspected.

The Namibia rectangles are the **explicitly supplied fictional polygons**, including a transition between two source states. They are not a map-tile defect or a real historical boundary. The Chile and Germany paths are declared illustrative city connections, not observed shipping/flight services. No country flag or unit was invented, and no camera movement is claimed: this preview consumer uses an actual locked V5 regional view.

The maps, areas and paths were rendered by the existing WORLD ENGINE functions; no AI image, finished-screen image overlay or repeated old movie was substituted. The comparison sheet adds only labels outside scaled copies of actual frames.

The moving-object graphics and Area color contrast are small/subtle at phone size. This functional proof does not establish reference-level cinematic quality. **QUALITY_REVIEW_REQUIRED / USER_REVIEW_REQUIRED** remains the decision. There is no NVIDIA, user-quality, historical-G3 or FINAL PASS.
