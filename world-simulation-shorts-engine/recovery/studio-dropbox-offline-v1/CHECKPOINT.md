# Dropbox offline authentication checkpoint

Protected parent: `165a3489eede6e6f66c20f2d6ca1d70fd8c79560` and immutable
durability image `sha256:54e7f67627a14755117a3f232c03785f9ceac4ab490a33e8f5834fb9fe114b9b`.

This independent namespace adds OAuth offline credential refresh only. The
existing App Folder prefix, encrypted objects, receipt catalog, scene/cache
backup barriers, fresh-root restore, claims, GPU admission, cost/time checks,
owner/Origin/CSRF and all FINAL/Candidate source remain unchanged.

Refresh/app credentials and the existing recovery key are supplied only through
approved Secrets/private files. Access tokens remain in memory, with bounded
refresh before expiry and at most one authentication retry on HTTP 401.
Authentication failure never advances the next scene. There is no static-token
fallback for a misconfigured offline profile and no automatic GPU execution.

Resume here: focused CPU authentication/runtime tests, protected-source check,
secret scan, additive candidate packaging and final user configuration guide.
Actual Dropbox authorization and persistence require user setup and remain
unverified until real API evidence exists.
