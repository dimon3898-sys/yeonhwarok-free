# World Engine login relay

`portal.py` is an isolated ASGI application. It serves its login page and health
endpoint before contacting any renderer provider, then relays the existing
authenticated mobile gateway. The engine, UI, rendering, and existing assets
remain under the existing gateway's control.

From `world-simulation-shorts-engine`:

```sh
python -m pip install -r deployment/one_url/requirements.txt
python -m unittest discover -s deployment/one_url -p 'test_portal.py' -v
```

The provider adapter supplies an idempotent `ensure()` method returning its
trusted **HTTPS origin**, with no path or query. The method can be synchronous or
asynchronous. It must return the public `MobileHandler` listener, which accepts
owner authentication; its private render listener is never suitable. The relay
serializes allocation and authentication and shares them between concurrent
requests. It checks the adapter again after 30 seconds of authenticated traffic.

Create `Portal(origin=..., owner_password=..., backend=..., session_key=...)`.
Load the password and signing key from the selected provider's secret store;
the password needs 16–512 characters and the signing key needs at least 32 bytes.
Do not place their values in source, logs, or command arguments. The same owner
password must configure the existing backend gateway. The front `origin` is one
fixed HTTPS address. No wildcard origins, caller-supplied backend URLs, or client
forwarding headers can change that address.

The front issues a host-only, Secure, HttpOnly, SameSite=Strict cookie with a
12-hour lifetime. Its signed claims work across front restarts when the origin,
password, and key stay fixed. Supply `revocation_store` with asynchronous
`contains(sid)` / `revoke(sid, expires)` for deployment. The Modal candidate uses
the separate control Volume; logout returns success only after its commit.
The local fallback uses process memory and must not be used as durable logout
protection. Both implementations have restart/replay regression tests; actual
provider persistence still requires live acceptance.
Login throttles are also bounded in-process state. The relay logs neither request
targets nor credentials. The backend cookie is retained only on the server.

Unauthenticated `/` redirects to `/auth/login`; `/api/health` and `/auth/session`
never call `ensure()`. Successful form or JSON login returns a 303 to `/` without
allocating. All POST requests require the exact configured Origin. Only existing
UI/static paths, project APIs, approved media/download paths, production defaults,
and job cancellation are forwarded. The backend still checks media ownership and
plan approval. Downloads stream through the relay, including Range and HEAD.
The relay rejects uploads above the existing gateway's 16 MiB limit before
allocation; its absolute buffer ceiling is 32 MiB. Ordinary JSON is bounded at
64 KiB. The candidate admits four concurrent front requests within a 512 MiB
memory limit. Existing gateway media ownership and format checks still apply.

For local tests only, a loopback front origin may set `allow_local_backend=True`
to connect to an HTTP backend on `localhost` or `127.0.0.1`. This override cannot
be enabled with a public front origin. HTTPS and exact proxy authority headers
remain mandatory for production backends. The front cookie always retains
Secure; HTTP test clients may need to supply that cookie explicitly.

The tests use a local ASGI transport and a mock HTTPS backend. They perform no
remote provisioning, billing, rendering, or publication. A provider adapter and
deployment must be separately configured and verified before a live URL exists.
