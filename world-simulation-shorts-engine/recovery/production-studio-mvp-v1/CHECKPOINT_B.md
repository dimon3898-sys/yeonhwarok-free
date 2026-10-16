# Implementation checkpoint B: before image CI

The additive mobile UI, structured input contracts, original-manager bridge,
owner policy/consent, detached supervisor, explicit recovery, SFX/recomposition
and fresh storage export are implemented. The protected old V4 image and its
373-file closure are unchanged; the new Studio installs outside that closure.

Focused evidence is retained in `SFX_VALIDATION.json`, `CONTRACT_VALIDATION.json`,
`RUNTIME_VALIDATION.json`, `UI_TEST_VALIDATION.json` and `validation/mobile-ui/`.
Controller tests separately passed 22 cases. Packaging/source/inventory tests
are recorded by the upcoming CI. Existing large legacy suites and historical
research are reused rather than repeated.

Actual local integration used synthetic CPU media: 2 seconds, 60 frames,
64×96 H.264, through the original silent composition/export, original licensed
SFX, AAC mux, fresh storage export and corruption rejection. It is not a
production 80-second NVIDIA video or external Dropbox delivery. Mobile testing
uses actual Chromium portrait emulation with a clearly marked fake controller.

The first image build must now independently rerun changed-component tests in
the pinned parent environment, perform the required inherited real software
draw/readPixels, verify protected sources and zero secrets, publish a new unique
tag, and pull the immutable digest on a fresh free runner. No image or digest is
declared by this checkpoint.

Product limits are explicit: this MVP supports interval SFX revisions, not
camera/territory/frontier interval editing. The original V4 preset remains
80 seconds; other configured lengths need complete verified native V3 plans.
No paid GPU, automatic deployment/stop or FINAL promotion is performed.
