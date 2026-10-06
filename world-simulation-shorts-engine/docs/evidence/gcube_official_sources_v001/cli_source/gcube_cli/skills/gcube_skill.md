---
name: gcube
description: >
  Manage GCube AI GPU Cloud resources with the gcube CLI — workloads, teams,
  GPUs, storage, credentials, points, and resource monitoring.
  Use when the user wants to deploy containerized AI/ML workloads on GPU
  infrastructure, check GPU availability and pricing, monitor deployments,
  stream logs, SSH into running containers, manage registry credentials,
  work with shared team workloads, or check point balance — even if they
  don't explicitly mention gcube.
license: proprietary
compatibility: Requires gcube CLI installed and authenticated (gcube auth login)
metadata:
  author: gcube
  version: "1.0"
---

# gcube CLI

gcube is the command-line tool for managing AI/ML workloads on GCube GPU Cloud. All commands require authentication and a configured platform URL.

## Authentication & Setup

1. Log in (opens browser for PKCE authentication):

```bash
gcube auth login
```

2. Verify your session:

```bash
gcube auth status
```

3. Check your configuration:

```bash
gcube config status
```

4. Set configuration values if needed:

```bash
gcube config set --platform-url https://api.gcube.ai
gcube config set --email user@example.com
```

Configuration is stored in `~/.gcube/config.yaml` (YAML format). Authentication tokens are stored inside this file under `auth.access_token` in plaintext — do not share or commit it to version control.

## Agent Workflow (for AI agents using gcube)

Rules that govern *how* to use this skill. These override the command reference below.

| Situation | Do | Don't |
|---|---|---|
| User wants to deploy a workload | Walk through: `gpu list` -> pick GPU -> `workload register` -> `workload start`. Show the GPU code and estimated hourly cost before proceeding. | Skip GPU selection or register without confirming the GPU spec. |
| Choosing a GPU | Run `gcube gpu list`, show the table with CODE, TIER, and PRICE. Explain tier trade-offs (tier1=stable but slow deploy, tier2=balanced, tier3=cheap but may interrupt). Let user pick by CODE. | Guess GPU codes. Never use GPU_NAME as `gpuCode`. Never recommend tier3 without warning about interruption risk. |
| Missing required input (image, GPU, description) | Ask the user with specific options from real CLI output. | Invent defaults or guess values. |
| Complex workload config (multi-container, env vars, storage mounts) | Use YAML workflow: `gcube workload register --skeleton > workload.yaml`, edit it, then `gcube workload register -f workload.yaml`. | Try to pass everything as inline flags — inline flags only support single-container / single-GPU; multi-container, env vars, storage mounts, and Istio options require structured YAML. |
| Simple single-container workload | Use inline flags: `gcube workload register --image <img> --gpu <code> --description <desc>`. | Force YAML for trivial cases. |
| `workload register` or `workload start` | Show the full command, GPU spec, and estimated hourly cost from `gpu list`; wait for user approval before running. | Run on first mention without confirmation. |
| `workload stop`, `workload delete`, or `credential delete` | Always confirm with the user before running. These are destructive operations. Deleting a credential may cause running workloads that reference it to fail on image re-pull. | Run without confirmation, especially in bulk. |
| Checking workload status | Use `workload describe SER` for details, `workload list` for overview. The STATE column shows the operational phase; the TEAM column (when present) shows which team owns the row. | Rely only on `list` — it doesn't show service URL, pods, or container details. |
| Monitoring a deployment | Use `workload start SER` to start + monitor (SSE). If the workload was already started (e.g. via web console), use `workload watch SER` to attach to the ongoing deployment. | Poll `workload describe` in a loop — use the built-in SSE watcher instead. |
| Streaming logs | Use `gcube workload logs SER`. For multi-pod/container workloads, specify `--pod` and `--container` indices. | Try to SSH in just to read logs. |
| Accessing a running container | Use `gcube workload ssh SER` for interactive shell access. Supports running one-off commands: `gcube workload ssh SER -- <command>`. | Assume SSH is always available — it only works when the workload is running. |
| Private container image | Register a credential first with `gcube credential create`, then pass `--credential` flag during `workload register`. | Attempt to register a workload with a private image without credentials. |
| Storage mounts | Run `gcube storage list` to get MOUNT KEY values. Use YAML to configure `userStorages`. For gcube built-in storage, use the literal key `gcube`. | Guess mount keys or bucket IDs. |
| Image verification fails | The CLI will prompt. Use `-y` to proceed anyway, but warn the user the image may not work. | Silently pass `-y` without informing the user. |
| Scheduling auto start/stop | Use `gcube workload schedule SER --days Mon-Fri --start 09:00 --stop 18:00` for simple cases. For complex schedules (one-time, mixed days, disabled entries), use YAML: `gcube workload schedule SER -f schedule.yaml`. | Forget that `-f` is full replacement — all entries must be in the file. Inline `--days/--start/--stop` appends safely. |
| Checking schedule execution history | Use `gcube workload schedule SER --logs`. Use `--limit N` to fetch more entries (default 20). | Poll `workload describe` to infer whether a schedule ran — use `--logs` instead. |
| Checking point spending per workload | Use `gcube point spending --workload SER` to see daily cost breakdown for a specific workload. Use `gcube point status` for overall balance. | Guess the cost — always look it up. |
| User mentions a team, or shared/our workloads | Run `gcube team list` to get the numeric ID, then pass `--team ID`. Team names are not unique, so the ID is the only safe identifier. | Pass a team name to `--team`. Guess the ID. |
| Registering into a team | Confirm the team name and ID with the user, then run `gcube workload register ... --team ID`. The CLI prints `Creating in team context: ID N` to stderr — surface it. | Rely on an inherited `GCUBE_TEAM` env var without telling the user which team it points at. |
| Workloads seem to be missing | `workload list` already returns personal + all teams. Narrow with `--team ID` or `--personal` instead of assuming data is lost. | Conclude a workload was deleted before checking `--team`. |
| Adding or removing team members | Direct the user to the web console. Member management is not in the CLI. | Look for a `gcube team invite` command — it does not exist. |
| Unknown error | Check `gcube auth status` (token expired?), then `gcube config status` (wrong URL?). | Retry the same command blindly. |

### Red flags — STOP

- About to run `workload stop`, `workload delete`, or `credential delete` without user confirmation -> ask first.
- About to use a GPU name (like "A100") as `--gpu` value -> use the CODE from `gpu list` instead.
- About to `workload register` without showing the command and cost -> propose it first.
- About to guess a `gpuCode`, `MOUNT KEY`, or credential -> look it up with the appropriate list command.
- About to run bare `gcube config` -> this launches interactive setup that hangs in non-interactive environments. Use `gcube config set --<key> <value>` or `gcube config status` instead.
- About to pass a team name to `--team` -> it takes a numeric ID. Look it up with `gcube team list`.
- About to `workload register --team` without naming the team to the user -> the workload's ownership and billing go to that team. Confirm first.

## Workload Management

Workloads are containerized AI/ML services deployed on GPU infrastructure. Each workload is identified by a **SER** — a numeric ID assigned at registration (e.g. `4436`). All workload commands take SER as their argument.

### Deployment workflow

1. Pick a GPU spec:

```bash
gcube gpu list
```

Output columns: CODE, GPU_NAME, TIER, GPUs, VRAM(GB), CPU(Core), MEM(GB), DISK(GB), PRICE/HR(KRW).

2. Register a workload (simple):

```bash
gcube workload register \
  --image pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime \
  --gpu 029 \
  --description "My inference service"
```

2-alt. Register a workload (YAML for full control):

```bash
# Generate a template
gcube workload register --skeleton > workload.yaml
# Edit the YAML, then:
gcube workload register -f workload.yaml
```

3. Start the workload (includes real-time deployment monitoring via SSE):

```bash
gcube workload start SER
```

The CLI streams deployment events in a live dashboard. Use `--plain` for piped/scripted output, `--no-watch` to skip monitoring, `--timeout N` to limit wait time.

4. Check status and get the service URL:

```bash
gcube workload describe SER
```

The service URL appears in the output once the workload reaches `running` state.

5. Stream container logs:

```bash
gcube workload logs SER
```

6. SSH into the running container:

```bash
gcube workload ssh SER
# Or run a one-off command:
gcube workload ssh SER -- nvidia-smi
```

7. Stop when done:

```bash
gcube workload stop SER
```

### Workload commands reference

```bash
gcube workload list                     # List your workloads (personal + all teams)
gcube workload list --all               # List ALL workloads on the platform (admin only)
gcube workload list --team 6            # Only team 6's workloads
gcube workload list --personal          # Only personal workloads
gcube workload list --owner user@co.kr  # Filter by owner
gcube workload describe SER             # Show workload details (state, GPU, URL, pods)
gcube workload register ...             # Register a new workload (see above)
gcube workload register ... --team 6    # Register under team 6
gcube workload update SER               # Update a stopped workload
gcube workload update SER --skeleton    # Export current config as editable YAML
gcube workload start SER                # Start and monitor deployment
gcube workload watch SER                # Monitor an already-started deployment
gcube workload stop SER                 # Stop a running workload
gcube workload delete SER               # Delete a workload permanently
gcube workload pods SER                 # List pods for a workload
gcube workload logs SER                 # Stream container logs
gcube workload ssh SER                  # SSH into running container
gcube workload schedule SER             # Show current schedules
gcube workload schedule SER --logs      # Show schedule execution history
gcube workload unschedule SER           # Remove all schedules
```

Output columns: SER, DESCRIPTION, GPU, STATE — with **TEAM** inserted after
DESCRIPTION when the result contains a team workload (personal rows show `-`).
Category is not a column; `describe` and `-o json` still carry it.

### Workload fields guide

Each field below corresponds to the web console's workload creation wizard. The guidance text (from the web console's tooltips) helps agents understand what each field means and how to configure it correctly.

#### Step 1: Basic Settings

**description** (required)
- Enter a name or description to identify the workload. Used for identification in the workload list.
- 2-80 characters.

#### Step 2: Container Settings

**repo** (required)
- Select the container registry where the image is stored. Private registries require credential authentication.
- Options: `docker.io` (Docker Hub), `ghcr.io` (GitHub), `nvcr.io` (NVIDIA), `quay.io` (Red Hat Quay), `registry.hf.space` (Hugging Face).
- Private registries require credentials registered via `gcube credential create`. The CLI auto-detects saved credentials matching the repo and sets `isCredential` automatically. Use `--credential`/`--no-credential` (inline) or explicit `isCredential: true/false` (YAML) to override auto-detection.

**containerImage** (required)
- Enter the full path of the container image to deploy and verify its accessibility.
- Example: `sbison/sdxl-web-auto1111:12`, `pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime`
- The CLI verifies the image before registration. Verification has 3 states:
  - **success**: Image verified and accessible.
  - **fail**: Verification failed — check repo type, image URL, and credentials.
  - **unverified**: Verification timed out — proceed with `-y` if confident the image exists.

**port** (optional for inline `--port`; defaults to 0 = auto-detect)
- The port number the container exposes externally.
- **Port 0 = auto-detect:** When set to 0 (YAML default), the platform inspects the image's EXPOSE directive and automatically extracts the correct port. This is the safest option.
- Range: 0 (auto-detect) or 1-65000 (explicit).
- **CRITICAL — never guess ports:** Do not assume a port based on the framework name (e.g. do not hardcode 7860 for Gradio — the actual image may use a different port like 7861). Always prefer auto-detect (port: 0) unless the user explicitly provides a port number.
- **Agent port selection rules:**
  1. **YAML registration:** Always use `port: 0` (auto-detect). This is the default and safest option.
  2. **Inline registration (`--port`):** Use `--port 0` for auto-detect, or the user-specified value.
  3. **User specifies a port:** Use that exact value.
  4. **Auto-detect fallback**: Images without an EXPOSE directive (e.g. bare PyTorch/CUDA runtime images) will have the CLI automatically fall back to port 8000 with a warning. When this happens, the agent should inform the user: "Port was not auto-detected; defaulting to 8000. Is this correct?" and let them override if needed.
  5. **Never hardcode** port numbers based on framework names (Gradio, Jupyter, Streamlit, etc.) — different image builds may use different ports.

**containerCommand** (optional)
- Command to execute when the container starts. If left blank, the image's default CMD runs.

**containerEnvs** (optional, YAML only)
- Environment variables for use inside the container. Each entry is a single key-value object (not a flat map).
- Example in YAML:
  ```yaml
  containerEnvs:
    - HF_TOKEN: "hf_abc123"
    - CUDA_VISIBLE_DEVICES: "0,1"
  ```

**userStorages** (optional, YAML only)
- Select pre-registered personal storage and enter the mount path inside the container. Multiple storages can be added.
- Personal storage must be registered first via the web console before it can be selected.
- Run `gcube storage list` to get MOUNT KEY values. For gcube built-in storage, use the literal key `gcube`.
- Example in YAML:
  ```yaml
  userStorages:
    - "95": "/mnt/data"           # external storage by MOUNT KEY
    - gcube: "/mnt/gcube-data"    # gcube built-in storage
  ```

**maxConnection** (required)
- The number of HTTP requests or connections that can be delivered to the service at once.
- Even a single user's browser can send multiple simultaneous requests (JS, CSS, images, API calls, WebSocket connections), so this value may differ from the actual number of concurrent users.
- If set too low, some page elements may fail to load or 503 errors may occur. If set too high, container, GPU, memory, and proxy resource usage increases.
- **Recommended values (agent should auto-select based on workload type):**
  - GPU inference API: 4
  - General REST API: 10
  - Web UI (Gradio, Streamlit, ComfyUI): 20-40
  - High concurrency service: 50-100
- Default: 4.
- **Agent auto-config rule:**
  1. Image name contains web UI keywords (`gradio`, `streamlit`, `comfyui`, `jupyter`, `webui`) → set to **20**.
  2. Otherwise → use default **4**.
  3. User explicitly requests a different value → use that value.

#### Step 3: GPU Settings

**gpuCode** (required)
- Run `gcube gpu list` and select by CODE column (e.g. `029`).
- Never use GPU_NAME (e.g. "RTX 4080 Super") — it is display-only and will not be accepted.
- The GPU list shows: CODE, GPU_NAME, TIER, GPUs, VRAM(GB), CPU(Core), MEM(GB), DISK(GB), PRICE/HR(KRW).
- By default, only available (in-stock) GPUs are shown. Use `gcube gpu list --all` to include out-of-stock GPUs.
- Add multiple entries under `gpuSpecs` for multi-replica deployments (max 10 total replicas).

**GPU presentation rule for agents:**

When presenting GPU options to the user, always:
1. Run `gcube gpu list` and show the **full table as-is** (do not summarize, group, or omit rows).
2. Add a **Tier legend** below the table explaining tier characteristics:
   - tier1 (Cloud): Stable, but image pull can take 30-60+ min
   - tier2 (Dedicated): Balanced speed and stability (~10-20 min)
   - tier3 (PC/Personal): Cheapest and fastest deploy, but GPU may be reclaimed
3. Mark your **recommended GPU(s)** with a note (e.g. "Recommended" or a star) based on the user's requirements and the rules below.
4. Explain *why* you recommend that GPU (tier trade-off, VRAM fit, price).

**GPU selection rules:**
- If user specifies a GPU name (e.g. "A100"), find matching CODE(s) from `gpu list` output.
- If user specifies VRAM requirement (e.g. "24GB VRAM"), filter by VRAM(GB) column.
- If user specifies a budget (e.g. "under 1000 won/hr"), filter by PRICE/HR column.
- If user specifies a tier preference, filter accordingly.
- If no preference is given, present all available options with tier trade-offs and let the user decide. Do not pre-select a tier on behalf of the user.
- Always get user confirmation before registering.

#### Step 4: Additional Options

**isIstioProxy** (optional, YAML only)
- Enables the Istio service mesh sidecar proxy. Enabled by default; disable if container errors occur after deployment.
- **Agent rule:** Leave enabled unless user reports container errors or explicitly asks to disable.

**isIstioL7Hash** (optional, YAML only)
- Uses L7 layer-based request hashing so the same client always connects to the same pod. Only available when replica count >= 2.
- **Agent rule:** Enable when deploying stateful web UIs (e.g. Gradio, ComfyUI) with multiple replicas. Leave disabled for stateless APIs.

**cuda** (optional)
- Select the minimum CUDA version required for the workload. Deployment only occurs on GPU nodes running this version or higher.
- **Conversion formula:** `MAJOR * 1000 + MINOR * 10 + PATCH` (NVIDIA CUDA Runtime convention; patch is usually 0). Examples: 12.1 → `12010`, 12.6 → `12060`, 11.8 → `11080`.
- **Agent rule:** If the container image tag includes a CUDA version (e.g. `cuda12.1`), extract the version and convert using the formula above. Otherwise leave empty.

**sharedMemory** (optional)
- Size of shared memory (tmpfs) to allocate to the container, in GB. Set a sufficient value when loading deep learning models.
- Range: 1-80 GB (hard limit), and must be less than GPU VRAM. Default: 1.
- **Agent rule:** For large model inference (LLM, Stable Diffusion), set to at least half the GPU VRAM (capped at 80 GB). For simple services, default 1 is fine.

#### Step 5: Review & Deploy

The web console offers two deploy methods:
- **Immediate Deploy:** Deployment proceeds immediately upon workload registration.
- **Manual Deploy:** Register only; deployment is performed later from the workload list.

In the CLI, this maps to:
- Immediate: `gcube workload register ... && gcube workload start SER`
- Manual: `gcube workload register ...` (start later with `gcube workload start SER`)

**Cost estimation** (shown in web console review step):
- Total estimated monthly cost: min~max KRW (VAT excluded).
- Estimated based on 24 hours/day, 30 days/month usage. Actual charges may vary.
- **Agent rule:** When proposing a workload, calculate and show: `PRICE/HR * 24 * 30` for monthly estimate. Always mention this is an estimate and VAT is excluded.

### Workload YAML reference

Generated by `gcube workload register --skeleton`:

```yaml
description: ""                      # required (2-80 chars)
cuda: ""                             # optional, e.g. "12060" for CUDA 12.6
sharedMemory: 1                      # GB (1-80, must be < GPU VRAM)

containers:
  - containerImage: ""               # required — full image path
    repo: docker.io                  # docker.io | ghcr.io | nvcr.io | quay.io | registry.hf.space
    port: 0                          # 0 = auto-detect from image EXPOSE (recommended)
    maxConnection: 4                 # concurrent requests (see guide above)
    containerCommand: ""             # startup command (blank = image default CMD)
    # isCredential: auto-detected from saved credentials; set explicitly to override
    containerEnvs: []                # list of KEY: VALUE pairs
    userStorages: []                 # list of "MOUNT_KEY": "/mount/path"
    # containerEnvs:
    #   - HF_TOKEN: "hf_abc123"
    # userStorages:
    #   - "95": "/mnt/data"          # external storage by MOUNT KEY
    #   - gcube: "/mnt/gcube-data"   # gcube built-in storage (literal key)

gpuSpecs:
  - gpuCode: ""                      # required — CODE from 'gcube gpu list'
  # add more entries for multi-replica:
  # - gpuCode: ""
```

### Workload states

The `STATE` column in `workload list` and `describe` shows the operational phase:

| Phase | Meaning |
|-------|---------|
| `idle` | Registered but never started, or stopped cleanly |
| `starting` | Deployment in progress |
| `running` | Running and serving (service URL available) |
| `stopping` | Shutting down |
| `finished` | Stopped after successful run |
| `failed` | Deployment or runtime failure |

**Note:** The phase is derived from the latest operation record (`operations[0]`), not the raw API `state` field. With `-o json`, the API returns raw states (`open`, `deploy`, `finish`). Fallback mapping (when no operations exist): `open` → `idle`, `deploy` → `running`, `finish` → `finished`.

### Update workflow

To modify a workload, it must be stopped first — the platform requires container re-creation for config changes, so hot-editing a running workload is not supported. Running `update` on a deployed workload will error with "Stop it first." To modify a stopped workload:

```bash
# Export current config as YAML
gcube workload update SER --skeleton > update.yaml
# Edit the YAML (change image, GPU, env vars, etc.)
gcube workload update SER -f update.yaml
# Restart
gcube workload start SER
```

The exported YAML includes GPU attributes (`gpu`, `gpuCount`, `vram`, `cpu`, `tier`) alongside `gpuCode`. These attributes are the **authoritative fields** — on register/update, they are reverse-matched against the current pricing list to resolve the correct code. This prevents silent mis-deployment when pricing codes are renumbered (e.g. a GPU moving from code "029" to "031" after repricing). If the resolved code differs from the written `gpuCode`, a warning is shown and the current code is used. If the GPU spec is no longer offered, the CLI errors out.

**Update YAML field editability:**

| Field | Editable? | Notes |
|-------|-----------|-------|
| `description`, `cuda`, `sharedMemory` | Yes | Top-level workload settings |
| `containers[*]` (all sub-fields) | Yes | image, port, env vars, storage mounts, etc. |
| `gpuSpecs[*].gpu`, `gpuCount`, `vram`, `cpu`, `tier` | **Do not edit** | These are the GPU identity fields used for reverse-matching. Editing them may cause a different GPU to be selected. |
| `gpuSpecs[*].gpuCode` | See below | When attributes are present, gpuCode is informational — the attributes take priority. Changing gpuCode alone does **not** switch the GPU. |

**To switch GPU in an update YAML:** Delete the entire `gpuSpecs` entry and replace it with a bare gpuCode from `gcube gpu list`:
```yaml
gpuSpecs:
  - gpuCode: "045"     # only gpuCode, no attribute fields → direct code lookup
```

### Deployment failure recovery

When a workload reaches `failed` state:

1. **Check logs:** `gcube workload logs SER` — look for crash reasons (OOM, missing files, port conflict, CUDA mismatch).
2. **Check pods:** `gcube workload pods SER` — inspect pod status and restart count.
3. **Stop the workload:** `gcube workload stop SER -y` — must stop before editing.
4. **Fix the issue:** `gcube workload update SER --skeleton > fix.yaml` — edit the YAML to fix the root cause.
5. **Re-deploy:** `gcube workload update SER -f fix.yaml && gcube workload start SER`

Common failure causes and fixes:

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| OOMKilled in logs | Model too large for GPU VRAM | Switch to a GPU with more VRAM |
| Port conflict / bind error | Wrong port or port already in use | Use `port: 0` (auto-detect) |
| CUDA version mismatch | Image requires newer CUDA | Set `cuda` field to match image requirement |
| Image pull error | Wrong image path or missing credentials | Check `containerImage`; register a credential via `gcube credential create` |
| Container exits immediately | Bad `containerCommand` or missing entrypoint | Remove or fix `containerCommand` |

### Schedule

Automate workload start/stop on a recurring or one-time basis. Scheduled workloads show a `(scheduled)` badge in `workload list`.

```bash
# Show current schedules
gcube workload schedule SER

# Inline mode — appends to existing schedules
gcube workload schedule SER --days Mon-Fri --start 09:00 --stop 18:00

# YAML mode — replaces ALL schedules (full replacement semantics)
gcube workload schedule SER -f schedule.yaml

# View execution history (default 20 entries)
gcube workload schedule SER --logs
gcube workload schedule SER --logs --limit 50

# Remove all schedules
gcube workload unschedule SER
```

Schedule YAML format:

```yaml
timezone: Asia/Seoul
schedules:
  # Sugar form — expands to separate START + STOP entries
  - days: Mon-Fri
    start: "09:00"
    stop: "18:00"

  # Full form — explicit action per entry
  - action: START
    time: "09:00"
    days: [Mon, Wed, Fri]
  - action: STOP
    time: "18:00"
    days: [Mon, Wed, Fri]

  # One-time schedule
  - action: START
    time: "14:00"
    date: "2026-08-01"
```

Day spec: `Mon`-`Sun` names, ranges (`Mon-Fri`), comma-separated (`Mon,Wed,Fri`), aliases (`daily`, `weekdays`, `weekend`), or bitmask integer (Mon=1..Sun=64; e.g. `31` = Mon-Fri).

**Agent schedule rules:**

| Situation | Do | Don't |
|---|---|---|
| Simple recurring start/stop | Use inline `--days/--start/--stop` | Overkill with YAML for a single pair |
| Complex mix (disabled entries, one-time + repeat, multiple time slots) | Use YAML `-f` | Try to chain multiple inline commands — inline appends, so order matters and there's no way to disable an entry inline |
| YAML full replacement | Include **all** entries (including disabled ones) in the file | Omit existing entries — they will be deleted |
| Verifying schedules ran | Use `--logs` to check execution history | Poll `workload describe` in a loop |

> Times are `HH:mm` strings interpreted in the schedule's timezone (default `Asia/Seoul`). Do not parse them as Date objects — pass as-is.

## Teams

Teams share workloads and a point pool. A workload belongs either to you personally
or to exactly one team.

```bash
gcube team list                         # List teams you belong to
gcube team show 6                       # Team details, members, and points
gcube team create --name ml-research    # Create a team (you become OWNER)
```

Output columns: ID, NAME, ROLE, MEMBERS, STATUS, OWNER.

**Team names are not unique** — the server allows duplicates. `--team` and
`GCUBE_TEAM` take the numeric **ID** from `team list`, never the name.

Member invite/removal, role changes, and team edit/archive are web console only;
`team show` is how you read the current roster.

### Team context

There is no `team switch` — context is set per invocation so it stays visible:

```bash
gcube workload list --team 6            # Flag
GCUBE_TEAM=6 gcube workload list        # Env var, for CI and scripts
```

Priority: `--team` > `GCUBE_TEAM` > personal. `GCUBE_TEAM` must be numeric;
anything else exits 1 (`0` and empty mean unset).

`workload list` with no team flag returns personal + every team you belong to.
`--team ID` and `--personal` narrow it and are mutually exclusive.
`workload register --team ID` creates under that team and prints
`Creating in team context: ID N` to stderr.

## GPU Management

```bash
gcube gpu list                          # List available GPUs (in stock)
gcube gpu list --all                    # Include out-of-stock GPUs
gcube gpu list --service-code gcube     # Filter by service code
```

### GPU list output columns

| Column | Description |
|--------|-------------|
| CODE | Unique GPU spec identifier. Use this for `--gpu` flag and YAML `gpuCode`. |
| GPU_NAME | Human-readable GPU name (e.g. "A100", "RTX 4080 Super"). Display only. |
| TIER | Infrastructure tier (see Tier guide below). |
| GPUs | Number of GPUs in the spec. |
| VRAM(GB) | Total GPU memory. |
| CPU(Core) | CPU cores allocated. |
| MEM(GB) | System RAM allocated. |
| DISK(GB) | Disk space allocated. |
| PRICE/HR(KRW) | Hourly cost range in Korean Won. |

**IMPORTANT:** `CODE` (e.g. `029`) is what you pass to `--gpu` or set in YAML `gpuCode`. Never use `GPU_NAME` (e.g. "RTX 4080 Super") — it is for display only and will not be accepted by the API.

### GPU Tier guide

Tiers represent the infrastructure type, not just pricing. Each tier has different deployment speed, stability, and interruption risk.

| Tier | Provider type | Deploy speed | Stability | Interruption risk |
|------|--------------|-------------|-----------|-------------------|
| **tier1** | Cloud providers (CSP) | Slow — image pull can take 30-60+ min | High — enterprise-grade infrastructure | Very low |
| **tier2** | Dedicated servers | Moderate — image pull ~10-20 min | High — contracted dedicated hardware | Low |
| **tier3** | PC cafes / personal PCs | Fast — often pre-cached images | Variable — depends on provider | **Higher — may be interrupted if the provider reclaims the GPU. When interrupted, workload transitions to `failed` state. No automatic re-deploy — follow the Deployment failure recovery playbook.** |

**Agent GPU recommendation rules:**

| User intent | Recommended tier | Reason |
|---|---|---|
| Production / long-running service | tier1 or tier2 | Stability and uptime priority |
| Development / testing | tier2 | Best balance of speed and stability; faster deploys |
| Quick experiment / cost-sensitive | tier3 OK, but warn user | Cheapest, but interruption possible — inform the user before selecting |
| First-time deploy of a large image (multi-GB) | Prefer tier2 | tier1 image pull can be extremely slow; tier2 is significantly faster |

**IMPORTANT:** When recommending a GPU, always mention the tier and its characteristics alongside price. Do not recommend tier3 without warning about potential interruptions. If the same GPU model is available across multiple tiers, explain the trade-offs and let the user choose.

## Storage

```bash
gcube storage list                      # List personal storages
```

Output columns: MOUNT KEY, DESCRIPTION, TYPE, CAPACITY, ACCESS MODE.

The `MOUNT KEY` is used in workload YAML `userStorages` to mount storage into containers:

```yaml
userStorages:
  - "95": "/mnt/data"          # external storage by MOUNT KEY
  - gcube: "/mnt/gcube-data"   # gcube built-in storage (literal key 'gcube')
```

## Credentials

Manage container registry credentials for pulling private images.

```bash
gcube credential list                   # List saved credentials
gcube credential create \
  --repo docker \
  --username myuser \
  --token mytoken                       # Create a credential
gcube credential delete --repo docker   # Delete a credential
```

Supported registries: `docker`, `github`, `harbor`, `aws`, `huggingface`, `quay`.

For AWS ECR, also pass `--region` and optionally `--registry-id`.

After creating a credential, the CLI auto-detects it when registering a workload with a matching private registry. You can force credential usage with `--credential`:

```bash
gcube workload register \
  --image ghcr.io/myorg/private-model:latest \
  --repo ghcr.io \
  --gpu 029 \
  --description "Private image workload" \
  --credential
```

`--credential` is a boolean flag (no value needed). It tells the platform to use the saved credential matching the `--repo` registry.

Registry mapping between `--repo` (workload register) and `credential create --repo`:

| Image registry | `workload register --repo` | `credential create --repo` |
|---|---|---|
| Docker Hub | `docker.io` | `docker` |
| GitHub (ghcr.io) | `ghcr.io` | `github` |
| NVIDIA (nvcr.io) | `nvcr.io` | (use `docker` with nvcr.io URL) |
| Quay.io | `quay.io` | `quay` |
| Hugging Face | `registry.hf.space` | `huggingface` |
| Harbor (self-hosted) | (use full domain) | `harbor` |
| AWS ECR | (use full domain) | `aws` |

## Points & Billing

```bash
gcube point status                      # Show point balance and spending summary
gcube point spending                    # Show daily point spending history
gcube point spending --month 2026-07    # Filter by month
gcube point spending --workload SER     # Filter by workload SER
```

`point status` output:
- Available Point: remaining balance
- Charged Point: total charged
- Spent Point: total spent
- Spending Summary: total / prev month / this month

All amounts are in Points (P), where 1P = 1 KRW.

## Resource Monitoring

```bash
gcube resource workload SER             # Show resource usage of a workload
```

Use `workload describe` for workload state, service URL, and pod info. Use `resource workload` for live CPU/GPU/memory utilization of a running workload.

## Configuration

```bash
gcube config status                     # Show current config with source annotations
gcube config set --platform-url URL     # Set platform URL
gcube config set --email EMAIL          # Set user email
gcube config set --output json          # Set default output format (persistent; overridden by gcube -o)
gcube config get platform-url           # Get a specific config value
```

`config status` shows each value's source: `(config)`, `(env)`, or `(default)`.

Environment variables override config file values:
- `GCUBE_PLATFORM_URL` — platform URL
- `GCUBE_ACCESS_TOKEN` — bearer token (useful for CI/CD, multi-account automation)
- `GCUBE_OUTPUT` — default output format (`table`|`json`|`yaml`)
- `GCUBE_SERVICE_CODE` — default service code filter

## Output Formats

The `-o` / `--output` flag is a **global option** and must come **before** the subcommand:

```bash
gcube -o json workload list             # JSON output
gcube -o yaml gpu list                  # YAML output
gcube -o table workload describe SER    # Default: human-readable table
```

**IMPORTANT:** `gcube workload list -o json` will NOT work — `-o` is not recognized after the subcommand. Always place `-o` immediately after `gcube`.

## Command Aliases

For faster typing:

| Full command | Alias |
|---|---|
| `gcube workload` | `gcube wl` |
| `gcube credential` | `gcube cred` |

## Shell Completion

```bash
gcube completion bash                   # Print bash completion script
gcube completion zsh                    # Print zsh completion script
gcube completion fish                   # Print fish completion script
gcube completion install                # Auto-detect and install
gcube completion install --shell bash   # Install for specific shell
```

## Gotchas

- **GPU CODE vs GPU_NAME**: `CODE` (e.g. `029`) is the identifier for API calls. `GPU_NAME` (e.g. "RTX 4080 Super") is for display only. Always use CODE for `--gpu` flag and YAML `gpuCode`.
- **SER is the workload identifier**: All workload commands take `SER` (a numeric ID) as the argument, not the description or name.
- **Workload states are operation-based**: The displayed phase (idle/starting/running/stopping/finished/failed) is derived from the latest operation, not the raw API state. This avoids stale state caused by DB write delays.
- **Image verification is 3-state**: When registering a workload, image verification can return success, fail, or unverified (timeout). A failed verification prompts for confirmation; use `-y` to skip.
- **Prices are in KRW**: GPU prices in `gpu list` are shown as hourly rates in Korean Won (KRW). Point balance (1P = 1 KRW).
- **YAML is required for advanced config**: Multi-container workloads, environment variables, storage mounts, and custom commands can only be set via YAML manifest (`-f` flag). Use `--skeleton` to generate a template.
- **Storage mount keys**: Use `gcube storage list` to find the correct `MOUNT KEY`. For gcube built-in storage, use the literal string `gcube` as the key.
- **SSH requires running state**: `gcube workload ssh` only works when the workload is in `running` state.
- **SSE monitoring**: `workload start` and `workload watch` use Server-Sent Events for real-time deployment status. Use `--plain` for non-interactive output (pipes, CI).
- **Service code filter**: Some commands accept `--service-code` to filter resources by service (gcube, edu, katech). Can also be set via `GCUBE_SERVICE_CODE` env var.
- **Token refresh**: Tokens are managed automatically via PKCE browser auth. If you see 401 errors, re-run `gcube auth login`.
- **EDU filters**: `workload list` supports `--org-code` and `--class-id` for EDU service administrators. These are rarely needed for general use.
- **Team IDs, not names**: `--team` and `GCUBE_TEAM` take the numeric ID from `gcube team list`. Team names may be duplicated server-side, so a name cannot identify a team.
- **TEAM column is conditional**: `workload list` adds it only when a team workload is in the result; personal rows show `-`. Column count varies — read the header before parsing positionally, or use `-o json`. If the column is absent, everything listed is personal.
- **Team workload `owner` is a virtual account**: A team workload reports `owner` as `team-{id}@team.gcube.internal`; the person who created it is `createdBy`. Never present the virtual account as a user.
- **Team member management is web-only**: The CLI lists, shows, and creates teams. Invites, removals, role changes, and archiving happen in the web console.
- **`--skeleton` for updates**: `gcube workload update SER --skeleton` exports the *current* workload config as editable YAML, including GPU identity attributes (`gpu`, `vram`, `tier`, etc.) that ensure the same GPU is selected even if pricing codes are renumbered. See the Update workflow section for field editability rules.
- **Container image whitespace**: Leading/trailing whitespace in image names is automatically trimmed.
- **Timeout for bulk operations**: `workload stop` has a 60-second timeout with automatic retry (2 retries with exponential backoff) to prevent bulk operation failures.
- **CLI confirmation prompts**: `workload stop`, `workload delete`, and `credential delete` display a `[y/N]` prompt. In non-interactive environments (agents, scripts, pipes), use the `-y`/`--yes` flag to skip the prompt. Agents should always obtain user confirmation *before* running the command, then pass `-y` to avoid the CLI prompt hanging.
- **Port auto-detect is preferred**: Use `port: 0` in YAML (or `--port 0`) to auto-detect the port from the image's EXPOSE directive. Never guess ports based on framework names — a Gradio image might expose 7861, not 7860. If auto-detect fails, ask the user.
- **Global `-o` flag position**: `-o json` / `-o yaml` must come **before** the subcommand: `gcube -o json workload list`, NOT `gcube workload list -o json`. Placing it after the subcommand silently fails.
- **Tier affects deploy speed**: tier1 (cloud) image pulls can take 30-60+ minutes for large images. tier2 (dedicated) is significantly faster (~10-20 min). tier3 (PC/personal) is fastest but may be interrupted. Consider tier when recommending GPUs, especially for first-time deploys of large images.
- **Schedule YAML is full replacement**: `schedule -f` replaces **all** schedules — omitted entries are deleted. Inline `--days/--start/--stop` safely appends. When editing via YAML, always include disabled entries too.
- **Schedule times are timezone-dependent**: Times are interpreted in the schedule's timezone (default `Asia/Seoul`), not hardcoded KST. If `--timezone UTC` is set, `09:00` means 09:00 UTC.
- **`--logs` for schedule verification**: Use `gcube workload schedule SER --logs` to confirm whether scheduled actions actually executed. The `errMsg` field shows failure reasons (e.g. no GPU available).
- **Skill file updates**: This skill file is bundled with the CLI package. After upgrading (`pip install --upgrade gcube-cli`), re-run `gcube skill install -y` to update it.
- **Windows cp949 encoding**: On Windows with cp949 locale, `gcube gpu list` (table) and `--skeleton` output crash on Unicode characters (₩, —). Use `-o json` or `-o yaml` as a workaround.
