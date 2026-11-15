"""Three-sixty frames: retrieved once with a companion manifest, reported offline.

The synthetic events and frames are invented. Each frame exercises one
case the report must count: an exact actor location, a small offset, a
duplicate key, an unmatched key, two actors, a malformed location, an
event without a location, and every kind of visible_area shape.
"""

import json

import pytest

from phaselens import cli, three_sixty
from phaselens.fetch import FetchError
from phaselens.ingest import ingest_match
from synthetic import (
    COMMIT,
    COMPETITION_ID,
    EVENTS_PATH,
    MATCH_ID,
    SEASON_ID,
    SECOND_MATCH_ID,
    THREE_SIXTY_PATH,
    files_under,
    snapshot,
    source_url,
)

MANIFEST = f"manifests/statsbomb/open-data/{COMMIT}/match_{MATCH_ID}.json"
COMPANION = f"manifests/statsbomb/open-data/{COMMIT}/match_{MATCH_ID}.three_sixty.json"
RAW_FRAMES = f"data/raw/statsbomb/open-data/{COMMIT}/{THREE_SIXTY_PATH}"
RAW_EVENTS = f"data/raw/statsbomb/open-data/{COMMIT}/{EVENTS_PATH}"
REPORT_DIR = f"data/processed/three_sixty/{COMMIT}/{MATCH_ID}"
FRAMES_URL = source_url(THREE_SIXTY_PATH)


def event(event_id, type_name, team, period, location=None):
    record = {"id": event_id, "type": {"id": 0, "name": type_name}, "period": period, "team": {"id": 0, "name": team}}
    if location is not None:
        record["location"] = location
    return record


EVENTS = [
    event("e1", "Pass", "Home", 1, [10.0, 20.0]),
    event("e2", "Pressure", "Away", 1, [30.0, 40.0]),
    event("e3", "Carry", "Home", 2, [50.0, 60.0]),
    event("e4", "Half Start", "Home", 1),
    event("e5", "Shot", "Home", 2, [100.0, 40.0]),
    event("e6", "Pass", "Away", 2, [70.0, 10.0]),
    {"id": "e7", "type": {"id": 0, "name": "Referee Ball-Drop"}},  # no team, no period
]


def entry(location, teammate=True, actor=False, keeper=False, **extra):
    record = {"location": location, "teammate": teammate, "actor": actor, "keeper": keeper, **extra}
    return {key: value for key, value in record.items() if value is not ...}


FRAMES = [
    {"event_uuid": "e1", "visible_area": [0, 0, 60, 0, 60, 80, 0, 80, 0, 0],
     "freeze_frame": [entry([10.0, 20.0], actor=True), entry([90.0, 40.0], teammate=False, keeper=True)]},
    {"event_uuid": "e2", "freeze_frame": [entry([30.5, 40.0], actor=True)]},  # no visible_area
    {"event_uuid": "e2", "visible_area": [0, 0, 10, 0, 10, 10], "freeze_frame": [entry([1.0, 1.0])]},
    {"event_uuid": "not-an-event", "visible_area": [0, 0, 1, 1, 0, 0],
     "freeze_frame": [entry([2.0, 2.0], teammate=False)]},
    {"event_uuid": "e3", "visible_area": [0, 0, 1],
     "freeze_frame": [entry([50.0, 60.0], actor=True), entry([51.0, 60.0], actor=True)]},
    {"event_uuid": "e5", "visible_area": [],
     "freeze_frame": [entry([100.0], actor=True),
                      entry([119.0, 40.0], teammate=..., keeper=True, player={"id": 9})]},
    {"event_uuid": "e4", "visible_area": ["a", 1], "freeze_frame": [entry([5.0, 5.0], actor=True, keeper=None)]},
]


def encode(value):
    return json.dumps(value).encode("utf-8")


@pytest.fixture
def project(tmp_path, monkeypatch, source):
    """A project root holding one ingested synthetic match; frames not yet retrieved."""
    source.responses[source_url(EVENTS_PATH)] = encode(EVENTS)
    source.responses[FRAMES_URL] = encode(FRAMES)
    (tmp_path / "pyproject.toml").write_text("")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "fetch_bytes", source.fetch)
    monkeypatch.setattr(cli, "url_exists", source.exists)
    assert cli.main(["ingest", "--commit", COMMIT, "--competition-id", "900",
                     "--season-id", "800", "--match-id", str(MATCH_ID)]) == 0
    source.fetched.clear()
    source.checked.clear()
    return tmp_path


@pytest.fixture
def retrieved(project, source):
    assert cli.main(["three-sixty-ingest", "--manifest", MANIFEST]) == 0
    source.fetched.clear()
    source.checked.clear()
    return project


def summary_of(project):
    return json.loads((project / REPORT_DIR / "summary.json").read_text(encoding="utf-8"))


def counts(rows):
    return {row["value"]: row["count"] for row in rows}


# --- retrieval ------------------------------------------------------------


def test_retrieval_checks_the_path_then_preserves_the_bytes(project, source):
    manifest_before = (project / MANIFEST).read_bytes()

    assert cli.main(["three-sixty-ingest", "--manifest", MANIFEST]) == 0

    assert source.checked == [FRAMES_URL] and source.fetched == [FRAMES_URL]
    assert (project / RAW_FRAMES).read_bytes() == encode(FRAMES)
    assert (project / MANIFEST).read_bytes() == manifest_before


def test_companion_manifest_records_the_file_and_binds_it_to_the_events(project):
    status, companion = three_sixty.ingest_three_sixty(project, project / MANIFEST,
                                                        fetch=lambda url: encode(FRAMES), exists=lambda url: True)
    assert status == "downloaded"
    on_disk = json.loads((project / COMPANION).read_text(encoding="utf-8"))
    assert on_disk == companion
    record = companion["file"]
    assert (record["source_url"], record["local_path"]) == (FRAMES_URL, RAW_FRAMES)
    data = (project / RAW_FRAMES).read_bytes()
    assert record["size_bytes"] == len(data)
    manifest = json.loads((project / MANIFEST).read_text(encoding="utf-8"))
    events_record = next(f for f in manifest["files"] if f["source_path"] == EVENTS_PATH)
    assert companion["event_source"] == {
        "match_manifest": MANIFEST,
        "events_file": {k: events_record[k] for k in ("local_path", "sha256", "size_bytes")},
    }


def test_rerun_verifies_and_reuses_without_any_request(retrieved, source, capsys):
    before = snapshot(retrieved)
    assert cli.main(["three-sixty-ingest", "--manifest", MANIFEST]) == 0
    assert source.fetched == [] and source.checked == []
    assert snapshot(retrieved) == before
    assert "reused" in capsys.readouterr().out


def test_changed_local_file_stops_the_rerun(retrieved, capsys):
    (retrieved / RAW_FRAMES).write_bytes(b'[{"event_uuid": "x"}]')
    before = snapshot(retrieved)
    assert cli.main(["three-sixty-ingest", "--manifest", MANIFEST]) == 1
    assert "conflicts with its manifest record" in capsys.readouterr().err
    assert snapshot(retrieved) == before


def test_missing_local_file_is_restored_and_verified(retrieved, source):
    (retrieved / RAW_FRAMES).unlink()
    companion_before = (retrieved / COMPANION).read_bytes()
    assert cli.main(["three-sixty-ingest", "--manifest", MANIFEST]) == 0
    assert source.fetched == [FRAMES_URL] and source.checked == []
    assert (retrieved / RAW_FRAMES).read_bytes() == encode(FRAMES)
    assert (retrieved / COMPANION).read_bytes() == companion_before


def test_restored_content_that_differs_is_not_published(retrieved, source):
    (retrieved / RAW_FRAMES).unlink()
    source.responses[FRAMES_URL] = b'[{"event_uuid": "different"}]'
    assert cli.main(["three-sixty-ingest", "--manifest", MANIFEST]) == 1
    assert not (retrieved / RAW_FRAMES).exists()


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda c: c["event_source"]["events_file"].update(sha256="0" * 64), "bound to another event source"),
        (lambda c: c.update(companion_format_version=2), "companion format version 2 is not supported"),
        (lambda c: c["file"].pop("sha256"), "its file record is incomplete"),
        (lambda c: c["file"].update(local_path="README.md"), "another commit, match or file location"),
    ],
    ids=["other events", "version", "incomplete", "other location"],
)
def test_companion_metadata_is_validated_before_reuse(retrieved, source, capsys, change, message):
    path = retrieved / COMPANION
    companion = json.loads(path.read_text(encoding="utf-8"))
    change(companion)
    path.write_text(json.dumps(companion), encoding="utf-8")
    assert cli.main(["three-sixty-ingest", "--manifest", MANIFEST]) == 1
    assert message in capsys.readouterr().err
    assert source.fetched == []


@pytest.mark.parametrize(
    "response, message",
    [
        (b'[{"event_uuid": "e1"', "not valid JSON"),
        (b'{"event_uuid": "e1"}', "non-empty JSON array of objects"),
        (FetchError(f"{FRAMES_URL}: timed out after 30 seconds"), "timed out"),
    ],
    ids=["invalid JSON", "not an array", "timeout"],
)
def test_failed_download_leaves_no_file_and_no_companion(project, source, capsys, response, message):
    source.responses[FRAMES_URL] = response
    assert cli.main(["three-sixty-ingest", "--manifest", MANIFEST]) == 1
    assert message in capsys.readouterr().err
    assert not (project / RAW_FRAMES).exists() and not (project / COMPANION).exists()
    assert not (project / (RAW_FRAMES + ".part")).exists()


def test_path_absent_at_the_commit_is_reported_and_nothing_is_downloaded(project, source, capsys):
    source.three_sixty = False
    assert cli.main(["three-sixty-ingest", "--manifest", MANIFEST]) == 1
    assert "HTTP 404 at the pinned commit" in capsys.readouterr().err
    assert source.fetched == []


def test_match_manifest_that_records_no_file_stops_before_any_request(project, source, capsys):
    path = project / MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["three_sixty_check"]["result"] = "absent"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert cli.main(["three-sixty-ingest", "--manifest", MANIFEST]) == 1
    assert "does not record a three-sixty file as present" in capsys.readouterr().err
    assert source.fetched == [] and source.checked == []


def test_existing_file_without_a_companion_is_not_adopted(project, source, capsys):
    (project / RAW_FRAMES).parent.mkdir(parents=True)
    (project / RAW_FRAMES).write_bytes(b"[]")
    assert cli.main(["three-sixty-ingest", "--manifest", MANIFEST]) == 1
    assert "refusing to overwrite or adopt" in capsys.readouterr().err
    assert (project / RAW_FRAMES).read_bytes() == b"[]"
    assert source.fetched == []


def test_companion_manifest_does_not_disturb_ingesting_another_match(retrieved, source):
    # The companion file shares the folder and the match_ prefix with match manifests.
    result = ingest_match(retrieved, COMMIT, COMPETITION_ID, SEASON_ID, SECOND_MATCH_ID,
                          fetch=source.fetch, exists=source.exists)
    assert result.manifest_written is True


# --- report: linkage and coverage -----------------------------------------


@pytest.fixture
def profiled(retrieved, source):
    assert cli.main(["three-sixty-profile", "--manifest", MANIFEST]) == 0
    assert source.fetched == [] and source.checked == []
    return summary_of(retrieved)


def test_linkage_counts_records_keys_duplicates_and_unmatched(profiled):
    linkage = profiled["linkage"]
    assert profiled["link_field"] == "event_uuid"
    assert linkage["records"] == 7
    assert linkage["distinct_keys"] == 6
    assert (linkage["duplicate_keys"], linkage["records_sharing_a_duplicate_key"]) == (1, 2)
    assert linkage["duplicate_key_examples"] == ["e2"]
    assert (linkage["unmatched_records"], linkage["unmatched_key_examples"]) == (1, ["not-an-event"])
    assert linkage["distinct_matched_events"] == 5
    assert (linkage["events_in_file"], linkage["events_without_a_record"]) == (7, 2)


def test_coverage_counts_distinct_events_not_records(profiled):
    # Six records are linked to events, but only five distinct events.
    assert profiled["coverage_overall"] == {
        "grouping": "all events", "value": "all", "events": 7, "events_with_360_record": 5, "percent": 71.43,
    }


def test_grouped_coverage_has_explicit_denominators_and_missing_groups(retrieved, profiled):
    lines = (retrieved / REPORT_DIR / "coverage.csv").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "grouping,value,events,events_with_360_record,percent"
    rows = {tuple(line.split(",")[:2]): tuple(line.split(",")[2:]) for line in lines[1:]}
    assert rows[("event type", "Pass")] == ("2", "1", "50.0")
    assert rows[("event type", "Pressure")] == ("1", "1", "100.0")
    assert rows[("team", "Away")] == ("2", "1", "50.0")
    assert rows[("team", "(missing)")] == ("1", "0", "0.0")
    assert rows[("period", "1")] == ("3", "3", "100.0")
    assert rows[("period", "(missing)")] == ("1", "0", "0.0")


# --- report: structure, identity, visible area -----------------------------


def test_flags_keep_true_false_null_and_missing_apart(profiled):
    flags = profiled["structure"]["freeze_frame"]["flags"]
    assert counts(flags["teammate"]) == {"true": 7, "false": 2, "missing": 1}
    assert counts(flags["actor"]) == {"true": 6, "false": 4}
    assert counts(flags["keeper"]) == {"false": 7, "true": 2, "null": 1}


def test_location_shapes_and_ranges(profiled):
    frame = profiled["structure"]["freeze_frame"]
    assert frame["entries"] == 10
    assert counts(frame["location_shapes"]) == {"two numbers": 9, "1 numbers": 1}
    assert frame["location_ranges"] == {"x": [1.0, 119.0], "y": [1.0, 60.0]}


def test_visible_area_shapes_are_structural_only(profiled):
    assert counts(profiled["structure"]["visible_area"]["records_by_shape"]) == {
        "even numeric, first point repeated at the end": 2,
        "even numeric, first point not repeated at the end": 1,
        "missing": 1,
        "empty list": 1,
        "odd number of values": 1,
        "non-numeric element": 1,
    }


def test_identity_separates_actor_keeper_and_candidate_identifiers(profiled):
    identity = profiled["identity"]
    # Counted over all seven records, the unmatched one included.
    assert counts(identity["records_by_actor_entries"]) == {"one": 4, "zero": 2, "more than one": 1}
    assert counts(identity["keeper_entries_by_teammate_flag"]) == {"false": 1, "missing": 1}
    assert counts(identity["undocumented_entry_keys"]) == {"player": 1}
    assert identity["undocumented_record_keys"] == []


# --- report: actor location ----------------------------------------------


def test_actor_comparison_counts_each_outcome(profiled):
    comparison = profiled["actor_location_comparison"]
    assert counts([{"value": r["value"], "count": r["count"]} for r in comparison["records_by_outcome"]]) == {
        "compared": 2,
        "no actor-marked entry": 1,
        "more than one actor-marked entry": 1,
        "actor location missing or malformed": 1,
        "event has no location": 1,
        "record not linked to an event": 1,
    }
    assert (comparison["compared"], comparison["exact_matches"]) == (2, 1)
    assert comparison["distance_quantiles"] == {"min": 0.0, "p50": 0.0, "p90": 0.5, "p99": 0.5, "max": 0.5}
    buckets = {row["bucket"]: row["count"] for row in comparison["distance_buckets"]}
    assert buckets["exactly 0"] == 1 and buckets["over 0.0 up to 0.5"] == 1
    assert "not converted to metres" in comparison["units"]


# --- report: offline and repeatable ---------------------------------------


def test_report_is_byte_identical_on_a_second_run(retrieved):
    outputs = []
    for _ in range(2):
        assert cli.main(["three-sixty-profile", "--manifest", MANIFEST]) == 0
        outputs.append({name: (retrieved / REPORT_DIR / name).read_bytes() for name in three_sixty.REPORT_FILES})
    assert outputs[0] == outputs[1]


def test_report_never_downloads_a_missing_frames_file(retrieved, source, capsys):
    (retrieved / RAW_FRAMES).unlink()
    assert cli.main(["three-sixty-profile", "--manifest", MANIFEST]) == 1
    assert "not on disk" in capsys.readouterr().err
    assert source.fetched == []
    assert not (retrieved / REPORT_DIR).exists()


def test_report_refuses_changed_frames_or_events(retrieved, capsys):
    (retrieved / RAW_FRAMES).write_bytes(b'[{"event_uuid": "x"}]')
    assert cli.main(["three-sixty-profile", "--manifest", MANIFEST]) == 1
    assert "conflicts with its manifest record" in capsys.readouterr().err
    assert files_under(retrieved / "data" / "processed") == []


def test_report_requires_a_companion_manifest(project, capsys):
    assert cli.main(["three-sixty-profile", "--manifest", MANIFEST]) == 1
    assert "no companion manifest" in capsys.readouterr().err
