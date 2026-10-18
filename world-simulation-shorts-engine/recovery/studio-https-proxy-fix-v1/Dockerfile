# syntax=docker/dockerfile:1
# Frozen HTTPS21, Studio51 and V4 parent373 files are inherited unchanged.
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:468deaa122ec9c687908e2142d1a5cd82331a8bc447d62154eabb5ff7c416833
USER root
RUN test ! -e /opt/world-engine-studio-https-proxy-fix && test ! -L /opt/world-engine-studio-https-proxy-fix
COPY extension/ /opt/world-engine-studio-https-proxy-fix/
RUN find /opt/world-engine-studio-https-proxy-fix -type f -exec chmod 0444 {} \; \
    && /usr/bin/python3 -B /opt/world-engine-studio-https-proxy-fix/manifest.py --verify
LABEL world-engine.studio-proxy.version="1" \
      world-engine.studio-proxy.parent-digest="sha256:468deaa122ec9c687908e2142d1a5cd82331a8bc447d62154eabb5ff7c416833"
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["/usr/bin/python3", "-B", "-c", "import urllib.request; r=urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:8080/healthz', timeout=3); raise SystemExit(0 if r.status==200 else 1)"]
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/usr/bin/python3", "-B", "/opt/world-engine-studio-https-proxy-fix/proxy_bootstrap.py"]
CMD []
