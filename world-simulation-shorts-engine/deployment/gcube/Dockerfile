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
# Sources precede the system-package layer to preserve the working VFS build pattern.
COPY . /opt/world-engine
RUN --mount=type=secret,id=proxy_ca \
    apt-get update && apt-get install -y --no-install-recommends \
      chromium ffmpeg espeak-ng fonts-noto-cjk ca-certificates git tini \
      libegl1 libgles2 libopengl0 libgl1 libglvnd0 libvulkan1 \
    && rm -rf /var/lib/apt/lists/* \
    && if [ -f /run/secrets/proxy_ca ]; then \
      cat /etc/ssl/certs/ca-certificates.crt /run/secrets/proxy_ca > /tmp/build-ca.pem; \
      export PIP_CERT=/tmp/build-ca.pem; \
    fi \
    && pip install --no-cache-dir -r requirements.txt && rm -f /tmp/build-ca.pem \
    && useradd --uid 1000 --create-home engine \
    && chmod -R a+rX /opt/world-engine \
    && chmod 0755 deployment/gcube/chromium_wrapper.py \
    && mkdir -p deployment/runtime cache assets/audio /data /world-storage /run/world-engine \
    && mv assets/audio assets/image_audio_seed \
    && rmdir cache \
    && ln -s /run/world-engine/cache cache \
    && ln -s /run/world-engine/audio assets/audio \
    && chmod 0700 /run/world-engine /data \
    && chown -R engine:engine deployment/runtime /run/world-engine /data
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 CHROMIUM_PATH=/usr/bin/chromium \
    NVIDIA_DRIVER_CAPABILITIES=graphics,utility
# Only vendor-neutral EGL/GLES/OpenGL/Vulkan loaders are installed above.
# Matching NVIDIA userspace driver libraries come from the provider's graphics
# runtime injection; no NVIDIA kernel driver/CUDA toolkit is baked into this image.
ENV WORLD_ENGINE_MAX_DURATION=180
# Bootstrap prepares storage and permanently drops to UID 1000 before serving.
# Device selection belongs to the provider's GPU allocation.
USER root
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD ["python", "-c", "import json,sys,urllib.request; opener=urllib.request.build_opener(urllib.request.ProxyHandler({})); response=opener.open('http://127.0.0.1:8000/healthz',timeout=3); value=json.loads(response.read(4096)); sys.exit(0 if response.status==200 and value.get('ok') is True and value.get('authentication_required') is True else 1)"]
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "python", "-m", "deployment.gcube.start"]
CMD []
