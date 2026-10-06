# syntax=docker/dockerfile:1
FROM node:24-bookworm-slim AS node_deps
WORKDIR /opt/world-engine/cinematic-world-map
COPY cinematic-world-map/package.json cinematic-world-map/package-lock.json ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    npm ci --strict-ssl=true

FROM python:3.12-slim-bookworm
COPY --from=node_deps /usr/local/bin/node /usr/local/bin/node
COPY --from=node_deps /opt/world-engine/cinematic-world-map/node_modules /opt/world-engine/cinematic-world-map/node_modules
WORKDIR /opt/world-engine/world-simulation-shorts-engine
# Keep sources before the single large system-package layer for VFS compatibility.
COPY . /opt/world-engine
RUN --mount=type=secret,id=proxy_ca \
    apt-get update && apt-get install -y --no-install-recommends \
      chromium ffmpeg espeak-ng fonts-noto-cjk ca-certificates git tini \
    && rm -rf /var/lib/apt/lists/* \
    && if [ -f /run/secrets/proxy_ca ]; then \
      cat /etc/ssl/certs/ca-certificates.crt /run/secrets/proxy_ca > /tmp/build-ca.pem; \
      export PIP_CERT=/tmp/build-ca.pem; \
    fi \
    && pip install --no-cache-dir -r requirements.txt && rm -f /tmp/build-ca.pem \
    && useradd --uid 1000 --create-home engine \
    && chmod -R a+rX /opt/world-engine \
    && mkdir -p deployment/runtime cache assets/audio \
    && chown -R engine:engine deployment/runtime cache assets/audio
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 CHROMIUM_PATH=/usr/bin/chromium
USER engine
EXPOSE 7860
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "deployment.mobile_server", "--host", "0.0.0.0", "--port", "7860", "--internal-port", "7861", "--state-root", "deployment/runtime", "--access-file", "deployment/runtime/owner-code.txt"]
