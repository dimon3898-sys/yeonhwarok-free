"""Workload subcommands for gcube CLI.

Implements PBI-007 (register), PBI-008 (list, describe),
PBI-009 (start, stop, delete), PBI-010 (logs, pods),
PBI-014 (update + camelCase unification).
"""

from __future__ import annotations

import contextlib
import json as _json
import math
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gcube_cli.api.ssh import SshInfo

import click
import yaml
from rich.console import Group
from rich.live import Live
from rich.text import Text

from gcube_cli._group import OrderedGroup
from gcube_cli.api._util import parse_server_dt
from gcube_cli.api.client import (
    APIError,
    AuthError,
    Client,
    decode_email_from_jwt,
    make_client_from_ctx,
)
from gcube_cli.api.sse import SSEAuthError, SSEClient, SSEConnectionError, SSEReadTimeout
from gcube_cli.api.user import UserAPI
from gcube_cli.api.workload import (
    _WEEKDAY_BITS,
    GpuPricing,
    ScheduleEntry,
    Workload,
    WorkloadAPI,
    is_gpu_available,
    match_gpu_pricing,
)
from gcube_cli.config.config import Config

# ---------------------------------------------------------------------------
# Deploy-state constants
# ---------------------------------------------------------------------------

IMAGE_DOWNLOAD_REASONS = {
    "pod_started",
    "image_pull_started",
    "image_pulling",
    "image_pull_retry",
}

STAGE_VM = 0
STAGE_NODE = 1
STAGE_DEPLOY_START = 2
STAGE_DEPLOY_DONE = 3

STAGE_NAMES = ["VM Provisioning", "Node Ready", "Image Pulling", "Container Start"]

REPLICA_DETAIL_THRESHOLD = 5
MAX_LOG_LINES = 5

# Fallback service port when it can't be determined (image not verified, or verified
# but no exposed port). Mirrors the web console, which defaults the port field to 8000.
DEFAULT_PORT = 8000

REASON_MESSAGES = {
    "image_pull_started": "Image pull started",
    "image_pulling": "Pulling image",
    "image_pull_retry": "Image pull retry",
    "image_pull_failed": "Image pull failed",
    "container_started": "Container started",
    "container_restarted": "Container restarted",
    "container_stopped": "Container stopped",
    "pod_started": "Pod scheduled",
    "pod_terminated": "Pod terminated",
    # Pod-level diagnostics from the SSE spec's expanded Reason table (2026-05).
    # See POD_PROGRESS_REASONS for why these are NOT treated as progress.
    "pod_scheduling_failed": "Pod scheduling failed",
    "pod_nodenotready": "Node not ready",
    "pod_failedmount": "Volume mount failed",
    "pod_backoff": "Container restart back-off",
    "pod_evicted": "Pod evicted (node resource pressure)",
    "pod_failedcreate": "Pod creation failed",
    "pod_tainttoleration": "Node taint not tolerated",
    "pod_nodeaffinity": "Node affinity not satisfied",
    "pod_failed": "Pod failed",
    "pod_exceededgraceperiod": "Termination grace period exceeded",
    "pod_failedkillpod": "Failed to terminate pod",
    "pod_inspectfailed": "Container runtime inspect failed",
    "pod_failedtoretrieveimagepullsecret": "Failed to retrieve image pull secret",
    "pod_unexpectedadmissionerror": "Admission validation error",
    "pod_failedpoststarthook": "Container post-start hook failed",
    "pod_taintmanagereviction": "Evicted by node taint policy change",
    "pod_provisioningfailed": "Storage provisioning failed",
    "pod_failedtoupdateendpointslices": "Failed to update service endpoints",
}

# Reasons that mean the deploy moved forward into the container-start stage. Only
# these advance STAGE_DEPLOY_START/DONE. Anything else (the expanded pod_* diagnostics
# above — scheduling/resource/storage/runtime problems) is surfaced as a warning log
# line WITHOUT advancing the stages, so a failure event can't be mistaken for progress.
# Listing progress reasons (rather than enumerating every diagnostic) also keeps the
# VRAM reason — whose exact key is uncertain in the spec — and any future reason on the
# safe side: unknown ⇒ diagnostic, not progress.
CONTAINER_PROGRESS_REASONS = {
    "container_started",
    "container_restarted",
    "container_stopped",
    "pod_terminated",
}

_SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


# ---------------------------------------------------------------------------
# Deploy state data model
# ---------------------------------------------------------------------------


@dataclass
class ReplicaStage:
    stages: list[str] = field(
        default_factory=lambda: ["pending", "pending", "pending", "pending"]
    )

    def current_stage_index(self) -> int:
        """Highest stage index that has progressed (non-pending), or -1 if none."""
        current = -1
        for i, s in enumerate(self.stages):
            if s != "pending":
                current = i
        return current

    def displayed_stages(self) -> list[str]:
        """Stages with front-end inference applied.

        A higher stage being active implies every lower stage already completed —
        vm/node events may never arrive for tier2/3 workloads, but reaching the
        deploy stage means node provisioning finished. Matches the web console:
        `i < current → 'done'` (deploy-status-section.tsx). Only stages strictly
        below the current one are coerced to "done"; the current stage keeps its
        real state (running/error/done).
        """
        current = self.current_stage_index()
        return ["done" if i < current else s for i, s in enumerate(self.stages)]


@dataclass
class DeployState:
    replica_count: int
    container_count: int
    images: list[str] = field(default_factory=list)  # container image names (for stage display)
    replicas: list[ReplicaStage] = field(init=False)
    started_slots: list[list[bool]] = field(init=False)
    done_count: int = field(default=0, init=False)
    recent_logs: list[str] = field(default_factory=list, init=False)
    is_done: bool = field(default=False, init=False)
    is_failed: bool = field(default=False, init=False)
    fail_reason: str = field(default="", init=False)
    deploy_progress: list[int] = field(default_factory=list, init=False)  # per-replica download %
    # podName → replica slot, assigned in first-seen order (see _slot_for_pod)
    pod_slots: dict[str, int] = field(default_factory=dict, init=False)
    # Server timestamp of the event currently being processed (set in update()), so
    # _add_log stamps log lines with the platform's time instead of the local clock.
    _current_ts: str | None = field(default=None, init=False)
    # Local HH:MM:SS at which each stage reached "done" (replica 0 timeline), shown
    # next to the stage in the single-replica detail view. Stamped once per stage.
    stage_done_time: list[str | None] = field(
        default_factory=lambda: [None, None, None, None], init=False
    )
    # Server timestamps for the final result: when this deployment was created
    # (depCreatedAt, first seen) and when it finished (timestamp of the is_done event).
    deploy_started_ts: str | None = field(default=None, init=False)
    done_ts: str | None = field(default=None, init=False)
    # Optional callback invoked by _add_log with (local_time, message) — used by the
    # non-interactive (plain) watch path to stream each event line immediately. None in
    # the Live dashboard path, which renders from recent_logs on its own refresh tick.
    log_sink: Callable[[str, str], None] | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.replicas = [ReplicaStage() for _ in range(max(self.replica_count, 1))]
        cc = max(self.container_count, 1)
        self.started_slots = [[False] * cc for _ in range(max(self.replica_count, 1))]
        self.deploy_progress = [-1] * max(self.replica_count, 1)

    @property
    def use_aggregate_view(self) -> bool:
        return self.replica_count > REPLICA_DETAIL_THRESHOLD

    def update(self, event: Any) -> None:
        d = event.data
        self._current_ts = d.get("timestamp")
        event_type = d.get("eventType")
        raw_replica = d.get("replica", 0)

        if event_type == "vm":
            self._handle_vm(d, self._clamp(int(raw_replica) if raw_replica is not None else 0))
        elif event_type == "node":
            self._handle_node(d, self._clamp(int(raw_replica) if raw_replica is not None else 0))
        elif event_type == "workload":
            # workload 이벤트의 replica는 string 타입 (프론트 parseInt 처리와 동일)
            self._handle_workload(d, self._clamp(int(d.get("replica", 0))))
        elif "replicas" in d:
            self._handle_snapshot(d)

        dep_created = d.get("depCreatedAt")
        if dep_created and self.deploy_started_ts is None:
            self.deploy_started_ts = dep_created
        self._record_stage_done_times()
        if self.is_done and self.done_ts is None:
            self.done_ts = self._current_ts

    def _record_stage_done_times(self) -> None:
        """Stamp the server time each stage reached "done" (replica 0 timeline).

        Uses displayed_stages so stages inferred-done (vm/node skipped on tier2/3, or
        a fast snapshot completing several at once) are stamped with the timestamp of
        the event that advanced the deploy. Falls back to the local clock when the
        triggering event carried no timestamp (e.g. Format B snapshots). Stamped once
        per stage — the first time it shows done.
        """
        for i, s in enumerate(self.replicas[0].displayed_stages()):
            if s == "done" and self.stage_done_time[i] is None:
                self.stage_done_time[i] = self._fmt_event_time(self._current_ts)

    def _clamp(self, r: int) -> int:
        return max(0, min(r, len(self.replicas) - 1))

    def _handle_vm(self, d: dict[str, Any], r: int) -> None:
        stages = self.replicas[r].stages
        # VM activation can transiently fail on tier3/PC nodes (e.g. "pc offline") and the
        # server retries on another node — this is NOT terminal. Surface it on the stage and
        # in the log, but keep the connection alive (same pattern as image_pull_failed).
        if d.get("state") == "fail":
            stages[STAGE_VM] = "error"
            self._add_log(f"{d.get('failMessage') or 'VM activation failed'} — retrying...")
            return
        if stages[STAGE_VM] != "done":
            stages[STAGE_VM] = "running"
        if d.get("step") == 3:
            stages[STAGE_VM] = "done"

    def _handle_node(self, d: dict[str, Any], r: int) -> None:
        stages = self.replicas[r].stages
        sub = d.get("subState")
        # Node join failure / timeout is also transient on PC nodes (retried, not terminal).
        if sub in ("joinfail", "timeout"):
            stages[STAGE_NODE] = "error"
            self._add_log(f"{d.get('failMessage') or 'Node join failed'} — retrying...")
            return
        if stages[STAGE_NODE] != "done":
            stages[STAGE_NODE] = "running"
        if sub == "join":
            stages[STAGE_NODE] = "done"

    def _handle_workload(self, d: dict[str, Any], r: int) -> None:
        # NOTE: Format A 이벤트의 `state` 필드는 워크로드 DB 상태 컬럼을 그대로 echo한 값
        # (재배포 시 항상 "finish" 등)으로, 현재 배포의 진행/종료 신호가 아니다.
        # 따라서 진행은 `reason`으로만 판단하고, 종료/실패는 Format B 스냅샷(completed/error)과
        # container_started 카운팅이 담당한다. (gcube-sse-2525.log로 확인)
        reason = d.get("reason", "")

        # image_pull_failed: 서버 내부 재시도 중 → 연결 유지 (reason만으로 판단)
        if reason == "image_pull_failed":
            self.replicas[r].stages[STAGE_DEPLOY_START] = "error"
            self._add_log("Image pull failed — retrying...")
            return

        if reason in IMAGE_DOWNLOAD_REASONS:
            stages = self.replicas[r].stages
            if stages[STAGE_DEPLOY_START] not in ("done", "error"):
                stages[STAGE_DEPLOY_START] = "running"
            if reason == "image_pulling":
                self._set_deploy_progress(r, d)
            self._add_log(self._reason_msg(reason, d))
        elif reason in CONTAINER_PROGRESS_REASONS:
            stages = self.replicas[r].stages
            if stages[STAGE_DEPLOY_START] != "done":
                stages[STAGE_DEPLOY_START] = "done"
            if stages[STAGE_DEPLOY_DONE] != "done":
                stages[STAGE_DEPLOY_DONE] = "running"
            self._add_log(self._reason_msg(reason, d))

            if reason == "container_started" and self.replica_count <= 1:
                # Format A always reports replica=0 (pod identity lives only in podName),
                # so per-replica container counting from Format A is reliable only for a
                # single replica. Multi-replica completion is driven by Format B snapshots.
                self._mark_container_started(r, int(d.get("containerIndex") or 0))
        elif reason:
            # Pod-level diagnostic (scheduling / resource / storage / runtime problem).
            # Non-terminal: the platform keeps retrying and a terminal verdict still
            # arrives only via a Format B `state=error` snapshot. Surface it as a warning
            # log line and leave the stages untouched so it isn't read as forward progress.
            self._add_log(self._diagnostic_msg(reason, d))

    def _mark_container_started(self, r: int, c: int) -> None:
        """Record that replica r's container c has started (idempotent).

        Increments done_count only on the False→True transition, marks the replica's
        deploy stages done once all its app containers have started, and flips is_done
        when every (replica, container) slot has started — the container_started
        completion fallback for when Format B `completed` never arrives.
        """
        cc = max(self.container_count, 1)
        if not (0 <= r < len(self.started_slots) and 0 <= c < cc):
            return
        if not self.started_slots[r][c]:
            self.started_slots[r][c] = True
            self.done_count += 1
        stages = self.replicas[r].stages
        if all(self.started_slots[r]):
            stages[STAGE_DEPLOY_START] = "done"
            stages[STAGE_DEPLOY_DONE] = "done"
        if self.done_count >= self.replica_count * cc:
            for rep in self.replicas:
                rep.stages[STAGE_DEPLOY_DONE] = "done"
            self.is_done = True

    def _mark_failed(self, message: str) -> None:
        """Mark the deploy as terminally failed. Only Format B `state=error` triggers this
        (vm/node/image_pull failures are transient and handled inline). `message` is shown
        to the user when non-empty; Format B error carries no detail, so it stays empty and
        the caller prints a generic "check web console" message."""
        self.is_failed = True
        self.fail_reason = message
        self.is_done = True

    def _slot_for_pod(self, pod: str) -> int | None:
        """Map a podName to a stable replica slot using first-seen order.

        Snapshot `replicas[]` ordering does not match Format A event arrival order
        (gcube-sse-2463.log: snapshot is sorted, events arrive unsorted), so the array
        index can't be used directly. Slots are assigned in the order pods are first
        encountered. Extra pods beyond replica_count are ignored (returns None).
        """
        if pod in self.pod_slots:
            return self.pod_slots[pod]
        slot = len(self.pod_slots)
        if slot >= len(self.replicas):
            return None
        self.pod_slots[pod] = slot
        return slot

    def _handle_snapshot(self, d: dict[str, Any]) -> None:
        snap_state = d.get("state")
        if snap_state == "completed":
            for rep in self.replicas:
                for i in range(4):
                    rep.stages[i] = "done"
            self.is_done = True
            return
        if snap_state == "error":
            # No per-replica detail in the snapshot → generic message (fail_reason left empty).
            self._mark_failed("")
            return

        # state=inProgress (or any other in-flight snapshot): Format B is the authoritative
        # per-replica source — Format A can't distinguish pods (replica is always 0).
        for entry in d.get("replicas") or []:
            pod = entry.get("pod", "")
            slot = self._slot_for_pod(pod) if pod else None
            if slot is None:
                continue
            stages = self.replicas[slot].stages
            for ct in entry.get("containers") or []:
                name = ct.get("name", "")
                if name == "istio-proxy":
                    # sidecar — not part of describe's container_array, so not counted
                    continue
                status = (ct.get("state") or {}).get("status", "")
                if status == "started":
                    self._mark_container_started(slot, _container_index(name))
                elif status and stages[STAGE_DEPLOY_START] not in ("done", "error"):
                    # pulling / PodInitializing / waiting → image download in progress
                    stages[STAGE_DEPLOY_START] = "running"

    def stage_counts(self) -> list[int]:
        """Return count of 'done' replicas per stage (for aggregate view).

        Uses displayed_stages() so lower stages inferred-done are counted too,
        keeping the aggregate progress bars consistent with the detail views.
        """
        counts = [0, 0, 0, 0]
        for rep in self.replicas:
            for i, s in enumerate(rep.displayed_stages()):
                if s == "done":
                    counts[i] += 1
        return counts

    def _set_deploy_progress(self, r: int, d: dict[str, Any]) -> None:
        """Store download % for a replica. Server sends downloadProgress as a string
        with decimals (e.g. "95.0"), so parse via float before int."""
        pct = _parse_progress(d.get("downloadProgress"))
        if pct is not None:
            self.deploy_progress[r] = pct

    def _reason_msg(self, reason: str, d: dict[str, Any]) -> str:
        if reason == "image_pulling":
            pct = _parse_progress(d.get("downloadProgress"))
            if pct is not None:
                return f"Pulling image ({pct}%)"
        return REASON_MESSAGES.get(reason, reason)

    def _diagnostic_msg(self, reason: str, d: dict[str, Any]) -> str:
        """Build a warning log line for a pod diagnostic reason.

        Falls back to the raw reason for keys not in REASON_MESSAGES (e.g. the spec's
        VRAM/out-of-resource reason, whose exact key is uncertain), so the user always
        sees something actionable. The "— retrying..." suffix mirrors the vm/node and
        image_pull_failed lines, signalling the event is non-terminal.
        """
        text = REASON_MESSAGES.get(reason)
        if text is None and reason.startswith("pod_outof"):
            text = "GPU/resource capacity exceeded"
        return f"{text or reason} — retrying..."

    def _add_log(self, msg: str) -> None:
        # No replica label: event logs come from Format A, whose `replica` is always 0,
        # so a "[replica-N]" prefix would be misleading. Per-replica progress lives in
        # the stage view (driven by Format B), not the log lines.
        ts = self._fmt_event_time(self._current_ts)
        self.recent_logs.insert(0, f"  {ts}  {msg}")
        self.recent_logs = self.recent_logs[:MAX_LOG_LINES]
        if self.log_sink is not None:
            self.log_sink(ts, msg)

    def result(self, ser: str) -> dict[str, Any]:
        """Machine-readable terminal result of the deploy (for ``-o json``/``yaml``).

        Times are the server's own timestamps (``depCreatedAt`` → the is_done event),
        so the duration is the real elapsed time regardless of when the CLI attached.
        """
        status = "failed" if self.is_failed else ("success" if self.is_done else "incomplete")
        return {
            "ser": _ser_value(ser),
            "status": status,
            "startedAt": self.deploy_started_ts,
            "completedAt": self.done_ts,
            "durationSec": _duration_seconds(self.deploy_started_ts, self.done_ts),
            "failReason": (self.fail_reason or None) if self.is_failed else None,
        }

    @staticmethod
    def _fmt_event_time(raw: str | None) -> str:
        """Format a server event timestamp as local HH:MM:SS.

        Both server shapes (naive UTC and ISO-8601 with offset) are handled by
        ``parse_server_dt``. Falls back to the local clock when the field is
        missing or unparseable (e.g. Format B snapshots carry no timestamp, but
        they emit no log lines anyway).
        """
        dt = parse_server_dt(raw)
        if dt is not None:
            return dt.astimezone().strftime("%H:%M:%S")
        return datetime.now().strftime("%H:%M:%S")


# ---------------------------------------------------------------------------
# Rich rendering helpers
# ---------------------------------------------------------------------------


def _ser_value(ser: str) -> int | str:
    """SER as an int when numeric (cleaner JSON), otherwise the raw string."""
    return int(ser) if str(ser).isdigit() else ser


def _emit_result(output: str, result: dict[str, Any]) -> None:
    """Print a single machine-readable deploy result object for ``-o json``/``yaml``."""
    if output == "yaml":
        from gcube_cli.output.yaml_out import print_yaml

        print_yaml(result)
    else:
        from gcube_cli.output.json_out import print_json

        print_json(result)


def _duration_seconds(start_raw: str | None, done_raw: str | None) -> int | None:
    """Whole seconds between two server timestamps, or None if either is missing.

    Clamped to >= 0 so clock skew between events never yields a negative duration.
    """
    start, done = parse_server_dt(start_raw), parse_server_dt(done_raw)
    if start is None or done is None:
        return None
    return max(0, int((done - start).total_seconds()))


def _container_index(name: str) -> int:
    """Extract the app container index from a snapshot container name.

    App containers are named ``dep{ser}-{index}`` (e.g. "dep2540-0"); the trailing
    number is the 0-based container index. Falls back to 0 if no suffix is present.
    """
    m = re.search(r"-(\d+)$", name)
    return int(m.group(1)) if m else 0


def _parse_progress(raw: Any) -> int | None:
    """Parse a downloadProgress value (server sends a string like "95.0") to int %.

    Returns None for missing/blank/unparseable values so callers leave state untouched.
    """
    if raw is None or raw == "":
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def _spin() -> str:
    return _SPINNER[int(time.monotonic() * 4) % len(_SPINNER)]


def _stage_icon(s: str) -> str:
    if s == "done":
        return "[green]✓[/green]"
    if s == "running":
        return f"[cyan]{_spin()}[/cyan]"
    if s == "error":
        return "[yellow]![/yellow]"
    return " "


class _LiveView:
    """Wrapper whose __rich__ recomputes _render(state) on every Live refresh tick.

    Rich's Live accepts an object with __rich__ and re-renders it at refresh_per_second,
    so the spinner animates and stage transitions appear without per-event live.update().
    """

    def __init__(self, state: DeployState) -> None:
        self.state = state

    def __rich__(self) -> Any:
        return _render(self.state)


def _render(state: DeployState) -> Any:
    lines: list[Any] = []

    if state.use_aggregate_view:
        # Large-scale (>5 replicas): a single completed-count line, not per-stage bars.
        # What matters at scale is "how many are up"; per-replica stage tracking depends
        # on Format B snapshots anyway (Format A replica is always 0).
        done = state.stage_counts()[STAGE_DEPLOY_DONE]
        if state.is_failed:
            verb = "Deploy failed"
        elif state.is_done:
            verb = "Deployed"
        else:
            verb = "Deploying..."
        lines.append(Text(f"  {verb}  {done}/{state.replica_count}"))
    elif state.replica_count == 1:
        stages = state.replicas[0].displayed_stages()
        for i, name in enumerate(STAGE_NAMES):
            icon = _stage_icon(stages[i])
            suffix = ""
            if i == STAGE_DEPLOY_START and stages[i] == "running":
                if state.images:
                    img = state.images[0]
                    suffix = f"  {img}"
                prog = state.deploy_progress[0] if state.deploy_progress else -1
                if prog >= 0:
                    suffix += f"  {prog}%"
            if stages[i] == "done" and state.stage_done_time[i]:
                suffix += f"  {state.stage_done_time[i]}"
            lines.append(Text.from_markup(f"  \\[{icon}] {name}{suffix}"))
    else:
        for r_idx, rep in enumerate(state.replicas):
            disp = rep.displayed_stages()
            stage_parts = "  ".join(
                f"\\[{_stage_icon(disp[i])}] {STAGE_NAMES[i]}" for i in range(4)
            )
            lines.append(Text.from_markup(f"  replica-{r_idx}  {stage_parts}"))

    # Fixed-height log section — always render MAX_LOG_LINES rows so Rich's height
    # measurement stays constant and cursor positioning never drifts.
    # Use " " (space) not "" because Text("") has measured height 0 in Rich.
    lines.append(Text(" "))
    lines.append(Text("  Recent events" if state.recent_logs else " "))
    for i in range(MAX_LOG_LINES):
        lines.append(Text(state.recent_logs[i] if i < len(state.recent_logs) else " "))

    return Group(*lines)


# ---------------------------------------------------------------------------
# Schedule helpers (PBI-021)
# ---------------------------------------------------------------------------

_WEEKDAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Lookup: lowercase name -> (index, bit)
_DAY_LOOKUP: dict[str, tuple[int, int]] = {}
for _i, _short in enumerate(_WEEKDAY_SHORT):
    _DAY_LOOKUP[_short.lower()] = (_i, _WEEKDAY_BITS[_i])

_DAY_ALIASES: dict[str, int] = {
    "daily": 127,
    "weekdays": 31,
    "weekend": 96,
}

# IANA zone prefixes with DST (simplified)
_DST_PREFIXES = ("America/", "Europe/", "Pacific/Auckland")

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _mask_to_weekday_label(mask: int) -> str:
    """Bitmask -> English label with range compression.

    127 -> 'daily', 0 -> 'once', 31 -> 'Mon-Fri', 21 -> 'Mon, Wed, Fri'.
    """
    if mask == 0:
        return "once"
    if mask == 127:
        return "daily"
    # Build ranges
    indexes = [i for i, bit in enumerate(_WEEKDAY_BITS) if mask & bit]
    ranges: list[tuple[int, int]] = []
    for idx in indexes:
        if ranges and ranges[-1][1] == idx - 1:
            ranges[-1] = (ranges[-1][0], idx)
        else:
            ranges.append((idx, idx))
    parts: list[str] = []
    for fr, to in ranges:
        if fr == to:
            parts.append(_WEEKDAY_SHORT[fr])
        else:
            parts.append(f"{_WEEKDAY_SHORT[fr]}-{_WEEKDAY_SHORT[to]}")
    return ", ".join(parts)


def _parse_days(value: str | int | list[str]) -> int:
    """Human day spec -> bitmask.

    Accepts:
    - list: ['Mon','Tue','Wed','Thu','Fri']
    - str range: 'Mon-Fri'
    - str csv: 'Mon,Wed,Fri'
    - alias: 'daily' / 'weekdays' / 'weekend'
    - raw int str: '31' (1~127)

    Raises click.BadParameter on invalid input.
    """
    # YAML may deliver an unquoted integer (e.g. days: 31)
    if isinstance(value, int):
        if 1 <= value <= 127:
            return value
        raise click.BadParameter(f"Day bitmask must be 1-127: {value}")

    if isinstance(value, list):
        mask = 0
        for name in value:
            key = str(name).strip().lower()
            if key not in _DAY_LOOKUP:
                raise click.BadParameter(f"Unknown day: {name}")
            mask |= _DAY_LOOKUP[key][1]
        if mask == 0:
            raise click.BadParameter("At least one day is required.")
        return mask

    text = value.strip()
    low = text.lower()

    # alias
    if low in _DAY_ALIASES:
        return _DAY_ALIASES[low]

    # raw integer
    if text.isdigit():
        n = int(text)
        if 1 <= n <= 127:
            return n
        raise click.BadParameter(f"Day bitmask must be 1-127: {text}")

    # range: Mon-Fri
    if "-" in text and "," not in text:
        parts = text.split("-", 1)
        start_key = parts[0].strip().lower()
        end_key = parts[1].strip().lower()
        if start_key not in _DAY_LOOKUP:
            raise click.BadParameter(f"Unknown day: {parts[0].strip()}")
        if end_key not in _DAY_LOOKUP:
            raise click.BadParameter(f"Unknown day: {parts[1].strip()}")
        si = _DAY_LOOKUP[start_key][0]
        ei = _DAY_LOOKUP[end_key][0]
        if ei < si:
            raise click.BadParameter(f"Invalid day range: {text}")
        mask = 0
        for i in range(si, ei + 1):
            mask |= _WEEKDAY_BITS[i]
        return mask

    # csv: Mon,Wed,Fri
    names = [n.strip() for n in text.split(",") if n.strip()]
    if names:
        mask = 0
        for name in names:
            key = name.lower()
            if key not in _DAY_LOOKUP:
                raise click.BadParameter(f"Unknown day: {name}")
            mask |= _DAY_LOOKUP[key][1]
        return mask

    raise click.BadParameter(f"Unrecognized day format: {text}")


def _is_valid_date(s: str) -> bool:
    """Check yyyy-MM-dd string is parseable."""
    if not _DATE_RE.match(s):
        return False
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _validate_schedule_entries(
    entries: list[Any],
) -> list[str]:
    """Client-side validation matching the extension.

    Returns a list of error messages. Empty == pass.
    Branch on date(one-time) vs no-date(repeat) FIRST, then apply
    branch-specific checks.
    """
    errors: list[str] = []
    for i, e in enumerate(entries, 1):
        # action
        if e.action not in ("START", "STOP"):
            errors.append(f"#{i}: action must be START or STOP")

        # time format
        if not _TIME_RE.match(e.time):
            errors.append(f"#{i}: invalid time format (expected HH:mm)")

        if e.date is not None:
            # -- one-time branch --
            if not _is_valid_date(e.date):
                errors.append(f"#{i}: invalid date format (expected yyyy-MM-dd)")
            if e.end_date is not None:
                errors.append(f"#{i}: endDate is not allowed for one-time schedules")
            if e.days_of_week != 0:
                errors.append(f"#{i}: days are not allowed for one-time schedules")
        else:
            # -- repeat branch --
            if e.days_of_week < 1 or e.days_of_week > 127:
                errors.append(f"#{i}: at least one day must be selected")
            if e.end_date is not None and not _is_valid_date(e.end_date):
                errors.append(f"#{i}: invalid endDate format (expected yyyy-MM-dd)")

    return errors


_API_ERROR_MAP: dict[str, str] = {
    "schedule date is past": "Schedule date is in the past. Please use a future date.",
    "schedule end date is past": "End date is in the past.",
}


def _friendly_api_error(e: APIError) -> str:
    """Map server error message to user-friendly Korean. Falls back to raw."""
    msg = (e.message or "").lower()
    for pattern, friendly in _API_ERROR_MAP.items():
        if pattern in msg:
            return friendly
    return f"API Error [{e.code}]: {e.message}"


def _expand_schedule_yaml(
    raw_list: list[dict[str, Any]],
) -> list[Any]:
    """Expand YAML schedule items (sugar or raw) into ScheduleEntry list.

    Sugar form (detected by 'start' or 'stop' key):
        {days: Mon-Fri, start: "09:00", stop: "18:00"}
        -> 2 entries: START 09:00 + STOP 18:00, same days/date/endDate/enabled

    Raw form (detected by 'action' + 'time' key):
        {action: START, time: "09:00", daysOfWeek: 31, enabled: true}
        -> 1 entry as-is. 'days' (list/str) also accepted instead of daysOfWeek.
    """
    entries: list[ScheduleEntry] = []
    for item in raw_list:
        enabled = item.get("enabled", True)
        date_val = item.get("date")
        end_date = item.get("endDate")

        # Resolve days_of_week from 'days' (human) or 'daysOfWeek' (raw)
        if "days" in item:
            mask = _parse_days(item["days"])
        elif "daysOfWeek" in item:
            try:
                mask = int(item["daysOfWeek"])
            except (TypeError, ValueError):
                raise click.BadParameter(
                    f"Invalid daysOfWeek value: {item['daysOfWeek']}"
                )
        elif date_val is not None:
            mask = 0  # one-time
        else:
            mask = 0

        is_sugar = "start" in item or "stop" in item

        if is_sugar:
            if "start" in item:
                entries.append(ScheduleEntry(
                    enabled=enabled, action="START", days_of_week=mask,
                    time=item["start"], date=date_val, end_date=end_date,
                ))
            if "stop" in item:
                entries.append(ScheduleEntry(
                    enabled=enabled, action="STOP", days_of_week=mask,
                    time=item["stop"], date=date_val, end_date=end_date,
                ))
        else:
            # raw form
            entries.append(ScheduleEntry(
                enabled=enabled,
                action=item.get("action", "START"),
                days_of_week=mask,
                time=item.get("time", ""),
                date=date_val,
                end_date=end_date,
            ))

    return entries


def _load_schedule_yaml(path: str) -> tuple[str, list[Any]]:
    """Load schedule YAML file -> (timezone, entries).

    Expected schema: {timezone: str, schedules: list[...]}
    timezone defaults to 'Asia/Seoul' if absent.
    """
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    tz = data.get("timezone") or data.get("timeZone") or "Asia/Seoul"
    raw_list = data.get("schedules", [])
    if not isinstance(raw_list, list):
        raise click.UsageError("YAML must contain a 'schedules' list.")
    return tz, _expand_schedule_yaml(raw_list)


class _ScheduleDumper(yaml.SafeDumper):
    """SafeDumper that quotes HH:mm strings consistently."""


def _represent_str(dumper: yaml.SafeDumper, data: str) -> Any:
    if _TIME_RE.match(data):
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="'")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_ScheduleDumper.add_representer(str, _represent_str)


def _dump_schedule_yaml(
    entries: list[Any],
    time_zone: str,
    *,
    header_comment: str = "",
) -> str:
    """Entries -> round-trip YAML string with timezone as a real key."""
    doc: dict[str, Any] = {
        "timezone": time_zone,
        "schedules": [e.to_yaml_dict() for e in entries],
    }
    body = yaml.dump(doc, Dumper=_ScheduleDumper, default_flow_style=False,
                     allow_unicode=True, sort_keys=False)
    if header_comment:
        return header_comment + body
    return body


def _lint_schedule_entries(
    entries: list[Any],
    time_zone: str,
) -> list[str]:
    """Emit warnings (not errors). Always shown on stderr."""
    warnings: list[str] = []

    actions = {e.action for e in entries}
    if "START" in actions and "STOP" not in actions:
        warnings.append(
            "Warning: No STOP schedule. "
            "The workload will not auto-stop and billing will continue."
        )

    # Detect same day+time collisions (action excluded — START+STOP at same time is also a conflict)
    seen: dict[tuple[int, str], int] = {}
    for i, e in enumerate(entries, 1):
        key = (e.days_of_week, e.time)
        if key in seen:
            warnings.append(
                f"Warning: #{seen[key]} and #{i} are scheduled at the same time."
            )
        else:
            seen[key] = i

    # DST warning
    if any(time_zone.startswith(p) for p in _DST_PREFIXES):
        has_repeat = any(e.date is None for e in entries)
        if has_repeat:
            warnings.append(
                f"Warning: {time_zone} observes DST. "
                "Scheduled times may shift by ±1 hour during transitions."
            )

    return warnings


def _print_schedule_table(
    entries: list[Any],
    time_zone: str,
    *,
    label: str = "",
) -> None:
    """Print schedule entries as a compact table."""
    if label:
        click.echo(label)
    has_end = any(e.end_date for e in entries)
    has_disabled = any(not e.enabled for e in entries)
    for i, e in enumerate(entries, 1):
        if e.date is not None:
            day_label = f"once({e.date})"
        else:
            day_label = _mask_to_weekday_label(e.days_of_week)
        line = f"  {i:>2}  {e.action:<5}  {e.time}  {day_label}"
        if has_end:
            line += f"  until {e.end_date or '-'}"
        if has_disabled:
            line += f"  {'ON' if e.enabled else 'OFF'}"
        click.echo(line)


def _show_schedule_logs(ctx: click.Context, ser: str, limit: int) -> None:
    """Fetch and display schedule execution history."""
    try:
        client = make_client_from_ctx(ctx)
        api = WorkloadAPI(client)
        output = ctx.obj.output

        log_entries, total = api.get_schedule_logs(ser, start_num=0, scale_num=limit)

        if output == "json":
            from gcube_cli.output.json_out import print_json

            print_json({"logs": log_entries, "total": total})
            return
        if output == "yaml":
            from gcube_cli.output.yaml_out import print_yaml

            print_yaml({"logs": log_entries, "total": total})
            return

        if not log_entries:
            click.echo("No execution history.")
            return

        # 테이블 헤더
        click.echo(f"Schedule Execution History (SER: {ser})")
        click.echo()
        click.echo(f"  {'Time':<22} {'Action':<7} {'Result':<9} Error")
        click.echo(f"  {'─' * 22} {'─' * 7} {'─' * 9} {'─' * 30}")
        for log in log_entries:
            t = log.get("strtDt") or "-"
            action = log.get("action", "")
            success = log.get("success", False)
            result_str = "Success" if success else "Fail"
            err = (log.get("errMsg") or "") if not success else ""
            click.echo(f"  {t:<22} {action:<7} {result_str:<9} {err}")

        if total > len(log_entries):
            click.echo()
            click.echo(
                f"Showing {len(log_entries)} of {total} entries."
                " Increase --limit to see more."
            )

    except AuthError as e:
        click.echo(str(e), err=True)
        sys.exit(3)
    except APIError as e:
        click.echo(f"API Error [{e.code}]: {e.message}", err=True)
        sys.exit(2)


# ---------------------------------------------------------------------------
# YAML skeleton template (camelCase — matches describe output and update input)
# ---------------------------------------------------------------------------

WORKLOAD_YAML_TEMPLATE = """\
description: ""                      # required (2-80 chars)
cuda: ""                             # optional — e.g. "12060" for CUDA 12.6
sharedMemory: 1                      # GB

containers:
  - containerImage: ""               # required
    repo: docker.io                  # docker.io | ghcr.io | nvcr.io | quay.io | registry.hf.space
    port: 0                          # 0 = auto-detect
    maxConnection: 4
    containerCommand: ""
    containerEnvs: []
    # containerEnvs:
    #   - KEY: VALUE
    userStorages: []
    # userStorages:
    #   - "123": "/mnt/data"         # SER-based (S3/drive) — MOUNT KEY from: gcube storage list
    #   - gcube: "/mnt/gcube-data"   # gcube storage — use literal key 'gcube'

gpuSpecs:
  - gpuCode: ""                      # required — run 'gcube gpu list' for CODE
  # add more entries for additional replicas:
  # - gpuCode: ""

# --- Schedule (set separately after register) ---
# gcube workload schedule <SER> -f schedule.yaml
# gcube workload schedule <SER> --days Mon-Fri --start 09:00 --stop 18:00
# Without a STOP schedule, the workload will not auto-stop and billing continues.
"""

# ---------------------------------------------------------------------------
# credential cloud 매핑
# ---------------------------------------------------------------------------

_REPO_TO_CLOUDS: dict[str, tuple[str, ...]] = {
    "docker.io": ("docker",),
    "ghcr.io": ("github",),
    "nvcr.io": ("nvidia",),           # 웹콘솔 크로스플랫폼 (CLI는 nvidia 크레덴셜 미지원)
    "quay.io": ("quay", "redhat"),     # CLI=quay, 웹콘솔=redhat
    "aws.ecr": ("aws",),
    "registry.hf.space": ("huggingface",),
}

# ---------------------------------------------------------------------------
# Register / update helpers
# ---------------------------------------------------------------------------


def _auto_detect_credentials(
    config: dict[str, Any],
    client: Client,
    owner: str,
) -> None:
    """Auto-detect isCredential by matching container repo against saved credentials.

    Behaviour per container:
    - ``"isCredential"`` key present (YAML / ``--credential`` / ``--no-credential``)
      → **skip** — the user's explicit intent is always honoured.
    - key absent → look up saved credentials and set True on match, leave absent
      otherwise (``_build_workload_body`` defaults absent to False).

    On lookup failure the config is left untouched — auto-detection is
    best-effort and must never block the deployment flow.
    """
    containers: list[dict[str, Any]] = config.get("containers") or []
    # 자동감지 대상: isCredential 키가 없는 컨테이너
    candidates = [ct for ct in containers if "isCredential" not in ct]
    if not candidates:
        return

    creds = _fetch_credentials_quiet(client, owner)
    if creds is None:
        return

    cloud_set = {c.cloud for c in creds}
    for ct in candidates:
        repo = ct.get("repo", "docker.io")
        matched_clouds = _REPO_TO_CLOUDS.get(repo, ())
        if any(c in cloud_set for c in matched_clouds):
            ct["isCredential"] = True


def _fetch_credentials_quiet(client: Client, owner: str) -> list[Any] | None:
    """Fetch credential list with short timeout, no retry, no stderr noise.

    Returns the credential list on success, or None on any failure.
    Uses ``Client.get_quiet()`` which reuses the shared httpx.Client —
    correct URL joining (trailing-slash safe), headers, and connection pool.
    """
    data = client.get_quiet(
        "/api/credential/list", params={"owner": owner},
    )
    if data is None:
        return None

    try:
        from gcube_cli.api.credential import Credential
        items = data.get("credentials", data.get("data", data.get("items", [])))
        return [Credential.from_dict(i) for i in items if isinstance(i, dict)]
    except Exception:
        return None


def _load_yaml_config(path: str) -> dict[str, Any]:
    """Load a workload YAML file and return its contents as a dict."""
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return dict(data)


def _build_from_flags(
    description: str | None,
    image: str | None,
    port: int | None,
    repo: str,
    gpu: str | None,
    is_credential: bool | None,
    cuda: str,
) -> dict[str, Any]:
    """Build a workload config dict from inline CLI flags (camelCase keys).

    When *is_credential* is None (default — neither ``--credential`` nor
    ``--no-credential`` given), the key is **omitted** so that auto-detection
    can fill it later.  Explicit True/False is preserved to honour the user's
    intent.
    """
    ct: dict[str, Any] = {
        "containerImage": image or "",
        "repo": repo,
        "port": port if port is not None else 0,
        "maxConnection": 4,
        "containerCommand": "",
        "containerEnvs": [],
    }
    if is_credential is not None:
        ct["isCredential"] = is_credential

    return {
        "description": description or "",
        "cuda": cuda,
        "sharedMemory": 1,
        "isIstioProxy": True,
        "isDeploy": False,
        "containers": [ct],
        "gpuSpecs": [
            {
                "gpuCode": gpu or "",
            }
        ],
    }


def _has_gpu_attrs(spec: dict[str, Any]) -> bool:
    """True when a gpuSpec carries reverse-matchable GPU attributes.

    These come from ``describe`` output (``gpu``/``vram``/…) and make the spec
    self-healing at register time. A bare hand-written ``gpuCode`` (no attributes)
    returns False and falls back to literal code lookup.
    """
    return bool(spec.get("gpu")) and spec.get("vram") is not None


def _validate_fields(config: dict[str, Any]) -> None:
    """Validate user-supplied fields locally. Prints error and exits 1 on failure."""
    desc: str = config.get("description") or ""
    if not desc:
        click.echo("Error: description is required", err=True)
        sys.exit(1)
    if len(desc) < 2 or len(desc) > 80:
        click.echo(
            f"Error: description must be 2-80 characters (got {len(desc)})",
            err=True,
        )
        sys.exit(1)

    cuda: str = str(config.get("cuda") or "")
    if cuda and not re.fullmatch(r"\d+", cuda):
        click.echo(
            f"Error: cuda '{cuda}' is invalid. Use a numeric code (e.g. \"12060\" for CUDA 12.6).",
            err=True,
        )
        sys.exit(1)

    shared_memory = config.get("sharedMemory", 1)
    try:
        sm_int = int(shared_memory)
    except (TypeError, ValueError):
        sm_int = -1
    if not (1 <= sm_int <= 80):
        click.echo(
            f"Error: sharedMemory must be 1-80 GB (got {shared_memory})",
            err=True,
        )
        sys.exit(1)

    containers: list[dict[str, Any]] = config.get("containers") or []
    if not containers:
        click.echo("Error: at least one container is required", err=True)
        sys.exit(1)
    for i, ct in enumerate(containers):
        if ct.get("containerImage"):
            ct["containerImage"] = ct["containerImage"].strip()
        if not ct.get("containerImage"):
            click.echo(f"Error: containers[{i}].containerImage is required", err=True)
            sys.exit(1)

    gpu_specs: list[dict[str, Any]] = config.get("gpuSpecs") or []
    if not gpu_specs:
        click.echo("Error: at least one gpuSpec is required", err=True)
        sys.exit(1)
    for i, spec in enumerate(gpu_specs):
        code = spec.get("gpuCode", "")
        if isinstance(code, int):
            # YAML parses unquoted leading-zero values as integers (octal in YAML 1.1).
            # e.g. gpuCode: 010 → 8 (octal), gpuCode: 001 → 1
            # Zero-pad integers so 1 → "001", 100 → "100", but warn about octal risk.
            code = f"{code:03d}"
            spec["gpuCode"] = code
        code = str(code)
        # gpuCode is optional when the spec carries GPU attributes: those are
        # reverse-matched to the current code at enrich time (see _resolve_gpu_pricing).
        if not code:
            if _has_gpu_attrs(spec):
                continue
            click.echo(f"Error: gpuSpecs[{i}].gpuCode is required", err=True)
            click.echo("Run 'gcube gpu list' to see available codes.", err=True)
            sys.exit(1)
        if not re.fullmatch(r"\d{3}", code):
            click.echo(
                f"Error: gpuSpecs[{i}].gpuCode '{code}' is invalid. "
                "Use a 3-digit code from 'gcube gpu list'.",
                err=True,
            )
            sys.exit(1)


def _resolve_gpu_pricing(
    spec: dict[str, Any],
    index: int,
    indexed: list[tuple[str, GpuPricing]],
    code_map: dict[str, GpuPricing],
) -> tuple[GpuPricing, str]:
    """Resolve a gpuSpec to its current pricing entry. Returns (pricing, code).

    Attribute-first: when the spec carries GPU attributes (gpu/vram/…), they are
    reverse-matched to the CURRENT code — this self-heals a stale ``gpuCode``
    after the pricing list is renumbered, so reusing an old file redeploys the
    same hardware without a separate 'update'.

    - attributes present, match found     → use resolved code; warn if it differs
                                            from the written gpuCode
    - attributes present, no match        → hard error (SKU no longer offered);
                                            never silently deploy a different GPU
    - attributes absent (bare gpuCode)    → legacy lookup by code

    Exits with code 1 on no-match / unknown code.
    """
    written_code = str(spec.get("gpuCode", "") or "")

    if _has_gpu_attrs(spec):
        code, pricing = match_gpu_pricing(spec, indexed)
        if pricing is None:
            click.echo(
                f"Error: gpuSpecs[{index}] "
                f"({spec.get('gpu')} tier{spec.get('tier')} {spec.get('vram')}GB) "
                "is no longer offered. Run 'gcube gpu list' and update the spec.",
                err=True,
            )
            sys.exit(1)
        if written_code and written_code != code:
            click.echo(
                f"Warning: gpuSpecs[{index}] gpuCode '{written_code}' now resolves "
                f"to '{code}' ({pricing.gpu_name}); using the current code.",
                err=True,
            )
        spec["gpuCode"] = code
        return pricing, code

    if written_code not in code_map:
        click.echo(
            f"GPU code '{written_code}' not found. "
            "Run 'gcube gpu list' to see available codes.",
            err=True,
        )
        sys.exit(1)
    return code_map[written_code], written_code


def _enrich_gpu_specs(
    config: dict[str, Any],
    api: WorkloadAPI,
    service_code: str | None = None,
) -> None:
    """Query pricing API, validate availability, and enrich gpuSpecs in place.

    Uses get_indexed_gpu_pricings() so CODE→GPU mapping is identical to 'gcube gpu list'.
    Each spec is resolved by _resolve_gpu_pricing() (attributes win over gpuCode).
    Raises APIError if the pricing API call fails (propagates to exit 2).
    Calls sys.exit(1) if a spec cannot be resolved or the GPU is unavailable.
    """
    _tier_map: dict[str, int] = {"tier1": 1, "tier2": 2, "tier3": 3}
    _target_map: dict[str, str] = {"tier1": "csp", "tier2": "svr", "tier3": "pc"}

    if service_code:
        click.echo(f"Using serviceCode={service_code}", err=True)

    # may raise APIError → propagates
    indexed = api.get_indexed_gpu_pricings(service_code=service_code)
    code_map: dict[str, GpuPricing] = dict(indexed)

    gpu_specs: list[dict[str, Any]] = config.get("gpuSpecs") or []
    for i, spec in enumerate(gpu_specs):
        matched, gpu_code = _resolve_gpu_pricing(spec, i, indexed, code_map)

        if not is_gpu_available(matched):
            display = matched.product_name or matched.gpu_name
            click.echo(
                f"GPU code '{gpu_code}' ({display} "
                f"{matched.product_code} {matched.vram}GB) is not available. "
                "Run 'gcube gpu list' to see available GPUs.",
                err=True,
            )
            sys.exit(1)

        # Convert USD prices to KRW if needed (backend expects KRW)
        price = matched.price
        usage_price = matched.usage_price
        if matched.currency_unit == "USD":
            if "_krw_rate" not in config:
                try:
                    pb = api.get_point_base()
                    config["_krw_rate"] = int(pb.get("krw", 0))
                except Exception:
                    config["_krw_rate"] = 0
            krw_rate = config["_krw_rate"]
            if krw_rate > 0:
                price = round(price * krw_rate)
                usage_price = round(usage_price * krw_rate)

        max_price = round(price + usage_price)
        spec["_gpu_name"] = matched.gpu_name   # API body의 "gpu" 필드에 사용
        spec["_gpu_ext"] = matched.gpu_ext
        spec["_pp_index"] = matched.pp_index
        spec["_tier"] = _tier_map.get(matched.product_code, 0)
        spec["_target"] = _target_map.get(matched.product_code, "any")
        spec["_gpu_count"] = matched.gpu or 1  # pricing.gpu = 해당 스펙의 GPU 수량
        spec["_vram"] = matched.vram
        spec["_cpu"] = matched.cpu
        spec["_memory"] = matched.memory
        spec["_disk"] = matched.disk
        spec["_max_price"] = max_price
        spec["_price"] = math.ceil(max_price * 0.75)

    # sharedMemory must be less than minimum VRAM across all gpuSpecs
    vram_values = [s.get("_vram", 0) for s in gpu_specs if s.get("_vram", 0) > 0]
    if vram_values:
        min_vram = min(vram_values)
        shared_memory = int(config.get("sharedMemory", 1))
        if shared_memory >= min_vram:
            click.echo(
                f"Error: sharedMemory ({shared_memory} GB) must be less than "
                f"GPU VRAM ({min_vram} GB)",
                err=True,
            )
            sys.exit(1)


# The verify API sometimes returns its message as an i18n key (e.g.
# "error.message.not.found.tag") instead of a sentence. Humanize the documented keys;
# `manifests.404` is an observed variant that does not match the doc's
# "error.not.found.manifest" — mapped from real output, not the spec.
_VERIFY_ERROR_MESSAGES = {
    "error.message.not.found.tag": "image tag not found",
    "error.not.found.manifest": "image manifest not found",
    "error.message.manifests.404": "image manifest not found",
    "error.not.found.config": "image config not found",
    "error.message.not.found.exposed.ports": "could not detect the image's exposed port",
    "error.message.access.token": "registry authentication failed (check the credential)",
}


def _humanize_verify_error(message: str) -> str:
    """Map a known image-verification error key to readable text; pass through otherwise."""
    return _VERIFY_ERROR_MESSAGES.get(message, message)


def _proceed_past_failure(assume_yes: bool, prompt: str) -> bool:
    """Decide whether to continue past an advisory (non-fatal) failure.

    Mirrors the web console, where a failed image verification warns but lets the
    user create the workload anyway. Translated to a CLI:
      - ``-y/--yes`` given        → proceed without asking
      - interactive TTY           → prompt ``[y/N]`` (default No)
      - non-interactive, no ``-y`` → refuse (safe default for scripts/CI)
    """
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        click.echo("  Re-run with -y to register anyway.", err=True)
        return False
    return click.confirm(prompt, default=False)


def _verify_images(
    config: dict[str, Any],
    api: WorkloadAPI,
    owner: str,
    previous_containers: list[dict[str, Any]] | None = None,
    assume_yes: bool = False,
) -> None:
    """Verify container images and auto-detect port when port is 0.

    When ``previous_containers`` is provided (update flow), containers whose
    ``containerImage`` is unchanged are skipped — the previous port is carried
    over if the new config has port 0.

    Image verification is advisory: a failure warns (with a credential-aware
    hint) and then asks whether to proceed (or honors ``assume_yes``). If the
    user proceeds, the port can no longer be auto-detected, so an explicit
    ``port`` is then required; otherwise this exits 1.
    """
    containers: list[dict[str, Any]] = config.get("containers") or []
    for i, container in enumerate(containers):
        prev = (previous_containers or [])[i] if previous_containers and i < len(previous_containers) else None
        if prev and prev.get("containerImage") == container.get("containerImage"):
            if not container.get("port") and prev.get("port"):
                container["port"] = prev["port"]
            container["_valid"] = "success"
            continue

        repo = container.get("repo", "docker.io")
        try:
            resp = api.verify_image(
                owner=owner,
                repo=repo,
                container_image=container["containerImage"],
                is_credential=bool(container.get("isCredential", False)),
            )
        except APIError as e:
            click.echo(
                f"Image verification failed for container[{i}]: "
                f"{container['containerImage']} ({repo})",
                err=True,
            )
            click.echo(f"  {_humanize_verify_error(e.message)}", err=True)
            click.echo("  Common causes:", err=True)
            click.echo("    - wrong image name or tag", err=True)
            if container.get("isCredential"):
                click.echo(
                    "    - private registry — check the saved credential: "
                    "gcube credential list",
                    err=True,
                )
            else:
                click.echo(
                    "    - private registry — register a credential: "
                    "gcube credential create ...",
                    err=True,
                )
            click.echo("    - registry unreachable", err=True)
            if not _proceed_past_failure(
                assume_yes, "Register anyway despite failed verification?"
            ):
                click.echo("Aborted.", err=True)
                sys.exit(1)
            container["_valid"] = "fail"
            # Proceeding despite failure: the verify response is unavailable, so the
            # port can't be auto-detected — fall back to the default (web parity).
            if not container.get("port"):
                container["port"] = DEFAULT_PORT
                click.echo(
                    f"  Port not determined (verification failed); defaulting to {DEFAULT_PORT}. "
                    "Set 'port' explicitly if your service uses a different port.",
                    err=True,
                )
            continue

        if not container.get("port"):
            port_str = resp.get("exposedPort") or (
                resp.get("data") or {}
            ).get("port", "")
            m = re.search(r"(\d+)", str(port_str))
            if m:
                container["port"] = int(m.group(1))
            else:
                container["port"] = DEFAULT_PORT
                click.echo(
                    f"container[{i}]: port not detected; defaulting to {DEFAULT_PORT}. "
                    "Set 'port' explicitly if your service uses a different port.",
                    err=True,
                )
        container["_valid"] = "success"


def _build_workload_body(
    config: dict[str, Any], owner: str, ser: int = 0, team_id: int = 0
) -> dict[str, Any]:
    """Assemble the workload request body for register (POST) or update (PUT).

    gpuSpecs is a flat array; each entry gets a 1-based sequential ``replica`` index.
    ``ser=0`` for new registrations; pass the actual SER for updates.

    ``team_id`` adds ``teamId`` to the body when non-zero.  ``owner`` stays the
    caller's own email either way — the server swaps it for the team's virtual
    account (``team-{id}@team.gcube.internal``) on the way in, so the CLI must
    not try to synthesise that address itself.
    """
    gpu_specs: list[dict[str, Any]] = config.get("gpuSpecs") or []
    containers: list[dict[str, Any]] = config.get("containers") or []

    total_max_price = sum(int(s.get("_max_price", 0)) for s in gpu_specs)

    gpu_specs_out: list[dict[str, Any]] = []
    for i, spec in enumerate(gpu_specs):
        gpu_specs_out.append({
            "replica": i + 1,
            "target": spec.get("_target", "any"),
            "tier": spec.get("_tier", 0),
            "gpu": spec.get("_gpu_name", ""),  # gpuCode로 조회한 pricing의 gpuName
            "gpuExt": spec.get("_gpu_ext", ""),
            "ppIndex": spec.get("_pp_index", 1),
            "gpuCount": int(spec.get("_gpu_count", 1)),
            "vram": spec.get("_vram", 0),
            "cpu": spec.get("_cpu", 0),
            "memory": spec.get("_memory", 0),
            "disk": spec.get("_disk", 0),
            "price": spec.get("_price", 0),
            "maxPrice": spec.get("_max_price", 0),
            "vramSlider": spec.get("_vram", 0),
            "selectGpu": "",
            "isAvailableGpuList": False,
        })

    containers_out: list[dict[str, Any]] = []
    for ct in containers:
        envs: list[dict[str, Any]] = ct.get("containerEnvs") or []
        containers_out.append(
            {
                "repo": ct.get("repo", "docker.io"),
                "containerImage": ct["containerImage"],
                "containerCommand": ct.get("containerCommand", ""),
                "containerEnvs": envs,
                "userStorages": [
                    {str(k): v for k, v in s.items()}
                    for s in (ct.get("userStorages") or [])
                    if isinstance(s, dict)
                ],
                "port": int(ct.get("port", 0)),
                "maxConnection": int(ct.get("maxConnection", 4)),
                "isCredential": bool(ct.get("isCredential", False)),
                "isValidImageUrl": ct.get("_valid", "success"),
            }
        )

    body: dict[str, Any] = {
        "ser": ser,
        "owner": owner,
        "description": config.get("description", ""),
        "category": "infer",
        "cuda": config.get("cuda", ""),
        "sharedMemory": int(config.get("sharedMemory", 1)),
        "isIstioL7Hash": bool(config.get("isIstioL7Hash", False)),
        "isIstioProxy": bool(config.get("isIstioProxy", True)),
        "isDeploy": bool(config.get("isDeploy", False)),
        "isDedicated": bool(config.get("isDedicated", False)),
        "replica": len(gpu_specs_out),
        "maxPrice": total_max_price,
        "containers": containers_out,
        "gpuSpecs": gpu_specs_out,
    }
    if team_id:
        body["teamId"] = team_id
    return body





def _hint(message: str) -> None:
    """Print a dimmed next-step hint to stderr, only when stderr is a TTY.

    Hints suggest the likely next command. They go to stderr (never stdout) so
    machine-parseable values like ``SER: 2540`` stay clean, and are suppressed
    when output is piped/redirected (e.g. CI) so scripts see no noise.
    """
    if not sys.stderr.isatty():
        return
    click.echo(click.style(f"→ {message}", dim=True), err=True)


# ---------------------------------------------------------------------------
# Team context (PBI-023)
#
# There is no persisted default team — context comes from ``--team`` or the
# ``GCUBE_TEAM`` env var, both visible at the call site.  See PBI-023 §10.
# ---------------------------------------------------------------------------


def resolve_list_scope(
    ctx: click.Context,
    explicit_team: int | None,
    personal: bool,
) -> dict[str, str]:
    """Build the team filter query params for ``workload list``.

    Three distinct server states, so an empty dict is meaningful and must not
    be collapsed into ``teamId=0``:

    - ``{}``                     → unified view (personal + every team)
    - ``{"personalOnly": ...}``  → personal only
    - ``{"teamId": ...}``        → that one team

    Values are strings because ``WorkloadAPI.list()`` types its params as
    ``dict[str, str]`` and stringifies everything else the same way.
    """
    if explicit_team is not None and personal:
        click.echo("--team and --personal are mutually exclusive.", err=True)
        sys.exit(1)
    if personal:
        return {"personalOnly": "true"}
    if explicit_team is not None:
        return {"teamId": str(explicit_team)}
    tid: int = ctx.obj.team_id          # GCUBE_TEAM, 0 when unset
    return {"teamId": str(tid)} if tid else {}


def resolve_team_id(ctx: click.Context, explicit_team: int | None) -> int:
    """Resolve the team context for mutating commands. 0 means personal.

    Priority: ``--team`` > ``GCUBE_TEAM`` > personal.
    """
    if explicit_team is not None:
        return explicit_team
    team_id: int = ctx.obj.team_id
    return team_id


def _announce_team_context(team_id: int) -> None:
    """Tell the user which team a resource is being created in.

    Unconditional (unlike ``_hint``, which is TTY-only): ``GCUBE_TEAM`` may be
    set in a shell or CI config the user has forgotten about, and creating a
    workload under the wrong team misassigns ownership and billing — undoing it
    means delete-and-recreate, and points already spent are not refunded.
    stderr keeps machine-readable stdout clean.
    """
    if team_id:
        click.echo(f"Creating in team context: ID {team_id}", err=True)


def _resolve_namespace(wl: Workload, client: Client, email: str) -> str:
    """Return the k8s namespace for SSE/SSH operations.

    Team workloads run in the team's namespace, not the user's personal one.
    Using the wrong namespace causes SSE subscriptions to receive no events
    and SSH relay lookups to fail.
    """
    if wl.team_id:
        from gcube_cli.api.team import TeamAPI

        team, _, _ = TeamAPI(client).get_detail(wl.team_id)
        if not team.namespace:
            click.echo(
                f"Error: team {wl.team_id} has no namespace assigned. "
                "Cannot resolve namespace for this team workload.",
                err=True,
            )
            sys.exit(2)
        return team.namespace
    return UserAPI(client).get_namespace(email)


_TERMINAL_OP_STATUSES = frozenset({
    "COMPLETED", "START_FAILED", "STOP_FAILED", "FORCE_STOP_REQUIRED",
    "VM_FAILED", "VM_ACTIVATE_FAILED", "NODE_JOIN_FAILED",
})
_FAILURE_OP_STATUSES = frozenset({
    "START_FAILED", "STOP_FAILED", "FORCE_STOP_REQUIRED",
    "VM_FAILED", "VM_ACTIVATE_FAILED", "NODE_JOIN_FAILED",
})


def _derive_phase(wl: Workload) -> tuple[str, bool]:
    """Return (phase, is_deploying).

    Phase names match the web console's ``derivePhase()`` output:
      ``starting``, ``running``, ``stopping``, ``finished``, ``failed``, ``idle``.

    ``is_deploying=True`` means a deploy is actively in progress and worth
    streaming via SSE; ``False`` means the workload is settled.

    Authority is ``operations[0]`` (newest-first), NOT ``state``.
    """
    ops = getattr(wl, "raw", {}).get("operations") or []
    latest = ops[0] if ops else None
    if latest:
        op_type = latest.get("type", "")
        op_status = latest.get("status", "")
        if op_status not in _TERMINAL_OP_STATUSES:
            if op_type == "STOP":
                return ("stopping", False)
            return ("starting", True)
        if op_status in _FAILURE_OP_STATUSES:
            return ("failed", False)
        if op_type == "STOP":
            return ("finished", False)
        return ("running", False)
    # No operations → fall back to state field.
    if wl.state == "finish":
        return ("finished", False)
    if wl.state == "open":
        return ("idle", False)
    if wl.state == "deploy":
        return ("running", False)
    return ("starting", True)


def _watch_deploy(
    ctx: click.Context,
    ser: str,
    client: Client,
    *,
    verb: str = "Deploying",
    plain: bool = False,
    timeout: int | None = None,
) -> None:
    """Stream SSE deploy events and render deployment status until done.

    Rendering mode is chosen automatically:
      - **Live dashboard** (default) on an interactive terminal.
      - **Plain** line-per-event stream when stdout is not a TTY (piped/redirected),
        when ``plain`` is forced, or under ``-o json``/``yaml`` — so batch scripts get
        clean, parseable output without a pseudo-terminal wrapper.
    With ``-o json``/``yaml`` only a single machine-readable result object is emitted.
    """
    output = getattr(ctx.obj, "output", "table")
    structured = output in ("json", "yaml")
    # Non-interactive whenever output isn't a live terminal, is forced, or is structured.
    plain = structured or plain or (not sys.stdout.isatty())
    cfg = Config.load()
    api = WorkloadAPI(client)

    # The namespace belongs to whoever the *effective token* identifies, so derive the
    # email from the token's JWT first — a token supplied via GCUBE_ACCESS_TOKEN/--token
    # then resolves its own account's namespace even when the config file holds a
    # different (or no) email. This is what makes a multi-account automation loop work:
    # only the token changes per iteration, the stale config email is ignored. Fall back
    # to the configured email only when the token carries no identity claim.
    email = decode_email_from_jwt(ctx.obj.token or "") or cfg.auth.user_email
    if not email:
        click.echo(
            "Email not configured. Run: gcube config set --email <your@email.com>",
            err=True,
        )
        sys.exit(1)

    try:
        wl = api.describe(ser)
    except AuthError as e:
        click.echo(str(e), err=True)
        sys.exit(3)
    except APIError as e:
        click.echo(f"API Error [{e.code}]: {e.message}", err=True)
        sys.exit(2)

    # Pre-check: don't open an SSE stream for a workload that isn't deploying — it would
    # just hang with no events (e.g. watching a long-stopped workload).
    phase, is_deploying = _derive_phase(wl)
    if not is_deploying:
        if structured:
            _emit_result(
                output,
                {
                    "ser": _ser_value(ser),
                    "status": "skipped",
                    "phase": phase,
                    "startedAt": None,
                    "completedAt": None,
                    "durationSec": None,
                    "failReason": None,
                },
            )
        elif phase == "idle":
            click.echo(f"Workload {ser} is not deployed yet. Run: gcube workload start {ser}")
        else:
            click.echo(f"Workload {ser} is already {phase}.")
        return

    try:
        namespace = _resolve_namespace(wl, client, email)
    except AuthError as e:
        click.echo(str(e), err=True)
        sys.exit(3)
    except APIError as e:
        click.echo(f"API Error [{e.code}]: {e.message}", err=True)
        sys.exit(2)

    # Use the effective token/url from the context (honors GCUBE_ACCESS_TOKEN /
    # GCUBE_PLATFORM_URL env vars and --token), NOT the raw config file — otherwise a
    # token supplied via env var works for describe/start but the SSE stream gets the
    # stale/empty config token and is rejected with 403.
    sse = SSEClient(ctx.obj.platform_url, ctx.obj.token or "")

    # Human preamble only when we're rendering for a person — suppressed under -o
    # json/yaml so stdout carries nothing but the final result object.
    if not structured:
        replica_label = f" ({wl.replica} replicas)" if wl.replica > 1 else ""
        click.echo(f'{verb} workload {ser} "{wl.description}"{replica_label}...')
        click.echo()
        # Redirected stdout is block-buffered, so a batch script tailing the file (or
        # hard-killing on timeout) would see nothing / lose buffered lines. Flush each
        # plain line as it is written so the log is live and durable.
        if plain:
            sys.stdout.flush()

    state = DeployState(
        replica_count=wl.replica,
        container_count=len(wl.container_array),
        images=[ct.get("containerImage", "") for ct in wl.container_array],
    )

    # Plain (non-structured) mode: stream each event line to stdout as it arrives.
    if plain and not structured:
        def _emit_line(ts: str, msg: str) -> None:
            click.echo(f"{ts} [{ser}] {msg}")
            sys.stdout.flush()

        state.log_sink = _emit_line

    MAX_RETRIES = 5
    retry = 0
    interrupted = False
    timed_out = False

    # When a deadline is set, bound each read so the loop can re-check the deadline (and
    # so Ctrl-C is delivered) instead of blocking forever on a silent stream. Poll cadence
    # is capped so an idle stream is noticed promptly; None keeps the legacy infinite read.
    deadline = (time.monotonic() + timeout) if timeout else None
    read_timeout = min(float(timeout), 15.0) if timeout else None

    # --debug dumps raw SSE events to a file (the Live dashboard owns the screen, so a
    # file is used instead of stderr). The "→ file" notice goes to stderr to keep both
    # stdout streams (plain log / json result) clean.
    debug = bool(getattr(ctx.obj, "debug", False))
    dbg_fh = open(f"gcube-sse-{ser}.log", "w", encoding="utf-8") if debug else None
    if dbg_fh:
        click.echo(f"[debug] raw SSE events → gcube-sse-{ser}.log", err=True)

    # Live dashboard only on an interactive terminal; plain mode runs the same loop with
    # no live region (events are streamed via state.log_sink instead).
    live_ctx: Any = (
        contextlib.nullcontext()
        if plain
        else Live(_LiveView(state), refresh_per_second=4, auto_refresh=True)
    )
    with live_ctx:
        try:
            while retry <= MAX_RETRIES:
                if deadline is not None and time.monotonic() >= deadline:
                    timed_out = True
                    break
                try:
                    for event in sse.stream(namespace, ser, read_timeout=read_timeout):
                        if dbg_fh:
                            raw = _json.dumps(event.data, ensure_ascii=False)
                            dbg_fh.write(f"{event.event}\t{raw}\n")
                            dbg_fh.flush()
                        state.update(event)
                        if state.is_done:
                            break
                        if deadline is not None and time.monotonic() >= deadline:
                            timed_out = True
                            break
                    else:
                        # Generator exhausted without completion → server closed stream
                        raise SSEConnectionError("Stream closed by server")
                    break  # is_done or timed_out — exit retry loop
                except SSEReadTimeout:
                    # Idle gap (no data within read_timeout). Not a failure: loop back to
                    # re-check the deadline and resubscribe without spending a retry.
                    continue
                except SSEAuthError:
                    click.echo(
                        "Token expired or invalid. "
                        "Please get a new token from https://console.gcube.ai",
                        err=True,
                    )
                    sys.exit(3)
                except SSEConnectionError:
                    retry += 1
                    if retry > MAX_RETRIES:
                        click.echo("Cannot connect to deploy status stream.", err=True)
                        sys.exit(4)
                    time.sleep(2**retry)
        except KeyboardInterrupt:
            interrupted = True

    if dbg_fh:
        dbg_fh.close()

    if interrupted:
        if structured:
            res = state.result(ser)
            res["status"] = "interrupted"
            _emit_result(output, res)
        else:
            click.echo()
            click.echo(
                f"Monitoring stopped. Workload {ser} continues deploying in the background."
            )
            _hint(f"Re-attach: gcube workload watch {ser}")
        return

    if timed_out:
        # Inconclusive: deploy neither completed nor reported terminal failure within the
        # deadline. Exit 124 (GNU `timeout` convention) so batch scripts can branch on it.
        if structured:
            res = state.result(ser)
            res["status"] = "timeout"
            _emit_result(output, res)
        else:
            click.echo()
            click.echo(
                f"Watch timed out after {timeout}s — workload {ser} did not finish "
                "deploying. It continues in the background.",
                err=True,
            )
            _hint(f"Re-attach: gcube workload watch {ser}")
        sys.exit(124)

    # Structured: emit only the result object (no human text on stdout).
    if structured:
        _emit_result(output, state.result(ser))
        if state.is_failed:
            sys.exit(1)
        return

    click.echo()
    if state.is_failed:
        if state.fail_reason:
            # vm/node failures carry a server-supplied failMessage worth surfacing.
            click.echo(
                f"Workload {ser} deployment failed: {state.fail_reason}", err=True
            )
        else:
            # Format B error has no actionable detail → point to the web console.
            click.echo(
                f"Workload {ser} deployment failed. Check web console for details.",
                err=True,
            )
        sys.exit(1)
    dur = _duration_seconds(state.deploy_started_ts, state.done_ts)
    took = f" (took {dur}s)" if dur is not None else ""
    click.echo(f"Workload {ser} deployed successfully.{took}")
    _hint(f"View logs: gcube workload logs {ser}")
    _hint(f"Details:   gcube workload describe {ser}")


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _fmt_gpu_name(spec: dict[str, Any]) -> str:
    """Build GPU display name including gpuExt variant if present."""
    name = spec.get("gpu", "")
    ext = spec.get("gpuExt", "")
    return f"{name} {ext}" if ext else name


def _fmt_gpu(gpu_specs: list[dict[str, Any]]) -> str:
    """Format GPU spec array into a compact string.

    Same GPU across all specs → 'RTXA6000 PCIE 48GB×1 (replica×2)'
    Different GPUs           → '[0] RTXA6000 PCIE 48GB×1\n[1] rtx3090 24GB×1'
    """
    if not gpu_specs:
        return ""
    keys = [(s.get("gpu", ""), s.get("gpuExt", "")) for s in gpu_specs]
    if len(set(keys)) == 1:
        display = _fmt_gpu_name(gpu_specs[0])
        vram = gpu_specs[0].get("vram", 0)
        gpu_count = gpu_specs[0].get("gpuCount", 1)
        n = len(gpu_specs)
        base = f"{display} {vram}GB×{gpu_count}"
        return f"{base} (replica×{n})" if n > 1 else base
    return "\n".join(
        f"[{i}] {_fmt_gpu_name(s)} {s.get('vram', 0)}GB×{s.get('gpuCount', 1)}"
        for i, s in enumerate(gpu_specs)
    )


def _fmt_gpu_detail(gpu_specs: list[dict[str, Any]]) -> list[str]:
    """Format GPU specs with resource details for describe output."""
    if not gpu_specs:
        return []
    lines: list[str] = []
    keys = [(s.get("gpu", ""), s.get("gpuExt", "")) for s in gpu_specs]
    if len(set(keys)) == 1 and len(gpu_specs) > 1:
        s = gpu_specs[0]
        label = _fmt_gpu_name(s)
        vram = s.get("vram", 0)
        gpu_count = s.get("gpuCount", 1)
        n = len(gpu_specs)
        lines.append(f"  {label} {vram}GB×{gpu_count} (replica×{n})")
        lines.append(f"      CPU: {s.get('cpu', 0)} Core / RAM: {s.get('memory', 0)} GB / Disk: {s.get('disk', 0)} GB")
    else:
        for i, s in enumerate(gpu_specs):
            label = _fmt_gpu_name(s)
            vram = s.get("vram", 0)
            gpu_count = s.get("gpuCount", 1)
            lines.append(f"  [{i}] {label} {vram}GB×{gpu_count}")
            lines.append(f"      CPU: {s.get('cpu', 0)} Core / RAM: {s.get('memory', 0)} GB / Disk: {s.get('disk', 0)} GB")
    return lines


def _print_describe(
    w: Workload,
    schedules: list[ScheduleEntry] | None = None,
) -> None:
    """Print a workload in kubectl-describe style plain text."""
    phase, _ = _derive_phase(w)
    is_running = phase == "running"

    click.echo(f"Name:        {w.description}")
    click.echo(f"SER:         {w.ser}")
    # Team rows appear only for team workloads.  ``owner`` is deliberately not
    # shown: for a team workload it is the virtual account
    # (team-{id}@team.gcube.internal), which means nothing to a human —
    # ``Created By`` is the useful value.
    if w.team_name:
        click.echo(f"Team:        {w.team_name}")
    if w.created_by:
        click.echo(f"Created By:  {w.created_by}")
    click.echo(f"Category:    {w.category}")
    click.echo(f"State:       {phase}")
    click.echo(f"Replica:     {w.replica}")
    click.echo(f"CUDA:        {w.cuda}")
    click.echo(f"Created:     {w.created_at}")
    if w.deploy_at:
        click.echo(f"Deployed:    {w.deploy_at}")

    gpu_lines = _fmt_gpu_detail(w.gpu_spec_array)
    if gpu_lines:
        click.echo()
        click.echo("GPU:")
        for line in gpu_lines:
            click.echo(line)

    click.echo()
    click.echo("Containers:")
    for i, ct in enumerate(w.container_array):
        click.echo(f"  [{i}] {ct.get('containerImage', '')}")
        click.echo(f"      Port:     {ct.get('port', '')}")
        if is_running:
            svc = ct.get("serviceUrl", "")
            if svc:
                click.echo(f"      SVC URL:  {svc}")

    active_pods = [
        p for p in (w.pods or [])
        if p.get("status") in ("Running", "Pending")
    ]
    if active_pods:
        click.echo()
        click.echo("Pods:")
        for i, pod in enumerate(active_pods):
            name = pod.get("name", "")
            status = pod.get("status", "")
            node = pod.get("node") or {}
            node_name = node.get("name", "") if isinstance(node, dict) else ""
            gpu_spec = node.get("gpuSpec", "") if isinstance(node, dict) else ""
            line = f"  [{i}] {name}   {status}"
            if node_name:
                line += f"   {node_name}"
            if gpu_spec:
                line += f"   {gpu_spec}"
            click.echo(line)

    if schedules:
        tz = schedules[0].time_zone or "Asia/Seoul"
        click.echo()
        _print_schedule_table(schedules, tz, label=f"Schedule ({tz}):")


# ---------------------------------------------------------------------------
# Command group
# ---------------------------------------------------------------------------


@click.group("workload", cls=OrderedGroup)
def workload() -> None:
    """Manage workloads"""


# ---------------------------------------------------------------------------
# register (PBI-007)
# ---------------------------------------------------------------------------


@workload.command("register")
@click.option(
    "-f", "--file", "yaml_file",
    default=None,
    type=click.Path(exists=True),
    help="YAML manifest path",
)
@click.option(
    "--skeleton",
    is_flag=True,
    help="Print a template workload.yaml to stdout and exit",
)
@click.option("--description", default=None, help="Workload description (2-80 chars)")
@click.option("--image", default=None, help="Container image (e.g. pytorch/pytorch:2.0)")
@click.option("--port", default=None, type=int, help="Service port (0 = auto-detect)")
@click.option("--repo", default="docker.io", show_default=True, help="Container registry")
@click.option("--gpu", default=None, help="GPU code from 'gcube gpu list' (e.g. 029)")
@click.option(
    "--credential/--no-credential", "is_credential",
    default=None,
    help="Use registered credential for private registry (auto-detected by default)",
)
@click.option("--cuda", default="", show_default=True, help="CUDA version code (e.g. 12020)")
@click.option(
    "--yes", "-y",
    is_flag=True, default=False,
    help="Register even if image verification fails (skips the confirmation prompt)",
)
@click.option("--service-code", default=None, envvar="GCUBE_SERVICE_CODE",
              help="Service code filter (gcube, edu, katech). [env: GCUBE_SERVICE_CODE]")
@click.option(
    "--team", "team_id", type=int, default=None,
    help="Create under this team (see: gcube team list)",
)
@click.pass_context
def workload_register(
    ctx: click.Context,
    yaml_file: str | None,
    skeleton: bool,
    description: str | None,
    image: str | None,
    port: int | None,
    repo: str,
    gpu: str | None,
    is_credential: bool | None,
    cuda: str,
    yes: bool,
    service_code: str | None,
    team_id: int | None,
) -> None:
    """Register a new workload

    Examples:

    \b
      # From a YAML file: full options (env vars, storage, command, multi-container/GPU)
      gcube workload register --skeleton > workload.yaml
      gcube workload register -f workload.yaml

    \b
      # Quick register with inline flags (single container, basic fields only)
      gcube workload register --image pytorch/pytorch:2.0 --gpu 029 --description demo
    """
    # ① --skeleton: print template and exit
    if skeleton:
        click.echo(WORKLOAD_YAML_TEMPLATE, nl=False)
        if sys.stdout.isatty():
            _hint("Save it:  gcube workload register --skeleton > <file>.yaml")
        else:
            _hint("Edit the file, then:  gcube workload register -f <file>.yaml")
        return

    # Determine input mode
    inline_flags = any([description, image, gpu])
    if yaml_file and inline_flags:
        click.echo(
            "Error: -f/--file and inline flags (--description, --image, --gpu, ...) "
            "are mutually exclusive",
            err=True,
        )
        sys.exit(1)
    if not yaml_file and not inline_flags:
        click.echo(
            "Error: provide -f workload.yaml or inline flags "
            "(--description, --image, --gpu, ...)",
            err=True,
        )
        sys.exit(1)

    # ② Build config dict
    if yaml_file:
        config = _load_yaml_config(yaml_file)
    else:
        config = _build_from_flags(
            description, image, port, repo, gpu,
            is_credential, cuda,
        )

    # Inline flags only support single container/GPU
    if not yaml_file:
        if (
            len(config.get("containers") or []) > 1
            or len(config.get("gpuSpecs") or []) > 1
        ):
            click.echo(
                "Error: multi-container or multi-GPU workloads require -f workload.yaml",
                err=True,
            )
            sys.exit(1)

    # ② Local field validation
    _validate_fields(config)

    # Require token
    gcube_ctx = ctx.obj
    if not gcube_ctx.token:
        click.echo(
            "No token configured. Run: gcube auth login",
            err=True,
        )
        sys.exit(1)

    client = Client(
        base_url=gcube_ctx.platform_url,
        token=gcube_ctx.token,
        debug=gcube_ctx.debug,
    )
    api = WorkloadAPI(client)
    owner = decode_email_from_jwt(gcube_ctx.token) or ""

    # Team context is announced before any work so the user sees it even if a
    # later step prompts or fails.  credential lookup and image verification
    # stay on the personal owner — the server authenticates pulls with the JWT
    # user's credentials regardless of the workload's team.
    eff_team_id = resolve_team_id(ctx, team_id)
    _announce_team_context(eff_team_id)

    try:
        # ③ GPU pricing enrichment (APIError propagates → exit 2)
        _enrich_gpu_specs(config, api, service_code=service_code)

        # ③-b Auto-detect isCredential from saved credentials
        _auto_detect_credentials(config, client, owner)

        # ④ Image verification (advisory — see _verify_images)
        _verify_images(config, api, owner, assume_yes=yes)

        # ⑤ POST registration
        body = _build_workload_body(config, owner, team_id=eff_team_id)
        data = client.post("/api/workloads/gai/register", json=body)
        workload_item: dict[str, Any] = data.get("workload", data.get("data", data))
        ser = workload_item.get("ser", "")
        click.echo("Workload registered.")
        click.echo(f"SER: {ser}")
        if ser:
            _hint(f"Next: gcube workload start {ser}")

    except AuthError as e:
        click.echo(str(e), err=True)
        sys.exit(3)
    except APIError as e:
        click.echo(f"API Error [{e.code}]: {e.message}", err=True)
        sys.exit(2)


# ---------------------------------------------------------------------------
# update (PBI-014)
# ---------------------------------------------------------------------------


@workload.command("update")
@click.argument("ser")
@click.option(
    "-f", "--file", "yaml_file",
    default=None,
    type=click.Path(exists=True),
    help="YAML manifest path",
)
@click.option(
    "--skeleton",
    is_flag=True,
    help="Print current workload config as editable YAML and exit",
)
@click.option(
    "--yes", "-y",
    is_flag=True, default=False,
    help="Update even if image verification fails (skips the confirmation prompt)",
)
@click.option("--service-code", default=None, envvar="GCUBE_SERVICE_CODE",
              help="Service code filter (gcube, edu, katech). [env: GCUBE_SERVICE_CODE]")
@click.pass_context
def workload_update(
    ctx: click.Context, ser: str, yaml_file: str | None, skeleton: bool, yes: bool,
    service_code: str | None,
) -> None:
    """Update a stopped workload

    Use --skeleton to export the current workload config as editable YAML,
    then pass it back with -f after editing.
    """
    client = make_client_from_ctx(ctx)
    api = WorkloadAPI(client)

    # --skeleton: fetch current workload and print skeleton-level YAML
    if skeleton:
        try:
            skel_yaml = api.get_update_skeleton(ser, service_code=service_code)
        except AuthError as e:
            click.echo(str(e), err=True)
            sys.exit(3)
        except APIError as e:
            click.echo(f"API Error [{e.code}]: {e.message}", err=True)
            sys.exit(2)
        click.echo(skel_yaml, nl=False)
        if sys.stdout.isatty():
            _hint(f"Save it:  gcube workload update {ser} --skeleton > <file>.yaml")
        else:
            _hint(f"Edit the file, then:  gcube workload update {ser} -f <file>.yaml")
        return

    if not yaml_file:
        raise click.UsageError(
            "Provide -f workload.yaml or use --skeleton to print the current config."
        )

    owner = decode_email_from_jwt(ctx.obj.token) or ""

    # ① State check
    try:
        current = api.describe(ser)
    except AuthError as e:
        click.echo(str(e), err=True)
        sys.exit(3)
    except APIError as e:
        click.echo(f"API Error [{e.code}]: {e.message}", err=True)
        sys.exit(2)

    if current.state == "deploy":
        click.echo(
            f"Workload {ser} is currently deployed. Stop it first.",
            err=True,
        )
        sys.exit(1)

    # ② Parse YAML
    config = _load_yaml_config(yaml_file)

    # ③ Local field validation
    _validate_fields(config)

    try:
        # ④ GPU pricing enrichment
        _enrich_gpu_specs(config, api, service_code=service_code)

        # ④-b Auto-detect isCredential from saved credentials
        _auto_detect_credentials(config, client, owner)

        # ⑤ Image verification (unchanged images skipped)
        _verify_images(
            config, api, owner,
            previous_containers=current.container_array,
            assume_yes=yes,
        )

        # ⑥ PUT update
        try:
            ser_int = int(ser)
        except ValueError:
            ser_int = 0
        # Carry the workload's existing team through untouched.  `update` has no
        # --team flag (moving a workload between teams is out of scope), but the
        # body must still declare teamId or the server could treat the PUT as a
        # move to personal.
        body = _build_workload_body(
            config, owner, ser=ser_int, team_id=current.team_id,
        )
        api.update(ser, body)
        click.echo(f"Workload updated. SER: {ser}")

    except AuthError as e:
        click.echo(str(e), err=True)
        sys.exit(3)
    except APIError as e:
        click.echo(f"API Error [{e.code}]: {e.message}", err=True)
        sys.exit(2)


# ---------------------------------------------------------------------------
# list (PBI-008)
# ---------------------------------------------------------------------------


@workload.command("list")
@click.option("--owner", default=None, help="Filter by owner email")
@click.option(
    "--all", "show_all", is_flag=True, default=False,
    help="Show all workloads without owner filter (admin only)",
)
@click.option(
    "--team", "team_id", type=int, default=None,
    help="Show only this team's workloads (see: gcube team list)",
)
@click.option(
    "--personal", is_flag=True, default=False,
    help="Show only personal workloads (exclude teams)",
)
@click.option(
    "--org-code",
    default=None,
    help="EDU org code (admin/operator only, use with --class-id)",
)
@click.option(
    "--class-id",
    type=int,
    default=None,
    help="EDU class ID (= group ID, use with --org-code)",
)
@click.pass_context
def workload_list(
    ctx: click.Context,
    owner: str | None,
    show_all: bool,
    team_id: int | None,
    personal: bool,
    org_code: str | None,
    class_id: int | None,
) -> None:
    """List workloads

    By default, shows your personal workloads plus every team you belong to.
    Use --all to show all workloads on the platform (admin only).
    """
    if show_all and owner is not None:
        click.echo("--all and --owner are mutually exclusive.", err=True)
        sys.exit(1)
    if show_all and (team_id is not None or personal):
        click.echo("--all cannot be combined with --team or --personal.", err=True)
        sys.exit(1)
    if (org_code is None) != (class_id is None):
        click.echo(
            "--org-code and --class-id must be used together.", err=True
        )
        sys.exit(1)
    # --owner 미지정 시 JWT email 로 자동 필터 (관리자가 전체를 보는 것을 방지)
    # --all 이면 owner 를 보내지 않아 전체 조회
    resolved_owner = owner
    if not show_all and owner is None:
        resolved_owner = (
            decode_email_from_jwt(ctx.obj.token or "") or Config.load().auth.user_email
        )
        if not resolved_owner:
            click.echo(
                "Cannot determine your account email, so the owner filter would be "
                "dropped -- an admin token would then list every workload on the "
                "platform. Run: gcube config set --email <your@email.com>, "
                "or pass --all if you really want the full list.",
                err=True,
            )
            sys.exit(1)
    # --all means the whole platform, so it must also defeat GCUBE_TEAM.
    # resolve_list_scope() only sees the flags, and would otherwise let the
    # env var narrow --all to a single team without saying so.
    scope = {} if show_all else resolve_list_scope(ctx, team_id, personal)
    try:
        client = make_client_from_ctx(ctx)
        api = WorkloadAPI(client)
        workloads = api.list(
            owner=resolved_owner, org_code=org_code, class_id=class_id, scope=scope,
        )

        output = ctx.obj.output
        list_dicts = [
            {k: v for k, v in w.to_public_dict().items() if k != "pods"}
            for w in workloads
        ]
        if output == "json":
            from gcube_cli.output.json_out import print_json

            print_json(list_dicts)
        elif output == "yaml":
            from gcube_cli.output.yaml_out import print_yaml

            print_yaml(list_dicts)
        else:
            from gcube_cli.output.table import print_table

            show_team = any(w.team_name for w in workloads)
            headers = (
                ["SER", "DESCRIPTION", "TEAM", "GPU", "STATE"]
                if show_team
                else ["SER", "DESCRIPTION", "GPU", "STATE"]
            )
            rows: list[list[str]] = []
            for w in workloads:
                gpu_str = _fmt_gpu(w.gpu_spec_array)
                phase, _ = _derive_phase(w)
                if getattr(w, "raw", {}).get("isScheduled"):
                    phase += " (scheduled)"
                row = [w.ser, w.description]
                if show_team:
                    row.append(w.team_name or "-")
                row += [gpu_str, phase]
                rows.append(row)
            print_table(headers, rows)
    except AuthError as e:
        click.echo(str(e), err=True)
        sys.exit(3)
    except APIError as e:
        click.echo(f"API Error [{e.code}]: {e.message}", err=True)
        sys.exit(2)


# ---------------------------------------------------------------------------
# describe (PBI-008)
# ---------------------------------------------------------------------------


@workload.command("describe")
@click.argument("ser")
@click.pass_context
def workload_describe(ctx: click.Context, ser: str) -> None:
    """Show workload details"""
    try:
        client = make_client_from_ctx(ctx)
        api = WorkloadAPI(client)
        w = api.describe(ser)

        # conditional schedule fetch
        schedules: list[ScheduleEntry] | None = None
        if getattr(w, "raw", {}).get("isScheduled"):
            try:
                schedules = api.get_schedules(ser)
            except APIError:
                pass  # schedule fetch failure is non-fatal

        output = ctx.obj.output
        if output == "json":
            from gcube_cli.output.json_out import print_json

            d = w.to_public_dict()
            if schedules:
                d["schedules"] = [s.to_yaml_dict() for s in schedules]
            print_json(d)
        elif output == "yaml":
            from gcube_cli.output.yaml_out import print_yaml

            d = w.to_public_dict()
            if schedules:
                d["schedules"] = [s.to_yaml_dict() for s in schedules]
            print_yaml(d)
        else:
            _print_describe(w, schedules)
    except AuthError as e:
        click.echo(str(e), err=True)
        sys.exit(3)
    except APIError as e:
        click.echo(f"API Error [{e.code}]: {e.message}", err=True)
        sys.exit(2)


# ---------------------------------------------------------------------------
# start (PBI-009)
# ---------------------------------------------------------------------------


@workload.command("start")
@click.argument("ser")
@click.option(
    "--no-watch",
    is_flag=True,
    default=False,
    help="Start workload without monitoring deployment status",
)
@click.option(
    "--plain",
    is_flag=True,
    default=False,
    help="Stream plain line-per-event output instead of the live dashboard "
    "(auto-enabled when output is piped/redirected or with -o json/yaml)",
)
@click.option(
    "--timeout",
    type=int,
    default=None,
    help="Stop watching after N seconds if the deploy hasn't finished (exit code 124)",
)
@click.pass_context
def workload_start(
    ctx: click.Context, ser: str, no_watch: bool, plain: bool, timeout: int | None
) -> None:
    """Start a workload and monitor deployment"""
    client = make_client_from_ctx(ctx)
    try:
        api = WorkloadAPI(client)
        api.start(ser)
    except AuthError as e:
        click.echo(str(e), err=True)
        sys.exit(3)
    except APIError as e:
        click.echo(f"API Error [{e.code}]: {e.message}", err=True)
        sys.exit(2)

    if no_watch:
        click.echo(f"Workload {ser} started.")
        return

    _watch_deploy(ctx, ser, client, plain=plain, timeout=timeout)


# ---------------------------------------------------------------------------
# watch (PBI-018)
# ---------------------------------------------------------------------------


@workload.command("watch")
@click.argument("ser")
@click.option(
    "--plain",
    is_flag=True,
    default=False,
    help="Stream plain line-per-event output instead of the live dashboard "
    "(auto-enabled when output is piped/redirected or with -o json/yaml)",
)
@click.option(
    "--timeout",
    type=int,
    default=None,
    help="Stop watching after N seconds if the deploy hasn't finished (exit code 124)",
)
@click.pass_context
def workload_watch(ctx: click.Context, ser: str, plain: bool, timeout: int | None) -> None:
    """Monitor deployment status in real time"""
    client = make_client_from_ctx(ctx)
    _watch_deploy(ctx, ser, client, verb="Connecting to", plain=plain, timeout=timeout)


# ---------------------------------------------------------------------------
# stop (PBI-009)
# ---------------------------------------------------------------------------


@workload.command("stop")
@click.argument("ser")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def workload_stop(ctx: click.Context, ser: str, yes: bool) -> None:
    """Stop a running workload"""
    if not yes and not click.confirm(f"Stop workload '{ser}'?"):
        click.echo("Aborted.")
        return
    try:
        client = make_client_from_ctx(ctx)
        api = WorkloadAPI(client)
        api.stop(ser)
        click.echo(f"Workload '{ser}' stopped.")
    except AuthError as e:
        click.echo(str(e), err=True)
        sys.exit(3)
    except APIError as e:
        click.echo(f"API Error [{e.code}]: {e.message}", err=True)
        sys.exit(2)


# ---------------------------------------------------------------------------
# delete (PBI-009)
# ---------------------------------------------------------------------------


@workload.command("delete")
@click.argument("ser")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def workload_delete(ctx: click.Context, ser: str, yes: bool) -> None:
    """Delete a workload"""
    if not yes and not click.confirm(f"Delete workload '{ser}'? This cannot be undone."):
        click.echo("Aborted.")
        return
    try:
        client = make_client_from_ctx(ctx)
        api = WorkloadAPI(client)
        api.delete(ser)
        click.echo(f"Workload '{ser}' deleted.")
    except AuthError as e:
        click.echo(str(e), err=True)
        sys.exit(3)
    except APIError as e:
        click.echo(f"API Error [{e.code}]: {e.message}", err=True)
        sys.exit(2)


# ---------------------------------------------------------------------------
# logs (PBI-016)
# ---------------------------------------------------------------------------


def _print_pod_container_table(
    ser: str,
    pods: list[dict[str, Any]],
    containers: list[dict[str, Any]],
    n_pods: int,
    n_containers: int,
    gpu_spec_array: list[dict[str, Any]] | None = None,
) -> None:
    """Print pod/container selection table and usage hint."""
    pod_word = "pods" if n_pods > 1 else "pod"
    ct_word = "containers" if n_containers > 1 else "container"
    click.echo(
        f"\nWorkload {ser} has {n_pods} {pod_word}, {n_containers} {ct_word} each:\n"
    )
    has_gpu = bool(gpu_spec_array)
    if has_gpu:
        click.echo(
            f"  {'POD':<4} {'NAME':<30} {'STATUS':<8} {'GPU':<22} CONTAINERS"
        )
    else:
        click.echo(f"  {'POD':<4} {'NAME':<30} {'STATUS':<8} CONTAINERS")
    for pod_i, pod in enumerate(pods):
        pod_name = pod.get("name", "")
        status = pod.get("status", "")
        # 1st: node.gpuSpec (actual scheduled GPU — ground truth)
        # 2nd: gpuSpecArray[pod_i] (requested spec — fallback for Pending pods)
        node = pod.get("node")
        node_gpu = node.get("gpuSpec", "") if isinstance(node, dict) else ""
        if node_gpu:
            gpu_col = str(node_gpu)
        elif has_gpu and pod_i < len(gpu_spec_array):
            s = gpu_spec_array[pod_i]
            gpu_col = (
                f"{_fmt_gpu_name(s)} {s.get('vram', 0)}GB"
                f"\u00d7{s.get('gpuCount', 1)}"
            )
        else:
            gpu_col = ""
        if len(gpu_col) > 22:
            gpu_col = gpu_col[:19] + "..."
        for ct_i, ct in enumerate(containers):
            image = ct.get("containerImage", "")
            if len(image) > 40:
                image = image[:37] + "..."
            if ct_i == 0:
                if has_gpu:
                    click.echo(
                        f"  {pod_i:<4} {pod_name:<30} {status:<8}"
                        f" {gpu_col:<22} [{ct_i}] {image}"
                    )
                else:
                    click.echo(
                        f"  {pod_i:<4} {pod_name:<30} {status:<8}"
                        f" [{ct_i}] {image}"
                    )
            else:
                pad = f"  {'':4} {'':30} {'':8}"
                if has_gpu:
                    pad += f" {'':22}"
                click.echo(f"{pad} [{ct_i}] {image}")
    click.echo("")


def _stream_logs(
    ws_url: str,
    token: str,
    ser: str,
    pod_name: str,
    ct_index: int,
) -> None:
    """Run the async WebSocket log streamer. Handles all exit cases."""
    import asyncio
    import sys as _sys

    from gcube_cli.api.logs import LogsAuthError, LogsConnectionError, LogStreamer

    # Windows ProactorEventLoop + SSL causes spurious tracebacks on Ctrl+C.
    # SelectorEventLoop handles SSL shutdown cleanly.
    if _sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(LogStreamer(ws_url, token).stream(ser, pod_name, ct_index))
    except KeyboardInterrupt:
        pass
    except LogsAuthError as exc:
        click.echo(str(exc), err=True)
        sys.exit(3)
    except LogsConnectionError as exc:
        click.echo(str(exc), err=True)
        sys.exit(4)


@workload.command("logs")
@click.argument("ser")
@click.option("--pod", "pod_idx", type=int, default=None, help="Pod index (0-based)")
@click.option("--container", "ct_idx", type=int, default=None, help="Container index (0-based)")
@click.pass_context
def workload_logs(ctx: click.Context, ser: str, pod_idx: int | None, ct_idx: int | None) -> None:
    """Stream container logs in real time"""
    from gcube_cli.config.config import Config

    cfg = Config.load()
    ws_url = cfg.ws_url
    token = ctx.obj.token or ""

    try:
        client = make_client_from_ctx(ctx)
        api = WorkloadAPI(client)
        wl = api.describe(ser)
    except AuthError as exc:
        click.echo(str(exc), err=True)
        sys.exit(3)
    except APIError as exc:
        click.echo(f"API Error [{exc.code}]: {exc.message}", err=True)
        sys.exit(2)

    if wl.state != "deploy":
        click.echo(f"Workload {ser} is not running (state: {wl.state}).", err=True)
        sys.exit(1)

    pods = wl.pods
    containers = wl.container_array
    n_pods = len(pods)
    n_containers = len(containers)

    if not pods:
        click.echo(f"Workload {ser} has no running pods.", err=True)
        sys.exit(1)

    # Single pod + single container + no explicit selection → stream immediately
    if n_pods == 1 and n_containers <= 1 and pod_idx is None and ct_idx is None:
        pod_name = pods[0].get("name", "")
        image = containers[0].get("containerImage", "") if containers else ""
        click.echo(f"Connecting to {pod_name} [{image}]...")
        _stream_logs(ws_url, token, ser, pod_name, 0)
        return

    # Multi pod/container with partial or no selection → show list and exit
    if pod_idx is None or (n_containers > 1 and ct_idx is None):
        _print_pod_container_table(
            ser, pods, containers, n_pods, n_containers, wl.gpu_spec_array,
        )
        click.echo(
            f"  Use: gcube workload logs {ser} --pod <N> --container <N>"
        )
        return

    # Validate pod index
    if pod_idx >= n_pods:
        click.echo(
            f"Pod index {pod_idx} out of range. Workload has {n_pods} pod{'s' if n_pods > 1 else ''}.",
            err=True,
        )
        sys.exit(1)

    resolved_ct = ct_idx if ct_idx is not None else 0

    # Validate container index
    if resolved_ct >= n_containers:
        click.echo(
            f"Container index {resolved_ct} out of range."
            f" Pod has {n_containers} container{'s' if n_containers > 1 else ''}.",
            err=True,
        )
        sys.exit(1)

    pod_name = pods[pod_idx].get("name", "")
    image = containers[resolved_ct].get("containerImage", "") if resolved_ct < len(containers) else ""
    click.echo(f"Connecting to {pod_name} [{image}]...")
    _stream_logs(ws_url, token, ser, pod_name, resolved_ct)


# ---------------------------------------------------------------------------
# pods (PBI-010)
# ---------------------------------------------------------------------------


@workload.command("pods")
@click.argument("ser")
@click.pass_context
def workload_pods(ctx: click.Context, ser: str) -> None:
    """List pods for a workload"""
    try:
        client = make_client_from_ctx(ctx)
        api = WorkloadAPI(client)
        pods = api.pods(ser)

        output = ctx.obj.output
        if output == "json":
            from gcube_cli.output.json_out import print_json

            print_json(pods)
        elif output == "yaml":
            from gcube_cli.output.yaml_out import print_yaml

            print_yaml(pods)
        else:
            from gcube_cli.output.table import print_table

            headers = ["NAME", "STATUS", "IP", "START_TIME"]
            rows = [
                [
                    p.get("name", ""),
                    p.get("status", ""),
                    p.get("ip", ""),
                    p.get("startTime", ""),
                ]
                for p in pods
            ]
            print_table(headers, rows)
    except AuthError as e:
        click.echo(str(e), err=True)
        sys.exit(3)
    except APIError as e:
        click.echo(f"API Error [{e.code}]: {e.message}", err=True)
        sys.exit(2)


# ---------------------------------------------------------------------------
# ssh (PBI-019)
# ---------------------------------------------------------------------------


def _is_pod_running(pod: dict[str, Any]) -> bool:
    """Pod status string-based check. Matches existing workload.py patterns."""
    return pod.get("status") == "Running"


def _ssh_connect(info: SshInfo) -> Any:
    """Create paramiko SSH connection with keepalive."""
    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        info.ssh_url,
        port=info.port,
        username=info.user_name,
        password=info.user_pwd,
        timeout=10,
    )
    transport = client.get_transport()
    if transport:
        transport.set_keepalive(30)
    return client


# The entry gateway relays into the pod with its own ssh client, so a failed
# relay never raises on our side — it arrives as the relay client's error text
# plus a non-zero exit status.  These markers identify it.
_RELAY_FAILURE_MARKERS = (
    "connection refused",
    "connection closed by",
    "ssh: connect to host",
    "no route to host",
    "connection timed out",
)

# Bytes of session output kept to detect a relay failure (see _interactive_shell)
_RELAY_TAP_LIMIT = 4096


def _has_relay_failure(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _RELAY_FAILURE_MARKERS)


def _tap(buf: bytearray, data: bytes) -> None:
    """Keep the first _RELAY_TAP_LIMIT bytes of a stream for later inspection."""
    if len(buf) < _RELAY_TAP_LIMIT:
        buf.extend(data[: _RELAY_TAP_LIMIT - len(buf)])


def _wait_ssh_ready(info: SshInfo, attempts: int = 5, delay: float = 2.0) -> bool:
    """Wait until the entry gateway can relay into the pod's sshd.

    Second line of defence: ``SshAPI.register`` already waits for the server to
    report ``dbear_state == "running"``, so only a short probe is needed here.

    Connecting succeeds as soon as the *gateway* accepts our credentials, which
    says nothing about the pod behind it — so the probe has to inspect the exit
    status and stderr of a remote command instead of relying on exceptions.
    255 is the ssh client's own failure code; the gateway may ignore the command
    we ask for, so anything without a failure marker counts as ready.

    Returns True once the relay works, False if every attempt failed.
    """
    import paramiko

    for i in range(attempts):
        client: paramiko.SSHClient | None = None
        try:
            client = _ssh_connect(info)
            _stdin, stdout, stderr = client.exec_command("true", timeout=5)
            exit_status = stdout.channel.recv_exit_status()
            # The relay may run under a PTY, which merges its error into stdout,
            # so both streams are checked. Reading after recv_exit_status() means
            # the remote command has already finished.
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            if (
                exit_status != 255
                and not _has_relay_failure(out)
                and not _has_relay_failure(err)
            ):
                return True
        except Exception:
            pass
        finally:
            if client:
                client.close()
        if i < attempts - 1:
            time.sleep(delay)

    return False


def _exec_ssh_command(info: SshInfo, command: tuple[str, ...]) -> int:
    """Non-interactive: execute remote command and return exit code."""
    import shlex

    client = _ssh_connect(info)
    cmd_str = " ".join(shlex.quote(c) for c in command)
    _stdin, stdout, _stderr = client.exec_command(cmd_str)
    channel = stdout.channel

    channel.settimeout(0.1)
    while not (
        channel.exit_status_ready()
        and not channel.recv_ready()
        and not channel.recv_stderr_ready()
    ):
        got = False
        if channel.recv_ready():
            sys.stdout.buffer.write(channel.recv(4096))
            sys.stdout.buffer.flush()
            got = True
        if channel.recv_stderr_ready():
            sys.stderr.buffer.write(channel.recv_stderr(4096))
            sys.stderr.buffer.flush()
            got = True
        if not got:
            # Only the blocking recv can time out; recv_ready/recv_stderr_ready are
            # non-blocking, so this is the single point that needs the timeout guard.
            try:
                data = channel.recv(4096)
                if data:
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
            except TimeoutError:
                pass

    # Flush remaining data
    while channel.recv_ready():
        sys.stdout.buffer.write(channel.recv(4096))
    while channel.recv_stderr_ready():
        sys.stderr.buffer.write(channel.recv_stderr(4096))

    exit_code = channel.recv_exit_status()
    client.close()
    return exit_code


def _posix_shell(channel: Any, tap: bytearray) -> None:
    """Unix interactive shell using select + tty.setraw."""
    import select
    import termios
    import tty

    oldtty = termios.tcgetattr(sys.stdin)
    try:
        tty.setraw(sys.stdin.fileno())
        channel.settimeout(0.0)
        while True:
            r, _w, _e = select.select([channel, sys.stdin], [], [])
            if channel in r:
                try:
                    data = channel.recv(4096)
                    if not data:
                        break
                    _tap(tap, data)
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                except Exception:
                    break
            if sys.stdin in r:
                ch = sys.stdin.read(1)
                if not ch:
                    break
                channel.send(ch)
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, oldtty)


def _windows_shell(channel: Any, tap: bytearray) -> None:
    """Windows interactive shell using msvcrt + threading.

    No termios/PTY, so arrow keys/tab completion may be limited.
    """
    import msvcrt
    import threading
    import time

    def _reader() -> None:
        while not channel.closed:
            if channel.recv_ready():
                data = channel.recv(4096)
                if data:
                    _tap(tap, data)
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
            else:
                time.sleep(0.01)

    reader = threading.Thread(target=_reader, daemon=True)
    reader.start()
    try:
        while not channel.closed:
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                channel.send(ch)
            else:
                time.sleep(0.01)
    except EOFError:
        pass


def _interactive_shell(info: SshInfo) -> int:
    """Interactive PTY shell session. Returns a process exit code."""
    import os

    client = _ssh_connect(info)
    try:
        cols, rows = os.get_terminal_size()
    except OSError:
        cols, rows = 80, 24
    channel = client.invoke_shell(width=cols, height=rows)

    tap = bytearray()
    if os.name == "posix":
        _posix_shell(channel, tap)
    else:
        _windows_shell(channel, tap)

    client.close()

    # A failed relay prints the gateway's ssh error and closes the session at
    # once. Without this the failure would be reported as a successful login.
    if _has_relay_failure(tap.decode("utf-8", errors="replace")):
        return 1
    return 0


def _print_ssh_info(info: SshInfo, show_password: bool) -> None:
    """Display SSH connection info."""
    pwd_display = info.user_pwd if show_password else "********  (use --show-password to reveal)"
    click.echo(f"SSH Host    : {info.ssh_url}")
    click.echo(f"SSH Port    : {info.port}")
    click.echo(f"User        : {info.user_name}")
    click.echo(f"Password    : {pwd_display}")
    click.echo(f"Public IP   : {info.pub_ip}")
    click.echo(f"Registered  : {info.created_at}")
    # Both fields are absent on backends that predate them — show nothing
    # rather than inventing a value.
    if info.dbear_state:
        click.echo(f"Daemon      : {info.dbear_state}")
    if info.target_ip:
        # Some backends omit target_port; ":0" would read as a real port.
        target = f"{info.target_ip}:{info.target_port}" if info.target_port else info.target_ip
        click.echo(f"Relay Target: {target}")


@workload.command("ssh", context_settings={"ignore_unknown_options": True})
@click.argument("ser")
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
@click.option("--pod", default=None, type=int, help="Pod index (0-based)")
@click.option(
    "--container", "ct", default=None, type=int, help="Container index (0-based)"
)
@click.option("--ip", default=None, help="Public IP (auto-detect if omitted)")
@click.option(
    "--info", "show_info", is_flag=True,
    help="Show SSH connection info without connecting",
)
@click.option("--show-password", is_flag=True, help="Reveal password in --info output")
@click.option("--delete", "do_delete", is_flag=True, help="Delete SSH connection info")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation for --delete")
@click.pass_context
def workload_ssh(
    ctx: click.Context,
    ser: str,
    command: tuple[str, ...],
    pod: int | None,
    ct: int | None,
    ip: str | None,
    show_info: bool,
    show_password: bool,
    do_delete: bool,
    yes: bool,
) -> None:
    """Connect to a running workload via SSH"""
    try:
        import paramiko  # noqa: F401
    except ImportError:
        click.echo("SSH library not available. Run: pip install paramiko", err=True)
        sys.exit(1)

    # Mutual exclusion
    if show_info and do_delete:
        raise click.UsageError("--info and --delete cannot be used together.")
    if (show_info or do_delete) and command:
        raise click.UsageError("--info/--delete cannot be used with -- <command>.")

    from gcube_cli.api.ssh import SshAPI, detect_public_ip, is_dbear_ready

    try:
        client = make_client_from_ctx(ctx)
        api = WorkloadAPI(client)
        ssh_api = SshAPI(client)

        # ① describe → get pods
        wl = api.describe(ser)
        pods = wl.pods
        containers = wl.container_array

        if not pods:
            click.echo(f"Workload {ser} has no pods.", err=True)
            sys.exit(1)

        n_pods = len(pods)
        n_containers = len(containers)

        # ③ get namespace (needed for --info/--delete/connect)
        cfg = Config.load()
        email = decode_email_from_jwt(ctx.obj.token or "") or cfg.auth.user_email
        if not email:
            click.echo(
                "Email not configured. Run: gcube config set --email <your@email.com>",
                err=True,
            )
            sys.exit(1)
        namespace = _resolve_namespace(wl, client, email)

        # ④ --info early exit (before pod selection gate)
        if show_info:
            resolved_ct_info = ct if ct is not None else 0
            if pod is not None:
                # Specific pod requested
                if pod >= n_pods:
                    click.echo(f"Pod index {pod} out of range (0-{n_pods - 1}).", err=True)
                    sys.exit(1)
                pod_name = pods[pod].get("name", "")
                existing = ssh_api.get(namespace, pod_name, resolved_ct_info)
                if existing is None:
                    click.echo(
                        f"SSH not registered for this workload. Run: gcube workload ssh {ser}",
                        err=True,
                    )
                    sys.exit(1)
                _print_ssh_info(existing, show_password)
            else:
                # No pod specified → show info for all pods
                found_any = False
                for i, p in enumerate(pods):
                    pod_name = p.get("name", "")
                    existing = ssh_api.get(namespace, pod_name, resolved_ct_info)
                    if existing is not None:
                        if found_any:
                            click.echo("")
                        click.echo(f"[Pod {i}] {pod_name}")
                        _print_ssh_info(existing, show_password)
                        found_any = True
                if not found_any:
                    click.echo(
                        f"SSH not registered for this workload. Run: gcube workload ssh {ser}",
                        err=True,
                    )
                    sys.exit(1)
            return

        # ④ --delete early exit (before pod selection gate)
        if do_delete:
            resolved_ct_del = ct if ct is not None else 0
            # Ambiguous target: multiple pods and none selected → show table and stop.
            if pod is None and n_pods > 1:
                _print_pod_container_table(
                    ser, pods, containers, n_pods, n_containers, wl.gpu_spec_array,
                )
                click.echo(f"  Use: gcube workload ssh {ser} --pod <N> --delete")
                return
            if pod is not None and pod >= n_pods:
                click.echo(f"Pod index {pod} out of range (0-{n_pods - 1}).", err=True)
                sys.exit(1)
            pod_name = pods[pod if pod is not None else 0].get("name", "")
            if not yes:
                click.confirm(f"Delete SSH connection info for {pod_name}?", abort=True)
            if ssh_api.delete(namespace, pod_name, resolved_ct_del):
                click.echo("SSH connection info deleted.")
            else:
                click.echo("SSH connection info not found or already deleted.", err=True)
                sys.exit(1)
            return

        # ①-b multi pod/container without explicit selection → show table
        if n_pods == 1 and n_containers <= 1:
            resolved_pod = pod if pod is not None else 0
            resolved_ct = ct if ct is not None else 0
        else:
            if pod is None or (n_containers > 1 and ct is None):
                _print_pod_container_table(
                    ser, pods, containers, n_pods, n_containers, wl.gpu_spec_array,
                )
                click.echo(
                    f"  Use: gcube workload ssh {ser} --pod <N> --container <N>"
                )
                return
            resolved_pod = pod
            resolved_ct = ct if ct is not None else 0

        # Validate pod/container range
        if resolved_pod >= n_pods:
            click.echo(
                f"Pod index {resolved_pod} out of range (0-{n_pods - 1}).",
                err=True,
            )
            sys.exit(1)
        if resolved_ct >= n_containers:
            click.echo(
                f"Container index {resolved_ct} out of range (0-{n_containers - 1}).",
                err=True,
            )
            sys.exit(1)

        # ② check selected pod is Running
        selected_pod = pods[resolved_pod]
        if not _is_pod_running(selected_pod):
            click.echo(
                f"Workload {ser} is not running. SSH requires a running pod.",
                err=True,
            )
            sys.exit(1)

        pod_name = selected_pod.get("name", "")

        # ⑤ GET existing SSH info → reuse or re-register
        ssh_info = ssh_api.get(namespace, pod_name, resolved_ct)

        # --ip with a different address than the existing registration → re-register.
        # Otherwise an existing registration is reused as-is.
        if ssh_info is not None and ip and ssh_info.pub_ip != ip:
            ssh_api.delete(namespace, pod_name, resolved_ct)
            ssh_info = None

        # ⑥ Register if needed
        ssh_was_registered = False
        if ssh_info is None:
            if ip:
                public_ip = ip
            else:
                click.echo("Detecting public IP...", err=True, nl=False)
                public_ip = detect_public_ip()
                if not public_ip:
                    click.echo("", err=True)
                    click.echo(
                        "Could not detect public IP. "
                        "Use --ip <address> to specify manually.",
                        err=True,
                    )
                    sys.exit(1)
                click.echo(f" {public_ip}", err=True)

            click.echo("Registering SSH connection...", err=True, nl=False)

            def _dot() -> None:
                click.echo(".", err=True, nl=False)

            try:
                ssh_info = ssh_api.register(
                    pod_name=pod_name,
                    namespace=namespace,
                    container=resolved_ct,
                    workload=ser,
                    public_ip=public_ip,
                    on_poll=_dot,
                )
            except APIError as reg_err:
                if reg_err.status_code == 400:
                    # Race: duplicate registration → delete and retry
                    ssh_api.delete(namespace, pod_name, resolved_ct)
                    ssh_info = ssh_api.register(
                        pod_name=pod_name,
                        namespace=namespace,
                        container=resolved_ct,
                        workload=ser,
                        public_ip=public_ip,
                        on_poll=_dot,
                    )
                else:
                    raise
            finally:
                click.echo("", err=True)  # newline after dots
            ssh_was_registered = True

        # ⑦ SSH info acquired
        # ⑧ Connect — after fresh registration, probe readiness first
        if ssh_was_registered:
            click.echo("Waiting for SSH daemon...", err=True)
            # register() already waited for the server to report readiness, so a
            # short probe is enough. When it never reported ready, the daemon is
            # the slow part — probe longer before giving up on it.
            probe_attempts = 5 if is_dbear_ready(ssh_info) else 10
            if not _wait_ssh_ready(ssh_info, attempts=probe_attempts):
                click.echo(
                    "SSH daemon is not accepting connections yet "
                    f"(daemon state: {ssh_info.dbear_state or 'unknown'}). "
                    "Connecting anyway — if this fails, run the same command again.",
                    err=True,
                )

        click.echo(
            f"Connecting to {pod_name} ({ssh_info.ssh_url}:{ssh_info.port})...",
            err=True,
        )
        try:
            if command:
                sys.exit(_exec_ssh_command(ssh_info, command))
            sys.exit(_interactive_shell(ssh_info))
        except Exception as e:
            click.echo(f"SSH connection failed: {e}", err=True)
            sys.exit(1)

    except AuthError as e:
        click.echo(str(e), err=True)
        sys.exit(3)
    except APIError as e:
        click.echo(f"API Error [{e.code}]: {e.message}", err=True)
        sys.exit(2)


# ---------------------------------------------------------------------------
# schedule (PBI-021)
# ---------------------------------------------------------------------------


@workload.command("schedule")
@click.argument("ser")
@click.option("-f", "--file", "yaml_file", default=None, type=click.Path(exists=True),
              help="Schedule YAML manifest path")
@click.option("--days", default=None, help="Days: Mon-Fri, daily, weekdays, 31, etc.")
@click.option("--start", "start_time", default=None, help="START time HH:mm")
@click.option("--stop", "stop_time", default=None, help="STOP time HH:mm")
@click.option("--timezone", default=None,
              help="IANA timezone (default: inherit existing or Asia/Seoul)")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--logs", is_flag=True, help="Show schedule execution history")
@click.option("--limit", "log_limit", default=20, type=int,
              help="Number of log entries to show (default: 20)")
@click.pass_context
def workload_schedule(
    ctx: click.Context,
    ser: str,
    yaml_file: str | None,
    days: str | None,
    start_time: str | None,
    stop_time: str | None,
    timezone: str | None,
    yes: bool,
    logs: bool,
    log_limit: int,
) -> None:
    """Set or show workload schedule

    \b
    Inline flags (--days/--start/--stop) append to existing schedules.
    To replace, use -f with a YAML file.
    Use --logs to view execution history.
    """
    if logs:
        has_set_args = yaml_file or days or start_time or stop_time
        if has_set_args:
            raise click.UsageError(
                "--logs cannot be combined with set flags "
                "(-f/--days/--start/--stop)."
            )
        _show_schedule_logs(ctx, ser, log_limit)
        return

    has_set_args = yaml_file or days or start_time or stop_time

    try:
        client = make_client_from_ctx(ctx)
        api = WorkloadAPI(client)

        if not has_set_args:
            # ── show mode ──
            existing = api.get_schedules(ser)
            output = ctx.obj.output
            if not existing:
                if output == "json":
                    from gcube_cli.output.json_out import print_json

                    print_json({"timezone": "Asia/Seoul", "schedules": []})
                elif output == "yaml":
                    from gcube_cli.output.yaml_out import print_yaml

                    print_yaml({"timezone": "Asia/Seoul", "schedules": []})
                else:
                    click.echo("No schedules configured.")
                return
            tz = existing[0].time_zone or "Asia/Seoul"
            if output == "json":
                from gcube_cli.output.json_out import print_json

                print_json({
                    "timezone": tz,
                    "schedules": [e.to_yaml_dict() for e in existing],
                })
            elif output == "yaml":
                from gcube_cli.output.yaml_out import print_yaml

                print_yaml({
                    "timezone": tz,
                    "schedules": [e.to_yaml_dict() for e in existing],
                })
            else:
                header = f"# Workload SER {ser}\n# Timezone: {tz}\n"
                click.echo(_dump_schedule_yaml(existing, tz, header_comment=header), nl=False)
            return

        # ── set mode ──
        if yaml_file:
            file_tz, new_entries = _load_schedule_yaml(yaml_file)
            effective_tz = timezone or file_tz
        else:
            # inline mode
            if not days:
                raise click.UsageError("--days is required. (e.g. Mon-Fri, daily)")
            if not start_time and not stop_time:
                raise click.UsageError("--start or --stop is required.")

            existing = api.get_schedules(ser)
            # inherit existing timezone
            if timezone:
                effective_tz = timezone
            elif existing:
                effective_tz = existing[0].time_zone or "Asia/Seoul"
            else:
                effective_tz = "Asia/Seoul"

            mask = _parse_days(days)
            new_inline: list[ScheduleEntry] = []
            if start_time:
                new_inline.append(ScheduleEntry(
                    enabled=True, action="START", days_of_week=mask,
                    time=start_time, date=None, end_date=None,
                ))
            if stop_time:
                new_inline.append(ScheduleEntry(
                    enabled=True, action="STOP", days_of_week=mask,
                    time=stop_time, date=None, end_date=None,
                ))
            new_entries = list(existing) + new_inline

        # validate
        errors = _validate_schedule_entries(new_entries)
        if errors:
            for err in errors:
                click.echo(err, err=True)
            sys.exit(1)

        # lint warnings (always shown)
        for w in _lint_schedule_entries(new_entries, effective_tz):
            click.echo(w, err=True)

        # diff preview
        if not yes:
            if yaml_file:
                current = api.get_schedules(ser)
            else:
                current = existing  # already fetched in inline mode
            if current:
                _print_schedule_table(
                    current, effective_tz,
                    label=f"Current ({len(current)} entries, {effective_tz}):",
                )
                click.echo()
            _print_schedule_table(
                new_entries, effective_tz,
                label=f"After ({len(new_entries)} entries, {effective_tz}):",
            )
            click.echo()
            if not click.confirm("Apply changes?", default=False):
                click.echo("Cancelled.")
                return

        # save
        try:
            api.save_schedules(ser, new_entries, time_zone=effective_tz)
        except APIError as e:
            click.echo(_friendly_api_error(e), err=True)
            sys.exit(2)

        click.echo("Schedule saved.")

    except AuthError as e:
        click.echo(str(e), err=True)
        sys.exit(3)
    except APIError as e:
        click.echo(f"API Error [{e.code}]: {e.message}", err=True)
        sys.exit(2)


# ---------------------------------------------------------------------------
# unschedule (PBI-021)
# ---------------------------------------------------------------------------


@workload.command("unschedule")
@click.argument("ser")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def workload_unschedule(ctx: click.Context, ser: str, yes: bool) -> None:
    """Remove all schedules from a workload"""
    try:
        client = make_client_from_ctx(ctx)
        api = WorkloadAPI(client)
        existing = api.get_schedules(ser)

        if not existing:
            click.echo("No schedules to remove.")
            return

        tz = existing[0].time_zone or "Asia/Seoul"
        _print_schedule_table(existing, tz, label=f"Current schedules ({len(existing)} entries):")

        if not yes:
            click.echo()
            if not click.confirm("Remove all schedules?", default=False):
                click.echo("Cancelled.")
                return

        try:
            api.delete_schedules(ser)
        except APIError as e:
            click.echo(_friendly_api_error(e), err=True)
            sys.exit(2)

        click.echo("All schedules removed.")

    except AuthError as e:
        click.echo(str(e), err=True)
        sys.exit(3)
    except APIError as e:
        click.echo(f"API Error [{e.code}]: {e.message}", err=True)
        sys.exit(2)


# Help display order
workload.commands = {k: workload.commands[k] for k in [  # type: ignore[assignment]
    "list", "describe", "register", "update",
    "start", "watch", "stop", "delete",
    "schedule", "unschedule",
    "pods", "logs", "ssh",
]}
