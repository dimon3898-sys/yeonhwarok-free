"""Dormant one-provider HTTPS deployment candidate.

Import performs no provider API calls. Building the App requires a current
operator-verified no-paid-overage budget. Live deployment needs Modal credentials
and is NOT performed by this module's import or by existing Codespaces startup.
Only <=20s acceptance jobs are enabled until provider restart tests pass.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import time

from deployment.one_url.budget import load_verified_budget

APP_NAME = 'world-engine-mobile'
SANDBOX_NAME = 'world-engine-owner'
APP_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = APP_ROOT.parent
REMOTE_APP = '/opt/world-engine/world-simulation-shorts-engine'


def build_app(budget_path=None):
    """Construct lazy SDK objects only; no signup, deployment or paid activation."""
    budget = load_verified_budget(budget_path or os.environ.get('WORLD_ONE_URL_BUDGET_FILE'))
    if budget.max_session_seconds < 300:
        raise ValueError('COMPUTE_LIFETIME_TOO_SHORT')
    import modal
    app = modal.App(APP_NAME)
    owner = modal.Secret.from_name('world-engine-owner')
    control = modal.Volume.from_name('world-engine-control-v1', create_if_missing=True)
    core_image = modal.Image.from_dockerfile(
        APP_ROOT / 'deployment/Dockerfile', context_dir=REPO_ROOT,
        ignore=modal.FilePatternMatcher.from_file(APP_ROOT / 'deployment/Dockerfile.dockerignore'))
    # Explicit base-image dependency hydrates the renderer Image at deployment,
    # before it is captured by the serialized broker. It performs no 3D work in
    # the front container; both images share the same approved source layers.
    front_image = (core_image
                   .pip_install('httpx==0.28.1', 'starlette==1.6.0')
                   .env({'PYTHONPATH': REMOTE_APP}))

    class ModalBackend:
        def __init__(self, control_state):
            self.lock = asyncio.Lock()
            self.last_touch = 0.0
            self.control_state = control_state

        async def ensure(self):
            # Portal authenticates BEFORE this method. A named singleton is also
            # enforced by the provider; local fcntl is not a distributed lock.
            async with self.lock:
                try:
                    sandbox = await modal.Sandbox.from_name.aio(APP_NAME, SANDBOX_NAME)
                except modal.exception.NotFoundError:
                    # These are lazy runtime dependencies of the Sandbox, not
                    # handles captured by the serialized front function. Only
                    # the isolated control Volume is mounted in the front.
                    runtime = modal.Volume.from_name('world-engine-runtime-v1', create_if_missing=True)
                    cache = modal.Volume.from_name('world-engine-cache-v1', create_if_missing=True)
                    generated_audio = modal.Volume.from_name('world-engine-audio-v1', create_if_missing=True)
                    await self.control_state.reserve(budget)
                    # Never refund an unsuccessful reservation automatically.
                    # Image/build/storage costs are covered by account-level
                    # no-paid-overage policy, not estimated compute alone.
                    # A slow control Volume commit must not move creation beyond
                    # the verified month's latest conservative admission time.
                    budget.require_available_session(0)
                    sandbox = await asyncio.wait_for(modal.Sandbox.create.aio(
                        'python', '-m', 'deployment.one_url.sandbox_boot',
                        app=app, name=SANDBOX_NAME, image=core_image,
                        secrets=[modal.Secret.from_dict({'WORLD_OWNER_PASSWORD': os.environ['WORLD_OWNER_PASSWORD']})],
                        workdir=REMOTE_APP,
                        cpu=(budget.cpu, budget.cpu),
                        memory=(budget.memory_mib, budget.memory_mib),
                        timeout=budget.max_session_seconds, idle_timeout=None,
                        encrypted_ports=[7860], gpu=None,
                        volumes={REMOTE_APP + '/deployment/runtime': runtime,
                                 REMOTE_APP + '/cache': cache,
                                 REMOTE_APP + '/assets/audio': generated_audio}), timeout=60)
                    tunnels = await sandbox.tunnels.aio()
                    origin = tunnels[7860].url
                    process = await sandbox.exec.aio(
                        'python', '-m', 'deployment.one_url.sandbox_boot',
                        '--configure-origin', origin, workdir=REMOTE_APP)
                    if await process.wait.aio() != 0:
                        raise ValueError('COMPUTE_CONFIGURATION_FAILED')
                tunnels = await sandbox.tunnels.aio()
                from deployment.one_url.sandbox_boot import trusted_tunnel
                origin = trusted_tunnel(tunnels[7860].url)
                if time.monotonic() - self.last_touch > 60:
                    p = await sandbox.exec.aio('python', '-m', 'deployment.one_url.sandbox_boot',
                                              '--touch', workdir=REMOTE_APP)
                    if await p.wait.aio() != 0:
                        raise ValueError('COMPUTE_HEARTBEAT_FAILED')
                    self.last_touch = time.monotonic()
                # HTTPS tunnel readiness is proved by the existing gateway,
                # bounded to 45s. No request log retains auth/cookie values.
                import httpx
                async with httpx.AsyncClient(timeout=3, follow_redirects=False) as client:
                    deadline = time.monotonic() + 45
                    while time.monotonic() < deadline:
                        try:
                            response = await client.get(origin + '/api/health')
                            if response.status_code == 200 and response.json().get('ok') is True:
                                return origin
                        except (httpx.HTTPError, ValueError):
                            pass
                        await asyncio.sleep(.5)
                raise ValueError('COMPUTE_NOT_READY')

    @app.function(image=front_image, cpu=(.25, .5), memory=(256, 512),
                  timeout=240, max_containers=1, scaledown_window=30,
                  secrets=[owner], volumes={'/control': control}, serialized=True, name='portal')
    @modal.concurrent(max_inputs=4)
    @modal.asgi_app(requires_proxy_auth=False)
    def portal():
        # get_web_url is provider metadata, never learned from request Host.
        from deployment.one_url.portal import Portal
        from deployment.one_url.control_state import ControlState
        origin = portal.get_web_url()
        if not origin:
            raise ValueError('DEPLOYED_HTTPS_URL_REQUIRED')
        state = ControlState('/control', reload=control.reload.aio, commit=control.commit.aio)
        return Portal(origin=origin, owner_password=os.environ['WORLD_OWNER_PASSWORD'],
                      session_key=os.environ['WORLD_PORTAL_SESSION_KEY'],
                      backend=ModalBackend(state), revocation_store=state)

    return app


# Operator CLI entrypoint. Leaving the budget variable unset blocks deployment
# before resources are constructed; old engine startup never imports this file.
if os.environ.get('WORLD_ONE_URL_BUDGET_FILE'):
    app = build_app()
