# Secure execution prerequisites

This is a saved configuration draft, not an applied connection or execution approval.
The current environment status observed on 2026-10-16 has no configured gCube
secret, runtime variable, outbound identity or TCP grant. The network policy is
configured restricted; its reported enforcement state is unknown. An actual
inherited-proxy request to the official history site returned HTTP tunnel403.

The supported cloud environment draft added these HTTPS destinations while
retaining the existing package-manager preset:

- history.state.gov
- history.army.mil
- www.history.navy.mil
- api.gcube.ai
- api.github.com (direct Actions status reads; current CONNECT403)

Non-secret account selectors GCUBE_EMAIL and GCUBE_WORKLOAD_SER are declared.
It also declares GCUBE_API_TOKEN as a secret used only at api.gcube.ai. No token
value was read, printed or written. The draft save succeeded and requires review,
save and Publish in environment settings before its application can be verified.
Do not paste credentials in chat, GitHub, Scene JSON or result folders.

Authenticated gCube account reads additionally need a non-secret account email
selector and real API authorization. Any future SSH execution needs a separately
approved secret-file selector, known-host verification, endpoint and explicit TCP
access; a proxy-injected HTTPS placeholder is not an SSH private key.

Official evidence does not establish a provider-enforced cumulative monetary
cap. Rendering timeout does not stop GPU billing. No deploy/start may execute
through the automated adapter while strict budget enforcement is unsupported.
Read-only workload/pricing/schedule/account checks and a safe plan can be prepared;
mock results are not current account verification. A stop response alone does
not prove that billing ceased. Actual stopped state and account records need
independent observation.

No paid GPU deployment, automatic paid retry or FINAL promotion is authorized.
