# syntax=docker/dockerfile:1
# Additive OAuth credential adapter only. No dependency installation or
# modification of the inherited encrypted vault, Studio, renderer or cache.
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:54e7f67627a14755117a3f232c03785f9ceac4ab490a33e8f5834fb9fe114b9b
USER root
RUN test ! -e /opt/world-engine-studio-dropbox-offline \
    && test ! -L /opt/world-engine-studio-dropbox-offline \
    && test -x /opt/world-engine-studio-durability-venv/bin/python \
    && /opt/world-engine-studio-durability-venv/bin/python -B \
       /opt/world-engine-studio-durability/manifest.py --verify
COPY extension/ /opt/world-engine-studio-dropbox-offline/
RUN find /opt/world-engine-studio-dropbox-offline -type f -exec chmod 0444 {} \; \
    && /opt/world-engine-studio-durability-venv/bin/python -B \
       /opt/world-engine-studio-dropbox-offline/offline_manifest.py --verify
LABEL world-engine.studio-dropbox-offline.version="1" \
      world-engine.studio-dropbox-offline.parent-digest="sha256:54e7f67627a14755117a3f232c03785f9ceac4ab490a33e8f5834fb9fe114b9b"
EXPOSE 8080
# Keep the immutable parent's existing health check and restore start grace.
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/opt/world-engine-studio-durability-venv/bin/python", "-B", "/opt/world-engine-studio-dropbox-offline/offline_entry.py", "bootstrap"]
CMD []
