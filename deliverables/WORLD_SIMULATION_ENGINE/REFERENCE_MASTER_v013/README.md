# REFERENCE_MASTER v013

The new preset allocates recognition time before compiling geographic scenes.
Existing saved plans keep their original source version; FAST_PLUS_LEGACY selects
v012. The actual reference/current frame evidence and motion proxies are in
ANALYSIS.md, metrics0.json and metrics1.json. SOURCE reference assets, text,
locations and story are not packaged into the operating image.

Four 12-second domain fixtures and a separate 75-second geographic planning
regression exercise the reference grammar. No 75-second video was rendered.
Synthetic JPEG media exercises encoding, audio, concat, QC and retry; it is not
a GPU map render. Pixel contrast, shader lighting and perception require a real
RTX4080S output. Planned/per-scene geometry is deliberately labeled separately.

Release is conditional on full regressions, all fixtures, container asset/runtime
checks and authenticated health/login persistence. A reference planning PASS is
not an actual-output quality PASS. Existing Diagnostic ZIP captures actual frame
invariants and the new direction/pixel records; preflight.json includes perceptual
geometry and planning metrics. No secret or whole-environment dump is introduced.

PWA, standalone application mode and brighter web UI remain separate TODO work.
