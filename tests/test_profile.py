"""The profiler counts what is present and reports what it cannot explain.

Events here are invented and minimal. They carry only the keys a test
needs and say nothing about the real StatsBomb schema.
"""

import pytest

from phaselens import cli
from phaselens.profile import (
    ALL_EVENTS,
    OUTPUT_FILES,
    build_profile,
    coordinate_fields,
    event_structure,
    field_presence,
    off_ball_availability,
    quality_findings,
    write_profile,
)
from synthetic import COMMIT, EVENTS_PATH, MATCH_ID, files_under, snapshot

MATCH = {"home_team": {"home_team_id": 10}, "away_team": {"away_team_id": 20}}
LINEUPS = [
    {
        "team_id": 10,
        "team_name": "Home",
        "lineup": [
            {"player_id": 100, "positions": [{"start_reason": "Starting XI"}], "cards": []},
            {"player_id": 101, "positions": [], "cards": []},
        ],
    },
    {"team_id": 20, "team_name": "Away", "lineup": [{"player_id": 200, "positions": []}]},
]


def event(index, type_name, **fields):
    """A well-formed event; `fields` add to it or override it."""
    base = {
        "id": f"id-{index}",
        "index": index,
        "period": 1,
        "timestamp": f"00:00:{index:02d}.000",
        "minute": 0,
        "second": index,
        "type": {"id": 1, "name": type_name},
        "team": {"id": 10, "name": "Home"},
        "player": {"id": 100, "name": "Player 100"},
    }
    base.update(fields)
    return base


def without(record, key):
    return {name: value for name, value in record.items() if name != key}


def finding(events, check, lineups=LINEUPS, match=MATCH):
    findings = {item["check"]: item for item in quality_findings(events, lineups, match)}
    return findings[check]


def presence(events, scope, path):
    rows = [row for row in field_presence(events) if (row["scope"], row["field_path"]) == (scope, path)]
    return rows[0] if rows else None


# --- structure and counts -------------------------------------------------


def test_events_are_counted_by_type_team_and_period():
    events = [
        event(1, "Pass"),
        event(2, "Pass"),
        event(3, "Carry", team={"id": 20, "name": "Away"}),
        event(4, "Pass", period=2),
    ]
    structure = event_structure(events)
    assert structure["event_count"] == 4
    assert structure["by_type"] == [{"value": "Pass", "count": 3}, {"value": "Carry", "count": 1}]
    assert structure["by_team"] == [{"value": "Home", "count": 3}, {"value": "Away", "count": 1}]
    assert structure["by_period"] == [{"period": 1, "events": 3}, {"period": 2, "events": 1}]


def test_nested_fields_get_dotted_paths_and_lists_are_not_expanded():
    events = [
        event(
            1,
            "Pass",
            **{"pass": {"end_location": [60.0, 40.0], "recipient": {"id": 101, "name": "Player 101"}}},
        )
    ]
    paths = {row["field_path"] for row in field_presence(events) if row["scope"] == ALL_EVENTS}
    assert {"pass", "pass.end_location", "pass.recipient", "pass.recipient.id"} <= paths
    assert presence(events, ALL_EVENTS, "pass.end_location")["value_kinds"] == "list"
    assert not any(path.startswith("pass.end_location.") for path in paths)


def test_missing_null_and_non_null_are_separate_counts():
    events = [
        event(1, "Pass", **{"pass": {"outcome": {"name": "Incomplete"}}}),
        event(2, "Pass", **{"pass": {"outcome": None}}),
        event(3, "Pass", **{"pass": {}}),
        event(4, "Pass"),
    ]
    row = presence(events, ALL_EVENTS, "pass.outcome")
    assert (row["non_null"], row["null"], row["missing"]) == (1, 1, 2)
    assert row["denominator"] == 4


def test_percentages_use_the_events_of_the_scope_as_denominator():
    events = [
        event(1, "Pass", **{"pass": {"end_location": [1.0, 2.0]}}),
        event(2, "Pass", **{"pass": {"end_location": [3.0, 4.0]}}),
        event(3, "Carry"),
        event(4, "Carry"),
        event(5, "Carry"),
    ]
    overall = presence(events, ALL_EVENTS, "pass.end_location")
    within_type = presence(events, "Pass", "pass.end_location")
    assert (overall["denominator"], overall["non_null"], overall["percent_non_null"]) == (5, 2, 40.0)
    assert (within_type["denominator"], within_type["percent_non_null"]) == (2, 100.0)
    # A field another type carries is not listed for Carry at all.
    assert presence(events, "Carry", "pass.end_location") is None


def test_off_ball_types_and_fields_absent_from_a_match_are_reported_as_zero():
    events = [event(1, "Pressure", counterpress=True), event(2, "Pressure"), event(3, "Pass")]
    availability = off_ball_availability(events)
    by_type = {item["event_type"]: item for item in availability["event_types"]}
    by_field = {item["field_path"]: item for item in availability["fields"]}
    assert (by_type["Pressure"]["events"], by_type["Pressure"]["with_counterpress"]) == (2, 1)
    assert by_type["Interception"]["events"] == 0
    assert by_field["counterpress"]["events"] == 1
    assert by_field["duel.outcome.name"]["events"] == 0


# --- consistency checks ---------------------------------------------------


def test_duplicate_event_ids_are_an_error():
    events = [event(1, "Pass"), event(2, "Pass", id="id-1"), event(3, "Pass")]
    duplicate = finding(events, "duplicate_event_ids")
    assert (duplicate["category"], duplicate["count"], duplicate["examples"]) == ("error", 1, ["id-1"])
    assert event_structure(events)["ids"]["distinct_ids"] == 2


def test_events_without_a_usable_player_do_not_crash_and_are_classified():
    events = [
        without(event(1, "Half Start"), "player"),
        event(2, "Pass"),
        without(event(3, "Pass"), "player"),
        event(4, "Pass", player=None),
        event(5, "Pass", player="not an object"),
    ]
    assert event_structure(events)["identifiers"]["events_with_player_id"] == 1
    structural = finding(events, "events_without_player_in_types_that_never_have_one")
    unexplained = finding(events, "events_without_player_in_types_that_usually_have_one")
    assert (structural["category"], structural["count"]) == ("expected_absence", 1)
    assert (unexplained["category"], unexplained["count"]) == ("unresolved", 3)


def test_team_outside_the_match_is_an_error_and_unlisted_player_a_warning():
    events = [
        event(1, "Pass"),
        event(2, "Pass", team={"id": 99, "name": "Elsewhere"}),
        event(3, "Pass", player={"id": 555, "name": "Unlisted"}),
    ]
    assert finding(events, "event_team_not_in_match")["category"] == "error"
    unlisted = finding(events, "event_player_not_in_team_lineup")
    assert unlisted["category"] == "warning"
    assert "team 10 player 555" in unlisted["examples"]


def test_related_event_missing_from_the_file_is_a_warning():
    events = [event(1, "Pass", related_events=["id-2", "id-404"]), event(2, "Carry")]
    missing = finding(events, "related_event_id_not_in_file")
    assert (missing["category"], missing["count"], missing["checked"]) == ("warning", 1, 2)


def test_unexpected_coordinate_shapes_are_reported_not_dropped():
    events = [
        event(1, "Pass", location=[10.0, 20.0]),
        event(2, "Pass", location=[30.0]),
        event(3, "Pass", location=[1.0, 2.0, 3.0, 4.0]),
        event(4, "Pass", location=["a", 2.0]),
        event(5, "Pass", location="10,20"),
        event(6, "Shot", shot={"end_location": [100.0, 40.0, 1.5]}),
    ]
    unexpected = finding(events, "unexpected_coordinate_shape")
    three = finding(events, "three_component_coordinates")
    assert (unexpected["category"], unexpected["count"]) == ("warning", 4)
    assert (three["category"], three["count"]) == ("unresolved", 1)

    location = next(f for f in coordinate_fields(events) if f["field_path"] == "location")
    assert location["not_a_list"] == 1
    assert location["with_non_numeric_element"] == 1
    assert location["list_lengths"] == [
        {"length": 1, "count": 1},
        {"length": 2, "count": 2},
        {"length": 4, "count": 1},
    ]
    assert location["observed_ranges"][0] == {"component": 0, "min": 1.0, "max": 30.0}


def test_coordinates_inside_lists_of_objects_are_found():
    frame = [{"location": [100.0, 30.0]}, {"location": [110.0, 50.0]}]
    events = [event(1, "Shot", shot={"freeze_frame": frame})]
    field = next(f for f in coordinate_fields(events) if f["field_path"] == "shot.freeze_frame[].location")
    assert (field["events"], field["values"]) == (1, 2)


def test_time_order_is_judged_within_each_period():
    restart = [
        event(1, "Pass", timestamp="00:44:59.000", minute=44, second=59),
        event(2, "Pass", period=2, timestamp="00:00:01.000", minute=45, second=1),
        event(3, "Pass", period=2, timestamp="00:00:02.000", minute=45, second=2),
    ]
    assert finding(restart, "timestamp_decreases_within_period")["category"] == "pass"

    backwards = restart + [event(4, "Pass", period=2, timestamp="00:00:01.500", minute=45, second=1)]
    drop = finding(backwards, "timestamp_decreases_within_period")
    assert (drop["category"], drop["count"]) == ("warning", 1)
    assert finding(backwards, "minute_second_decreases_within_period")["count"] == 1
    assert finding(backwards, "period_decreases_in_file_order")["category"] == "pass"


def test_empty_and_shapeless_inputs_are_profiled_without_a_crash():
    assert build_profile([], [], {})["summary"]["events"]["event_count"] == 0
    shapeless = build_profile([{"id": "x"}, {}], [{"team_id": 1}], {})
    assert shapeless["summary"]["events"]["by_type"] == [{"value": "(missing)", "count": 2}]
    assert finding([{"id": "x"}, {}], "events_without_usable_id", [], {})["count"] == 1


# --- outputs --------------------------------------------------------------


def test_same_input_gives_byte_identical_output(tmp_path):
    events = [
        event(1, "Pass", location=[1.0, 2.0], related_events=["id-2"], under_pressure=True),
        event(2, "Pressure", counterpress=True, location=[3.0, 4.0]),
        event(3, "Carry", carry={"end_location": [5.0, 6.0]}),
    ]
    for name in ("first", "second"):
        write_profile(tmp_path / name, build_profile(events, LINEUPS, MATCH))
    assert files_under(tmp_path / "first") == sorted(OUTPUT_FILES)
    for name in OUTPUT_FILES:
        assert (tmp_path / "first" / name).read_bytes() == (tmp_path / "second" / name).read_bytes()


# --- command line, on an ingested synthetic match --------------------------

MANIFEST = f"manifests/statsbomb/open-data/{COMMIT}/match_{MATCH_ID}.json"
PROFILE_DIR = f"data/processed/profiles/{COMMIT}/{MATCH_ID}"
SELECTION = ["--competition-id", "900", "--season-id", "800", "--match-id", str(MATCH_ID)]


@pytest.fixture
def ingested(tmp_path, monkeypatch, source):
    """A project root holding one ingested synthetic match."""
    (tmp_path / "pyproject.toml").write_text("")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "fetch_bytes", source.fetch)
    monkeypatch.setattr(cli, "url_exists", source.exists)
    assert cli.main(["ingest", "--commit", COMMIT, *SELECTION]) == 0
    source.fetched.clear()
    source.checked.clear()
    return tmp_path


def test_profile_command_writes_outputs_and_touches_nothing_else(ingested, source, capsys):
    before = snapshot(ingested)

    assert cli.main(["profile", "--manifest", MANIFEST]) == 0

    after = snapshot(ingested)
    assert {path: after[path] for path in before} == before
    assert sorted(set(after) - set(before)) == sorted(f"{PROFILE_DIR}/{name}" for name in OUTPUT_FILES)
    assert source.fetched == [] and source.checked == []
    assert "Verified against the manifest: 4 files" in capsys.readouterr().out


def test_profile_command_is_repeatable_byte_for_byte(ingested):
    assert cli.main(["profile", "--manifest", MANIFEST]) == 0
    first = {name: (ingested / PROFILE_DIR / name).read_bytes() for name in OUTPUT_FILES}
    assert cli.main(["profile", "--manifest", MANIFEST]) == 0
    second = {name: (ingested / PROFILE_DIR / name).read_bytes() for name in OUTPUT_FILES}
    assert first == second


def test_profile_refuses_a_raw_file_that_differs_from_the_manifest(ingested, capsys):
    events = ingested / f"data/raw/statsbomb/open-data/{COMMIT}" / EVENTS_PATH
    events.write_bytes(b'[{"id": "tampered"}]')

    assert cli.main(["profile", "--manifest", MANIFEST]) == 1

    assert "conflicts with its manifest record" in capsys.readouterr().err
    assert not (ingested / PROFILE_DIR).exists()


def test_profile_does_not_download_a_missing_raw_file(ingested, source, capsys):
    (ingested / f"data/raw/statsbomb/open-data/{COMMIT}" / EVENTS_PATH).unlink()

    assert cli.main(["profile", "--manifest", MANIFEST]) == 1

    assert "not on disk" in capsys.readouterr().err
    assert source.fetched == []
    assert not (ingested / PROFILE_DIR).exists()
