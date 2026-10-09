Current video is 1080×1920, 30 fps, 720 frames / 24.000s. CPU ffmpeg decoded every frame; all-frame metrics are in `frame_metrics.csv`. All requested cue windows were inspected densely, with every-frame crops at entrance/exit boundaries. Artifacts are under this directory only, with no decoded frame archive.

Visible text pattern: thin uppercase pale-gray/ivory text, narrow dark outline, broad soft neutral/dark shadow. Text opacity resolves over ~12 frames (~0.4s); it exits over ~10 frames (~0.33s). The shadow is already strong on the first active frame and remains strong near the final active frame. No confirmed entrance translation, scale animation, bounce or letter-by-letter reveal. Screen glyph size stays similar through camera zooms, including the 14s wide view.

| Label | First affected frame | Resolved by | Fade-out frames | Absent |
|---|---:|---:|---:|---:|
| SUEZ CANAL | 61 / 2.033s | 72 / 2.400s | 440–449 / 14.667–14.967s | 450 / 15.000s |
| CANAL CLOSED | 181 / 6.033s | 192 / 6.400s | 320–329 / 10.667–10.967s | 330 / 11.000s |
| CANAL OPEN | 331 / 11.033s | 342 / 11.400s | 440–449 / 14.667–14.967s | 450 / 15.000s |
| SINGAPORE | 451 / 15.033s | 462 / 15.400s | 710–719 / 23.667–23.967s | Ends at frame 719 with barely visible text |

Suez has a faint peach/orange geographic X during CLOSED: hard on at f180 / 6.000s, present through f329 / 10.967s, gone at f330 / 11.000s. Its native center is approximately (534,961), and its arms occupy about 80×86px. One arm is nearly vertical and the other diagonal. No expansion or cyclic pulse is confirmed. Orange limb bounds remain similar at the first and last active frame; the apparent gradual intensity change in neutral background subtraction is contaminated by the closed-text shadow. See the native crop and marker timeline.

No conventional location pin, dot with leader, radial pulse, green OPEN marker, colored status glow, route highlight or region fill is visible. No Singapore pin/pulse is visible in dense close-view anchor crops. General rendering includes a narrow cyan globe limb, clouds, night terminator and city lights. A large diffuse Mediterranean light patch is visible before CLOSED and remains through the close shot; it is not timed to a status cue.

At 14.000s, SUEZ CANAL and CANAL OPEN keep approximately their close-view screen size and sit nearly left-aligned around native x138, with vertical line origins around y836 and y688. Their glyph height is about 44–50 native pixels; exact font/outline widths and easing curves cannot be established from compressed pixels alone. At 19.500s, SINGAPORE sits around native bbox (486,1028)–(800,1076).

All 720 frames are globe/map content. There is no distinct outro, end-card, logo or subscribe overlay. The map remains at the end while the Singapore text fades. Detailed data and uncertainties are recorded in `findings.json`.
