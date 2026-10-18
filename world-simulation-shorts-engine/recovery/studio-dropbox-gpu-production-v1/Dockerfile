# syntax=docker/dockerfile:1
# Only an additive input adapter; no inherited file or dependency changes.
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:6d2e87fc8fb7f10edc2ebb7f77b5d666e329904b9c37f7f060b289f943bdd9d0
USER root
RUN test ! -e /opt/world-engine-studio-dropbox-gpu-production \
    && /opt/world-engine-studio-durability-venv/bin/python -B /opt/world-engine-studio-dropbox-offline/offline_manifest.py --verify
COPY extension/ /opt/world-engine-studio-dropbox-gpu-production/
RUN find /opt/world-engine-studio-dropbox-gpu-production -type f -exec chmod 0444 {} \; \
    && /opt/world-engine-studio-durability-venv/bin/python -B /opt/world-engine-studio-dropbox-gpu-production/production_manifest.py --verify
LABEL world-engine.studio-dropbox-gpu-production.version="1" \
      world-engine.studio-dropbox-gpu-production.parent-digest="sha256:6d2e87fc8fb7f10edc2ebb7f77b5d666e329904b9c37f7f060b289f943bdd9d0"
EXPOSE 8080
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/opt/world-engine-studio-durability-venv/bin/python", "-B", "/opt/world-engine-studio-dropbox-gpu-production/production_entry.py", "bootstrap"]
CMD []
