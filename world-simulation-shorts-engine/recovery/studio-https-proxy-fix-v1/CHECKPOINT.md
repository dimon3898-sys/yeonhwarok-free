# HTTPS proxy compatibility checkpoint

The authenticated read-only probe at 2026-10-18 10:01 KST found workload5373 in finish/Terminating; its exact user-confirmed service URL returned404. Neither historical incoming Host/Forwarded/XFP/XFH nor container exit code was available. These values are not guessed. No workload was started, redeployed, updated or stopped.

A separate code-level defect is reproduced: the frozen fixed-origin policy accepts an absent X-Forwarded-Proto, but rejects a single http value even when the external HTTPS authority and mutation Origin exactly match independently configured/owner-confirmed values. A TLS edge and its inner HTTP transport are different concepts; this advisory header is not proof of browser TLS and never grants trusted authority.

This additive candidate permits only that single transport case after exact external Host/XFH validation and rechecks the entire unchanged original policy. Duplicate/chain protocols, wrong Host/XFH/Origin, missing mutation Origin, unconfirmed origins, CSRF/authentication failures remain blocked. Arbitrary internal Host rewriting and origin learning from Forwarded are not implemented. Forwarded remains non-authoritative as in the original.

The inherited authenticated setup core and normal Studio handler are reused. New private-state setup preserves the owner credential and existing records. The original supervisor remains responsible for UID/GID1000, source/policy/private-state checks, the GPU process and shutdown; the new bootstrap substitutes only the exact UI child entrypoint. GPU jobs are never automatically started. Policy/GPU admission remains unchanged.

New bounded request diagnostics publish only error enums, header counts, protocol/fetch-site classifications and known-origin comparison booleans. No raw headers, cookies, paths, query strings, body, credentials or actual URL/IP are logged. This allows a later approved live execution to identify a different rejection instead of speculating.

Local verification: targeted compatibility/security and actual TLS mobile Chromium pass. These are controlled proxy fixtures, not the stopped gCube service. Free CI must also run the actual immutable-base CPU entrypoint, mobile flow, source verification, Secret Scan, unique-tag build/push and independent digest pull before this candidate is submitted. Old HTTPS21, Studio51, engine373 and FINAL are protected.

A candidate cannot be called the proven fix for the user's actual historical header failure until a live request confirms its incoming header classifications and authenticated registration/login. No paid GPU operation is authorized in this task.
