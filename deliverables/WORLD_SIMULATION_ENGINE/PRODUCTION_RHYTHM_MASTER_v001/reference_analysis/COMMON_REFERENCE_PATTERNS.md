# Two-reference common-pattern analysis before implementation

Analysis date: 2026-10-06 (Asia/Seoul). Both user-uploaded files were decoded and their actual images inspected. These are cropped excerpts of already-running Shorts, not complete introductions or whole narratives.

| Measurement | Reference A | Reference B |
|---|---|---|
| File duration | 8.500 s | 14.133333 s |
| Actual narrative image interval | 0–6.500 s (frame 195 is the first export-ending frame) | 0–12.133333 s (frame 364 starts the export ending) |
| Excluded export ending | 2.000 s | 2.000 s |
| Actual mixed-audio integrated loudness | −22.7 LUFS | −15.4 LUFS |
| Actual mixed-audio true peak | −8.3 dBTP | −1.9 dBTP |
| Short local energy dips measured in decoded PCM | 0.05–0.18 s | 0.05–0.11 s |

The already-present line, initial moving trails, continuously growing effects, ordinary camera travel and subtitle swaps are not counted as newly occurring graphical story events. A's detail-readability reveal around 3.867–4.333 s is followed by two direction indicators around 5.000–5.0667 s and state markers around 5.333–5.400 s: two fresh overlays and one detail reveal, not a whole-video event-rate proof. B has seven conservative new graphical onsets around 0.733, 1.967, 4.8, 6.0, 7.4, 8.1 and 10.9 s: 1.694 s between onsets on average, with a maximum of 2.833 s. B values retain the visual-review sampling uncertainty (approximately 0.1–0.2 s for gradual appearances); A late indicator onsets are bracketed by actual frames.

## Shared patterns and bounded adoption

- **Unequal beat lengths:** a detail or subject is introduced, movement accelerates, then a result has a short reading interval. The files do not establish a universal fixed one-second beat. Keep meaningful events in the existing story; subdivide motion/focus/anticipation into separate, explicitly non-counted micro beats.
- **Anticipating camera:** A begins its regional dive around 2.7 s before detailed region information; B begins the next regional move around 4.5–4.7 s before the next tint around 4.8 s and new entities around 6.0 s. Retain native NEXT EVENT CAMERA and its real event clock.
- **Speed contrast:** both actual image sequences contain fast travel followed by a more readable local composition. Use component-local camera/route ramps, preserving their endpoints, geographic geometry and global event/text clock. Do not globally accelerate the video or narration.
- **Focus contrast:** active geography or a small active object is separated from its surroundings. Preserve approved AUTO FOCUS, route hierarchy and v004 materials rather than copying reference color fills or shapes.
- **Short information:** text changes with the immediate situation and is not a decorative slogan. Their text placement differs: A combines local map labels with narration fragments; B chiefly uses short lower-center narration fragments. The common principle is timely, concise information, not a shared font, placement or script. Keep sourced places, distances and brief scenario statuses; remove generated decorative questions.
- **Audio dynamic contrast:** real PCM has frequent transients and very short energy decreases. Because narration, music and effects overlap, these measurements do not identify individual SFX files or prove every decrease is an intentional pre-hit pause. Adopt restrained short breaths, distinct original timbres and stronger important hits; measure our isolated stems and event bindings independently.
- **Peak/result rhythm:** movement culminates in a visual result, followed by a short readable interval and a cue toward another event. Preserve the existing fresh final route reveal; add a short pre-hit, one main impact and a restrained tail, not repeated booms.

## Evidence limits

The runtime does not support listening to attached audio through the assistant's audio input. Audio findings here are decoded-waveform, spectral-onset and loudness measurements, not a claim of human listening or exact reference SFX identification. Mixed-track onset candidates include speech; they are not an SFX count. The shared ranges above inform timing, while all output sounds are original licensed synthesis. No reference audio, script, country choice, warfare scene, map palette or screenshot is incorporated into the output or published deliverables.

Detailed independent visual timelines are recorded in the sibling `rhythm_reference_analysis_A_v001` and `rhythm_reference_analysis_B_v001` evidence directories. Reference screenshots and frame extracts remain private analysis files.
