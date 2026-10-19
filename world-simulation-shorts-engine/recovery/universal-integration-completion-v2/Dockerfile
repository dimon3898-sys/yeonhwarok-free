# syntax=docker/dockerfile:1
# Existing GPU/Studio/source layers are immutable and inherited byte-for-byte.
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da
USER root
RUN test ! -e /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-integration-v1 \
    && test ! -e /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-integration-completion-v2
COPY integration/ /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-integration-v1/
COPY completion/ /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-integration-completion-v2/
RUN find /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-integration-v1 \
         /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-integration-completion-v2 \
         -type f -exec chmod 0444 {} \; \
    && find /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-integration-v1 \
            /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-integration-completion-v2 \
            -type d -exec chmod 0555 {} \; \
    && /usr/bin/python3 -B /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-integration-completion-v2/package_manifest.py
LABEL world-engine.completion.version="2" \
      world-engine.completion.parent-digest="sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da"
EXPOSE 8080
# Reuse the existing inherited 8080 healthcheck; it never reports GPU success.
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/usr/bin/python3", "-B", "/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/universal-integration-completion-v2/bootstrap.py"]
CMD []
