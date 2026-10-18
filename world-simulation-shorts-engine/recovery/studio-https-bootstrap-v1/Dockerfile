# syntax=docker/dockerfile:1
# The existing Studio51 and V4 parent373 are inherited without modification.
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:5a35e44947aaed3fffe39aad2352ff17c22b9375b4591e635129feed4ec90d94
USER root
RUN test ! -e /opt/world-engine-studio-https-bootstrap && test ! -L /opt/world-engine-studio-https-bootstrap
COPY extension/ /opt/world-engine-studio-https-bootstrap/
RUN find /opt/world-engine-studio-https-bootstrap -type f -exec chmod 0444 {} \; \
    && /usr/bin/python3 -B /opt/world-engine-studio-https-bootstrap/manifest.py --verify
LABEL world-engine.studio-https.version="1" \
      world-engine.studio-https.parent-digest="sha256:5a35e44947aaed3fffe39aad2352ff17c22b9375b4591e635129feed4ec90d94"
EXPOSE 8080
# Service availability is independent of GPU admission. This endpoint never
# reports renderAllowed=true merely because the setup web service is alive.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["/usr/bin/python3", "-B", "-c", "import urllib.request; r=urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:8080/healthz', timeout=3); raise SystemExit(0 if r.status==200 else 1)"]
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/usr/bin/python3", "-B", "/opt/world-engine-studio-https-bootstrap/https_bootstrap.py"]
CMD []
