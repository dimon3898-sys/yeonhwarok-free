"""Publish allowlisted fresh proof; never publish private Scene/auth/cache files."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parents[1]
JOB = "studio-cabdd833dbd67903da41f58a7993d9c3"
CAPTURE = HERE / "captures" / JOB


def put_json(file, value):
    file.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def persist():
    report_file = CAPTURE / "proof/CAPTURE_REPORT.json"
    report = json.loads(report_file.read_bytes())
    comparison_root = HERE / "comparisons" / JOB
    comparison = json.loads((comparison_root / "STUDIO_REFERENCE_ALL_150_FRAME_COMPARISON.json").read_bytes())
    spec = importlib.util.spec_from_file_location("_persist_actual_gates", HERE / "gates.py")
    gates = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gates)
    result = gates.assess_gates(report_file, HERE / "reports/STUDIO_HTTP_EXECUTION.json")
    result["g1"]["strictEncodedReproductionStatus"] = comparison["status"]
    result["g1"]["decodedMovie"] = comparison["decodedMovie"]
    result["g1"]["interpretation"] = "Raw draw and all visual state fields match exactly. Lossy MP4 pixels differ after encoding; original encoder environment details remain unverified. This is a source-path render candidate, not user visual approval or bit-exact movie approval."
    put_json(HERE / "reports/GATE_RESULTS.json", result)
    public = HERE / "public-review"
    public.mkdir(exist_ok=True)
    allowed = [report["video"]["file"], "SHA256SUMS", *[r["file"] for r in report["checkpoints"]]]
    for name in allowed:
        if name == "SHA256SUMS":
            continue
        source = CAPTURE / "public-review" / name
        target = public / name
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise RuntimeError("REFUSE_REPLACE_DIFFERENT_REVIEW_FILE")
        if not target.exists():
            shutil.copyfile(source, target)
    for name in ("STUDIO_REFERENCE_SIDE_BY_SIDE.png", "STUDIO_REFERENCE_TEMPORAL_CONTACT.png"):
        target = public / name
        source = comparison_root / name
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise RuntimeError("REFUSE_REPLACE_DIFFERENT_COMPARISON")
        if not target.exists():
            shutil.copyfile(source, target)
    # Omit runtime.domainGeometryBinding, full source Scene, internal auth and
    # bulky native geometry diagnostics. Preserve per-frame cryptographic proof.
    evidence = {k: v for k, v in report.items() if k not in {"runtime", "frames"}}
    evidence["fullCaptureReportSHA256"] = hashlib.sha256(report_file.read_bytes()).hexdigest()
    evidence["runtimeSummary"] = {"backend": report["runtime"]["backend"], "cameraMotion": report["runtime"]["cameraMotion"]}
    evidence["frames"] = []
    for row in report["frames"]:
        item = {k: row[k] for k in ("frame", "timeSeconds", "raw_rgba_sha256", "png_sha256", "originalRawRgbaEqual", "originalPngEqual", "captureWallMilliseconds")}
        item["componentSHA256"] = {key: hashlib.sha256(json.dumps(row.get(key), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
                                    for key in ("camera", "scalarControl", "frontier", "units", "material", "protection")}
        evidence["frames"].append(item)
    put_json(HERE / "reports/G1_CAPTURE_EVIDENCE.json", evidence)
    rows = [{"file": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
            for p in sorted(public.iterdir()) if p.is_file() and p.name != "SHA256SUMS"]
    (public / "SHA256SUMS").write_text("".join(r["sha256"] + "  " + r["file"] + "\n" for r in rows))
    print(json.dumps({"g1": result["g1"]["status"], "g2": result["g2"]["status"], "g3": result["g3"], "reviewFiles": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    persist()
