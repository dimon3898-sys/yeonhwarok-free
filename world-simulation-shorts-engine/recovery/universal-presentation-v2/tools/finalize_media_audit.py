"""Aggregate completed actual-frame audits and make a temporal contact sheet."""
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parents[1]
CASES = [
    ("UP2_AVIATION_EUROPE", "MOVIE_AUDIT_1_TRACE_SCOPED", "AVIATION_EUROPE_NL"),
    ("UP2_TRADE_SOUTH_AMERICA", "MOVIE_AUDIT_2", "TRADE_SOUTH_AMERICA_NL"),
    ("UP2_FICTIONAL_AFRICA", "MOVIE_AUDIT_3", "FICTIONAL_AFRICA_NL"),
]


def sha(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


if __name__ == "__main__":
    indices = [0, 20, 45, 89, 90, 110, 135, 179]
    sheet = Image.new("RGB", (len(indices) * 240, len(CASES) * 461), "#111827")
    draw = ImageDraw.Draw(sheet)
    results, source_images = [], []
    for row, (name, directory, example) in enumerate(CASES):
        base = HERE / "reports" / directory
        report = json.loads((base / "ACTUAL_MOVIES_AUDIT.json").read_text())
        if report["technicalStatus"] != "PASS" or len(report["movies"]) != 1:
            raise ValueError("ACTUAL_MOVIE_AUDIT_PASS_REQUIRED")
        movie = report["movies"][0]
        public = HERE / "public-review"
        receipt = json.loads((public / (name + "_CAPTURE_RECEIPT.json")).read_text())
        request = public / (name + "_RENDER_REQUEST.json")
        if (sha(public / (name + ".mp4")) != movie["encodedVideo"]["videoSHA256"]
                or sha(request) != receipt["packageSHA256"]):
            raise ValueError("EXACT_PUBLIC_VIDEO_AND_RENDER_REQUEST_BINDING_REQUIRED")
        for column, index in enumerate(indices):
            file = base / f"{name}_F{index:03d}.png"
            with Image.open(file) as image:
                if image.size != (1080, 1920):
                    raise ValueError("ACTUAL_DECODED_RESOLUTION_REQUIRED")
                thumbnail = image.convert("RGB").resize((240, 427), Image.Resampling.LANCZOS)
            x, y = column * 240, row * 461
            sheet.paste(thumbnail, (x, y + 32))
            draw.text((x + 4, y + 2), name.replace("UP2_", ""), fill="white")
            draw.text((x + 4, y + 16), f"f{index:03d} / {index / 30:.3f}s", fill="#b6d9ff")
            source_images.append({"movie": name, "frame": index,
                                  "file": file.relative_to(HERE).as_posix(), "sha256": sha(file)})
        mapping = base / (name + "_INPUT_SCENE_PIXEL_MAPPING.json")
        results.append({"name": name, "video": (public / (name + ".mp4")).relative_to(HERE).as_posix(),
            "videoSHA256": movie["encodedVideo"]["videoSHA256"], "frames": 180, "fps": 30,
            "seconds": 6, "resolution": [1080, 1920], "codec": "h264", "audio": False,
            "originalNaturalLanguageEnvelope": "examples/" + example + ".json",
            "originalNaturalLanguageEnvelopeSHA256": sha(HERE / "examples" / (example + ".json")),
            "actualCompiledRenderRequest": request.relative_to(HERE).as_posix(), "renderRequestSHA256": sha(request),
            "actualFrameMapping": mapping.relative_to(HERE).as_posix(), "frameMappingSHA256": sha(mapping),
            "audit": (base / "ACTUAL_MOVIES_AUDIT.json").relative_to(HERE).as_posix(),
            "auditSHA256": sha(base / "ACTUAL_MOVIES_AUDIT.json"), "all180FramesDecoded": True,
            "all180CameraProjectionAndDataChecks": "PASS", "segments": movie["segments"],
            "identicalEncodedConsecutiveFrames": movie["encodedVideo"]["decodedIdenticalConsecutiveFrameIndices"],
            "identicalFrameScope": "Measured; deliberate end holds are retained, not concealed or removed.",
            "technicalStatus": "PASS", "visualQuality": "USER_REVIEW_REQUIRED"})
    output = HERE / "public-review/STUDIO_THREE_TOPIC_CONTACT_SHEET.png"
    if output.exists():
        raise ValueError("REFUSE_EXISTING_CONTACT_SHEET")
    sheet.save(output)
    result = {"schema": "WORLD_ENGINE_UP2_FINAL_MOVIES_V1", "technicalStatus": "PASS",
        "actualStudioMovies": 3, "totalActualDecodedFrames": 540, "movies": results,
        "sourceCommit": "002d90516551774aaf5740eb3968fdda07ed5600", "runtime": "SOURCE_CHECKOUT_NOT_OCI_IMAGE",
        "actualSoftwareBackend": "SwiftShader", "paidGpuExecuted": False, "paidApiUsed": False,
        "nvidiaVerified": False, "visualQuality": "USER_REVIEW_REQUIRED", "userApproved": False,
        "contactSheet": {"file": output.relative_to(HERE).as_posix(), "sha256": sha(output),
                         "scope": "24 actual H.264 decoded frames; labels only in review sheet, never in movies",
                         "sourceImages": source_images}}
    write(HERE / "reports/FINAL_MOVIES_AUDIT.json", result)
    print(json.dumps({"technicalStatus": "PASS", "actualStudioMovies": 3, "actualFrames": 540,
                      "contactSheetSHA256": sha(output), "visualQuality": "USER_REVIEW_REQUIRED"}))
