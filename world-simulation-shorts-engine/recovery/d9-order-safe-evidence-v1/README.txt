D9 verification order and safe evidence — preparation only

Safe base e163de2602a486196ec75683ddf0609bdcffb2ed; target e83ac5b423b77e730815ec73334ad67209ac6a6e.
The branches are divergent and were not merged. Only the workflow preparation
and the target's one exact D9 mismatchstop line were changed on the safe branch.

New order: OCI -> installed355 -> IMAGE_CONFIG_SAFE generation+validation -> D9
-> publication. Runtime checkout af9347963b4405dac66cdbe0ad6c6898c3d42ea0, source
manifests, bootstrap, Dockerfile/context and all existing build steps are frozen.
Generator and backup load from e163de... in a separate sparse checkout path.
The verified parent argument binds preflight, GHCR preflight, verified context
and pulled parent RepoDigests. Candidate rawinspect remains outside both artifact
directories; only the closed safe receipt is collected. No raw env/auth export.

Generation uses check=True, safe schema failures propagate, and explicit publish
outcomes require installed/safe_config/comparison success along with GitHub's
implicit success() condition. D9 equality stop is retained; no mismatch allowance.
Only final always-evidence collection creates SAFE_INDEX, once, using pinned
backup so IMAGE_CONFIG_SAFE is included on D9 failure. No early index overwrite.

12 NEW focused controls passed once, plus actionlint1.7.12/YAML/bash/Python
static checks. Publisher comparison functions were extracted as AST and run with
stub reads/writes; inline control validation used stub producers/validators.
No actual generator, old unit/contract/runtime cases, Docker/network, Actions,
images, GHCR or GPU executed. Locked PASS are reused without reruns.

Use only ACTUAL_CHANGE.patch for a later separately reviewed integration; do not
copy/merge the whole safe branch or overwrite target-specific guards. The safe
before value07ba... and target before7efe... were preserved; currenttargete83...
does not match the nextpush guard. Target branch and main were not updated.

Preparation PASS is not an actualimage/355/internalvalidation/publication PASS.
ImageID mismatch cause is stillUNKNOWN. Previous rebuild allowance is exhausted;
no additional run is authorized. Next is separate target integration/execution
gate review. Do not build/publish automatically after this source commit.
