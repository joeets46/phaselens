"""A second match at the same commit reuses shared files only when verified.

The competition index and the match list are shared by every match of a
competition-season. A copy already on disk is reused when another
manifest at the same commit records it and its bytes still match.
"""

import json
import os

import pytest

from phaselens import ingest as ingest_module
from phaselens.ingest import IngestError, ingest_match
from synthetic import (
    COMMIT,
    COMPETITION_ID,
    COMPETITIONS_PATH,
    MATCH_ID,
    MATCHES_PATH,
    SEASON_ID,
    SECOND_EVENTS_PATH,
    SECOND_LINEUPS_PATH,
    SECOND_MATCH_ID,
    snapshot,
    source_url,
)

RAW_DIR = f"data/raw/statsbomb/open-data/{COMMIT}"
MANIFEST_DIR = f"manifests/statsbomb/open-data/{COMMIT}"
FIRST_MANIFEST = f"{MANIFEST_DIR}/match_{MATCH_ID}.json"
SECOND_MANIFEST = f"{MANIFEST_DIR}/match_{SECOND_MATCH_ID}.json"

FIRST_RUN_TIME = "2001-01-01T00:00:00Z"
SECOND_RUN_TIME = "2002-02-02T00:00:00Z"


def ingest(project, source, match_id):
    return ingest_match(
        project, COMMIT, COMPETITION_ID, SEASON_ID, match_id,
        fetch=source.fetch, exists=source.exists,
    )


def read_json(project, path):
    return json.loads((project / path).read_text(encoding="utf-8"))


@pytest.fixture
def first_match(project, source, monkeypatch):
    """The first match is ingested; returns the state it left on disk.

    The clock then moves on, so a timestamp written by a later run is
    distinguishable from one carried over.
    """
    monkeypatch.setattr(ingest_module, "_utc_now", lambda: FIRST_RUN_TIME)
    ingest(project, source, MATCH_ID)
    monkeypatch.setattr(ingest_module, "_utc_now", lambda: SECOND_RUN_TIME)
    source.fetched.clear()
    source.checked.clear()
    return snapshot(project)


# --- the corrected behaviour --------------------------------------------


def test_second_match_reuses_shared_files_and_downloads_only_its_own(
    project, source, first_match
):
    result = ingest(project, source, SECOND_MATCH_ID)

    assert result.file_statuses == {
        f"{RAW_DIR}/{COMPETITIONS_PATH}": "reused",
        f"{RAW_DIR}/{MATCHES_PATH}": "reused",
        f"{RAW_DIR}/{SECOND_LINEUPS_PATH}": "downloaded",
        f"{RAW_DIR}/{SECOND_EVENTS_PATH}": "downloaded",
    }
    assert source.fetched == [source_url(SECOND_LINEUPS_PATH), source_url(SECOND_EVENTS_PATH)]


def test_second_match_leaves_earlier_files_and_the_first_manifest_untouched(
    project, source, first_match
):
    ingest(project, source, SECOND_MATCH_ID)

    after = snapshot(project)
    # Same bytes and same modification time for everything that existed.
    assert {path: after[path] for path in first_match} == first_match
    assert sorted(set(after) - set(first_match)) == [
        f"{RAW_DIR}/{SECOND_EVENTS_PATH}",
        f"{RAW_DIR}/{SECOND_LINEUPS_PATH}",
        SECOND_MANIFEST,
    ]


def test_second_match_gets_its_own_manifest_with_the_original_shared_records(
    project, source, first_match
):
    ingest(project, source, SECOND_MATCH_ID)

    first = read_json(project, FIRST_MANIFEST)
    second = read_json(project, SECOND_MANIFEST)
    assert second["selection"]["match_id"] == SECOND_MATCH_ID
    assert second["match_metadata"]["match_id"] == SECOND_MATCH_ID
    assert second["source"] == first["source"]
    # The shared records are the first run's records, retrieval time included.
    assert second["files"][:2] == first["files"][:2]
    assert [entry["retrieved_at_utc"] for entry in second["files"]] == [
        FIRST_RUN_TIME,
        FIRST_RUN_TIME,
        SECOND_RUN_TIME,
        SECOND_RUN_TIME,
    ]


def test_both_matches_verify_on_a_rerun_without_any_request(project, source, first_match):
    ingest(project, source, SECOND_MATCH_ID)
    source.fetched.clear()
    state = snapshot(project)

    for match_id in (MATCH_ID, SECOND_MATCH_ID):
        result = ingest(project, source, match_id)
        assert set(result.file_statuses.values()) == {"reused"}
        assert result.manifest_written is False

    assert source.fetched == []
    assert snapshot(project) == state


def test_unknown_match_id_is_reported_even_when_shared_files_exist(
    project, source, first_match
):
    with pytest.raises(IngestError, match="no match with match_id 799"):
        ingest(project, source, 799)

    # No lineups or events were requested and no manifest was created.
    assert source.fetched == [] and source.checked == []
    assert snapshot(project) == first_match


# --- reuse is refused when it cannot be justified -----------------------


def test_changed_shared_file_stops_the_second_match_and_is_left_as_found(
    project, source, first_match
):
    competitions = project / RAW_DIR / COMPETITIONS_PATH
    competitions.write_bytes(b'[{"competition_id": 900, "season_id": 800}]')
    state = snapshot(project)

    with pytest.raises(IngestError, match="conflicts with its manifest record"):
        ingest(project, source, SECOND_MATCH_ID)

    assert source.fetched == []
    assert snapshot(project) == state


def test_existing_file_that_no_manifest_records_is_not_adopted(project, source, first_match):
    stray = project / RAW_DIR / SECOND_LINEUPS_PATH
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_bytes(b'[{"team_id": 2}]')
    state = snapshot(project)

    with pytest.raises(IngestError, match="no manifest .* records it"):
        ingest(project, source, SECOND_MATCH_ID)

    assert source.fetched == []
    assert snapshot(project) == state


@pytest.mark.parametrize(
    "field, value",
    [
        ("sha256", "0" * 64),
        ("size_bytes", 1),
        ("retrieved_at_utc", "1999-09-09T00:00:00Z"),
    ],
)
def test_conflicting_provenance_records_stop_the_run(
    project, source, first_match, field, value
):
    # A third manifest at this commit records the shared file differently.
    other = read_json(project, FIRST_MANIFEST)
    other["selection"]["match_id"] = 650
    other["files"][0][field] = value
    (project / MANIFEST_DIR / "match_650.json").write_text(json.dumps(other), encoding="utf-8")
    state = snapshot(project)

    with pytest.raises(IngestError, match=f"conflict.*disagree on {field}"):
        ingest(project, source, SECOND_MATCH_ID)

    assert source.fetched == []
    assert snapshot(project) == state


def test_record_for_another_location_cannot_vouch_for_the_file(project, source, first_match):
    manifest = read_json(project, FIRST_MANIFEST)
    manifest["files"][0]["source_url"] = "https://example.invalid/competitions.json"
    (project / FIRST_MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(IngestError, match="cannot vouch"):
        ingest(project, source, SECOND_MATCH_ID)

    assert source.fetched == []


def test_failed_write_for_the_second_match_keeps_the_reused_files(
    project, source, first_match, monkeypatch
):
    real_replace = os.replace

    def replace_failing_on_second_events(temporary, destination):
        if str(destination).endswith(f"{SECOND_MATCH_ID}.json") and "events" in str(destination):
            raise OSError("disk full")
        real_replace(temporary, destination)

    monkeypatch.setattr(os, "replace", replace_failing_on_second_events)
    with pytest.raises(IngestError, match="cannot write file"):
        ingest(project, source, SECOND_MATCH_ID)

    # The second match's lineups were rolled back; shared files were kept.
    assert snapshot(project) == first_match
