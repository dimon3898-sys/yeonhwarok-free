# syntax=docker/dockerfile:1
# Completed V2 runtime, original sources and fixture layers remain immutable.
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:a956c93e4b23bc1f73990d94948c85e4db0c2f18f0bdef301f61ad7882be4886
USER root
RUN test ! -e /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-overnight-v3
COPY overnight/ /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-overnight-v3/
RUN find /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-overnight-v3 -type f -exec chmod 0444 {} \; \
    && find /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-overnight-v3 -type d -exec chmod 0555 {} \; \
    && /usr/bin/python3 -B /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-overnight-v3/package_manifest.py
LABEL world-engine.overnight.version="3" \
      world-engine.overnight.parent-digest="sha256:a956c93e4b23bc1f73990d94948c85e4db0c2f18f0bdef301f61ad7882be4886"
EXPOSE 8080
# The inherited 8080 healthcheck reports web-service readiness, never GPU proof.
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/usr/bin/python3", "-B", "/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-overnight-v3/bootstrap.py"]
CMD []
