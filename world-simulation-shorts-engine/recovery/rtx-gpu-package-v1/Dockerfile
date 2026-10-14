# syntax=docker/dockerfile:1
# Context is produced by stage_package.py; never build from the repository root.
FROM node@sha256:e5a8dee7bc1e6a215d224a7ef8206f7e77271bc3cabd5febf2beafac0674f174 AS npm
WORKDIR /opt/rtx-npm
COPY repo/cinematic-world-map/package.json repo/cinematic-world-map/package-lock.json ./
RUN --mount=type=secret,id=proxy_ca,required=false \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm ci --include=dev --ignore-scripts --strict-ssl=true

FROM ghcr.io/osgeo/gdal@sha256:c19fa2faa89895719a94d366cb600df9572bff1356d1eb60ab760af31df76d0e
USER root
WORKDIR /opt/rtx-package
COPY source_contract.json STAGING_RECEIPT.json ./
COPY repo/ ./repo/
COPY --from=npm /usr/local/bin/node /usr/local/bin/node
COPY --from=npm /opt/rtx-npm/node_modules ./repo/cinematic-world-map/node_modules

# Preserve the base's GDAL 3.10.3 Python stack. No apt python3-gdal or pip mix.
RUN --mount=type=secret,id=proxy_ca,required=false \
    set -eu; \
    rtx_ca_bundle=/etc/ssl/certs/ca-certificates.crt; \
    if [ -f /run/secrets/proxy_ca ]; then rtx_ca_bundle=/run/secrets/proxy_ca; fi; \
    apt-get -o Acquire::https::CaInfo="$rtx_ca_bundle" update; \
    xargs -r apt-get -o Acquire::https::CaInfo="$rtx_ca_bundle" install -y --no-install-recommends \
      < repo/world-simulation-shorts-engine/recovery/rtx-gpu-package-v1/native-packages.lock; \
    curl --fail --location --cacert "$rtx_ca_bundle" \
      https://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_155.0.8059.79-1_amd64.deb \
      --output /tmp/rtx-chrome.deb; \
    echo 'b7726070ca707965e9a17b38e4f15ba283bf6f65c339626c092862af7b19badc  /tmp/rtx-chrome.deb' | sha256sum --check --strict; \
    apt-get -o Acquire::https::CaInfo="$rtx_ca_bundle" install -y --no-install-recommends /tmp/rtx-chrome.deb; \
    ln -s /usr/bin/google-chrome-stable /usr/bin/chromium; \
    rm -f /tmp/rtx-chrome.deb /etc/apt/sources.list.d/google-chrome.list; \
    rm -rf /var/lib/apt/lists/*

RUN set -eu; \
    chmod -R a+rX /opt/rtx-package; \
    if getent passwd engine >/dev/null; then \
      test "$(id -u engine)" = 1000; \
    elif getent passwd 1000 >/dev/null; then \
      rtx_existing_user="$(getent passwd 1000 | cut -d: -f1)"; \
      usermod --login engine --home /home/engine --move-home "$rtx_existing_user"; \
    else \
      useradd --uid 1000 --create-home --home-dir /home/engine engine; \
    fi; \
    install -d -m 0700 -o 1000 -g "$(id -g engine)" /run/world-engine /world-storage/rtx-gpu-package-v1; \
    /usr/bin/python3 repo/world-simulation-shorts-engine/recovery/rtx-gpu-package-v1/stage_package.py \
      verify-context --package-root /opt/rtx-package; \
    /usr/bin/python3 repo/world-simulation-shorts-engine/recovery/rtx-gpu-package-v1/verify_dependencies.py \
      --repo-root /opt/rtx-package/repo \
      --contract repo/world-simulation-shorts-engine/recovery/rtx-gpu-package-v1/dependency_contract.json

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    NVIDIA_DRIVER_CAPABILITIES=graphics,utility \
    WORLD_ENGINE_RENDER_MODE=gpu-required \
    WORLD_ENGINE_CHROMIUM_REAL=/usr/bin/chromium \
    RTX_STORAGE_ROOT=/world-storage/rtx-gpu-package-v1
# Root bootstrap preserves provider device groups, then drops to engine UID1000.
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/usr/bin/python3", "/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/rtx-gpu-package-v1/bootstrap.py"]
CMD []
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD ["/usr/bin/python3", "-c", "import urllib.request; o=urllib.request.build_opener(urllib.request.ProxyHandler({})); r=o.open('http://127.0.0.1:8000/healthz',timeout=3); assert r.status==200"]
