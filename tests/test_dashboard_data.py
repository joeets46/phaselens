"""Dashboard data access: verified, read-only, and honest about nulls.

Runs without the dashboard dependency group: dashboard_data imports only
the standard library and PhaseLens modules.
"""

import csv
import io
import json
import string

import pytest

from phaselens import cli, dashboard_data as data, pilot, three_sixty
from phaselens.dashboard_i18n import LANGUAGES, TEXT
from synthetic import (
    COMMIT,
    EVENTS_PATH,
    MATCH_ID,
    SECOND_EVENTS_PATH,
    THREE_SIXTY_PATH,
    snapshot,
    source_url,
)

PILOT = "pilots/test_pilot.json"
MANIFEST = f"manifests/statsbomb/open-data/{COMMIT}/match_{MATCH_ID}.json"
SAVED_CSV = f"data/processed/three_sixty/{COMMIT}/{MATCH_ID}/spatial_context.csv"


def starting_xi(event_id, team_id, players):
    return {"id": event_id, "index": 0, "period": 1, "timestamp": "00:00:00.000",
            "type": {"id": 35, "name": "Starting XI"}, "team": {"id": team_id, "name": f"Team {team_id}"},
            "tactics": {"lineup": [{"player": {"id": p, "name": f"Player {p}"}} for p in players]}}


def pressure(event_id, index, team_id, player_id, location):
    return {"id": event_id, "index": index, "period": 1, "timestamp": f"00:00:{index:02d}.000",
            "type": {"id": 17, "name": "Pressure"}, "team": {"id": team_id, "name": f"Team {team_id}"},
            "player": {"id": player_id, "name": f"Player {player_id}"}, "location": location}


FIRST = [starting_xi("xi-1", 1, [11]), starting_xi("xi-2", 2, [21]),
         pressure("p1", 1, 1, 11, [50.0, 40.0]), pressure("p2", 2, 2, 21, [70.0, 30.0])]
SECOND = [starting_xi("yi-2", 2, [21]), starting_xi("yi-3", 3, [31]), pressure("q1", 1, 3, 31, [10.0, 10.0])]
FRAMES = [{"event_uuid": "p1", "visible_area": [0, 0, 120, 0, 120, 80, 0, 0],
           "freeze_frame": [
               {"location": [50.0, 40.0], "teammate": True, "actor": True, "keeper": False},
               {"location": [53.0, 44.0], "teammate": False, "actor": False, "keeper": False},
               {"location": [125.0, 40.0], "teammate": False, "actor": False, "keeper": True},
               {"location": [1.0], "teammate": True, "actor": False, "keeper": False},
           ]}]


@pytest.fixture
def project(tmp_path, monkeypatch, source):
    """A synthetic two-match pilot, plus three-sixty frames and context for match 700."""
    source.responses[source_url(EVENTS_PATH)] = json.dumps(FIRST).encode("utf-8")
    source.responses[source_url(SECOND_EVENTS_PATH)] = json.dumps(SECOND).encode("utf-8")
    source.responses[source_url(THREE_SIXTY_PATH)] = json.dumps(FRAMES).encode("utf-8")
    (tmp_path / "pyproject.toml").write_text("")
    (tmp_path / "pilots").mkdir()
    (tmp_path / PILOT).write_text(json.dumps({
        "pilot_format_version": 1, "source_commit": COMMIT, "competition_id": 900,
        "season_id": 800, "match_ids": [700, 701]}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "fetch_bytes", source.fetch)
    monkeypatch.setattr(cli, "url_exists", source.exists)
    assert cli.main(["pilot", "--file", PILOT]) == 0
    assert cli.main(["three-sixty-ingest", "--manifest", MANIFEST]) == 0
    assert cli.main(["three-sixty-context", "--manifest", MANIFEST]) == 0
    source.fetched.clear()
    source.checked.clear()
    return tmp_path


# --- view 1 ---------------------------------------------------------------


def test_overview_returns_the_verified_pilot_query_results(project, source):
    before = snapshot(project)
    loaded = data.load_overview(project, PILOT)
    columns, rows = pilot.run_pilot_query(project, project / PILOT, "team-totals")
    assert loaded["team_totals"] == [dict(zip(columns, row)) for row in rows]
    assert [r["match_id"] for r in loaded["player_rows"]] == [700, 700, 701, 701]
    assert [m["match_id"] for m in loaded["matches"]] == [700, 701]
    assert loaded["matches"][0]["label"] == "Ünited v City · 2000-01-02"
    assert snapshot(project) == before and source.fetched == []


def test_match_summary_shows_only_what_the_verified_record_holds(project):
    summary = data.match_summary(project, project / MANIFEST)
    assert (summary["competition"], summary["season"], summary["date"]) == ("Synthetic Cup", "2000", "2000-01-02")
    assert (summary["home_team"], summary["away_team"]) == ("Ünited", "City")
    # The synthetic match list holds no stage and no score: nothing is invented.
    assert summary["stage"] is None
    assert (summary["home_score"], summary["away_score"]) == (None, None)


def test_comparison_rows_use_shares_of_the_pair_and_handle_zero_safely():
    summary = {"match_id": 700, "home_team_id": 1, "away_team_id": 2}
    totals = [
        {"match_id": 700, "team_id": 1, "pressure_event_count": 3, "counterpress_pressure_event_count": 0,
         "counterpress_flagged_event_count": 1},
        {"match_id": 700, "team_id": 2, "pressure_event_count": 1, "counterpress_pressure_event_count": 0,
         "counterpress_flagged_event_count": 0},
        {"match_id": 701, "team_id": 2, "pressure_event_count": 99, "counterpress_pressure_event_count": 9,
         "counterpress_flagged_event_count": 9},
    ]
    rows = {row["metric"]: row for row in data.comparison_rows(totals, summary)}
    pressure = rows["pressure_event_count"]
    assert (pressure["home"], pressure["away"], pressure["home_share"], pressure["away_share"]) == (3, 1, 0.75, 0.25)
    both_zero = rows["counterpress_pressure_event_count"]
    assert (both_zero["home"], both_zero["away"], both_zero["home_share"], both_zero["away_share"]) == (0, 0, 0.0, 0.0)
    one_side = rows["counterpress_flagged_event_count"]
    assert (one_side["home_share"], one_side["away_share"]) == (1.0, 0.0)
    assert rows["counterpress_flagged_event_count"]["label"] == "Counterpress-flagged events — supported types"


def test_comparison_rows_without_a_team_row_show_no_value():
    rows = data.comparison_rows([], {"match_id": 700, "home_team_id": 1, "away_team_id": 2})
    assert all(r["home"] is None and r["away"] is None and r["home_share"] == 0.0 for r in rows)


def test_overview_without_pilot_output_says_what_to_run(project):
    combined = project / f"data/processed/analytics/{COMMIT}/pilots/test_pilot/build_metadata.json"
    combined.unlink()
    with pytest.raises(data.DashboardDataError, match=r"uv run phaselens pilot --file"):
        data.load_overview(project, PILOT)


# --- view 2 ---------------------------------------------------------------


def test_explorer_recomputes_context_from_verified_inputs(project, source):
    before = snapshot(project)
    loaded = data.load_explorer(project, MANIFEST)
    rows, _, _ = three_sixty.build_spatial_context(FRAMES, FIRST, COMMIT, MATCH_ID)
    assert loaded["context_by_event"] == {row["event_id"]: row for row in rows}
    assert loaded["radii"] == [5.0, 10.0, 20.0]
    assert snapshot(project) == before and source.fetched == []


def test_events_without_a_frame_stay_selectable_with_null_values(project):
    loaded = data.load_explorer(project, MANIFEST)
    assert [e["id"] for e in loaded["events"]] == ["xi-1", "xi-2", "p1", "p2"]
    row = loaded["context_by_event"]["p2"]
    assert row["calculation_status"] == "no_frame"
    assert row["visible_opponents"] is None and row["nearest_visible_opponent_distance"] is None
    assert loaded["frames_by_event"].get("p2") is None


def test_explorer_refuses_changed_frames_and_says_what_to_run(project):
    (project / f"data/raw/statsbomb/open-data/{COMMIT}/{THREE_SIXTY_PATH}").write_bytes(b"[]")
    with pytest.raises(data.DashboardDataError, match="three-sixty-ingest"):
        data.load_explorer(project, MANIFEST)


def test_explorer_without_frames_says_what_to_run_and_downloads_nothing(project, source):
    (project / f"manifests/statsbomb/open-data/{COMMIT}/match_{MATCH_ID}.three_sixty.json").unlink()
    with pytest.raises(data.DashboardDataError, match="no companion manifest"):
        data.load_explorer(project, MANIFEST)
    assert source.fetched == [] and source.checked == []


# --- saved CSV comparison --------------------------------------------------


def comparison(project, event_id="p1"):
    loaded = data.load_explorer(project, MANIFEST)
    row = loaded["context_by_event"][event_id]
    return data.compare_with_saved(row, loaded["saved_csv"]), row


def rewrite_csv(project, change):
    path = project / SAVED_CSV
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(change(lines)) + "\n", encoding="utf-8")


def test_saved_csv_that_matches_is_reported_as_such(project):
    (status, differing), _ = comparison(project)
    assert (status, differing) == ("matches saved CSV", [])


def test_an_edited_csv_value_is_reported_and_does_not_replace_the_computed_value(project):
    path = project / SAVED_CSV
    records = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"), newline="")))
    edited = next(r for r in records if r["event_id"] == "p1")
    assert edited["nearest_visible_opponent_distance"] == "5.0"
    edited["nearest_visible_opponent_distance"] = "0.5"
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(records[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(records)
    path.write_text(buffer.getvalue(), encoding="utf-8")

    (status, differing), row = comparison(project)

    assert (status, differing) == ("differs from saved CSV", ["nearest_visible_opponent_distance"])
    assert row["nearest_visible_opponent_distance"] == 5.0


@pytest.mark.parametrize(
    "change, status",
    [
        (lambda lines: [lines[0].replace("event_id", "event"), *lines[1:]], "unreadable"),
        (lambda lines: [*lines, "only,three,fields"], "unreadable"),
        (lambda lines: [*lines, lines[3]], "duplicate rows in saved CSV"),
        (lambda lines: [line for line in lines if ",p1," not in line], "event missing from saved CSV"),
    ],
    ids=["other columns", "short row", "duplicate event", "missing event"],
)
def test_comparison_problems_are_reported_without_raising(project, change, status):
    rewrite_csv(project, change)
    (found, _), row = comparison(project)
    assert found == status
    assert row["calculation_status"] == "computed"


def test_missing_or_undecodable_csv_is_reported_without_raising(project):
    (project / SAVED_CSV).write_bytes(b"\xff\xfe\x00broken")
    assert comparison(project)[0][0] == "unreadable"
    (project / SAVED_CSV).unlink()
    assert comparison(project)[0][0] == "absent"


# --- filters and notices --------------------------------------------------


def test_filters_are_built_from_the_events_and_can_be_empty(project):
    events = data.load_explorer(project, MANIFEST)["events"]
    options = data.filter_options(events)
    assert options["types"] == ["Pressure", "Starting XI"]
    assert options["teams"] == [(1, "Team 1"), (2, "Team 2")]
    assert options["players"] == [(11, "Player 11"), (21, "Player 21")]
    assert [e["id"] for e in data.filter_events(events, "Pressure", 2, None)] == ["p2"]
    assert data.filter_events(events, "Pressure", 1, 21) == []
    assert data.event_label(events[2]) == "00:00:01.000 · 1st half · Pressure · Player 11"


def test_player_choices_follow_the_chosen_team_and_type(project):
    events = data.load_explorer(project, MANIFEST)["events"]
    assert data.filter_options(events, team_id=2)["players"] == [(21, "Player 21")]
    assert data.filter_options(events, "Starting XI")["players"] == []


def test_squad_orders_players_from_goalkeeper_to_attack_and_keeps_recorded_times():
    def player(pid, position=None):
        entry = {"player": {"id": pid, "name": f"P{pid}"}}
        return {**entry, "position": {"name": position}} if position else entry

    events = [
        {"type": {"name": "Starting XI"}, "team": {"id": 1, "name": "A"},
         "tactics": {"lineup": [player(9, "Center Forward"), player(1, "Goalkeeper"), player(4, "Left Back"),
                                player(7, "Center Midfield")]}},
        {"type": {"name": "Substitution"}, "team": {"id": 1, "name": "A"}, "minute": 67, "second": 19,
         "player": {"id": 9, "name": "P9"}, "substitution": {"replacement": {"id": 19, "name": "P19"}}},
        {"type": {"name": "Tactical Shift"}, "team": {"id": 1, "name": "A"},
         "tactics": {"lineup": [player(19, "Right Wing"), player(4, "Center Back")]}},
        {"type": {"name": "Pressure"}, "team": {"id": 1, "name": "A"}, "player": {"id": 50, "name": "P50"}},
        *[{"type": {"name": "Pass"}, "team": {"id": 1, "name": "A"}, "player": {"id": pid, "name": f"P{pid}"}}
          for pid in (9, 1, 4, 7, 19)],
    ]
    squad = data.squad(events)
    assert [pid for pid, _ in data.filter_options(events)["players"]] == [1, 4, 7, 19, 9, 50]
    assert squad[4]["position"] == "Left Back"  # the first recorded lineup position
    assert data.player_label(squad[9]) == "P9 · Center Forward · Starting XI · off 67:19"
    assert data.player_label(squad[19], "tr") == "P19 · Sağ kanat · 67:19 girdi"
    assert data.player_label(squad[50], "de") == "P50 · Position nicht erfasst"


# --- display formatting ---------------------------------------------------


@pytest.mark.parametrize(
    "column, value, shown",
    [
        ("nearest_visible_opponent_distance", None, "not computed"),
        ("nearest_visible_opponent_distance", 0.0, "0.000"),
        ("actor_event_distance", 1.5728399701642189e-06, "<0.001"),
        ("actor_event_distance", 0.0009999, "<0.001"),
        ("actor_event_distance", 0.001, "0.001"),
        ("nearest_visible_opponent_distance", 9.379557851291144, "9.380"),
        ("actor_x", 50.5, "50.500"),
        ("actor_y", -1.9991685738044538, "-1.999"),
        ("event_x", 0.0004, "0.000"),
        ("visible_opponents", 0, "0"),
        ("visible_teammates_within_5u", 3, "3"),
        ("player_id", 3205, "3205"),
        ("match_id", 3943043, "3943043"),
        ("context_has_excluded_entries", True, "yes"),
        ("frame_available", False, "no"),
        ("calculation_status", "no_frame", "no_frame"),
    ],
)
def test_values_are_formatted_for_display_only(column, value, shown):
    assert data.format_value(column, value) == shown


def test_formatting_leaves_the_computed_row_untouched(project):
    loaded = data.load_explorer(project, MANIFEST)
    row = loaded["context_by_event"]["p1"]
    before = dict(row)
    [data.format_value(column, row[column]) for column in loaded["context_columns"]]
    data.notices(row, loaded["frames_by_event"]["p1"])
    assert row == before and isinstance(row["nearest_visible_opponent_distance"], float)


def test_distance_in_a_notice_uses_the_same_formatting():
    row = {"calculation_status": "computed", "actor_event_distance": 1.6e-06,
           "entries_outside_frame_convention": 0, "actor_outside_frame_convention": False}
    texts = " ".join(text for _, text in data.notices(row, [{}]))
    assert "is <0.001 units from the recorded action spot" in texts


def test_notices_describe_the_frame_neutrally(project):
    loaded = data.load_explorer(project, MANIFEST)
    computed = data.notices(loaded["context_by_event"]["p1"], loaded["frames_by_event"]["p1"])
    texts = " ".join(text for _, text in computed)
    assert "1 entries in the snapshot were left out" in texts
    assert "outside the 120 × 80 pitch grid" in texts and "not moved" in texts
    assert "0.000 units" in texts and "no limit" in texts
    assert "error" not in texts.lower()
    no_frame = data.notices(loaded["context_by_event"]["p2"], [])
    assert no_frame == [("info", "There is no 360° snapshot for this action, so the situation values are not "
                                 "computed. 'Not computed' is not the same as 0.")]


# --- languages ------------------------------------------------------------


def test_every_text_exists_in_every_language_with_the_same_placeholders():
    def fields(text):
        return {name for _, name, _, _ in string.Formatter().parse(text) if name}

    for key, entry in TEXT.items():
        assert set(entry) == set(LANGUAGES), key
        assert all(entry[language].strip() for language in LANGUAGES), key
        assert len({frozenset(fields(text)) for text in entry.values()}) == 1, key


def test_every_status_and_comparison_result_has_a_text():
    statuses = ["computed", "no_frame", "duplicate_frames", "freeze_frame_malformed",
                "actor_selection_ambiguous", "no_actor", "multiple_actors", "actor_location_invalid"]
    assert all(f"status_{status}" in TEXT for status in statuses)
    results = ["absent", "unreadable", "duplicate rows in saved CSV", "event missing from saved CSV",
               "matches saved CSV", "differs from saved CSV"]
    assert all(f"cmp_{result}" in TEXT for result in results)
    assert all(f"metric_{metric}" in TEXT for metric in data.METRIC_LABELS)


@pytest.mark.parametrize(
    "language, null, true",
    [("en", "not computed", "yes"), ("tr", "hesaplanmadı", "evet"), ("de", "nicht berechnet", "ja")],
)
def test_formatting_translates_words_but_not_numbers(language, null, true):
    assert data.format_value("actor_event_distance", None, language) == null
    assert data.format_value("frame_available", True, language) == true
    assert data.format_value("actor_event_distance", 1.6e-06, language) == "<0.001"
    assert data.format_value("actor_x", 50.5, language) == "50.500"


def test_notices_follow_the_language_and_keep_the_raw_status(project):
    loaded = data.load_explorer(project, MANIFEST)
    no_frame = data.notices(loaded["context_by_event"]["p2"], [], "de")
    assert no_frame == [("info", "Für diese Aktion gibt es keine 360°-Momentaufnahme, daher sind die Werte nicht "
                                 "berechnet. „Nicht berechnet“ ist nicht dasselbe wie 0.")]
    row = {"calculation_status": "no_actor", "entries_outside_frame_convention": 0,
           "actor_outside_frame_convention": False, "actor_event_distance": None}
    (level, text), = data.notices(row, [{}], "tr")
    assert level == "warning" and "aksiyon oyuncusu işaretli değil (no_actor)" in text
    assert data.event_label(loaded["events"][2], "tr") == "00:00:01.000 · 1. yarı · Pres · Player 11"
