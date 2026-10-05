# Read-only public tunnel feasibility probe

Official GitHub release retrieval is reachable: latest redirects to **2026.9.3**. The Linux amd64 binary has **40,122,749 bytes**; a constrained metadata GET read one byte into `/dev/null`, without saving or installing the binary.

The QuickTunnel control address `https://api.trycloudflare.com/tunnel` failed **before reaching the origin**: proxy CONNECT **403**, curl exit **56**, curl-reported HTTP **000**. This is an observed connection denial, not an inference from an unknown policy state. No alternative tunnel service or proxy bypass was attempted.

The exact release's official `quick_tunnel.go` states account-less tunnels are experimental, have no uptime guarantee, and should not be used for production. It implements tunnel creation with POST. This audit used GET only and never provisioned a tunnel. Other service limits were not independently verified here.

`PROBE_REPORT.json` records precise UTC timestamps for the final two probes, safe HTTP/header subsets, the prior official-source GET timestamp, SHA checks, and the previous public GitHub artifact verification. Public downloadable GitHub MP4 files and a publicly reachable interactive rendering app are separate outcomes; the latter remains unverified. No physical-phone validation is claimed.

Only these new evidence files were written. No source/test/server/Git changes, credential disclosure, package installation, tunnel startup, public-port opening, or rendering occurred.
