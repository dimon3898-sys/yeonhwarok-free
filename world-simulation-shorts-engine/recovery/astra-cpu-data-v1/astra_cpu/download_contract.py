"""Bounded acquisition handoff shared by planners, transport and raw cache."""
from dataclasses import dataclass, field
import math
import re
from urllib.parse import urlsplit
from .model import DataError, validate_bbox


@dataclass(frozen=True)
class DownloadRequest:
    url: str
    source_id: str
    source_version: str
    max_bytes: int
    expected_sha256: str | None = None
    byte_range: tuple | None = None
    expected_etag: str | None = None
    bbox: tuple | None = None
    crs: str = 'EPSG:4326'
    resolution: object = None
    source_metadata_sha256: str | None = None
    total_object_bytes: int | None = None

    def validate(self):
        parsed = urlsplit(self.url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise DataError('download URL must be HTTPS without credentials or fragment')
        if not self.source_id or not self.source_version:
            raise DataError('pinned source identity and version are required')
        if isinstance(self.max_bytes, bool) or not isinstance(self.max_bytes, int) or not 0 < self.max_bytes <= 64*1024*1024:
            raise DataError('bounded response size must be 1..64MiB')
        for digest in (self.expected_sha256, self.source_metadata_sha256):
            if digest is not None and (not isinstance(digest, str) or re.fullmatch('[0-9a-f]{64}', digest) is None):
                raise DataError('expected hashes must be lowercase SHA-256')
        if self.bbox is not None:
            validate_bbox(self.bbox)
        if self.byte_range is not None:
            if (not isinstance(self.byte_range, (tuple,list)) or len(self.byte_range)!=2
                    or any(isinstance(v,bool) or not isinstance(v,int) for v in self.byte_range)
                    or not 0 <= self.byte_range[0] <= self.byte_range[1]
                    or self.byte_range[1]-self.byte_range[0]+1 > self.max_bytes):
                raise DataError('invalid inclusive bounded byte range')
            if self.total_object_bytes is not None and self.byte_range[1] >= self.total_object_bytes:
                raise DataError('byte range exceeds known source object')
        if self.total_object_bytes is not None and (isinstance(self.total_object_bytes,bool)
                or not isinstance(self.total_object_bytes,int) or self.total_object_bytes <= 0):
            raise DataError('source object size must be a positive integer')


@dataclass(frozen=True)
class DownloadResponse:
    status: int
    headers: dict
    body: bytes


@dataclass(frozen=True)
class AcquisitionPlan:
    status: str
    stage: str
    requests: tuple = ()
    metadata: dict = field(default_factory=dict)
    coverage: dict = field(default_factory=dict)
    warnings: tuple = ()

    def __post_init__(self):
        if self.status not in {'planned','unavailable','auth_required','version_changed','license_unverified','invalid_data'}:
            raise DataError('acquisition planning cannot claim an available download')
        for request in self.requests:
            request.validate()
