# Duplicate place-label QC regression

The new post-draw audit check catches a persistent place label and an event-owned world label placed twice for the same unambiguous location ID/text in one Earth view. Disjoint boxes still fail: geometric clipping alone cannot catch this semantic duplication.

## Actual regression

- Preserved shipping project `project_594442ec2df9/v001`, S002: `ROTTERDAM_PORT`, E008, two distinct ROTTERDAM world-label boxes.
- Native local 3.533333–4.633333 seconds, 34 frames, 1.133333 audited-frame-equivalent seconds; the boxes do not intersect.
- Existing encoded local 3.90-second still was directly viewed and confirms the two visible placements. No new clip or frame render was performed.
- Only the two completed shipping Scenes (450 native frames) were inspected. This does not claim full75-second playback/QC.

## Earlier real20-second exports

Both `project_b89a30908047/v003` and `project_21a865e0dc8d/v001` were checked against their own preserved immutable plan and all 600 native audit frames. Neither contains a concurrent base/event pair with the same world-label text. Comparison Scenes were included; no blanket COMPARISON exemption remains. This is an independent read-only audit finding, not a replacement or mutation of their earlier QC reports.

## False-positive protections

Information/story labels, subtitles/narration and clip annotations are excluded. Separate explicit panel/view IDs do not compare across panels; COMPARISON scene type alone is not exempt. Identical place names with distinct IDs, unresolved multiple base targets, invisible opacity ≤.1, invalid boxes, or a repeated identical box record cannot establish duplicate spatial placements. Live city_reveal/arrival event-owned world labels are checked too.

The checker uses actual post-draw opacity/boxes and binds missing native place IDs to the immutable Scene's unambiguous spatial labels/event. It does not claim OCR, geolocation from pixels, or that unresolved targets are duplicate-free.

## Validation and integration

18 focused tests passed in 1.975 seconds. The QC dispatch test uses a mocked one-frame decoder solely to verify persisted failure/report propagation; it does not assert a publication-ready film. Full-suite execution belongs to the coordinator after source freeze.

`engine.visibility.analyze_duplicate_place_labels(plan, frames, fps=30.)` accepts flattened native frames (use `engine.qc._audit_frames(audits)` for paths/containers). `run_qc` now invokes it after flattening audits, adds `DUPLICATE_PLACE_LABEL` to failures, stores `duplicate_place_labels` in JSON and writes the count in Markdown.

Existing server/worker imports may retain the old run_qc function. This change is **not assumed applied to the current running75-second job**. A fresh Python cold post-check and/or a newly loaded version pipeline must record actual application. No server restart or worker action was performed here.

## Preservation

`source_before/` and BEFORE/AFTER manifests preserve exact original source bytes/hashes. Original immutable shipping plan, S002 audit, Earth adapter and renderer tool retain their hashes. The visual renderer cache version remains `2225c34373166e87f4ab1101e7d15756d2a82526668e64b1e1fb1f2184271646`; no renderer/asset code changed. Current IR, QC records, approval, worker, Git and outputs were untouched.

Native reports ending `_native_label_probe_v2.json` are authoritative. Earlier probes in this folder are preserved but used an overly broad COMPARISON exemption; the final v2 probes remove it and include all single-Earth comparison Scenes.
