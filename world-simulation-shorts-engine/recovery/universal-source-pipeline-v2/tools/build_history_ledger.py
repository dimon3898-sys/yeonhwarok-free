"""Audit cached official history and bind source-coordinate observations.

No network download, geometry invention, renderer or production admission.
"""
import csv
import hashlib
import json
from pathlib import Path
import unicodedata

import fitz

HERE = Path(__file__).resolve().parents[1]
CACHE = Path("/workspace/astra-history-p0-research-20261021")


def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def build():
    prior = json.loads((HERE.parent / "studio-integration-gates-v1/fixtures/INCHEON_SOURCE_GATE.json").read_bytes())
    files = {"GOVINFO_CMH_19_7_UN_OFFENSIVE": CACHE / "GOVINFO_UN_OFFENSIVE_1950.pdf",
             "GOVINFO_CMH_APPLEMAN": CACHE / "GOVINFO_SOUTH_NAKTONG_NORTH_YALU.pdf",
             "GOVINFO_NAVY_ASSAULT_INCHON": CACHE / "GOVINFO_ASSAULT_FROM_SEA_INCHON.pdf"}
    rows = []
    for row in prior["sourceCatalog"]:
        local = files[row["sourceId"]]
        actual_hash = digest(local)
        if actual_hash != row["originalSHA256"] or local.stat().st_size != row["sourceBytes"]:
            raise ValueError("CACHED_OFFICIAL_SOURCE_IDENTITY_CHANGED")
        record = dict(row)
        record.update(originalBytesVerified=True, downloadedAgain=False,
            verificationScope="Cached original PDF bytes, text, and actual map/symbol review; not a new external server availability claim",
            historicalCompleteBilateralCoverage=False, verifiedGeographicCoordinatesCreated=0,
            independentGCPs=0, residualMeters=None, heldOutResidualMeters=None,
            mapCRS=None, mapDatum=None, scaleQualification="Printed graphic/numeric scale does not establish projection/datum or precise EPSG geometry",
            renderQualification="FACT_DATE_AND_SOURCE_CARTOGRAPHY_ONLY_NOT_GEOGRAPHIC_CONTROL")
        if row["sourceId"] == "GOVINFO_CMH_19_7_UN_OFFENSIVE":
            record["newGeometry"] = {"path": "source-review/CMH_UN_OFFENSIVE_PDF008_POSITION_PATHS.json",
                "sha256": digest(HERE / "source-review/CMH_UN_OFFENSIVE_PDF008_POSITION_PATHS.json"),
                "coordinateSpace": "PDF_PAGE_POINTS_TOP_LEFT", "pathCount": 8,
                "night15Paths": 6, "night16Paths": 2,
                "geographicTransform": "BLOCKED_NOT_REGISTERED", "completeOwnerMask": False}
        if row["sourceId"] == "GOVINFO_CMH_APPLEMAN":
            record["newGeometry"] = None
            record["newReinspection"] = "Map VII remains dated open U.S. forward-position traces; gray built-up urban extent, road arrows and assault arrows are not full ownership. No re-tracing because georeferencing would remain unqualified."
        if row["sourceId"] == "GOVINFO_NAVY_ASSAULT_INCHON":
            record["reviewedPDFPages1"] = [2, 4, 6, 15, 21, 24, 27, 30, 31]
            record["printedPageQualification"] = "This PDF uses two-page spreads after introductory pages; PDF page15 contains printed20–21, page27 contains44–45, page30 contains50–51."
            record["newBaseMapLead"] = {"pdfPage1": 15, "printedPages": [20, 21],
                "caption": "This detailed map of the Inchon area, prepared in 1950, clearly shows the narrow passages and numerous mud and tidal flats in the approaches to the harbor. (LC Geography and Map Division)",
                "embeddedXref": 995, "nativeRasterSize": [570, 841], "nativeSHA256": "284134378a3428f67ace6410bef37e863145ef131973b87057d95a3ca58dd406",
                "sourceKind": "1950 historical base/topographic chart, not a control/position map",
                "candidateScale": "1:50,000 header; actual reproduction reduced to570x841pixels",
                "datumProjectionAndGraticuleReadReliably": False, "GCPsCertified": 0,
                "geographicTransform": None, "independentHistoricalDatumIdentified": False,
                "originalLOCItemURL": None, "recordSpecificRights": "UNVERIFIED; embedded chart not republished in this review package",
                "publishedNewImage": False, "useAsControlGeometry": False}
        rows.append(record)
    context = prior["geographicContext"]
    rows.append({"sourceId": "NATURAL_EARTH_MODERN_CONTEXT_ONLY", "institution": "Natural Earth",
        "title": "Natural Earth populated-place Incheon locality (existing receipt)", "publicationYear": None,
        "sourceURL": "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_populated_places_simple.geojson",
        "originalSHA256": context["sourceSHA256"], "license": "Natural Earth Public Domain",
        "existingReceipt": context["receipt"], "coordinates": context["coordinates"],
        "meaning": context["meaning"], "originalBytesVerified": "Existing receipt/hash binding reused; not redownloaded",
        "independentGCPs": 0, "residualMeters": None, "heldOutResidualMeters": None,
        "mapCRS": "EPSG:4326 locality context", "mapDatum": "WGS84",
        "renderQualification": "MODERN_CITY_CONTEXT_ONLY_NOT_1950_LANDING_OR_OWNER_GEOMETRY",
        "historicalCompleteBilateralCoverage": False, "verifiedGeographicCoordinatesCreated": 0})
    facts = [
        {"event_id": "INCHON_LANDING", "fact_id": "CHROMITE_INITIAL_WOLMI", "historical_date": "1950-09-15",
         "time_qualifier": "0633_LOCAL_SOURCE_TIME", "claim": "Initial assault on Wolmi Island began at0633; source says reduction completed0750.",
         "source_id": "GOVINFO_CMH_19_7_UN_OFFENSIVE", "pdf_page_1": 7, "printed_page": "7",
         "quote": "The invasion of Inch’on, code-named Operation CHROMITE, began on the morning of 15 September",
         "geometry_status": "LOCATION_NAMED_ONLY_NO_SOURCE_QUALIFIED_LANDING_COORDINATE", "source_claim_verified": True},
        {"event_id": "INCHON_LANDING", "fact_id": "RED_BLUE_BEACH_EVENING", "historical_date": "1950-09-15",
         "time_qualifier": "EVENING", "claim": "Red and Blue Beach landings took place in the late afternoon; printed times1733 and1732 respectively.",
         "source_id": "GOVINFO_CMH_19_7_UN_OFFENSIVE", "pdf_page_1": 8, "printed_page": "8",
         "quote": "Meanwhile, the 1st Marines’ first wave reached Blue Beach at 1732",
         "geometry_status": "NAMED_BEACH_POSITIONS_IN_SOURCE_MAP_NOT_GEOREGISTERED", "source_claim_verified": True},
        {"event_id": "INCHON_LANDING", "fact_id": "DATED_LOCAL_POSITION_GEOMETRY", "historical_date_interval": ["1950-09-15", "1950-09-16"],
         "time_qualifier": "NIGHT", "claim": "Map legend distinguishes Marine positions on the nights of15 and16September, landing arrows and BHL separately.",
         "source_id": "GOVINFO_CMH_19_7_UN_OFFENSIVE", "pdf_page_1": 8, "printed_page": "8",
         "quote": "Marine Positions, Night, 15 Sep",
         "additional_quote_fragments": ["Marine Positions, Night, 16 Sep", "Beachhead Line"],
         "geometry_status": "8_ORIGINAL_NATIVE_PDF_VECTOR_PATHS_EXTRACTED_IN_PAGE_POINTS", "source_claim_verified": True},
        {"event_id": "INCHON_LANDING", "fact_id": "BEACHHEAD_EVENING_16", "historical_date": "1950-09-16",
         "time_qualifier": "EVENING", "claim": "By evening Marines reached the prearranged beachhead line, described as six miles inland. This narrative does not license filling either owner mask.",
         "source_id": "GOVINFO_CMH_19_7_UN_OFFENSIVE", "pdf_page_1": 9, "printed_page": "9",
         "quote": "By evening they had reached a prearranged beachhead line, six miles inland from the actual landing area.",
         "geometry_status": "NARRATIVE_DISTANCE_NOT_FULL_OWNER_POLYGON", "source_claim_verified": True},
        {"event_id": "SEOUL_RECAPTURE", "fact_id": "SEOUL_EARLY_DECLARATION_IS_NOT_CAPTURE", "historical_date": "1950-09-25",
         "time_qualifier": "BEFORE_MIDNIGHT", "claim": "An early declaration of liberation on25September is distinguished from continued control/fighting; do not use declaration as proof of full ownership.",
         "source_id": "GOVINFO_NAVY_ASSAULT_INCHON", "pdf_page_1": 30, "printed_page": "50–51",
         "quote": "Just before midnight on the 25th, he declared Seoul liberated.",
         "geometry_status": "DECLARATION_NOT_OBSERVED_FULL_CONTROL", "source_claim_verified": True},
        {"event_id": "SEOUL_RECAPTURE", "fact_id": "SEOUL_CAPTURE_28", "historical_date": "1950-09-28",
         "time_qualifier": "DATE_ONLY", "claim": "Naval history explicitly dates capture of Seoul to28September, separate from15September landings.",
         "source_id": "GOVINFO_NAVY_ASSAULT_INCHON", "pdf_page_1": 6, "printed_page": "2–3",
         "quote": "Marine, Army, and South Korean troops captured Seoul on 28 September.",
         "geometry_status": "EVENT_DATE_VERIFIED_NOT_1950_OWNER_POLYGON", "source_claim_verified": True},
        {"event_id": "SEOUL_RECAPTURE", "fact_id": "SEOUL_CEREMONY_29", "historical_date": "1950-09-29",
         "time_qualifier": "DATE_ONLY", "claim": "Ceremonial return of Seoul is a separate event on29September; suburban firing does not imply the entire city was peaceful.",
         "source_id": "GOVINFO_CMH_19_7_UN_OFFENSIVE", "pdf_page_1": 14, "printed_page": "14",
         "quote": "In a brief ceremony on 29 September General MacArthur returned control of Seoul to President Rhee.",
         "geometry_status": "CEREMONY_DATE_NOT_NEW_CONTROL_STATE", "source_claim_verified": True},
    ]
    # Check every factual quotation against actual source-page text. NFKC only
    # expands typographic ligatures; it neither revises dates nor fills history.
    docs = {source_id: fitz.open(path) for source_id, path in files.items()}
    for fact in facts:
        actual = " ".join(unicodedata.normalize("NFKC", docs[fact["source_id"]][fact["pdf_page_1"] - 1].get_text()).split())
        fragments = [fact["quote"], *fact.get("additional_quote_fragments", [])]
        if any(" ".join(unicodedata.normalize("NFKC", fragment).split()) not in actual for fragment in fragments):
            raise ValueError("SOURCE_QUOTATION_NOT_FOUND:" + fact["fact_id"])
        fact["quoteVerifiedAgainstActualPageText"] = True
        fact["normalizedPageTextSHA256"] = hashlib.sha256(actual.encode()).hexdigest()
    for document in docs.values():
        document.close()
    ledger = {"schema": "WORLD_ENGINE_HISTORICAL_PROVENANCE_LEDGER_V2", "baselineCommit": "e6ff697348a8e63c9308d7b4546682cbc6620c96",
        "evidenceRead": {"newG2G3Master": "FULL_TEXT", "assignedASTRAFirstLine": 1601, "assignedASTRALastLine": 3200,
            "cachedOfficialPDFsFullByteHashesVerified": 3, "PDFSourcePositionPathsLosslesslyExtracted": 8,
            "externalNewHistoryDownloadsSucceeded": 0}, "sources": rows, "factClaims": facts,
        "unsupportedGeographicRegistration": {"independentGCPs": 0, "fitResidualMeters": None, "heldOutResidualMeters": None,
            "historicalSourceDatum": None, "sourceToEPSG4326Transform": None,
            "originalCoordinatePrecisionNotEquivalentToGeographicAccuracy": True},
        "fullControlArea": {"status": "BLOCKED", "missing": ["Complete source-qualified bilateral owner masks on1950-09-15night and1950-09-16night",
            "Independent historical landmark/graticule GCPs and held-out geographic validation", "Original datum/projection or validated transform with uncertainty",
            "Source-supported owner/front temporal correspondence, local event ROI and camera admission"],
            "opponentComplementCreated": False, "partialPathsClosedAgainstShoreline": False,
            "modernBoundariesBusanOrFictional65422Substituted": False},
        "verifiedLocalOnly": {"status": "BLOCKED_GEOGRAPHIC_REGISTRATION", "sourceImageOnlyPositions": "VERIFIED_SOURCE_NATIVE_COMMANDS",
            "historicalMapVideoAllowed": False, "partialPreviewIsG3Achievement": False},
        "networkEvidence": {"officialCatalogURL": "https://www.loc.gov/maps/?fo=json&fa=location:korea%7Clocation:inchon&c=25",
            "initialSandboxAttempt": "URLError Operation not permitted; no HTTP request completed",
            "authorizedProxyAttempt": "Tunnel connection failed:403Forbidden", "actualProxyAttempts": 1,
            "sameDeniedDestinationRetried": False, "proxyTLSOrNetworkPolicyBypassed": False,
            "cachedGovInfoPDFsNotRedownloaded": True}, "g2FullArea": "BLOCKED", "g3HistoricalRenderAllowed": False,
        "syntheticProviderTestsAreHistoricalEvidence": False, "visualQualityApproved": False}
    (HERE / "source-ledger.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    columns = ["sourceId", "institution", "title", "publicationYear", "sourceURL", "originalSHA256", "pdfPage1", "mapTitle",
               "classification", "mapCRS", "mapDatum", "independentGCPs", "residualMeters", "heldOutResidualMeters",
               "license", "renderQualification", "historicalCompleteBilateralCoverage"]
    with (HERE / "source-ledger.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"sources": len(rows), "factClaims": len(facts), "fullControlArea": "BLOCKED"}))
    return ledger


if __name__ == "__main__":
    build()
