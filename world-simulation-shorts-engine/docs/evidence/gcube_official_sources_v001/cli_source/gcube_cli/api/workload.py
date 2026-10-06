"""Workload API client and data models for gcube CLI."""

from __future__ import annotations

import builtins
import json
import re
from dataclasses import dataclass, field
from typing import Any

from gcube_cli.api._util import fmt_date, to_float, to_int
from gcube_cli.api.client import Client

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GAI_BASE = "/api/workloads/gai/"

# Keys kept when building public JSON output from raw API containers / GPU specs / pods.
_CONTAINER_PUBLIC_KEYS = frozenset({
    "containerImage", "containerCommand", "isCredential",
    "port", "serviceUrl", "repo",
    "maxConnection", "containerEnvs", "userStorages",
})
_GPU_SPEC_PUBLIC_KEYS = frozenset({"gpu", "gpuCount", "vram", "target", "tier"})
_POD_PUBLIC_KEYS = frozenset({"name", "status", "startTime", "node"})
_NODE_PUBLIC_KEYS = frozenset({"name", "gpuSpec", "hostSpec", "category"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# Canonical implementations live in api/_util.py so api/team.py shares them.
# Re-exported under the original private names: they are used throughout this
# module and imported by tests/test_workload.py.
_fmt_date = fmt_date
_int = to_int
_num = to_float


def _fmt_pod_times(pods: list[dict[str, Any]]) -> None:
    """Format each pod's startTime in place (UTC → local)."""
    for p in pods:
        if "startTime" in p:
            p["startTime"] = _fmt_date(p["startTime"])


# ---------------------------------------------------------------------------
# GPU Pricing
# ---------------------------------------------------------------------------


@dataclass
class GpuPricing:
    """One entry from GET /api/gpu/available/pricing/list."""

    gpu_name: str           # JSON: gpuName — internal chip identifier (used in API body)
    gpu_ext: str            # JSON: gpuExt — GPU variant (e.g. "PCIE"), can be ""
    product_name: str       # JSON: productName — user-facing display name (e.g. "B200 SXM6")
    product_code: str       # JSON: productCode ("tier1" | "tier2" | "tier3")
    pp_index: int           # JSON: ppIndex — product provider index (default 1)
    gpu: int                # JSON: gpu — GPU count in the spec (not gpuCount)
    price: float
    usage_price: float      # JSON: usagePrice
    currency_unit: str      # JSON: currencyUnit — "KRW" or "USD"
    vram: int               # GB
    cpu: int
    memory: int             # GB
    disk: int               # GB
    availability: bool
    nodes: list[dict[str, Any]] = field(default_factory=list)  # node detail list (passthrough)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GpuPricing:
        return cls(
            gpu_name=d.get("gpuName", ""),
            gpu_ext=d.get("gpuExt", ""),
            product_name=d.get("productName", ""),
            product_code=d.get("productCode", ""),
            pp_index=_int(d.get("ppIndex", 1)),
            gpu=_int(d.get("gpu", 1)),
            price=_num(d.get("price", 0)),
            usage_price=_num(d.get("usagePrice", 0)),
            currency_unit=d.get("currencyUnit", "KRW"),
            vram=_int(d.get("vram", 0)),
            cpu=_int(d.get("cpu", 0)),
            memory=_int(d.get("memory", 0)),
            disk=_int(d.get("disk", 0)),
            availability=bool(d.get("availability", False)),
            nodes=d.get("nodes") or [],
        )


def is_gpu_available(pricing: GpuPricing) -> bool:
    """Return True if the GPU has available capacity."""
    return pricing.availability is True


def match_gpu_pricing(
    spec: dict[str, Any],
    indexed: list[tuple[str, GpuPricing]],
) -> tuple[str, GpuPricing | None]:
    """Reverse-match a gpuSpec's attributes to the CURRENT pricing CODE.

    Matching criteria — stricter than the web console's ``enrichGpuSpecsWithPrices``
    (which only checks gpuName/gpuCount/vram/cpu/tier) to correctly distinguish
    GPU specs that share those five fields but differ in memory/disk (e.g. CODE
    093 vs 124, both RTX 4060 tier3 8GB 12-core but 16GB/50GB vs 20GB/76GB RAM/disk).

    Full field list (mirrors web console ``buildGpuKey``):
    gpuName + gpuExt + ppIndex + gpuCount + vram + cpu + memory + disk + tier.
    Fields absent from spec (zero/empty) are skipped for backward compatibility.

    Used both by ``get_update_skeleton`` (to print the current code) and by the
    register/update path (to self-heal a stale ``gpuCode`` after the pricing
    list is renumbered). Attributes are authoritative; the numeric code is only
    a hint. Returns ``(code, pricing)`` or ``("", None)`` when nothing matches.
    """
    gpu = str(spec.get("gpu") or "").lower()
    gpu_ext = str(spec.get("gpuExt") or "").lower()
    pp_index = spec.get("ppIndex", 0)
    gpu_count = spec.get("gpuCount", 1)
    vram = spec.get("vram", 0)
    cpu = spec.get("cpu", 0)
    memory = spec.get("memory", 0)
    disk = spec.get("disk", 0)
    product_code = f"tier{spec.get('tier', 0)}"
    for code, p in indexed:
        if (
            p.gpu_name.lower() == gpu
            and p.gpu == gpu_count
            and p.vram == vram
            and p.cpu == cpu
            and p.product_code == product_code
            and (not gpu_ext or p.gpu_ext.lower() == gpu_ext)
            and (not pp_index or p.pp_index == pp_index)
            and (not memory or p.memory == memory)
            and (not disk or p.disk == disk)
        ):
            return code, p
    return "", None


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------

_SCHEDULE_TIMEZONE_DEFAULT = "Asia/Seoul"


@dataclass
class ScheduleEntry:
    """One schedule item for a workload (start/stop reservation).

    Field-name mapping:
    - Request ``date`` <-> Response ``scheduleDate``
    - ``from_response()`` converts the response shape.
    """

    enabled: bool
    action: str  # 'START' | 'STOP'
    days_of_week: int  # bitmask: Mon=1 Tue=2 Wed=4 Thu=8 Fri=16 Sat=32 Sun=64
    time: str  # 'HH:mm' KST — keep as string, never parse to datetime
    date: str | None  # one-time date yyyy-MM-dd (daysOfWeek must be 0)
    end_date: str | None  # repeat end-date yyyy-MM-dd
    # response-only fields
    ser: int | None = None
    time_zone: str = ""
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_response(cls, d: dict[str, Any]) -> ScheduleEntry:
        """Build from GET/PUT response dict.

        Key mapping: ``scheduleDate`` (response) -> ``date`` (request).
        ``createdAt``/``updatedAt``: Array[Int] with variable length (nanos).
        """
        return cls(
            enabled=d.get("enabled", True),
            action=d.get("action", "START"),
            days_of_week=_int(d.get("daysOfWeek", 0)),
            time=d.get("time", ""),
            date=d.get("scheduleDate"),
            end_date=d.get("endDate"),
            ser=d.get("ser"),
            time_zone=d.get("timeZone", ""),
            created_at=_fmt_date(d.get("createdAt")),
            updated_at=_fmt_date(d.get("updatedAt")),
        )

    def to_request_dict(self) -> dict[str, Any]:
        """Serialize for PUT body (camelCase, server fields only)."""
        return {
            "enabled": self.enabled,
            "action": self.action,
            "daysOfWeek": self.days_of_week,
            "time": self.time,
            "date": self.date,
            "endDate": self.end_date,
        }

    def to_yaml_dict(self) -> dict[str, Any]:
        """Serialize for round-trip YAML (human-friendly day names)."""
        d: dict[str, Any] = {
            "enabled": self.enabled,
            "action": self.action,
            "time": self.time,
        }
        if self.date is not None:
            d["date"] = self.date
        else:
            d["days"] = _mask_to_day_names(self.days_of_week)
            if self.end_date:
                d["endDate"] = self.end_date
        return d


# -- bitmask helpers (used by ScheduleEntry.to_yaml_dict) --

_WEEKDAY_BITS = [1, 2, 4, 8, 16, 32, 64]  # index 0=Mon .. 6=Sun
_WEEKDAY_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _mask_to_day_names(mask: int) -> builtins.list[str]:
    """Convert bitmask to English day-name list.  31 -> ['Mon'..'Fri']."""
    return [_WEEKDAY_EN[i] for i, bit in enumerate(_WEEKDAY_BITS) if mask & bit]


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class Workload:
    """Represents a workload resource returned by the gcube API."""

    ser: str
    owner: str
    description: str
    category: str       # infer | learn | job
    state: str          # open | deploy | finish
    replica: int
    cuda: str
    svc_url: str
    created_at: str     # formatted from createdAt array, "" if absent
    deploy_at: str      # formatted from deployAt array, "" if null
    container_array: list[dict[str, Any]]   # containerArray
    gpu_spec_array: list[dict[str, Any]]    # gpuSpecArray
    pods: list[dict[str, Any]]              # pod list
    # Team fields (PBI-023). Personal workloads leave these at 0/"".
    # Note ``owner`` is the team's virtual account (team-{id}@team.gcube.internal)
    # for team workloads; ``created_by`` is the human who made it.
    team_id: int = 0
    team_name: str = ""
    created_by: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Workload:
        """Construct a Workload from an API response dict.

        Handles real API format with nested containerArray / gpuSpecArray,
        and falls back to JSON-string containers / gpuSpecs fields.
        """
        # --- container array -------------------------------------------
        container_arr: list[dict[str, Any]] = data.get("containerArray") or []
        if not container_arr and data.get("containers"):
            try:
                container_arr = json.loads(data["containers"])
            except (ValueError, TypeError):
                container_arr = []

        # --- GPU spec array --------------------------------------------
        gpu_arr: list[dict[str, Any]] = data.get("gpuSpecArray") or []
        if not gpu_arr and data.get("gpuSpecs"):
            try:
                gpu_arr = json.loads(data["gpuSpecs"])
            except (ValueError, TypeError):
                gpu_arr = []

        w = cls(
            ser=str(data["ser"]),
            owner=data.get("owner", ""),
            description=data.get("description", ""),
            category=data.get("category", ""),
            state=data.get("state", ""),
            replica=_int(data.get("replica", 1)),
            cuda=data.get("cuda", ""),
            svc_url=data.get("svc_url") or data.get("svcUrl", ""),
            created_at=_fmt_date(data.get("createdAt")),
            deploy_at=_fmt_date(data.get("deployAt")),
            container_array=container_arr,
            gpu_spec_array=gpu_arr,
            pods=data.get("pods", []),
            team_id=_int(data.get("teamId")),
            team_name=data.get("teamName") or "",
            created_by=data.get("createdBy") or "",
        )
        w.raw = data  # type: ignore[attr-defined]
        return w

    def to_public_dict(self) -> dict[str, Any]:
        """Return a sanitized dict for public JSON output.

        Excludes billing fields, internal flags, and infrastructure details.
        Dates are formatted as strings.  ``containerArray`` → ``containers``,
        ``gpuSpecArray`` → ``gpuSpec`` (single object) or ``gpuSpecArray`` (multiple).
        """
        raw: dict[str, Any] = getattr(self, "raw", {})

        containers = [
            {k: v for k, v in ct.items() if k in _CONTAINER_PUBLIC_KEYS}
            for ct in (raw.get("containerArray") or [])
        ]

        pods_out: list[dict[str, Any]] = []
        for pod in (raw.get("pods") or []):
            p = {k: v for k, v in pod.items() if k in _POD_PUBLIC_KEYS}
            if "node" in p and isinstance(p["node"], dict):
                p["node"] = {k: v for k, v in p["node"].items() if k in _NODE_PUBLIC_KEYS}
            pods_out.append(p)
        _fmt_pod_times(pods_out)

        result: dict[str, Any] = {
            "ser": raw.get("ser"),
            "description": raw.get("description", ""),
            # ``owner`` is kept as the API reports it — for team workloads that is
            # the team's virtual account, which is correct, not a bug.  The human
            # readable value is ``createdBy`` below.
            "owner": raw.get("owner", ""),
            "category": raw.get("category", ""),
            "state": raw.get("state", ""),
            "replica": raw.get("replica"),
            "createdAt": _fmt_date(raw.get("createdAt")),
            "deployAt": _fmt_date(raw.get("deployAt")),
        }
        if "closeAt" in raw:
            result["closeAt"] = _fmt_date(raw["closeAt"])

        # Team fields — only present on team workloads, so omit the keys entirely
        # for personal ones rather than emitting null/0.
        if raw.get("teamId"):
            result["teamId"] = _int(raw.get("teamId"))
            result["teamName"] = raw.get("teamName") or ""
        if raw.get("createdBy"):
            result["createdBy"] = raw["createdBy"]

        gpu_specs_out = [
            {k: v for k, v in spec.items() if k in _GPU_SPEC_PUBLIC_KEYS}
            for spec in (raw.get("gpuSpecArray") or [])
        ]

        result.update({
            "cuda": raw.get("cuda", ""),
            "sharedMemory": raw.get("sharedMemory", 1),
            "isIstioProxy": raw.get("isIstioProxy", True),
            # API returns lowercase 'h'; output as capital H for update pipeline consistency
            "isIstioL7Hash": raw.get("isIstioL7hash") or raw.get("isIstioL7Hash", False),
            "containers": containers,
            "gpuSpecs": gpu_specs_out,
        })

        result["pods"] = pods_out
        if raw.get("isScheduled"):
            result["isScheduled"] = True
        return result


# ---------------------------------------------------------------------------
# API Client
# ---------------------------------------------------------------------------


class WorkloadAPI:
    """High-level Workload API client.

    All operations use the GAI namespace endpoints (/api/workloads/gai/*).
    """

    def __init__(self, client: Client) -> None:
        self._client = client

    def get_gpu_pricings(
        self, service_code: str | None = None,
    ) -> builtins.list[GpuPricing]:
        """Fetch available GPU pricing list.

        ``GET /api/gpu/available/pricing/list``
        Response envelope: ``{ "status": 200, "pricings": [...] }``
        """
        params: dict[str, str] = {}
        if service_code:
            params["serviceCode"] = service_code
        data = self._client.get(
            "/api/gpu/available/pricing/list",
            params=params or None,
        )
        items: builtins.list[dict[str, Any]] = data.get("pricings", data.get("data", []))
        return [GpuPricing.from_dict(item) for item in items]

    def get_indexed_gpu_pricings(
        self, service_code: str | None = None,
    ) -> builtins.list[tuple[str, GpuPricing]]:
        """Fetch pricing list and assign stable 3-digit CODEs.

        CODE = 1-based sequential index in API response order.
        Both ``gpu list`` and workload register/update use this function to ensure
        the CODE→GPU mapping is always consistent between commands.
        """
        pricings = self.get_gpu_pricings(service_code=service_code)
        return [(f"{i + 1:03d}", p) for i, p in enumerate(pricings)]

    def get_point_base(self) -> dict[str, Any]:
        """Fetch exchange-rate info.

        ``GET /api/point/base``
        Response envelope: ``{ "pointBase": { "krw": <number>, ... } }``
        """
        data = self._client.get("/api/point/base")
        return data.get("pointBase", {})

    def verify_image(
        self,
        owner: str,
        repo: str,
        container_image: str,
        is_credential: bool = False,
    ) -> dict[str, Any]:
        """Verify a container image URL and retrieve the exposed port.

        ``GET /api/workloads/container/url/verify``
        Response envelope: ``{ "status": 200, "exposedPort"?: str, "data"?: {"port": str} }``
        Raises APIError when status != 200 (image verification failed).
        """
        return self._client.get(
            "/api/workloads/container/url/verify",
            params={
                "owner": owner,
                "repo": repo,
                "containerImage": container_image,
                "isCredential": str(is_credential).lower(),
            },
        )

    def list(
        self,
        owner: str | None = None,
        org_code: str | None = None,
        class_id: int | None = None,
        scope: dict[str, str] | None = None,
    ) -> builtins.list[Workload]:
        """List workloads.

        ``GET /api/workloads/gai/list?owner={email}``

        EDU admins/staff (``ROLE_ADMIN``, ``ROLE_EDU_STAFF``) may pass
        ``org_code`` and ``class_id`` together to retrieve every workload
        belonging to that class.

        ``scope`` carries the team filter built by
        ``commands.workload.resolve_list_scope()`` — ``{"teamId": "6"}``,
        ``{"personalOnly": "true"}``, or ``{}`` for the unified default view.
        It is merged verbatim so the three states stay distinguishable
        (an empty dict is not the same as ``teamId=0``).
        """
        params: dict[str, str] = {}
        if owner is not None:
            params["owner"] = owner
        if org_code is not None:
            params["orgCode"] = org_code
        if class_id is not None:
            params["classId"] = str(class_id)
        if scope:
            params.update(scope)
        data = self._client.get(_GAI_BASE + "list", params=params)
        items: builtins.list[dict[str, Any]] = data.get(
            "workloads", data.get("data", data.get("items", []))
        )
        return [Workload.from_dict(item) for item in items]

    def describe(self, ser: str) -> Workload:
        """Get details for a single workload by serial number.

        ``GET /api/workloads/gai/{ser}``
        """
        data = self._client.get(f"{_GAI_BASE}{ser}")
        item: dict[str, Any] = data.get("workload", data.get("data", data))
        return Workload.from_dict(item)

    def start(self, ser: str) -> None:
        """Deploy (start) a workload.

        ``GET /api/workloads/gai/{ser}/state/deploy``
        """
        self._client.get(f"{_GAI_BASE}{ser}/state/deploy")

    def stop(self, ser: str) -> None:
        """Finish (stop) a workload.

        ``GET /api/workloads/gai/{ser}/state/finish``
        """
        self._client.get(f"{_GAI_BASE}{ser}/state/finish")

    def delete(self, ser: str) -> None:
        """Delete a workload.

        ``DELETE /api/workloads/gai/delete/{ser}``
        """
        self._client.delete(f"{_GAI_BASE}delete/{ser}")

    def logs(self, ser: str, pod: str) -> str:
        """Retrieve logs for a specific pod of a workload.

        ``GET /api/workloads/{ser}/logs/{pod}``
        """
        data = self._client.get(f"/api/workloads/{ser}/logs/{pod}")
        return str(data.get("data", data.get("logs", "")))

    def update(self, ser: str, body: dict[str, Any]) -> Workload:
        """Update a stopped workload.

        ``PUT /api/workloads/gai/update``
        Only allowed when workload state is not ``deploy``.
        """
        data = self._client.put(_GAI_BASE + "update", json=body)
        item: dict[str, Any] = data.get("workload", data.get("data", data))
        return Workload.from_dict(item)

    # -- Schedule API --

    def get_schedules(self, ser: str) -> builtins.list[ScheduleEntry]:
        """Fetch schedules for a workload.

        ``GET /api/workloads/gai/{ser}/schedule``
        """
        data = self._client.get(f"{_GAI_BASE}{ser}/schedule")
        return [ScheduleEntry.from_response(s) for s in data.get("schedules", [])]

    def save_schedules(
        self,
        ser: str,
        entries: builtins.list[ScheduleEntry],
        time_zone: str = _SCHEDULE_TIMEZONE_DEFAULT,
    ) -> builtins.list[ScheduleEntry]:
        """Save (replace all) schedules for a workload.

        ``PUT /api/workloads/gai/{ser}/schedule``
        PUT semantics: full replacement — send every entry including disabled ones.
        """
        body: dict[str, Any] = {
            "timeZone": time_zone,
            "schedules": [e.to_request_dict() for e in entries],
        }
        data = self._client.put(f"{_GAI_BASE}{ser}/schedule", json=body)
        return [ScheduleEntry.from_response(s) for s in data.get("schedules", [])]

    def delete_schedules(self, ser: str) -> None:
        """Delete all schedules for a workload.

        ``DELETE /api/workloads/gai/{ser}/schedule``
        """
        self._client.delete(f"{_GAI_BASE}{ser}/schedule")

    def get_schedule_logs(
        self,
        ser: str,
        start_num: int = 0,
        scale_num: int = 20,
    ) -> tuple[builtins.list[dict[str, Any]], int]:
        """Fetch schedule execution history.

        ``GET /api/workloads/gai/{ser}/schedule/logs``
        Returns (logs, totalNum).
        """
        data = self._client.get(
            f"{_GAI_BASE}{ser}/schedule/logs",
            params={"startNum": str(start_num), "scaleNum": str(scale_num)},
        )
        logs: builtins.list[dict[str, Any]] = data.get("logs", [])
        total = _int((data.get("paging") or {}).get("totalNum", len(logs)))
        return logs, total

    def get_update_skeleton(self, ser: str, service_code: str | None = None) -> str:
        """Return current workload config as an editable YAML string.

        Produces output at the same level of detail as the register skeleton —
        only user-editable fields.  Enriched fields (price, tier, target, vram, …)
        are excluded; ``_enrich_gpu_specs()`` recomputes them from the pricing API.

        gpuCode is auto-matched against the current pricing list via
        ``match_gpu_pricing`` (gpuName + gpuExt + ppIndex + gpuCount + vram +
        cpu + memory + disk + tier).  This is stricter than the web console's
        ``enrichGpuSpecsWithPrices`` to distinguish specs that share the basic
        five fields but differ in memory/disk (e.g. CODE 093 vs 124).
        If matching fails, gpuCode is left blank with a comment for manual lookup.

        Returns a YAML string (not a dict) because yaml.dump() does not support
        inline comments.
        """
        import yaml as _yaml

        wl = self.describe(ser)
        raw: dict[str, Any] = getattr(wl, "raw", {})
        containers = raw.get("containerArray") or []
        gpu_specs = raw.get("gpuSpecArray") or []

        # Build CODE lookup for GPU reverse-matching
        try:
            indexed = self.get_indexed_gpu_pricings(service_code=service_code)
        except Exception:
            indexed = []

        def _qs(v: Any) -> str:
            """Serialize a value for inline YAML (single-line, no document markers).

            yaml.dump appends '\\n...\\n' after scalar values (document-end marker).
            Removing it prevents ParserError when the output is later parsed as
            a single YAML document.
            """
            dumped = _yaml.dump(v, default_flow_style=True, allow_unicode=True)
            return dumped.replace("\n...\n", "\n").strip()

        lines: list[str] = [
            f"description: {_qs(raw.get('description', ''))}",
            f"cuda: {_qs(raw.get('cuda', ''))}"
            f'                             # optional — e.g. "12060" for CUDA 12.6',
            f"sharedMemory: {raw.get('sharedMemory', 1)}"
            f"                      # GB",
            "",
            "containers:",
        ]
        for ct in containers:
            envs = ct.get("containerEnvs") or []
            storages = ct.get("userStorages") or []
            lines += [
                f"  - containerImage: {ct.get('containerImage', '')}",
                f"    repo: {ct.get('repo', 'docker.io')}"
                f"                  # docker.io | ghcr.io | nvcr.io | quay.io | registry.hf.space",
                f"    port: {ct.get('port', 0)}",
                f"    maxConnection: {ct.get('maxConnection', 4)}",
                f"    containerCommand: {_qs(ct.get('containerCommand', ''))}",
                f"    isCredential: {'true' if ct.get('isCredential') else 'false'}",
                f"    containerEnvs: {_qs(envs)}",
                "    # containerEnvs:",
                "    #   - KEY: VALUE",
                f"    userStorages: {_qs(storages)}",
                '    # userStorages:',
                '    #   - "123": "/mnt/data"         # SER mount key — see: gcube storage list',
                '    #   - gcube: "/mnt/gcube-data"   # gcube storage — use literal key \'gcube\'',
            ]

        lines += ["", "gpuSpecs:"]
        for gs in gpu_specs:
            gpu_name = gs.get("gpu", "")
            gpu_count = gs.get("gpuCount", 1)
            tier = gs.get("tier", "")
            vram = gs.get("vram", "")
            cpu = gs.get("cpu", "")
            memory = gs.get("memory", "")
            disk = gs.get("disk", "")
            matched_code, matched_pricing = match_gpu_pricing(gs, indexed)
            display = re.sub(
                r"^NVIDIA GeForce |^NVIDIA ", "",
                matched_pricing.product_name,
            ) if matched_pricing and matched_pricing.product_name else gpu_name
            # The attributes below are reverse-matched at register time so reusing
            # this file redeploys the same GPU even after codes are renumbered.
            lines.append(
                f'  - gpuCode: "{matched_code}"'
                f"                    # {display or 'unknown'}"
                f" — change this (see 'gcube gpu list') to switch"
            )
            lines.append(f'    gpu: "{gpu_name}"')
            lines.append(f"    gpuCount: {gpu_count}")
            lines.append(f"    vram: {vram}")
            lines.append(f"    cpu: {cpu}")
            lines.append(f"    memory: {memory}")
            lines.append(f"    disk: {disk}")
            lines.append(f"    tier: {tier}")
        lines.append('  # more replicas: add \'- gpuCode: "NNN"\'')

        return "\n".join(lines) + "\n"

    def pods(self, ser: str) -> builtins.list[dict[str, Any]]:
        """List pods for a workload.

        ``GET /api/workloads/gai/{ser}``  (same as describe)
        Response envelope: ``{ workload: { pods: [...] } }``
        """
        data = self._client.get(f"{_GAI_BASE}{ser}")
        item: dict[str, Any] = data.get("workload", data.get("data", data))
        pods: builtins.list[dict[str, Any]] = item.get("pods") or []
        _fmt_pod_times(pods)
        return pods
