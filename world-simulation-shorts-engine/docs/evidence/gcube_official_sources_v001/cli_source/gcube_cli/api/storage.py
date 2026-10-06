"""Personal storage API client for gcube CLI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gcube_cli.api.client import Client


@dataclass
class Storage:
    """One personal storage (PVC) entry returned by the storage list API."""

    ser: str
    description: str
    storage_type: str   # JSON: type
    capacity: str
    access_mode: str    # JSON: accessMode
    bucket: str | None = None  # non-null → gcube storage

    @property
    def is_gcube(self) -> bool:
        return self.bucket is not None

    @property
    def mount_key(self) -> str:
        """Key to use in workload userStorages: 'gcube' for gcube type, ser otherwise."""
        return "gcube" if self.is_gcube else self.ser

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Storage:
        capacity = d.get("capacity", "")
        return cls(
            ser=str(d.get("ser", "")),
            description=d.get("description") or d.get("name", ""),
            storage_type=d.get("type", ""),
            capacity=f"{capacity}GB" if isinstance(capacity, int) else str(capacity),
            access_mode=d.get("accessMode", ""),
            bucket=d.get("bucket"),
        )

    @staticmethod
    def is_bound(d: dict[str, Any]) -> bool:
        """Return True only if both pvStatus and pvcStatus are 'bound'."""
        return (
            str(d.get("pvStatus", "")).lower() == "bound"
            and str(d.get("pvcStatus", "")).lower() == "bound"
        )


class StorageAPI:
    """High-level personal storage API client."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def list(self, owner: str) -> list[Storage]:
        """GET /api/users/storage/list?owner={email}

        Returns only storages where both pvStatus and pvcStatus are 'bound'.
        """
        data = self._client.get("/api/users/storage/list", params={"owner": owner})
        items: list[dict[str, Any]] = data.get(
            "userStorages", data.get("storages", data.get("data", data.get("items", [])))
        )
        return [Storage.from_dict(item) for item in items if Storage.is_bound(item)]
