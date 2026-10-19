#!/usr/bin/env python3
"""Read the frozen 80 s source schedule; never generate historical geometry."""
import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
RECOVERY = HERE.parent
ENGINE = RECOVERY.parent
REPO = ENGINE.parent


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def points(coordinates):
    if coordinates and isinstance(coordinates[0], (float, int)):
        yield coordinates[:2]
    else:
        for item in coordinates:
            yield from points(item)


def bbox(geometry):
    p = list(points(geometry["coordinates"]))
    return [min(x[0] for x in p), min(x[1] for x in p),
            max(x[0] for x in p), max(x[1] for x in p)]


def binding(path):
    return {"path": str(path.relative_to(REPO)), "sha256": sha(path), "bytes": path.stat().st_size}


def main():
    submission_file = RECOVERY / "universal-integration-completion-v2/fixtures/VALIDATED_80S_SUBMISSION.json"
    parent_file = RECOVERY / "verified-front-data-v4-recovery/VIDEO_PLAN_80S.json"
    admission_file = RECOVERY / "universal-integration-completion-v2/reports/HISTORY_ADMISSION.json"
    profile_file = RECOVERY / "verified-front-data-v4-recovery/FRONT_PROFILE.json"
    review_file = RECOVERY / "verified-front-data-v4-recovery/evidence/CMH_21_2_SOURCE_REVIEW.json"
    submission = read(submission_file)
    plan, admission, fronts, review = submission["videoPlan"], read(admission_file), read(profile_file), read(review_file)
    chapters = plan["productionV3"]["eventChapters"]
    assert len(chapters) == 12 and plan["totalFrames"] == 2400 and plan["fps"] == 30
    assert [(c["startFrame"], c["endFrame"]) for c in chapters] == [(i * 200, (i + 1) * 200) for i in range(12)]
    geometries = {g["id"]: g for g in plan["legacyScenePlan"]["geometries"]}
    front_by_id = {f["frontId"]: f for f in fronts["fronts"]}
    locations = plan["legacyScenePlan"]["locations"]
    source_files = [submission_file, parent_file, admission_file, profile_file, review_file]
    front_records = []
    for front in fronts["fronts"]:
        path = profile_file.parent / front["sourceFile"]
        assert sha(path) == front["geoJsonSha256"], path
        original = read(path)
        assert original["features"][0]["geometry"] == front["geometry"], path
        source_files.append(path)
        front_records.append({
            **{k: front[k] for k in ("frontId", "mapDate", "mapId", "geoJsonSha256", "sourceFile", "partialSegments", "verifiedSourceExtent", "source")},
            "outputCRS": "EPSG:4326", "sourceMapCRS": "UNKNOWN_NOT_PRINTED",
            "bbox": bbox(front["geometry"]),
            "license": "Official Army map authorship evidence under 17 U.S.C.105; no whole-book blanket license claim",
            "actualSHA256Verified": True,
        })

    rows, chapter_records, all_segments = [], [], []
    count = {"NO_EVENT_GEOMETRY": 0, "SCHEMATIC_HELD_CORE": 0, "ARCHIVAL_PARTIAL_FRONT": 0}
    cover_by_id = {c["chapterId"]: c for c in admission["chapterCoverage"]}
    for chapter in chapters:
        coverage = cover_by_id[chapter["chapterId"]]
        segments = []
        for segment in coverage["sourceSegments"]:
            state = segment["sourceGeometryClock"]["sourceStateId"]
            front_id = segment.get("frontId")
            if not segment["areasAllowed"] and not front_id:
                kind = "NO_EVENT_GEOMETRY"
                refs, details = [], []
            elif front_id:
                kind = "ARCHIVAL_PARTIAL_FRONT"
                front = front_by_id[front_id]
                refs = [front_id]
                details = [{"ref": front_id, "file": str((profile_file.parent / front["sourceFile"]).relative_to(REPO)),
                            "sha256": front["geoJsonSha256"], "bbox": bbox(front["geometry"]), "mapDate": front["mapDate"],
                            "outputCRS": "EPSG:4326", "sourceCRS": "UNKNOWN", "accuracy": front["source"]}]
            else:
                kind = "SCHEMATIC_HELD_CORE"
                clocks = segment["sourceGeometryClock"]
                states = list(dict.fromkeys([clocks["fromStateId"], clocks["toStateId"]]))
                refs = [ref for s in states for ref in (f"HELD_CORE_{s}", f"FRONT_{s}")]
                details = [{"ref": ref, "sourcePlan": str(submission_file.relative_to(REPO)), "sourcePlanSHA256": sha(submission_file),
                            "geometryCanonicalSHA256": hashlib.sha256(canonical(geometries[ref]["geometry"]).encode()).hexdigest(),
                            "outputCRS": "EPSG:4326", "sourceId": geometries[ref]["source_id"],
                            "bbox": bbox(geometries[ref]["geometry"]), "accuracy": "AUTHORED_SCHEMATIC_NOT_MEASURED_MILITARY_CONTROL"} for ref in refs]
            count[kind] += segment["frames"]
            seg = {**segment, "truthKind": kind, "geometryRefs": refs, "geometryEvidence": details}
            segments.append(seg)
            all_segments.append({"chapterId": chapter["chapterId"], "eventId": chapter["eventId"], **seg})
            row = {
                "chapterId": chapter["chapterId"], "eventId": chapter["eventId"], "eventTitle": chapter["title"],
                "eventDateOrRange": chapter["displayLabel"], "historicalEventDateEvidence": chapter["eventTimeWindow"]["status"],
                "startFrame": segment["startFrame"], "endFrameExclusive": segment["endFrame"],
                "startSeconds": round(segment["startFrame"] / 30, 6), "endSecondsExclusive": round(segment["endFrame"] / 30, 6),
                "geometryTruthKind": kind, "sourceStateId": state,
                "sourceMapDate": front_by_id[front_id]["mapDate"] if front_id else segment["sourceGeometryClock"]["snapshotDate"],
                "frontId": front_id or "", "sourceIds": ";".join(chapter["sourceIds"] + (["CMH_PUB_21_2"] if front_id else ["SCHEMATIC_STATES"])),
                "geometryRefs": ";".join(refs), "geometrySourcesAndSHA256": canonical(details),
                "CRS": "EPSG:4326 output/reference; original historical map CRS UNKNOWN" if front_id else "EPSG:4326",
                "spatialAccuracy": "APPROXIMATE_PARTIAL; total positional accuracy UNKNOWN" if front_id else ("NO_EVENT_GEOMETRY" if kind == "NO_EVENT_GEOMETRY" else "SCHEMATIC_NOT_SURVEYED"),
                "territoryAreaPolicy": "SUPPRESSED_PARTIAL_FRONT_ONLY" if front_id else ("NONE" if kind == "NO_EVENT_GEOMETRY" else "SOURCE_ROK_OR_ALLIED_HELD_CORE_ONLY_NO_OPPONENT_COMPLEMENT"),
                "completeBilateralOccupationAvailable": False, "observedDailyMovementAvailable": False,
                "cameraSourceRefs": ";".join(chapter["cameraIntent"]["sourceGeometryRefs"]),
                "cameraTargets": "SOURCE_GEOMETRY_BOUNDING_BOX; optional existing context locations only; candidate output trace required",
                "sourceUnitPositions": "BLOCKED_NO_DATED_NATIONAL_UNIT_POSITIONS_OR_TRACKS",
                "audioCue": "NONE; frozen plan audioSettings.enabled=false; no MP4 generated",
                "license": "Official Army map authorship evidence under 17 U.S.C.105" if front_id else "Newly authored repository schematic data + Natural Earth public-domain coastline",
            }
            rows.append(row)
        camera_targets = []
        for ref in chapter["cameraIntent"]["sourceGeometryRefs"]:
            geo = geometries[ref]["geometry"]
            box = bbox(geo)
            camera_targets.append({"geometryRef": ref, "bbox": box, "bboxCenter": [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2],
                                   "meaning": "Geometric framing target, never troop/event coordinate"})
        chapter_records.append({"chapterId": chapter["chapterId"], "eventId": chapter["eventId"], "title": chapter["title"],
                                "startFrame": chapter["startFrame"], "endFrame": chapter["endFrame"],
                                "startSeconds": chapter["startFrame"] / 30, "endSeconds": chapter["endFrame"] / 30,
                                "eventTimeWindow": chapter["eventTimeWindow"], "sourceEventLabel": chapter["displayLabel"],
                                "narrative": chapter["narration"]["summary"], "sourceGeometrySegments": segments,
                                "cameraIntent": chapter["cameraIntent"], "sourceGeometryCameraTargets": camera_targets,
                                "nationalUnits": "BLOCKED_NO_DATED_COORDINATES", "audio": "SILENT_FROZEN_SOURCE",
                                "fullOpponentArea": "BLOCKED_NO_SOURCE_POLYGONS", "continuousHistoricalFront": "BLOCKED_NO_INTERMEDIATE_OBSERVATIONS"})
    assert count == {"NO_EVENT_GEOMETRY": 60, "SCHEMATIC_HELD_CORE": 1490, "ARCHIVAL_PARTIAL_FRONT": 850}, count
    assert sum(c["endFrame"] - c["startFrame"] for c in chapter_records) == 2400
    # Director buckets are presentation intentions, not new event dates or scheduling authority.
    director = ["발발·남하", "서울 함락·남측 방어", "낙동강 방어", "인천상륙·서울 수복", "북진", "중국군 개입·역전", "재반격·교착", "정전·최종 전선"]
    director_conflicts = []
    for i, intent in enumerate(director):
        actual = [c for c in chapter_records if c["startFrame"] < (i + 1) * 300 and c["endFrame"] > i * 300]
        director_conflicts.append({"startSeconds": i * 10, "endSeconds": (i + 1) * 10, "directorIntent": intent,
                                   "actualChapterIds": [c["chapterId"] for c in actual], "actualTitles": [c["title"] for c in actual],
                                   "status": "CONFLICT_DO_NOT_RETIME_FROZEN_EVENTS" if i in {1, 2, 3, 4, 5, 6, 7} else "PARTIAL_ALIGNMENT_PRESERVE_FROZEN_EVENTS"})
    samples = []
    for frame in range(0, 2400, 150):
        c = next(c for c in chapter_records if c["startFrame"] <= frame < c["endFrame"])
        s = next(s for s in c["sourceGeometrySegments"] if s["startFrame"] <= frame < s["endFrame"])
        samples.append({"frame": frame, "seconds": frame / 30, "chapterId": c["chapterId"], "eventId": c["eventId"],
                        "title": c["title"], "geometryTruthKind": s["truthKind"], "geometryRefs": s["geometryRefs"],
                        "frontId": s.get("frontId"), "sourceStateId": s["sourceGeometryClock"]["sourceStateId"],
                        "areasAllowed": s["areasAllowed"], "sourceDate": front_by_id[s["frontId"]]["mapDate"] if s.get("frontId") else s["sourceGeometryClock"]["snapshotDate"]})
    report = {
        "schema": "WORLD_ENGINE_STORY_DIRECTOR_HISTORY_AND_SCENE_V1", "sourceAuditStatus": "SOURCE_SCHEDULE_VERIFIED_WITH_EXPLICIT_DATA_GAPS",
        "sourceBindings": [binding(p) for p in source_files], "sourceSubmissionSHA256": sha(submission_file),
        "sourcePlanSHA256": sha(parent_file), "sourceEmbeddedVideoPlanCanonicalSHA256": hashlib.sha256(canonical(plan).encode()).hexdigest(),
        "totalFrames": 2400, "fps": 30, "durationSeconds": 80, "chapterCount": 12,
        "chapterRangesAreNotRenderWorkUnitRanges": True, "originalPlanModified": False, "originalGeometryModified": False,
        "frameCoverage": count, "sourceOfficialDatedPartialFronts": front_records, "schematicStates": ["START", "BUSAN", "NORTH_ADVANCE", "SEOUL_WITHDRAWAL", "ARMISTICE"],
        "sourceOfficialMapDocument": {"title": review["document"]["title"], "sourceURL": review["sourceUrl"], "sha256": review["sourceSha256"], "rights": review["rights"]},
        "historicalDateEvidencePolicy": "Curated established event dates remain distinct from dated official map ink; official map retrieval does not certify first-seven-chapter exact fronts",
        "sourceCRSPolicy": "EPSG:4326 output and reference anchors only; historical map projection/datum not printed and total position accuracy unknown",
        "cameraPolicy": "Use existing API and source geometry/context. New presentation targets are not historical event or troop coordinates.",
        "existingGeographicContextLocations": locations, "chapters": chapter_records,
        "directorWindowConflicts": director_conflicts, "samples16": samples,
        "blocked": ["Complete opposing occupation polygons", "Dated national troop positions", "Historical transport/landing/combat routes", "Observed intermediate daily fronts", "Exact source projection and complete historical positional accuracy"],
        "audio": plan["audioSettings"], "visualQuality": "USER_REVIEW_REQUIRED_NOT_GRADED_BY_SOURCE_AUDIT",
    }
    HERE.mkdir(parents=True, exist_ok=True)
    (HERE / "reports").mkdir(exist_ok=True)
    with (HERE / "STORY_80S_SOURCE_LEDGER.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (HERE / "reports/HISTORY_AND_SCENE.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    (HERE / "reports/HISTORY_CAMERA_TARGETS.json").write_text(json.dumps({"existingLocations": locations, "chapters": chapter_records, "samples16": samples}, ensure_ascii=False, indent=2) + "\n")
    lines = ["# 80초 원본 12장면 스토리와 자료 한계", "", "원본 80초·30fps·2,400프레임의 사건 장 순서는 유지한다. 이 문서는 렌더 전 소스 감사이며, 화면 품질 합격 증거가 아니다.", "",
             f"- 정규화된 원본 submission: `{submission_file.relative_to(REPO)}` / SHA-256 `{sha(submission_file)}`.",
             f"- 원본 부모 Scene: `{parent_file.relative_to(REPO)}` / SHA-256 `{sha(parent_file)}`.",
             "- 사건 장은 `productionV3.eventChapters`의 12개 `[startFrame,endFrame)`이다. `scenes`의 렌더 작업 분할 구간과 혼동하지 않는다.",
             "- 첫 60프레임(0~2초)은 사건 Geometry 없음. 이후 도식 held-core 1,490프레임과 공식 지도에 근거한 근사·부분 전선 850프레임이다.",
             "- 양측 전체 점령 폴리곤·관측된 매일의 전선·날짜별 국가 부대 좌표는 없다. 없는 상대편 영토를 보완하거나 국기/부대/상륙 경로를 생성하지 않는다.",
             "- 기존 음향 설정은 무음이다. SFX scheduler 존재와 실제 오디오 출력은 별개다.", "",
             "| 장 | 원본 시간(초) / 프레임 | 사건·날짜 | 실제 화면에 허용되는 자료 | 검증 범위·화면에서 남는 제약 |", "|---|---|---|---|---|"]
    for c in chapter_records:
        data = "; ".join(f"{s['startFrame']/30:.3f}–{s['endFrame']/30:.3f}s {s['truthKind']} {s.get('frontId') or s['sourceGeometryClock']['sourceStateId']}" for s in c["sourceGeometrySegments"])
        caveat = "부분 전선만 표시·모든 점령 면 숨김" if any(s.get("frontId") for s in c["sourceGeometrySegments"]) else "도식 자료의 원래 날짜 유지·실제 사건 당일 점령선 주장 금지"
        if c["eventId"] == "INCHON_LANDING": caveat += "; 인천 상륙 부대·경로·지점 근거 없음"
        if c["eventId"] == "CHINESE_INTERVENTION": caveat += "; 10/25 첫 전투와 10/19 월경·11월 공세 구분"
        lines.append(f"| {c['chapterId']} | {c['startSeconds']:.3f}–{c['endSeconds']:.3f} / [{c['startFrame']},{c['endFrame']}) | {c['title']} · {c['sourceEventLabel']} | {data} | {caveat} |")
    lines += ["", "## 감독 의도와 원본 시간표 충돌", "", "첨부 지시서의 10초 단위 8개 구간은 연출 의도다. 원본 12장의 사건 시점을 그 구간에 강제로 옮기지 않는다. 예를 들어 20초는 낙동강 방어가 아닌 인천상륙작전 장이며, 40초는 북진 장이 아닌 중국군 참전 장이다.", "", "| 감독 구간 | 요청된 의도 | 원본 사건 장 | 판정 |", "|---|---|---|---|"]
    for c in director_conflicts:
        lines.append(f"| {c['startSeconds']}–{c['endSeconds']}s | {c['directorIntent']} | {', '.join(c['actualTitles'])} | {c['status']} |")
    lines += ["", "## 기존 좌표의 카메라 사용", "", "서울 `[126.978,37.5665]`, 부산 `[129.0756,35.1796]`, 평양 `[125.7625,39.0392]`은 원본 `legacyScenePlan.locations`의 지명 맥락이다. 이는 전투·부대·상륙 좌표가 아니다. 전선·held-core의 기존 bbox로 구도를 정할 수 있으나 실제 확대/이동은 별도 픽셀 트레이스로 확인해야 한다.", "", "## 공식 부분 전선의 정확도", "", "CMH PUB21-2의 8개 날짜를 기존 GeoJSON과 SHA로 검증했다. 원본 지도 투영법·datum·전체 위치 정확도는 미확인이다. EPSG:4326은 출력/참조 기준이며 지도 원본 CRS를 증명하지 않는다. 모델 잔차 약 2.26~4.13km는 지도 총 오차가 아니다. 1951-05-19의 잉크 점선 간격을 연결하지 않으며, 1953-07-27은 정밀 측량 MDL이라고 주장하지 않는다.", "", "## 16개 실제 샘플의 소스 상태", "", "| 초 | 전역 프레임 | 원본 사건 | 소스 상태 |", "|---|---|---|---|"]
    for s in samples:
        lines.append(f"| {s['seconds']:g} | {s['frame']} | {s['title']} | {s['geometryTruthKind']}: {s['frontId'] or s['sourceStateId']} ({s['sourceDate']}) |")
    lines += ["", "16장은 반드시 새 PNG 렌더와 provenance로 증명한다. 본 소스 문서만으로 FRAME_RENDER_PASS 또는 VISUAL_QUALITY_PASS를 부여하지 않는다.", ""]
    (HERE / "STORYBOARD_12_SCENES.md").write_text("\n".join(lines))
    print(json.dumps({"chapterCount": len(chapter_records), "ledgerRows": len(rows), "frameCoverage": count, "fronts": len(front_records), "submissionSHA256": sha(submission_file)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
