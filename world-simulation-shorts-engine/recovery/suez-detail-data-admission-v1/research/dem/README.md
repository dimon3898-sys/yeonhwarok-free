# Existing DEM audit

Run from the repository root:

```sh
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/suez-detail-data-admission-v1/research/dem/audit_existing_dem.py
```

The audit reads the existing registered height metadata, the frozen navigation
axis, the V5 regional extent and safe area, the native Float32 height atlas, and
all four original GLO-30 COGs. It downloads no DEM and changes no source. Native
sample bits are compared with the matching atlas windows. EPSG:4326, hashes,
finite sample counts, dimensions, height ranges, and source grid transforms are
recorded in `EXISTING_DEM_AUDIT.json`.

The three research extents target 350, 550, and 800 projected pixels of complete
navigation-axis length. They inherit the regional geographic aspect and center
the full, unchanged axis in the safe area with a generic 12-pixel line reserve.
These are measurable candidates, **not certified safe camera extents**. Terrain,
GIS accuracy, protected graphics, and text placement require independent checks.

Existing GLO-30 sampling resolution passes the unchanged one output pixel per
sample limit for every candidate. Real-height spatial coverage does not: the
registered northern edge is approximately 31 degrees north while the full axis
reaches 31.2757 degrees north. Only 81 of 92 original nodes and 80.7758% of the
projected axis length lie in the registered height footprint. The report also
computes the smaller positive-weight and full-weight regions required by the
unchanged renderer's real-height neighbourhood guard. It does not count fallback
terrain as actual DEM coverage.

Consequently, `requireRealDEM=true` requires more spatial coverage before a
whole-detail extent can pass. If real DEM is optional, existing partial heights
and the existing terrain fallback can remain, with an explicit limitation; that
does not waive terrain, GIS, or Event accuracy requirements. It is incorrect to
claim unqualified `DEM_EXISTING_SUFFICIENT` for the entire requested extent.

The original registered metadata identifies user-provided Copernicus GLO-30
COGs and their product conventions, but supplies neither an original retrieval
date nor a license record. Those are recorded as missing, not invented. This
audit verifies the saved source bytes and existing spatial registration; it
does not issue a new provenance or Detail Admission certificate.
