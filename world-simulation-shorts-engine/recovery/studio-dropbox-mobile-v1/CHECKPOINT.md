# Mobile Dropbox connection checkpoint

Protected parent: `5b0478f0aafeb03f4a05ae47f41dcbd154712ee1`.
Branch: `development/dropbox-mobile-connect-v1-20261018`.

This additive candidate replaces the user-facing PC/terminal enrollment with a
browser-only PKCE consent page. Existing refresh, encrypted backup, recovery,
FINAL/Candidate namespaces and existing website remain unchanged.

Only PKCE verifier/state may enter short-lived browser session storage. Dropbox
refresh/access tokens, GitHub authorization, app secret and recovery key remain
in memory or their approved Secret destination. GitHub Secret uploads are sealed
to the repository public key in the browser. No credential enters a URL, public
log, chat, source or workflow input.

Account consent and repository Secret-write authorization remain mandatory.
Existing platform GitHub access cannot be treated as Secret-write permission.
An existing unrelated Pages site must never be replaced with this candidate.
No paid GPU deployment or rendering is performed.

Resume: complete independent web core/UI, pinned crypto vendor, CPU/mobile
tests, safe HTTPS hosting permission check, source/Secret scan, remote save.
Actual Dropbox proof is performed only after the owner completes real consent.
