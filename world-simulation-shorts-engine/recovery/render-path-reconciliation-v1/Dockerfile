# syntax=docker/dockerfile:1
# Additive preflight reconciliation. The frozen rendered source is unchanged.
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:7d45f95a7dd30a8e66a8cf6ef521e8ed38981e1fd07bd992eee4aea0ba78a645
USER root
RUN test ! -e /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/render-path-reconciliation-v1
COPY reconciliation/ /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/render-path-reconciliation-v1/
RUN find /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/render-path-reconciliation-v1 -type f -exec chmod 0444 {} \; \
    && find /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/render-path-reconciliation-v1 -type d -exec chmod 0555 {} \; \
    && /usr/bin/python3 -B /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/render-path-reconciliation-v1/package_manifest.py
LABEL world-engine.reconciliation.version="1" \
      world-engine.reconciliation.parent-digest="sha256:7d45f95a7dd30a8e66a8cf6ef521e8ed38981e1fd07bd992eee4aea0ba78a645"
EXPOSE 8080
# Keep the inherited service-only healthcheck; never a claim of GPU readiness.
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/usr/bin/python3", "-B", "/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/render-path-reconciliation-v1/bootstrap.py"]
CMD []
