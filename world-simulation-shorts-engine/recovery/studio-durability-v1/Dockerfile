# syntax=docker/dockerfile:1
# Additive wrapper only. The inherited renderer, GPU launcher and private
# filesystem policy are not modified. Never install into the parent Python.
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da
USER root
RUN test ! -e /opt/world-engine-studio-durability \
    && test ! -L /opt/world-engine-studio-durability \
    && test ! -e /opt/world-engine-studio-durability-venv
COPY extension/ /opt/world-engine-studio-durability/
# --without-pip avoids Debian ensurepip bootstrap changes. The inherited pip
# installs exclusively into the new venv, leaving the old interpreter intact.
RUN /usr/bin/python3 -m venv --system-site-packages --without-pip /opt/world-engine-studio-durability-venv \
    && /usr/bin/python3 -m pip --python /opt/world-engine-studio-durability-venv install \
       --no-cache-dir --only-binary=:all: \
       --requirement /opt/world-engine-studio-durability/requirements.txt \
    && find /opt/world-engine-studio-durability -type f -exec chmod 0444 {} \; \
    && /opt/world-engine-studio-durability-venv/bin/python -B \
       /opt/world-engine-studio-durability/manifest.py --verify
LABEL world-engine.studio-durability.version="1" \
      world-engine.studio-durability.parent-digest="sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da"
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["/opt/world-engine-studio-durability-venv/bin/python", "-B", "-c", "import urllib.request; r=urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:8080/healthz',timeout=3); raise SystemExit(0 if r.status==200 else 1)"]
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/opt/world-engine-studio-durability-venv/bin/python", "-B", "/opt/world-engine-studio-durability/bootstrap.py"]
CMD []
