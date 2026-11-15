"""A pilot runs its matches in order, stops at the first failure, and
publishes a combined table only when every match succeeded.

Two synthetic matches of one competition-season at one commit are used:
match 700 (teams 1 v 2) and match 701 (teams 2 v 3). Match 701 has
events in periods 3, 4 and 5, which the metric contract counts like any
other period.
"""

import json

import pytest

from phaselens import analytics, cli, pilot
from phaselens.metrics import METRIC_NAMES
from synthetic import (
    COMMIT,
    COMPETITIONS_PATH,
    EVENTS_PATH,
    LINEUPS_PATH,
    MATCH_ID,
    MATCHES_PATH,
    SECOND_EVENTS_PATH,
    SECOND_LINEUPS_PATH,
    SECOND_MATCH_ID,
    files_under,
    snapshot,
    source_url,
)

PILOT = "pilots/test_pilot.json"
COMBINED_DIR = f"data/processed/analytics/{COMMIT}/pilots/test_pilot"
COMBINED_PARQUET = f"{COMBINED_DIR}/{analytics.PARQUET_FILE}"
COMBINED_METADATA = f"{COMBINED_DIR}/{analytics.METADATA_FILE}"


def component_dir(match_id):
    return f"data/processed/analytics/{COMMIT}/{match_id}"


def metrics_dir(match_id):
    return f"data/processed/metrics/{COMMIT}/{match_id}"


def raw(source_path):
    return f"data/raw/statsbomb/open-data/{COMMIT}/{source_path}"


def starting_xi(event_id, team_id, player_ids):
    return {
        "id": event_id, "index": 0, "period": 1,
        "type": {"id": 35, "name": "Starting XI"},
        "team": {"id": team_id, "name": f"Team {team_id}"},
        "tactics": {"lineup": [{"player": {"id": p, "name": f"Player {p}"}} for p in player_ids]},
    }


def action(event_id, type_id, type_name, team_id, player_id, period=1, **fields):
    return {
        "id": event_id, "index": 0, "period": period,
        "type": {"id": type_id, "name": type_name},
        "team": {"id": team_id, "name": f"Team {team_id}"},
        "player": {"id": player_id, "name": f"Player {player_id}"},
        **fields,
    }


def pressure(event_id, team_id, player_id, period=1, **fields):
    return action(event_id, 17, "Pressure", team_id, player_id, period, **fields)


FIRST_EVENTS = [
    starting_xi("a-xi-1", 1, [11, 12]),
    starting_xi("a-xi-2", 2, [21]),
    pressure("a-p1", 1, 11, counterpress=True),
    pressure("a-p2", 2, 21),
]
# Periods 3 to 5 stand for extra time and a shoot-out; nothing filters them.
SECOND_EVENTS = [
    starting_xi("b-xi-2", 2, [21, 22]),
    starting_xi("b-xi-3", 3, [31]),
    pressure("b-p1", 2, 21),
    {
        **action("b-sub", 19, "Substitution", 3, 31, period=3),
        "substitution": {"replacement": {"id": 32, "name": "Player 32"}},
    },
    pressure("b-p2", 2, 22, period=3, counterpress=True),
    pressure("b-p3", 3, 32, period=4),
    action("b-d1", 4, "Duel", 3, 32, period=5, counterpress=True),
]
# (match, team) -> totals of the three metrics, worked out by hand.
EXPECTED_TEAM_TOTALS = [
    (700, 1, "Team 1", 1, 1, 1),
    (700, 2, "Team 2", 1, 0, 0),
    (701, 2, "Team 2", 2, 1, 1),
    (701, 3, "Team 3", 1, 0, 1),
]


def encode(value):
    return json.dumps(value).encode("utf-8")


def write_pilot(project, match_ids, name="test_pilot", **fields):
    definition = {
        "pilot_format_version": 1,
        "source_commit": COMMIT,
        "competition_id": 900,
        "season_id": 800,
        "match_ids": match_ids,
        **fields,
    }
    path = project / "pilots" / f"{name}.json"
    path.write_text(json.dumps(definition), encoding="utf-8")
    return path


@pytest.fixture
def project(tmp_path, monkeypatch, source):
    """A project root with a two-match pilot definition and nothing run yet."""
    source.responses[source_url(EVENTS_PATH)] = encode(FIRST_EVENTS)
    source.responses[source_url(SECOND_EVENTS_PATH)] = encode(SECOND_EVENTS)
    (tmp_path / "pyproject.toml").write_text("")
    (tmp_path / "pilots").mkdir()
    write_pilot(tmp_path, [MATCH_ID, SECOND_MATCH_ID])
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "fetch_bytes", source.fetch)
    monkeypatch.setattr(cli, "url_exists", source.exists)
    return tmp_path


@pytest.fixture
def ran(project, source):
    """The project after one successful pilot run."""
    assert cli.main(["pilot", "--file", PILOT]) == 0
    source.fetched.clear()
    source.checked.clear()
    return project


def combined_table(project):
    return analytics.read_parquet(project / COMBINED_PARQUET)


def read_json(project, path):
    return json.loads((project / path).read_text(encoding="utf-8"))


def edit_json(project, path, change):
    document = read_json(project, path)
    change(document)
    (project / path).write_text(json.dumps(document), encoding="utf-8")


def pilot_query_fails(project, capsys, message, name="team-totals"):
    """pilot-query exits 1 with one clean error line and changes nothing."""
    before = snapshot(project)
    capsys.readouterr()
    assert cli.main(["pilot-query", "--file", PILOT, "--name", name]) == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("error: ") and message in captured.err
    assert "Traceback" not in captured.err and captured.out == ""
    assert snapshot(project) == before


# --- a successful run -----------------------------------------------------


def test_every_match_is_processed_and_the_combined_table_reconciles(ran):
    schema, rows = combined_table(ran)
    assert schema == list(analytics.COLUMNS)
    assert [(row[2], row[3], row[5]) for row in rows] == [
        (700, 1, 11), (700, 1, 12), (700, 2, 21),
        (701, 2, 21), (701, 2, 22), (701, 3, 31), (701, 3, 32),
    ]
    metadata = read_json(ran, COMBINED_METADATA)
    assert metadata["row_count"] == 7
    assert metadata["metric_totals"] == dict(zip(METRIC_NAMES, (5, 2, 3)))
    assert [c["match_id"] for c in metadata["components"]] == [700, 701]
    for component in metadata["components"]:
        own = read_json(ran, f"{component_dir(component['match_id'])}/{analytics.METADATA_FILE}")
        assert component["parquet_artifact"] == own["parquet_artifact"]
        assert (component["row_count"], component["metric_totals"]) == (own["row_count"], own["metric_totals"])
        part = [row for row in rows if row[2] == component["match_id"]]
        assert len(part) == own["row_count"] and analytics.totals_of(part) == own["metric_totals"]
    assert metadata["pilot"]["match_ids"] == [700, 701]
    assert metadata["pilot"]["definition_path"] == PILOT


def test_per_match_outputs_stay_separate(ran):
    for match_id in (700, 701):
        assert (ran / component_dir(match_id) / analytics.PARQUET_FILE).is_file()
        assert (ran / metrics_dir(match_id) / "player_match_metrics.csv").is_file()
        assert (ran / f"data/processed/profiles/{COMMIT}/{match_id}/summary.json").is_file()
        assert (ran / f"manifests/statsbomb/open-data/{COMMIT}/match_{match_id}.json").is_file()


def test_shared_source_files_are_downloaded_once(project, source):
    assert cli.main(["pilot", "--file", PILOT]) == 0
    assert source.fetched == [
        source_url(path)
        for path in (COMPETITIONS_PATH, MATCHES_PATH, LINEUPS_PATH, EVENTS_PATH,
                     SECOND_LINEUPS_PATH, SECOND_EVENTS_PATH)
    ]
    assert len(source.checked) == 2


def test_periods_beyond_two_are_reported_and_counted_like_any_other(project, source):
    results, _ = pilot.run_pilot(project, project / PILOT, fetch=source.fetch, exists=source.exists)
    second = results[1]
    assert second["events_by_period"] == [
        {"period": 1, "events": 3},
        {"period": 3, "events": 2},
        {"period": 4, "events": 1},
        {"period": 5, "events": 1},
    ]
    # b-p2 (period 3), b-p3 (period 4) and b-d1 (period 5) all count.
    assert second["metric_totals"] == dict(zip(METRIC_NAMES, (3, 1, 2)))


def test_rerun_makes_no_network_request_and_is_logically_identical(ran, source):
    before_table = combined_table(ran)
    before = read_json(ran, COMBINED_METADATA)

    assert cli.main(["pilot", "--file", PILOT]) == 0

    assert source.fetched == [] and source.checked == []
    assert combined_table(ran) == before_table
    after = read_json(ran, COMBINED_METADATA)
    for key in ("pilot", "row_count", "metric_totals", "columns", "composite_key", "metric_contract_version"):
        assert after[key] == before[key]


# --- failures -------------------------------------------------------------


def test_failure_on_a_later_match_stops_and_publishes_no_combined_output(project, source, capsys):
    broken = [*SECOND_EVENTS, pressure("b-p1", 2, 21)]  # repeats an event id
    source.responses[source_url(SECOND_EVENTS_PATH)] = encode(broken)

    assert cli.main(["pilot", "--file", PILOT]) == 1

    captured = capsys.readouterr()
    assert "match 701 failed at stage metrics" in captured.err
    assert "No combined output was built in this run." in captured.err
    assert "older combined output" not in captured.err
    assert "match 700: ingest, profile, metrics, analytics completed" in captured.out
    assert (project / component_dir(700) / analytics.PARQUET_FILE).is_file()
    assert not (project / metrics_dir(701)).exists()
    assert not (project / COMBINED_DIR).exists()


def test_a_failed_rerun_does_not_pass_off_the_older_combined_output(ran, capsys):
    before = snapshot(ran / COMBINED_DIR)
    (ran / raw(SECOND_EVENTS_PATH)).write_bytes(b'[{"id": "tampered"}]')

    assert cli.main(["pilot", "--file", PILOT]) == 1

    error = capsys.readouterr().err
    assert "match 701 failed at stage ingest" in error
    assert "No combined output was built in this run." in error
    assert f"An older combined output from an earlier run remains at {COMBINED_DIR}/" in error
    assert snapshot(ran / COMBINED_DIR) == before
    # The older output is refused while match 701's inputs do not verify.
    pilot_query_fails(ran, capsys, "conflicts with its manifest record")


def test_match_missing_from_the_match_list_fails_at_ingest(project, capsys):
    write_pilot(project, [MATCH_ID, 799])
    assert cli.main(["pilot", "--file", PILOT]) == 1
    assert "match 799 failed at stage ingest" in capsys.readouterr().err
    assert not (project / COMBINED_DIR).exists()


@pytest.mark.parametrize(
    "fields, message",
    [
        ({"match_ids": [700, 701, 700]}, "lists [700] more than once"),
        ({"match_ids": []}, "non-empty list of integers"),
        ({"match_ids": [700, "701"]}, "non-empty list of integers"),
        ({"source_commit": "master"}, "full 40-character commit SHA"),
        ({"season_id": "800"}, "season_id must be an integer"),
        ({"pilot_format_version": 2}, "pilot_format_version must be 1"),
    ],
    ids=["duplicate match", "empty", "string id", "branch name", "string season", "version"],
)
def test_invalid_pilot_definitions_are_rejected_before_any_work(project, source, capsys, fields, message):
    write_pilot(project, **{"match_ids": [MATCH_ID, SECOND_MATCH_ID], **fields})
    assert cli.main(["pilot", "--file", PILOT]) == 1
    assert message in capsys.readouterr().err
    assert source.fetched == []


def test_pilot_definition_outside_the_project_is_rejected(project, tmp_path_factory):
    outside = tmp_path_factory.mktemp("elsewhere") / "test_pilot.json"
    outside.write_text((project / PILOT).read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(pilot.PilotError, match="must be inside the project"):
        pilot.load_pilot(project, outside)


# --- combining rows -------------------------------------------------------


def row(match_id, team_id, player_id, counts=(1, 0, 0), commit=COMMIT, version=1):
    return (commit, version, match_id, team_id, "T", player_id, "P", *counts)


def component(match_id, rows, version=1):
    return {
        "match_id": match_id,
        "metric_contract_version": version,
        "row_count": len(rows),
        "metric_totals": analytics.totals_of(rows),
    }


def test_combine_sorts_and_reconciles_rows():
    first, second = [row(701, 2, 21)], [row(700, 1, 11, (2, 1, 1)), row(700, 1, 12)]
    rows = pilot.combine([component(701, first), component(700, second)], [first, second], COMMIT)
    assert [(r[2], r[5]) for r in rows] == [(700, 11), (700, 12), (701, 21)]


def test_combine_rejects_conflicting_commits():
    part = [row(700, 1, 11, commit="b" * 40)]
    with pytest.raises(pilot.PilotError, match="not the pilot's"):
        pilot.combine([component(700, part)], [part], COMMIT)


def test_combine_rejects_conflicting_contract_versions():
    first, second = [row(700, 1, 11)], [row(701, 2, 21, version=2)]
    with pytest.raises(pilot.PilotError, match="different metric contract versions"):
        pilot.combine([component(700, first), component(701, second, version=2)], [first, second], COMMIT)


def test_combine_rejects_duplicate_composite_keys():
    first, second = [row(700, 1, 11)], [row(700, 1, 11)]
    with pytest.raises(pilot.PilotError, match="duplicate composite key"):
        pilot.combine([component(700, first), component(700, second)], [first, second], COMMIT)


def test_combine_rejects_rows_that_do_not_reconcile_with_their_metadata():
    part = [row(700, 1, 11)]
    record = {**component(700, part), "row_count": 2}
    with pytest.raises(pilot.PilotError, match="do not reconcile with its build metadata"):
        pilot.combine([record], [part], COMMIT)


def test_contract_version_conflict_between_real_components_stops_the_build(ran):
    for name in ("run_summary.json", "diagnostics.json"):
        edit_json(ran, f"{metrics_dir(701)}/{name}", lambda d: d.update(metric_contract_version=2))
    analytics.build(ran, ran / f"manifests/statsbomb/open-data/{COMMIT}/match_701.json")
    with pytest.raises(pilot.PilotError, match=r"different metric contract versions \[1, 2\]"):
        pilot.build_combined(ran, pilot.load_pilot(ran, ran / PILOT))


# --- component artifacts at query time ------------------------------------


def test_unchanged_output_is_queried_successfully(ran, capsys):
    assert cli.main(["pilot-query", "--file", PILOT, "--name", "team-totals"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ["match_id", "team_id", "team_name", *METRIC_NAMES]
    assert lines[-1] == "(4 rows)"


def test_missing_component_parquet_is_refused(ran, capsys):
    (ran / component_dir(701) / analytics.PARQUET_FILE).unlink()
    pilot_query_fails(ran, capsys, "the Parquet file is missing although its build metadata exists")


def test_altered_component_parquet_is_refused(ran, capsys):
    path = ran / component_dir(700) / analytics.PARQUET_FILE
    _, rows = analytics.read_parquet(path)
    analytics.write_parquet([(*r[:7], r[7] + 1, *r[8:]) for r in rows], path)
    pilot_query_fails(ran, capsys, "does not match the checksum recorded when it was built")


def test_component_whose_metrics_files_changed_is_refused_although_its_parquet_did_not(ran, capsys):
    parquet = (ran / component_dir(700) / analytics.PARQUET_FILE).read_bytes()
    with (ran / metrics_dir(700) / "run_summary.json").open("ab") as handle:
        handle.write(b" ")
    assert (ran / component_dir(700) / analytics.PARQUET_FILE).read_bytes() == parquet
    pilot_query_fails(ran, capsys, "has changed since the analytical output was built")


def test_component_rebuilt_since_the_combined_build_is_refused(ran, capsys):
    # Same content, different bytes: the build metadata no longer matches the record.
    edit_json(ran, f"{component_dir(701)}/{analytics.METADATA_FILE}", lambda d: None)
    assert cli.main(["query", "--manifest", f"manifests/statsbomb/open-data/{COMMIT}/match_701.json",
                     "--name", "team-totals"]) == 0
    pilot_query_fails(ran, capsys, "is not the one the combined output was built from")


def test_build_refuses_a_component_without_published_output(ran):
    (ran / component_dir(701) / analytics.METADATA_FILE).unlink()
    with pytest.raises(analytics.AnalyticsError, match="no complete analytical output"):
        pilot.build_combined(ran, pilot.load_pilot(ran, ran / PILOT))


# --- the combined artifact itself -----------------------------------------


def test_altered_combined_parquet_is_refused(ran, capsys):
    _, rows = combined_table(ran)
    analytics.write_parquet([(*r[:7], r[7] + 1, *r[8:]) for r in rows], ran / COMBINED_PARQUET)
    pilot_query_fails(ran, capsys, "does not match the checksum recorded when it was built")


def test_missing_combined_parquet_or_metadata_is_refused(ran, capsys):
    (ran / COMBINED_PARQUET).unlink()
    pilot_query_fails(ran, capsys, "the combined Parquet file is missing")
    (ran / COMBINED_METADATA).unlink()
    pilot_query_fails(ran, capsys, "no complete combined output")


def test_combined_output_of_another_match_set_is_refused(ran, capsys):
    write_pilot(ran, [MATCH_ID])
    pilot_query_fails(ran, capsys, "was built for another pilot definition")


def test_unsupported_combined_metadata_version_is_refused(ran, capsys):
    edit_json(ran, COMBINED_METADATA, lambda d: d.update(combined_metadata_version=2))
    pilot_query_fails(ran, capsys, "combined metadata version 2 is not supported")


# --- match-aware queries --------------------------------------------------


def query(project, name):
    return pilot.run_pilot_query(project, project / PILOT, name)


def test_team_totals_keep_each_match_separate(ran):
    columns, rows = query(ran, "team-totals")
    assert columns == ["match_id", "team_id", "team_name", *METRIC_NAMES]
    # Team 2 plays in both matches and has one row per match.
    assert rows == EXPECTED_TEAM_TOTALS


def test_team_player_counts_count_rows_within_each_match(ran):
    columns, rows = query(ran, "team-player-counts")
    assert columns == [
        "match_id", "team_id", "team_name", "eligible_player_rows",
        "rows_with_zero_pressure_event_count",
        "rows_with_zero_counterpress_pressure_event_count",
        "rows_with_zero_counterpress_flagged_event_count",
    ]
    assert rows == [
        (700, 1, "Team 1", 2, 1, 1, 1),
        (700, 2, "Team 2", 1, 0, 1, 1),
        (701, 2, "Team 2", 2, 0, 1, 1),
        (701, 3, "Team 3", 2, 1, 2, 1),
    ]


def test_player_rows_keep_one_row_per_match_for_a_repeated_player(ran):
    _, rows = query(ran, "player-rows")
    assert len(rows) == 7
    assert [(r[0], r[1]) for r in rows if r[3] == 21] == [(700, 2), (701, 2)]


def test_integrity_checks_pass_and_detect_planted_violations(ran, tmp_path):
    assert all(violations == 0 for _, violations in query(ran, "integrity-checks")[1])
    broken = tmp_path / "broken.parquet"
    analytics.write_parquet(
        [row(700, 1, 11), row(700, 1, 11), row(701, 2, 21, (1, 2, 0), commit="b" * 40, version=2)],
        broken,
    )
    found = dict(analytics.query_file(broken, "integrity-checks", pilot.PILOT_QUERIES)[1])
    assert found == {
        "counterpress_pressure_exceeds_flagged": 1,
        "counterpress_pressure_exceeds_pressure": 1,
        "duplicate_composite_key": 1,
        "more_than_one_metric_contract_version": 1,
        "more_than_one_source_commit": 1,
        "negative_count": 0,
    }


def test_single_match_queries_are_unchanged_by_the_pilot(ran):
    manifest = ran / f"manifests/statsbomb/open-data/{COMMIT}/match_701.json"
    columns, rows = analytics.run_query(ran, manifest, "team-totals")
    assert columns == ["team_id", "team_name", *METRIC_NAMES]
    assert rows == [(2, "Team 2", 2, 1, 1), (3, "Team 3", 1, 0, 1)]
    assert files_under(ran / "pilots") == ["test_pilot.json"]
