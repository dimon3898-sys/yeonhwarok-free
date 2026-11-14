# Common V2 image release evidence

Image: ghcr.io/dimon3898-sys/world-simulation-shorts-engine:universal-input-v2-f32d54dc0150-43567343017
Digest: sha256:8afa856b2c87378354aae42755b3329eceed7c1db27a27491d367b76c15dc10d
Source: f32d54dc01507036fd66c4b06813611e48a6214b
Run:43567343017; artifact:14102539044. Source/evidence publication uses direct bounded GitHub commits. The image workflow has contents:read, packages:write and performs no branch writes.

Why one rebuild was necessary: the previous successful image and the previous20-second image lacked the common reviewed external-data loader and exact global timeline window contract. Input-only changes cannot install those common capabilities. The new image reuses the existing formal Dockerfile generator, pinned parent and NVIDIA route; no new renderer or topic-specific image is introduced. The external package is excluded. See PRE_IMPLEMENTATION_REVIEW.md and BUILD_DECISION.json for the pre-build gate.

Free actual-image results: UID1000, no network, read-only root, capabilities dropped, no-new-privileges, GPU devices absent. All three exact JSONs load the operator-pinned catalog, normalize through the real Controller and preserve runtime bytes through the real Worker writer. Required source/startup/native-route/worker-publication checks passed, followed by registry publication and remote digest confirmation. Five gate cases cover generic32MiB limit, imported reader large fixture, wrong SHA, unsafe permissions and hardlink rejection. Original full PASS suites were not rerun.

The new image's release approval concerns publication eligibility only. Original WebGL2/EGL initialization failure is not diagnosed or fixed by the data/window contract. Old success image/source/MP4 evidence remains retained; actual old Pod digest was not recovered. Current gCube#5373 remains stopped on a different5090 node and configured with its previous image. GPU executions0; Studio renders0; MP4 generated0.

The automatic source-application workflow was rejected by approval review; the safer alternative was direct, bounded UI commits. All61 source/evidence files were verified by SHA256 at d7072f0f0302139b6a971a61c95c935379004fff before image preparation. The unused auto-apply workflow is archived/disabled and contains no source-application action.
