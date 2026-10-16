# Focused integration review

Scope: only the additive Studio API, detached runtime, export adapter and
bootstrap. Existing FINAL, renderer, camera, frontier and old source contracts
are protected. This is a source/CPU review, not hardware or penetration-test
certification.

Concrete issues identified during integration:

1. The new GPU-health reader initially expected a vendor-prefixed model name,
   while the frozen GPU launcher returns normalized `RTX 4080 SUPER`, `RTX 4090`
   or `RTX 5090`. Align the reader with the actual old health contract and test
   that shape; do not change the original launcher or pretend to probe hardware.
2. Shared export readers initially bounded only the file's starting size. A file
   growing during read could exceed that size before the final identity check.
   Bound each read/copy by the original size and hard maximum, reject mutation,
   and clean only the newly created incomplete private copy.
3. HTTP downloads originally hashed and then streamed the shared file itself.
   Snapshot to a bounded private temporary file, verify identity and expected
   SHA, and stream the verified snapshot. A post-verification mutation of shared
   bytes must never replace the downloaded content. Limit concurrent snapshots
   and check disk reserve.
4. The UI initially ignored the runtime's actual `phase` field. Display the
   observed phase instead of an invented progress stage.
5. Generic error redaction initially also removed authored missing-field and
   unsupported-operation explanations. Expose only recognized contract errors'
   fixed safe hints and bounded field names; keep arbitrary exception text and
   credentials private.

Focused tests and final CI evidence, rather than this checklist, establish which
fixes have passed. Explicit owner-consented recovery is being wired through the
existing manager; no failed claim may be erased and no restart may auto-render.

The independent review found no additional admission bypass in the fixed-command
handoff, original approval binding, owner/CSRF boundary, PID identity, old global
GPU lease, claim preservation or fail-closed orphan detection. A Studio timeout
does not stop provider billing or immediately kill every independently detached
native process; the original coordinator retains its original approved deadline,
and active native state vetoes parallel resubmission. The operator still stops
the workload manually.

The product limitation remains explicit: interval visual/camera edits are not
implemented; interval SFX revisions recompose verified video without new GPU
rendering. Actual NVIDIA execution, real gCube proxy/mobile use, external Dropbox
synchronization and user video quality review remain unverified.
