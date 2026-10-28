G1 diagnostic contract repair (CPU only)
Base: 478c6c33648e94f662673cab533bf14b74133f91
Known defect: page.evaluate adds text to exceptions; exact-enum safe exporter then loses the code. Cleanup exceptions can also skip the final receipt.
Changes: fixed enum browser result envelope, nested operation checkpoints acknowledged by Node, atomic private progress, separate first/cleanup errors, safe exporter checkpoint fallback, explicit storage failure classifications.
No renderer arithmetic, Scene, Vulkan launch flags, NVIDIA admission, supervisor, authorization or lease changes.
Existing runtime closure remains unchanged in the repository. New helper must be registered (353 files) and all variant/runtime/bootstrap/startup pins regenerated in an isolated G2 derivative before use. This branch is NOT a deployable image.
Browser tests exercise real page.evaluate and fault injection. Native test mocks are CPU_ONLY; no GPU result is claimed.
Original CHECKPOINT.json/evidence attachment not available; this checkpoint documents only this new execution and cites the supplied master.
CI uses public standard Ubuntu only. Artifact quota is unverified: no cache/artifact uploads. Safe evidence is printed for exact backup into this branch; artifact-specific gate remains unverified.
GPU_ROOT_CAUSE_UNKNOWN. gCube deployment/render prohibited.
