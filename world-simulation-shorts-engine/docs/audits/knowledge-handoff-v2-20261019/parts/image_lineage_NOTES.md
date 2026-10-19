# Image/source lineage findings

The current operation image is fixed at `8ef393…`, source `83bf1e0…`. Its historical independent digest-pull record binds the full recursive source manifests. A fresh Docker pull/build/GPU execution was not performed by this audit. Root separately checks the public registry metadata.

The source closure has 373 engine paths, 51 Studio paths, 21 HTTPS setup paths and 12 proxy extension paths: 457 distinct explicitly bound image paths. This count excludes the OS/library filesystem; additional inherited executable aliases have their own hash checks. The flat path/hash table is in `IMAGE_AND_BASELINE_LINEAGE.json`.

**Advanced five-second Reference V2 modules are included in this image.** Saying “an old image lacks all advanced V2 effects” is incorrect. Current Studio selects the V4/V3 long renderer, whose selected area/front/camera/unit passes differ from `ref2_runtime.mjs`. A file being present does not establish a parser field, a Scene control, or current rendering invocation. See the map and planner audits for the actual selected pass graph.

The later durability/offline/Dropbox production extensions are not ancestors of the current no-backup image. Their presence in GitHub does not activate them in this image. Existing standalone FINAL manifests remain reference baselines; their presence in Git does not mean the complete standalone fixture route is selectable in Studio.

The audit inspected metadata/source text only. No image rebuild, deployment, source change, new workload or GPU rendering occurred. Current80s output visual/hardware verification remains NOT_VERIFIED.
