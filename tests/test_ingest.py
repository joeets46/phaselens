"""Ingestion preserves bytes, records provenance, and never half-finishes."""

import hashlib
import json
import os
from pathlib import PurePosixPath

import pytest

from phaselens import ingest as ingest_module
from phaselens import statsbomb
from phaselens.fetch import FetchError
from phaselens.ingest import IngestError, ingest_match
from synthetic import (
    COMMIT,
    COMPETITION_ID,
    COMPETITIONS_PATH,
    EVENTS_PATH,
    MATCH_ID,
    MATCHES_PATH,
    SEASON_ID,
    SOURCE_FILES,
    THREE_SIXTY_PATH,
    files_under,
    source_url,
)

RAW_DIR = f"data/raw/statsbomb/open-data/{COMMIT}"
MANIFEST = f"manifests/statsbomb/open-data/{COMMIT}/match_{MATCH_ID}.json"


def ingest(project, source, match_id=MATCH_ID, commit=COMMIT):
    return ingest_match(
        project, commit, COMPETITION_ID, SEASON_ID, match_id,
        fetch=source.fetch, exists=source.exists,
    )


def read_manifest(project):
    return json.loads((project / MANIFEST).read_text(encoding="utf-8"))


# --- first run ---------------------------------------------------------


def test_raw_files_hold_exactly_the_downloaded_bytes(project, source):
    ingest(project, source)
    for source_path, data in SOURCE_FILES.items():
        assert (project / RAW_DIR / source_path).read_bytes() == data


def test_first_run_creates_only_the_four_raw_files_and_the_manifest(project, source):
    ingest(project, source)
    expected = [f"{RAW_DIR}/{path}" for path in SOURCE_FILES] + [MANIFEST]
    assert files_under(project) == sorted(expected)


def test_manifest_checksums_and_sizes_match_the_files_on_disk(project, source):
    ingest(project, source)
    entries = read_manifest(project)["files"]
    assert [entry["source_path"] for entry in entries] == list(SOURCE_FILES)
    for entry in entries:
        data = (project / entry["local_path"]).read_bytes()
        assert entry["sha256"] == hashlib.sha256(data).hexdigest()
        assert entry["size_bytes"] == len(data)


def test_manifest_records_the_pinned_origin_of_each_file(project, source):
    ingest(project, source)
    manifest = read_manifest(project)
    assert manifest["manifest_format_version"] == 1
    assert manifest["source"]["repository_url"] == statsbomb.REPOSITORY_URL
    assert manifest["source"]["commit_sha"] == COMMIT
    for entry in manifest["files"]:
        assert entry["source_url"] == source_url(entry["source_path"])
        assert f"/{COMMIT}/" in entry["source_url"]
        assert not PurePosixPath(entry["local_path"]).is_absolute()
        assert entry["retrieved_at_utc"].endswith("Z")


def test_manifest_records_selection_and_match_fields_as_in_the_source(project, source):
    ingest(project, source)
    manifest = read_manifest(project)
    assert manifest["selection"] == {
        "competition_id": COMPETITION_ID,
        "season_id": SEASON_ID,
        "match_id": MATCH_ID,
    }
    assert manifest["match_metadata"] == {
        "match_id": 700,
        "match_date": "2000-01-02",
        "competition": {"competition_id": 900, "competition_name": "Synthetic Cup"},
        "season": {"season_id": 800, "season_name": "2000"},
        "home_team": {"home_team_id": 1, "home_team_name": "Ünited"},
        "away_team": {"away_team_id": 2, "away_team_name": "City"},
    }


@pytest.mark.parametrize("available, recorded", [(True, "present"), (False, "absent")])
def test_three_sixty_file_is_checked_but_not_downloaded(project, source, available, recorded):
    source.three_sixty = available
    ingest(project, source)
    check = read_manifest(project)["three_sixty_check"]
    assert check["result"] == recorded
    assert check["source_url"] == source_url(THREE_SIXTY_PATH)
    assert source.checked == [source_url(THREE_SIXTY_PATH)]
    assert source_url(THREE_SIXTY_PATH) not in source.fetched


# --- failures leave nothing behind --------------------------------------


def test_invalid_json_stops_the_run_and_publishes_nothing(project, source):
    source.responses[source_url(EVENTS_PATH)] = b'[{"id": "e1"}, {"id": '
    with pytest.raises(IngestError, match="not valid JSON"):
        ingest(project, source)
    assert files_under(project) == []


def test_json_that_is_not_an_array_of_objects_is_rejected(project, source):
    source.responses[source_url(EVENTS_PATH)] = b'{"message": "Not Found"}'
    with pytest.raises(IngestError, match="non-empty JSON array"):
        ingest(project, source)
    assert files_under(project) == []


def test_failed_download_publishes_nothing(project, source):
    # The first three files download fine; the last one fails.
    source.responses[source_url(EVENTS_PATH)] = FetchError("events: timed out")
    with pytest.raises(FetchError, match="timed out"):
        ingest(project, source)
    assert files_under(project) == []


def test_failed_three_sixty_check_is_an_error_not_an_absence(project, source):
    source.three_sixty = FetchError("three-sixty: HTTP 503")
    with pytest.raises(FetchError, match="HTTP 503"):
        ingest(project, source)
    assert files_under(project) == []


def test_match_missing_from_the_match_list_stops_the_run(project, source):
    with pytest.raises(IngestError, match="no match with match_id 799"):
        ingest(project, source, match_id=799)
    assert files_under(project) == []
    # Only the competition index and the match list were requested.
    assert source.fetched == [source_url(COMPETITIONS_PATH), source_url(MATCHES_PATH)]


def test_failed_write_leaves_no_partial_file_and_no_earlier_files(project, source, monkeypatch):
    real_replace = os.replace

    def replace_failing_on_events(temporary, destination):
        if str(destination).endswith(f"{MATCH_ID}.json") and "events" in str(destination):
            raise OSError("disk full")
        real_replace(temporary, destination)

    monkeypatch.setattr(os, "replace", replace_failing_on_events)
    with pytest.raises(IngestError, match="cannot write file"):
        ingest(project, source)
    assert files_under(project) == []


def test_branch_name_is_not_accepted_as_a_commit(project, source):
    with pytest.raises(IngestError, match="40-character commit SHA"):
        ingest(project, source, commit="master")
    assert source.fetched == []


def test_existing_file_without_a_manifest_is_never_overwritten(project, source):
    stray = project / RAW_DIR / COMPETITIONS_PATH
    stray.parent.mkdir(parents=True)
    stray.write_bytes(b"not from this pipeline")
    with pytest.raises(IngestError, match="no manifest .* records it"):
        ingest(project, source)
    assert stray.read_bytes() == b"not from this pipeline"
    assert source.fetched == []


# --- repeated run -------------------------------------------------------


def test_rerun_reuses_valid_files_and_keeps_the_manifest_byte_identical(
    project, source, monkeypatch
):
    monkeypatch.setattr(ingest_module, "_utc_now", lambda: "2001-01-01T00:00:00Z")
    first = ingest(project, source)
    manifest_before = (project / MANIFEST).read_bytes()
    source.fetched.clear()
    source.checked.clear()

    # A later clock must not leak into the manifest of an identical rerun.
    monkeypatch.setattr(ingest_module, "_utc_now", lambda: "2002-02-02T00:00:00Z")
    second = ingest(project, source)

    assert first.manifest_written is True
    assert second.manifest_written is False
    assert set(second.file_statuses.values()) == {"reused"}
    assert source.fetched == [] and source.checked == []
    assert (project / MANIFEST).read_bytes() == manifest_before
    assert b"2001-01-01T00:00:00Z" in manifest_before


def test_changed_raw_file_stops_the_rerun_and_is_left_as_found(project, source):
    ingest(project, source)
    manifest_before = (project / MANIFEST).read_bytes()
    events = project / RAW_DIR / EVENTS_PATH
    events.write_bytes(b'[{"id": "tampered"}]')
    source.fetched.clear()

    with pytest.raises(IngestError, match="conflicts with its manifest record"):
        ingest(project, source)

    assert events.read_bytes() == b'[{"id": "tampered"}]'
    assert (project / MANIFEST).read_bytes() == manifest_before
    assert source.fetched == []


def test_missing_raw_file_is_restored_and_verified_against_the_manifest(project, source):
    ingest(project, source)
    manifest_before = (project / MANIFEST).read_bytes()
    events = project / RAW_DIR / EVENTS_PATH
    events.unlink()
    source.fetched.clear()

    result = ingest(project, source)

    assert events.read_bytes() == SOURCE_FILES[EVENTS_PATH]
    assert result.file_statuses[f"{RAW_DIR}/{EVENTS_PATH}"] == "restored"
    assert source.fetched == [source_url(EVENTS_PATH)]
    assert (project / MANIFEST).read_bytes() == manifest_before


def test_restored_content_that_differs_from_the_manifest_is_not_published(project, source):
    ingest(project, source)
    events = project / RAW_DIR / EVENTS_PATH
    events.unlink()
    source.responses[source_url(EVENTS_PATH)] = b'[{"id": "different upstream content"}]'

    with pytest.raises(IngestError, match="conflicts with its manifest record"):
        ingest(project, source)

    assert not events.exists()


def test_manifest_pointing_elsewhere_is_rejected(project, source):
    ingest(project, source)
    manifest = read_manifest(project)
    manifest["files"][0]["local_path"] = "README.md"
    (project / MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(IngestError, match="no consistent record"):
        ingest(project, source)
