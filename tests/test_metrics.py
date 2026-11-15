"""The three event counts follow docs/metric_catalog.md, contract version 1.

"Case N" refers to the acceptance table in that document. Events here
are invented and carry only the keys the contract reads.
"""

import csv
import hashlib
import io
import json

import pytest

from phaselens import cli
from phaselens.metrics import (
    METRIC_NAMES,
    OUTPUT_FILES,
    MetricError,
    compute_match_metrics,
)
from synthetic import (
    COMMIT,
    EVENTS_PATH,
    LINEUPS_PATH,
    MATCH_ID,
    files_under,
    snapshot,
    source_url,
)

# The synthetic match list gives match 700 these two team ids.
HOME, AWAY = 1, 2
MATCH = {"home_team": {"home_team_id": HOME}, "away_team": {"away_team_id": AWAY}}
TYPE_IDS = {
    "Pressure": 17,
    "Duel": 4,
    "Block": 6,
    "Foul Committed": 22,
    "Pass": 30,
    "Starting XI": 35,
    "Substitution": 19,
}


def starting_xi(event_id, team_id, player_ids):
    return {
        "id": event_id,
        "type": {"id": 35, "name": "Starting XI"},
        "team": {"id": team_id, "name": f"Team {team_id}"},
        "tactics": {"lineup": [{"player": {"id": p, "name": f"Player {p}"}} for p in player_ids]},
    }


def substitution(event_id, team_id, player_off, player_on):
    return {
        "id": event_id,
        "type": {"id": 19, "name": "Substitution"},
        "team": {"id": team_id, "name": f"Team {team_id}"},
        "player": {"id": player_off, "name": f"Player {player_off}"},
        "substitution": {"replacement": {"id": player_on, "name": f"Player {player_on}"}},
    }


def action(event_id, type_name, player_id=11, team_id=HOME, **fields):
    """An event of a player. `fields` add keys or override the defaults."""
    event = {
        "id": event_id,
        "type": {"id": TYPE_IDS[type_name], "name": type_name},
        "team": {"id": team_id, "name": f"Team {team_id}"},
        "player": {"id": player_id, "name": f"Player {player_id}"},
    }
    event.update(fields)
    return event


def lineups():
    """Home starts players 11 and 12; away starts player 21."""
    return [starting_xi("xi-home", HOME, [11, 12]), starting_xi("xi-away", AWAY, [21])]


def compute(*events):
    return compute_match_metrics([*lineups(), *events], MATCH)


def counts(result, player_id=11):
    row = next(row for row in result.rows if row["player_id"] == player_id)
    return tuple(row[name] for name in METRIC_NAMES)


def raised(result):
    return {name: ids for name, ids in result.diagnostics.items() if ids}


# --- what one event contributes -------------------------------------------

SINGLE_EVENT_CASES = [
    ("case 1", action("e", "Pressure"), (1, 0, 0), None),
    ("case 2", action("e", "Pressure", counterpress=True), (1, 1, 1), None),
    ("case 3", action("e", "Duel", counterpress=True), (0, 0, 1), None),
    ("case 5", action("e", "Pass", counterpress=True), (0, 0, 0),
     "counterpress_true_outside_supported_types"),
    ("case 6", action("e", "Pressure", counterpress=False), (1, 0, 0),
     "counterpress_explicit_false"),
    ("case 7", action("e", "Pressure", counterpress=None), (1, 0, 0), "counterpress_null"),
    ("case 8", action("e", "Duel"), (0, 0, 0), None),
    ("case 9 string", action("e", "Pressure", counterpress="true"), (1, 0, 0),
     "counterpress_non_boolean"),
    ("case 9 number", action("e", "Pressure", counterpress=1), (1, 0, 0),
     "counterpress_non_boolean"),
    ("case 9 on a duel", action("e", "Duel", counterpress=1), (0, 0, 0),
     "counterpress_non_boolean"),
    ("case 13", action("e", "Foul Committed", counterpress=True,
                       foul_committed={"offensive": True}), (0, 0, 0),
     "offensive_foul_with_counterpress"),
    ("case 14", action("e", "Pressure", type={"id": 17, "name": "Pressing"}), (1, 0, 0),
     "type_name_differs_from_documented"),
    ("case 23", action("e", "Foul Committed", counterpress=True), (0, 0, 1), None),
    ("case 24", action("e", "Foul Committed", foul_committed={"offensive": True}),
     (0, 0, 0), None),
    ("case 25 false", action("e", "Foul Committed", counterpress=True,
                             foul_committed={"offensive": False}), (0, 0, 1),
     "offensive_flag_unexpected_value"),
    ("case 25 string", action("e", "Foul Committed", counterpress=True,
                              foul_committed={"offensive": "true"}), (0, 0, 1),
     "offensive_flag_unexpected_value"),
]


@pytest.mark.parametrize(
    "event, expected, diagnostic",
    [case[1:] for case in SINGLE_EVENT_CASES],
    ids=[case[0] for case in SINGLE_EVENT_CASES],
)
def test_contribution_of_a_single_event(event, expected, diagnostic):
    result = compute(event)
    assert counts(result) == expected
    assert raised(result) == ({diagnostic: ["e"]} if diagnostic else {})
    # Nobody else's row is affected.
    assert counts(result, 12) == (0, 0, 0) and counts(result, 21) == (0, 0, 0)


def test_events_of_one_player_add_up_and_stay_with_that_player():
    result = compute(
        action("a", "Pressure"),
        action("b", "Pressure", counterpress=True),
        action("c", "Duel", counterpress=True),
        action("d", "Pressure", player_id=21, team_id=AWAY),
    )
    assert counts(result, 11) == (2, 1, 2)
    assert counts(result, 21) == (1, 0, 0)
    assert raised(result) == {}


@pytest.mark.parametrize(
    "event",
    [
        {key: value for key, value in action("e", "Pressure", counterpress=True).items()
         if key != "player"},
        action("e", "Pressure", counterpress=True, player=None),
        action("e", "Pressure", counterpress=True, player={"name": "No Id"}),
        action("e", "Pressure", counterpress=True, team={"name": "No Id"}),
    ],
    ids=["no player", "null player", "player without id", "team without id"],
)
def test_event_without_a_usable_player_or_team_is_reported_not_counted(event):  # case 4
    result = compute(event)
    assert all(counts(result, player) == (0, 0, 0) for player in (11, 12, 21))
    assert raised(result) == {"unattributed_event": ["e"]}


def test_diagnostics_list_event_ids_in_file_order():
    result = compute(
        action("z", "Pass", counterpress=True),
        action("a", "Pass", counterpress=True),
        action("m", "Pass", counterpress=True),
    )
    assert result.diagnostics["counterpress_true_outside_supported_types"] == ["z", "a", "m"]


# --- eligibility and zero rows --------------------------------------------


def test_every_starter_gets_a_row_and_zero_without_qualifying_events():  # case 11
    result = compute(action("e", "Pass"))
    assert [(row["team_id"], row["player_id"]) for row in result.rows] == [
        (HOME, 11),
        (HOME, 12),
        (AWAY, 21),
    ]
    assert all(counts(result, player) == (0, 0, 0) for player in (11, 12, 21))


def test_substitution_replacement_is_eligible_with_or_without_events():  # case 15
    quiet = compute(substitution("sub", HOME, 12, 13))
    assert counts(quiet, 13) == (0, 0, 0)

    active = compute(
        substitution("sub", HOME, 12, 13),
        action("e", "Pressure", player_id=13, counterpress=True),
    )
    assert counts(active, 13) == (1, 1, 1)


def test_player_named_more_than_once_has_one_row():  # case 16
    events = [
        starting_xi("xi-home", HOME, [11, 11, 12]),
        starting_xi("xi-away", AWAY, [21]),
        substitution("sub", HOME, 12, 11),
        action("e", "Pressure"),
    ]
    result = compute_match_metrics(events, MATCH)
    assert [row["player_id"] for row in result.rows] == [11, 12, 21]
    assert counts(result, 11) == (1, 0, 0)


def test_rows_are_sorted_by_team_id_then_player_id_whatever_the_file_order():
    events = [
        starting_xi("xi-away", AWAY, [25, 21]),
        starting_xi("xi-home", HOME, [12, 11]),
        substitution("sub", AWAY, 25, 3),
    ]
    result = compute_match_metrics(events, MATCH)
    assert [(row["team_id"], row["player_id"]) for row in result.rows] == [
        (HOME, 11), (HOME, 12), (AWAY, 3), (AWAY, 21), (AWAY, 25),
    ]


def test_names_are_labels_taken_from_the_first_eligibility_record():
    events = [*lineups(), substitution("sub", HOME, 12, 11)]
    events[2]["substitution"]["replacement"]["name"] = "Another Spelling"
    row = next(row for row in compute_match_metrics(events, MATCH).rows if row["player_id"] == 11)
    assert (row["team_name"], row["player_name"]) == ("Team 1", "Player 11")


def test_pass_by_a_player_outside_the_eligible_set_is_ignored():  # case 22
    result = compute(action("e", "Pass", player_id=99))
    assert [row["player_id"] for row in result.rows] == [11, 12, 21]
    assert raised(result) == {}


# --- conditions that stop the run -----------------------------------------


def stops(events, message, match=MATCH):
    with pytest.raises(MetricError, match=message):
        compute_match_metrics(events, match)


def test_duplicate_event_id_stops_the_run():  # case 10
    stops([*lineups(), action("e", "Pressure"), action("e", "Pass")], "more than once")


@pytest.mark.parametrize("bad_id", [None, True, 1.5, ["x"]], ids=repr)
def test_event_without_a_usable_id_stops_the_run(bad_id):  # case 26
    stops([*lineups(), action(bad_id, "Pass")], "no usable id")
    stops([*lineups(), {"type": {"id": 30, "name": "Pass"}}], "no usable id")


def test_match_team_without_a_starting_xi_stops_the_run():  # case 17
    stops([starting_xi("xi-home", HOME, [11])], f"team {AWAY} has 0 Starting XI events")


@pytest.mark.parametrize(
    "tactics",
    [
        {},
        {"lineup": []},
        {"lineup": "11, 12"},
        {"lineup": [{"player": {"name": "No Id"}}]},
        {"lineup": [{"player": {"id": "11"}}]},
        {"lineup": ["11"]},
    ],
    ids=["no lineup", "empty", "not a list", "entry without id", "string id", "entry not an object"],
)
def test_malformed_starting_xi_stops_the_run(tactics):  # case 18
    broken = starting_xi("xi-home", HOME, [11])
    broken["tactics"] = tactics
    stops([broken, starting_xi("xi-away", AWAY, [21])], "Starting XI")


def test_two_starting_xi_events_for_one_team_stop_the_run():  # case 19
    events = [*lineups(), starting_xi("xi-home-again", HOME, [11, 12])]
    stops(events, f"team {HOME} has 2 Starting XI events")


def test_starting_xi_or_substitution_of_a_team_outside_the_match_stops_the_run():
    stops([*lineups(), starting_xi("xi-other", 77, [70])], "match's teams")
    stops([*lineups(), substitution("sub", 77, 70, 71)], "match's teams")


def test_substitution_without_a_replacement_id_stops_the_run():
    broken = substitution("sub", HOME, 12, 13)
    broken["substitution"] = {"outcome": {"name": "Tactical"}}
    stops([*lineups(), broken], "without an integer id")


def test_player_eligible_for_both_teams_stops_the_run():  # case 20
    events = [starting_xi("xi-home", HOME, [11, 12]), starting_xi("xi-away", AWAY, [11])]
    stops(events, "eligible for both teams")


@pytest.mark.parametrize(
    "event",
    [
        action("e", "Pressure", player_id=99),
        action("e", "Duel", player_id=99, counterpress=True),
        # An eligible player, but credited to the other team.
        action("e", "Pressure", player_id=11, team_id=AWAY),
    ],
    ids=["pressure", "flagged duel", "wrong team"],
)
def test_countable_event_of_a_player_outside_the_eligible_set_stops_the_run(event):  # case 21
    stops([*lineups(), event], "outside the eligible set")


@pytest.mark.parametrize(
    "match",
    [{}, {"home_team": {"home_team_id": 1}}, {"home_team": {"home_team_id": 1},
                                             "away_team": {"away_team_id": 1}}],
    ids=["empty", "one team", "same team twice"],
)
def test_match_record_without_two_team_ids_stops_the_run(match):
    stops(lineups(), "two different integer team ids", match=match)


# --- properties of every valid result -------------------------------------


def test_rows_respect_the_documented_inequalities():
    flags = [True, False, None, "true", 1, 0]
    events = [
        action(f"p{number}", "Pressure", player_id=player, counterpress=flag)
        for number, (player, flag) in enumerate((p, f) for p in (11, 12) for f in flags)
    ]
    events += [action(f"d{number}", "Duel", player_id=12, counterpress=True) for number in range(3)]
    events += [action("plain", "Pressure", player_id=11), action("block", "Block", counterpress=True)]
    result = compute(*events)
    pressure, counterpress_pressure, flagged = METRIC_NAMES
    for row in result.rows:
        assert 0 <= row[counterpress_pressure] <= row[pressure]
        assert row[counterpress_pressure] <= row[flagged]
    assert counts(result, 11) == (7, 1, 2)
    assert counts(result, 12) == (6, 1, 4)


# --- command line, on an ingested synthetic match --------------------------

MANIFEST = f"manifests/statsbomb/open-data/{COMMIT}/match_{MATCH_ID}.json"
METRICS_DIR = f"data/processed/metrics/{COMMIT}/{MATCH_ID}"
SELECTION = ["--competition-id", "900", "--season-id", "800", "--match-id", str(MATCH_ID)]

MATCH_EVENTS = [
    starting_xi("xi-home", HOME, [11, 12]),
    starting_xi("xi-away", AWAY, [21]),
    action("p1", "Pressure", counterpress=True),
    action("p2", "Pressure"),
    action("d1", "Duel", player_id=21, team_id=AWAY, counterpress=True),
    action("x1", "Pass", counterpress=True),
]
# Player 19 is on the home team sheet and never enters the match.
TEAM_SHEETS = [
    {"team_id": HOME, "team_name": "Team 1",
     "lineup": [{"player_id": 11}, {"player_id": 12}, {"player_id": 19}]},
    {"team_id": AWAY, "team_name": "Team 2", "lineup": [{"player_id": 21}]},
]


@pytest.fixture
def ingested(tmp_path, monkeypatch, source):
    """A project root holding one ingested synthetic match with usable events."""
    def encode(value):
        return json.dumps(value).encode("utf-8")

    source.responses[source_url(EVENTS_PATH)] = encode(MATCH_EVENTS)
    source.responses[source_url(LINEUPS_PATH)] = encode(TEAM_SHEETS)
    (tmp_path / "pyproject.toml").write_text("")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "fetch_bytes", source.fetch)
    monkeypatch.setattr(cli, "url_exists", source.exists)
    assert cli.main(["ingest", "--commit", COMMIT, *SELECTION]) == 0
    source.fetched.clear()
    source.checked.clear()
    return tmp_path


def read_rows(project):
    text = (project / METRICS_DIR / "player_match_metrics.csv").read_text(encoding="utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def test_metrics_command_writes_three_files_and_touches_nothing_else(ingested, source, capsys):
    before = snapshot(ingested)

    assert cli.main(["metrics", "--manifest", MANIFEST]) == 0

    after = snapshot(ingested)
    assert {path: after[path] for path in before} == before
    assert sorted(set(after) - set(before)) == sorted(f"{METRICS_DIR}/{name}" for name in OUTPUT_FILES)
    assert source.fetched == [] and source.checked == []
    assert "Eligible players: 3" in capsys.readouterr().out


def test_metrics_csv_has_one_row_per_eligible_player_and_no_bench_player(ingested):  # case 12
    assert cli.main(["metrics", "--manifest", MANIFEST]) == 0
    rows = read_rows(ingested)
    assert list(rows[0]) == [
        "source_commit", "match_id", "team_id", "team_name", "player_id", "player_name",
        *METRIC_NAMES,
    ]
    assert [(row["team_id"], row["player_id"]) for row in rows] == [("1", "11"), ("1", "12"), ("2", "21")]
    assert all(row["source_commit"] == COMMIT and row["match_id"] == str(MATCH_ID) for row in rows)
    assert [tuple(row[name] for name in METRIC_NAMES) for row in rows] == [
        ("2", "1", "1"), ("0", "0", "0"), ("0", "0", "1"),
    ]


def test_run_summary_and_diagnostics_describe_the_run(ingested):
    assert cli.main(["metrics", "--manifest", MANIFEST]) == 0
    summary = json.loads((ingested / METRICS_DIR / "run_summary.json").read_text(encoding="utf-8"))
    diagnostics = json.loads((ingested / METRICS_DIR / "diagnostics.json").read_text(encoding="utf-8"))

    assert summary["metric_contract_version"] == 1
    assert (summary["source_commit"], summary["match_id"]) == (COMMIT, MATCH_ID)
    assert summary["eligible_player_count"] == 3
    assert summary["metric_totals"] == dict(zip(METRIC_NAMES, (2, 1, 2)))
    assert [team["metric_totals"] for team in summary["teams"]] == [
        dict(zip(METRIC_NAMES, (2, 1, 1))), dict(zip(METRIC_NAMES, (0, 0, 1))),
    ]
    assert len(summary["verified_inputs"]) == 4 and summary["limitations"]
    assert summary["diagnostic_totals"]["counterpress_true_outside_supported_types"] == 1
    # No clock value: the summary must be repeatable.
    assert not any("time" in key or "date" in key for key in summary)

    by_name = {item["name"]: item for item in diagnostics["diagnostics"]}
    assert by_name["counterpress_true_outside_supported_types"]["event_ids"] == ["x1"]
    assert list(by_name) == list(summary["diagnostic_totals"])


def test_metrics_command_is_repeatable_byte_for_byte(ingested):
    assert cli.main(["metrics", "--manifest", MANIFEST]) == 0
    first = {name: (ingested / METRICS_DIR / name).read_bytes() for name in OUTPUT_FILES}
    assert cli.main(["metrics", "--manifest", MANIFEST]) == 0
    second = {name: (ingested / METRICS_DIR / name).read_bytes() for name in OUTPUT_FILES}
    assert first == second


def test_contract_violation_exits_nonzero_and_writes_nothing(ingested, capsys):
    events = ingested / f"data/raw/statsbomb/open-data/{COMMIT}" / EVENTS_PATH
    manifest = ingested / MANIFEST
    # Replace the events with a version that breaks the contract, and record
    # it in the manifest so that input verification still passes.
    broken = json.dumps([*MATCH_EVENTS, action("p1", "Pressure")]).encode("utf-8")
    record = json.loads(manifest.read_text(encoding="utf-8"))
    entry = next(item for item in record["files"] if item["source_path"] == EVENTS_PATH)
    entry["sha256"], entry["size_bytes"] = hashlib.sha256(broken).hexdigest(), len(broken)
    events.write_bytes(broken)
    manifest.write_text(json.dumps(record), encoding="utf-8")

    assert cli.main(["metrics", "--manifest", MANIFEST]) == 1

    assert "more than once" in capsys.readouterr().err
    assert not (ingested / METRICS_DIR).exists()


def test_metrics_refuses_a_raw_file_that_differs_from_the_manifest(ingested, source, capsys):
    events = ingested / f"data/raw/statsbomb/open-data/{COMMIT}" / EVENTS_PATH
    events.write_bytes(b'[{"id": "tampered"}]')

    assert cli.main(["metrics", "--manifest", MANIFEST]) == 1

    assert "conflicts with its manifest record" in capsys.readouterr().err
    assert source.fetched == []
    assert files_under(ingested / "data" / "processed") == []
