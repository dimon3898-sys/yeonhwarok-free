# Modal free-runtime review

Verified 2026-10-06 16:35:17 KST from current official `modal-labs` GitHub sources. Read-only research; no provider login, token, deployment, render or paid activation.

Modal is a credible compute-platform candidate for the existing engine: a deployed ASGI app supplies the mobile URL, a bounded CPU function or Sandbox runs FFmpeg/Chromium work, and a Volume preserves files. The free-cost admission and billing conditions remain unverified.

## Free account and credits: evidence strength

- [Official examples README](https://github.com/modal-labs/modal-examples/blob/main/README.md#L12) says “First, sign up for a free account”. It requires an API key.
- [Current Discord bot example](https://github.com/modal-labs/modal-examples/blob/main/07_web/discord_bot.py#L248) says “Modal's $30/month of credits on the free tier.” This is official example commentary fetched today, not independent verification of the current pricing contract, eligibility for this account, no-card admission, or a credit-exhaustion hard stop.
- [Current embeddings example](https://github.com/modal-labs/modal-examples/blob/main/06_gpu_and_ml/embeddings/amazon_embeddings.py#L177) names “Starter (free)”.
- Current pricing, no-card requirements, credit renewal/account entitlement, overage blocking, retained-volume charges and unit prices could not be verified from the available official sources. Native Modal access is blocked under the parent session's network policy; no bypass was attempted.

## Deployment behavior

- [Official web example](https://github.com/modal-labs/modal-examples/blob/main/07_web/basic_web.py#L59) distinguishes temporary `modal serve` from persistent `modal deploy`; the latter remains available after closing the terminal/computer. The example `.modal.run` address is not an actual deployed WorldEngine URL.
- The same example warns that `requires_proxy_auth=True` produces HTTP401 in a normal browser. The mobile entry should reach the existing app owner login with app authentication and CSRF protection, without Modal workspace proxy headers on that page.
- [Official SDK](https://github.com/modal-labs/modal-client/blob/main/py/modal/_functions.py#L2209) supports `Function.spawn()` followed by polling. [An official example](https://github.com/modal-labs/modal-examples/blob/main/06_gpu_and_ml/embeddings/amazon_embeddings.py#L199) configures two hours. Function and Sandbox default to 300 seconds; set an explicit bounded render timeout. Universal maximum runtime was not verified.
- [Sandbox SDK](https://github.com/modal-labs/modal-client/blob/main/py/modal/sandbox.py#L686) accepts CPU request/limit, memory request/limit in MiB, Secrets, Volume mounts and TLS encrypted ports. `cpu=(2,2)` and `memory=(8192,8192)` configure the intended limits; actual Starter resource admission and render performance remain untested.
- A named Sandbox can be looked up under a deployed app. Its tunnel metadata maps container ports to URLs, but replacement-stable tunnel addresses are not established. Keep the single mobile URL on a persistently deployed ASGI broker.
- [Volume SDK](https://github.com/modal-labs/modal-client/blob/main/py/modal/volume.py#L485) supports durable state, explicit `commit()` and `reload()`. Concurrent writes to the same file lose data; use one active render owner and separate job directories. Reload requires closed files. Storage free allowance/current price is unverified.
- [Official Modal SDK skill](https://github.com/modal-labs/modal-client/blob/main/py/modal/skills/modal/SKILL.md) states that executing Modal code requires network and an authorization token, with no local development mode. Local adapter tests are not provider validation.

## Conditional route and remaining external step

Prepare the deployment adapter independently: persistent ASGI gateway → owner login → topic/plan/approval → bounded function or Sandbox → Volume state/output → authenticated HTTPS download. Keep the approved engine core and assets unchanged. Use one active job, explicit timeouts, no always-warm containers by default, and exact retention cleanup.

Actual activation requires a user-authorized Modal account/token and allowed provider connectivity. Before activation, the actual account must confirm Starter/free-credit eligibility, no-card admission and an enforceable zero-paid billing stop. Without those conditions, this report does not claim a zero-cost production host.

## Hugging Face ZeroGPU comparison

The current HF official overview requires a paid plan to create ordinary Docker or Gradio compute Spaces. Its free exception is up to two Gradio ZeroGPU Spaces for a free personal account in good standing; current ZeroGPU requirements include verified email and account age over 30 days. ZeroGPU supports only the Gradio SDK; Python3.12.12 is listed. No general CPU-only prohibition was found, but the reviewed documentation does not affirm long CPU-only rendering eligibility or exact CPU/RAM allocation. Fake GPU calls must not be added to force qualification. Full source metadata is in `/tmp/free_mobile_stable_url_research_20261006/REPORT.json`.

The companion `REPORT.json` contains 11 primary official sources, 25 exact quotation ranges, HTTP timestamps, downloaded-byte counts and SHA256 checks. SHA256 identifies downloaded source bytes, not a repository commit.
