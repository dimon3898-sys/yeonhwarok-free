# GCUBE T4 Codex-first diagnosis — evidence, not a speculative fix

## Finding

**Actual triggering rule: not established.** The available v003–v005 artifacts
contain the generic error but no actual T4 proxy header envelope or TCP peer.
The v005 proof explicitly records `actual_t4_raw_proxy_headers: UNAVAILABLE` and
`actual_gcube_deployment: NOT_RUN`. The existing HTTP logger suppresses request
logging, and its security error response does not identify the failed rule.

550 selected local repository/log/artifact files were inventoried, including
gitignored files. Nine text files referred to proxy/error diagnostics; zero JSON
records contained the actual request header/peer fields. Remote gcube Container
Logs and Deployment Events are unavailable in this session. They were not
silently treated as inspected. No actual gcube workload was accessed or changed.

The reported service authority `e.gcube.ai:24999` is accepted by v005; the
hostname/dynamic-port format alone does not reproduce this error. This does not
prove that gcube sends that same authority to the application.

## Exact error path and rejection inventory

`GcubePolicy.check_request` → `request_envelope` → `parse_forwarding` and its
helpers → `invalid_forwarding` → `SecurityError(INVALID_FORWARDED_HEADERS, 403)`.
The validator SHA-256 is
`b5e66d4ceee91c25eab4daa8a24339a67c89592ae25ba2dacdc68c6bdb2ede07`.
It is unchanged in the diagnostic image.

These are all 21 explicit call sites in `deployment/gcube/proxy.py` of v005:

| Function / line | Rejected condition | Diagnostic rule |
|---|---|---|
| list_header / 66 | More than 8 physical XFF/Forwarded fields; non-ASCII, disallowed controls, non-string, or field over 4096 characters | CHAIN_FIELD_BOUNDS_OR_CONTROL |
| list_header / 69 | Joined physical fields over 4096 characters | CHAIN_TOTAL_SIZE_LIMIT |
| split_quoted / 86 | Unclosed quote or escape | CHAIN_QUOTE_SYNTAX |
| split_quoted / 89 | Empty chain element or more than 32 elements | CHAIN_EMPTY_OR_TOO_MANY_ENTRIES |
| forwarded_value / 96 | Unclosed quoted parameter value | FORWARDED_UNCLOSED_QUOTED_VALUE |
| forwarded_value / 100 | Embedded quote/backslash in unquoted result | FORWARDED_ESCAPED_VALUE |
| forwarded_value / 102 | Invalid bare parameter token | FORWARDED_VALUE_TOKEN_SYNTAX |
| port_number / 108 | Non-decimal port, >5 digits, or outside 1–65535 | PORT_FORMAT_OR_RANGE |
| forwarded_ip / 128 | Invalid IP, scoped IPv6, invalid RFC node syntax; bare XFF/Envoy IP cannot have a port or brackets | IP_NODE_FORMAT (with header family) |
| parse_forwarding / 164 | X-Forwarded-Proto is present and not exactly https | X_FORWARDED_PROTO_NOT_HTTPS |
| parse_forwarding / 177 | Missing parameter '='; invalid name or duplicate name in a Forwarded element | FORWARDED_PARAMETER_SYNTAX_OR_DUPLICATE |
| parse_forwarding / 183 | RFC proto not absent/http/https | FORWARDED_PROTO_VALUE |
| parse_forwarding / 189 | XFF, Forwarded, or Envoy address present and actual TCP peer not loopback/exact own Pod address | FORWARDED_PEER_NOT_TRUSTED |
| parse_forwarding / 192 | First RFC element proto present and not https | FORWARDED_FIRST_PROTO_NOT_HTTPS |
| parse_forwarding / 194 | First RFC for differs from first normalized XFF entry | FORWARDED_FOR_XFF_DISAGREE |
| parse_forwarding / 197 | RFC first proto differs from X-Forwarded-Proto | FORWARDED_PROTO_HEADERS_DISAGREE |
| request_envelope / 215 | XFH and first RFC host resolve to different public origins | FORWARDED_HOST_HEADERS_DISAGREE |
| request_envelope / 222 | Public Host/candidate differ with untrusted peer, missing HTTPS, different hostname, or a conflicting external port | HOST_FORWARDED_AUTHORITY_DISAGREE |
| request_envelope / 229 | XFP port conflicts with supplied authority outside the constrained listener-port rewrite | X_FORWARDED_PORT_AUTHORITY_DISAGREE |
| request_envelope / 232 | External port reconstruction requires a trusted HTTPS proxy but lacks it | PORT_RECONSTRUCTION_PEER_OR_PROTO |
| request_envelope / 239 | Later RFC host is neither internal listener nor compatible same public authority | FORWARDED_LATER_HOST_DISAGREE |

Additionally, `RequestPolicy._single_header` at `deployment/security.py:294`
rejects physical duplicates, non-string, whitespace, or comma in Host, Origin,
XFH, XFProto, XFPort, and Envoy external address. Host/Origin violations have
their distinct INVALID_HOST/INVALID_ORIGIN codes; the other fields yield
INVALID_FORWARDED_HEADERS. The observer distinguishes duplicate vs other
single-field syntax and reports the fixed header name. Valid repeated XFF and
Forwarded physical fields instead use the bounded chain parser.

The shared `RequestPolicy.check_request` also has six forwarding rejection
branches (untrusted peer, missing/invalid proto or host, local-authority mismatch,
HTTPS mismatch, effective-host mismatch). These belong to local-mode/Codespaces
processing, not the normal gcube public path. Local development tests are kept.

Some inventory sites are redundant/unreachable under earlier checks; enumerating
them is not a claim that each could be the actual T4 failure. Origin mismatch
raises INVALID_ORIGIN, not INVALID_FORWARDED_HEADERS. Invalid provider authority
typically raises INVALID_HOST. Authentication happens after envelope validation.

## Official proxy behavior comparison

Reviewed official sources (HTTP 200; hashes stored in evidence):

- [Envoy HTTP connection manager headers](https://github.com/envoyproxy/envoy/blob/main/docs/root/configuration/http/http_conn_man/headers.rst): XFH can be appended on authority rewrite; XFPort can append/overwrite; XFProto can reflect the upstream HTTP hop when TLS terminates before Envoy, depending on trusted-hop settings. XFF depends on use_remote_address/xff_num_trusted_hops.
- [Istio network topology](https://istio.io/latest/docs/ops/configuration/traffic-management/network-topologies/): trusted client selection depends on gatewayTopology.numTrustedProxies and the actual intervening proxies.
- [Werkzeug ProxyFix](https://github.com/pallets/werkzeug/blob/main/src/werkzeug/middleware/proxy_fix.py): trust counts are explicitly configured per header and values selected from the right. The application is currently http.server, not WSGI. Switching frameworks would not establish the missing trusted topology and must not be used to trust every forwarded field.

Concrete *possible*, locally reproduced conflicts include comma-valued XFProto
or XFH, an internal HTTP proto, a valid XFF received from an untrusted bridge
peer, bare XFF addresses containing ports, authority/port disagreement, and RFC
first-node/XFF disagreement. **None is established as the actual gcube failure.**
IPv4, native IPv6, IPv4-mapped IPv6, bounded multiple XFF, and valid quoted RFC
IPv6 nodes pass under the documented v005 assumptions. IPv4-mapped loopback
`::ffff:127.0.0.6` is recognized as trusted in the tested Python runtime; there
is no evidence for calling it the cause.

## Minimal observation required

`gcube-v006-diag` overlays only a proxy observation server and its tests onto the
immutable public v005 digest. It uses the **same GcubePolicy/validator** and
port 8000. It neither runs GPU preflight nor the engine, a frame, nor a video.
Engine READY stays false; `/readyz` is 503; render/GPU/project routes are disabled.

The public rejection page retains the real error HTTP status and shows only
bounded structural diagnostics with `FAILED_VALIDATION_RULE`. Showing failure
metadata does not authorize login, origin binding or protected API access.
The successful diagnostic route still requires the owner code. The existing
owner/session implementation is reused with new private temporary state only.

Captured allowlist: Host, Origin, XFH, XFProto, XFPort, XFF, Forwarded, and Envoy
external address. It records physical counts, length/control/quote/comma shape,
typed/quoted IP entries, normalized numeric public ports, masked authority
patterns, and trusted-peer outcome. Per-process keyed IDs allow equality
comparison without exposing IPs or workload names. Known Envoy/Istio header
*names* may be listed; arbitrary names/values are not reflected. Owner code,
Cookie, Authorization, body, query, token, session and unknown values are never
captured or printed. Rate limiting bounds rejection logging.

The source hash and AST map fail closed if the validator changes. This observes
the exact first exception; it does not rewrite headers, return true, broaden
trust, admit software renderers or switch to CPU.

## Boundary before actual T4 use

No root-cause fix and no final v006 production image are claimed. One masked
request capture from real gcube is necessary to identify the first failing
rule and actual peer/header shape. Only then can a constrained correction be
designed. T4 NVIDIA Graphics Capability remains unverified; RTX3070's lack of
that capability is confirmed by the user's official support response.

Existing renderer/core/GPU/storage/UI/auth source and the old image publishing
workflow stay byte-for-byte unchanged. This standalone workflow publishes only
the new diagnostic tag. v001–v005 are never republished. No new T4 deployment or
GPU/video rendering is performed by this task.

## CI fixture correction before publication

The first diagnostic CI build succeeded but the regression step requested two
repository `tests.*` modules that the approved base `.dockerignore` excludes.
The publication gate stopped before login/push, so no incomplete image was
published. The test directory is now mounted read-only into the test container;
it is not added to the deployed image, and the base ignore file is unchanged.
Local regression was also verified under UID/GID 1000 (231 tests, one skip).
CI failure reports contain only test IDs, exception classes and source line
locations; exception values and request/auth data are omitted.

The expanded fresh-image suite additionally identified missing certification
data (also deliberately excluded by the base build) and legacy upload fixtures
which create temporary files inside root-owned source directories. The legacy
suite alone uses root and read-only mounts of the original test/certification
files. The diagnostic tests and deployed/HTTP-tested server still run as UID
1000; no deployed directory permission or engine source is changed.

The existing NativePersonalStorage foreign-replacement fixture also failed on
Docker overlayfs, while passing in the local UID1000 run: its check depends on
device/inode identity, which can be reused immediately after unlink/recreate.
The fresh-image legacy suite uses disposable tmpfs for its test fixtures to
avoid that inode-reuse ambiguity. **This is a test filesystem profile, not a
claim that the existing storage replacement check was fixed on overlayfs.**
The diagnostic server does not invoke NativePersonalStorage, accept uploads,
open projects or access existing storage. This pre-existing production storage
edge case is recorded and left unchanged under the user's scope restriction.
