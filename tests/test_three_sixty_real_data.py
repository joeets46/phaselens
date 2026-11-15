"""The three-sixty report of the ingested final is internally consistent.

Computed in memory from the verified local files; nothing is written.
Skipped when the frames file or its companion manifest is absent: they
are not in Git. No network is used.
"""

import json
from pathlib import Path

import pytest

from phaselens import three_sixty
from phaselens.ingest import check_against_record

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMMIT = "4b73468fc5b0f1950f9f66fada70ad3a4f9327cb"
MATCH_ID = 3943043
COMPANION = PROJECT_ROOT / f"manifests/statsbomb/open-data/{COMMIT}/match_{MATCH_ID}.three_sixty.json"


@pytest.fixture(scope="module")
def report():
    if not COMPANION.is_file():
        pytest.skip("no companion manifest; `phaselens three-sixty-ingest --manifest` retrieves the file")
    companion = json.loads(COMPANION.read_bytes())
    frames_path = PROJECT_ROOT / companion["file"]["local_path"]
    events_path = PROJECT_ROOT / companion["event_source"]["events_file"]["local_path"]
    if not frames_path.is_file() or not events_path.is_file():
        pytest.skip("the frames or events file is not on disk")
    frames_bytes, events_bytes = frames_path.read_bytes(), events_path.read_bytes()
    check_against_record(frames_bytes, companion["file"], str(frames_path))
    check_against_record(events_bytes, companion["event_source"]["events_file"], str(events_path))
    return three_sixty.build_report(json.loads(frames_bytes), json.loads(events_bytes))


def test_linkage_counts_add_up(report):
    linkage = report["summary"]["linkage"]
    assert linkage["events_in_file"] == linkage["distinct_matched_events"] + linkage["events_without_a_record"]
    assert linkage["records_with_usable_key"] == linkage["records"] - (
        linkage["records_with_missing_key"] + linkage["records_with_null_key"] + linkage["records_with_non_string_key"]
    )
    assert linkage["distinct_matched_events"] <= linkage["distinct_keys"] <= linkage["records_with_usable_key"]


def test_grouped_coverage_adds_up_to_the_overall_figure(report):
    overall = report["summary"]["coverage_overall"]
    for grouping in ("event type", "team", "period"):
        rows = [row for row in report["coverage"] if row["grouping"] == grouping]
        assert sum(row["events"] for row in rows) == overall["events"]
        assert sum(row["events_with_360_record"] for row in rows) == overall["events_with_360_record"]


def test_actor_comparison_accounts_for_every_record(report):
    comparison = report["summary"]["actor_location_comparison"]
    assert sum(row["count"] for row in comparison["records_by_outcome"]) == report["summary"]["linkage"]["records"]
    assert sum(row["count"] for row in comparison["distance_buckets"]) == comparison["compared"]
