# Cache and recovery verification

Final integrated evidence contains **62 passing cache cases** (`evidence/ALL_TEST_RESULTS.json`). Earlier E58 evidence is preserved as the actual pre-hardening checkpoint, not counted twice.

`CacheRequest` binds provider, version, W/S/E/N bbox, CRS, resolution intent, raw SHA, transform identity, source-metadata SHA, optional URL hash/range/ETag/object length. Derived metadata SHA includes source catalog, vertical datum, attribution and exact PGW/PRJ hashes. The composed provider additionally binds the whole request bbox so date-line parts cannot reuse another request's aggregate coverage. Parser/source code SHA automatically versions transforms. A changed version or changed auxiliary metadata selects a separate key.

`FileCache` maintains immutable content-addressed raw/derived blobs and atomic fsync-published lookups. Derived neutral data retains source dtype, signed values, axes and invalid cells; no GPU layout is assigned. Every hit rechecks identity, size, SHA and receipt claims. Failure/partial data cannot be registered as a successful artifact. Changed derived output cannot replace the same identity. Corruption is rejected explicitly, never silently overwritten. Empty raw bytes may be a valid exact byte artifact; a parsed provider still validates the source format.

| Focused behavior | Actual evidence | Result |
|---|---|---|
| Identical cache request reuse | Repeated raw producer, real provider hit without archive read/parsing | PASS |
| Duplicate work prevention | Shared-instance threads, independent caches, four fresh processes; producer count one | PASS |
| Default concurrency cap | Four processes sharing two request slots; observed maximum two | PASS |
| Atomic publication failure | Publication failure leaves prior hit intact and cleans pending artifacts | PASS |
| Failed requests/retry bounds | Mock 429/5xx/timeouts, global retry budget and deadline; terminal/auth errors explicit | PASS |
| Restart/resume | Fresh process restores individually SHA-verified 206 chunks with stable strong ETag/object size | PASS |
| Bad ranges/changed objects | Range200, wrong Content-Range/length/compression/ETag rejected; no append | PASS |
| Corruption | Bad blob/receipt/oversized state, invalid neutral metadata, FIFO/nonregular files rejected | PASS |
| Version/metadata isolation | Source version, raw hash, sidecar/datum and parser identity changes | PASS |
| Fork/recursion safety | Inherited lock state reset; recursive producer fails instead of deadlocking | PASS |
| Read-only initialization | `FileCache(..., create=False)` changes no absent/incomplete directories; existing hits remain readable | PASS |
| Export protection | Identical CLI output is not rewritten; conflicting output and input/cache aliases rejected; atomic create-if-absent publication reused | PASS |

`DownloadManager` defaults network off, maxConcurrency2, timeout10s, deadline30s, maxRetries2, Retry-After ceiling10s, bounded chunks/artifacts. HTTPS requires an explicit allowed host and retains system proxy/CA trust. Redirects and reads remain bounded; no TLS bypass or rate-limit bypass. Unknown artifact hashes are labeled self-computed, not supplier-certified. Pinned content reuse does not claim an unobserved ETag.

All HTTP responses here are injected/mock/local protocol fixtures. Live vendor transport: **BLOCKED / NOT EXECUTED**. Saved raw/neutral examples are permanent; a mutable cache is replaceable and no required `/tmp` path exists.
