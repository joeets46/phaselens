"""The spatial context table of the final is consistent with its inputs.

Computed in memory from the verified local files; nothing is written.
Skipped when the frames file or its companion manifest is absent. The
expected totals are derived from the inputs, not hard-coded.
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
def inputs():
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
    frames, events = json.loads(frames_bytes), json.loads(events_bytes)
    rows, columns, counts = three_sixty.build_spatial_context(frames, events, COMMIT, MATCH_ID)
    return frames, events, rows, counts


def test_one_row_per_source_event(inputs):
    _, events, rows, _ = inputs
    assert [row["event_id"] for row in rows] == [event["id"] for event in events]


def test_rows_with_a_frame_equal_the_distinct_linked_events(inputs):
    frames, events, rows, counts = inputs
    linked = {frame["event_uuid"] for frame in frames} & {event["id"] for event in events}
    assert sum(row["frame_available"] for row in rows) == len(linked)
    assert counts["records_linked_to_an_event"] + counts["records_not_linked_to_an_event"] \
        + counts["records_with_unusable_key"] == counts["records"] == len(frames)


def test_uncomputed_rows_have_null_indicators_and_computed_rows_are_monotone(inputs):
    _, _, rows, _ = inputs
    labels = [three_sixty.radius_label(r) for r in three_sixty.CONTEXT_RADII]
    for row in rows:
        if row["calculation_status"] != "computed":
            assert row["visible_opponents"] is None and row["nearest_visible_opponent_distance"] is None
            continue
        for side, group in (("teammates", "visible_teammates"), ("opponents", "visible_opponents")):
            values = [row[f"visible_{side}_within_{label}"] for label in labels]
            assert values == sorted(values) and values[-1] <= row[group]
        assert (row["nearest_visible_opponent_distance"] is None) == (row["visible_opponents"] == 0)
