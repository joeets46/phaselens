"""The analytical layer copies the metrics to typed Parquet without changing them.

Each test starts from a project root holding one ingested synthetic
match and the metrics bundle the real `metrics` command wrote for it.
Negative tests then damage that bundle in one specific way.
"""

import csv
import hashlib
import io
import json

import duckdb
import pytest

from phaselens import analytics, cli
from phaselens.metrics import METRIC_NAMES
from synthetic import COMMIT, EVENTS_PATH, MATCH_ID, files_under, snapshot, source_url

MANIFEST = f"manifests/statsbomb/open-data/{COMMIT}/match_{MATCH_ID}.json"
METRICS_DIR = f"data/processed/metrics/{COMMIT}/{MATCH_ID}"
ANALYTICS_DIR = f"data/processed/analytics/{COMMIT}/{MATCH_ID}"
CSV_FILE = f"{METRICS_DIR}/player_match_metrics.csv"
SUMMARY_FILE = f"{METRICS_DIR}/run_summary.json"
SELECTION = ["--competition-id", "900", "--season-id", "800", "--match-id", str(MATCH_ID)]
HOME, AWAY = 1, 2


def player(player_id, name):
    return {"id": player_id, "name": name} if name is not None else {"id": player_id}


def starting_xi(event_id, team_id, team_name, players):
    return {
        "id": event_id,
        "type": {"id": 35, "name": "Starting XI"},
        "team": {"id": team_id, "name": team_name},
        "tactics": {"lineup": [{"player": entry} for entry in players]},
    }


def pressure(event_id, team_id, player_id, **fields):
    return {
        "id": event_id,
        "type": {"id": 17, "name": "Pressure"},
        "team": {"id": team_id},
        "player": {"id": player_id},
        **fields,
    }


# Player 11 has a non-ASCII name containing a comma, player 12 has no
# qualifying event, and player 13 has no name in the source.
MATCH_EVENTS = [
    starting_xi("xi-home", HOME, "Ünited", [player(11, "Çələbi, Ünal"), player(12, "Bo"), player(13, None)]),
    starting_xi("xi-away", AWAY, "City", [player(21, "Ana María")]),
    pressure("p1", HOME, 11, counterpress=True),
    pressure("p2", HOME, 11),
    pressure("p3", HOME, 13),
    pressure("p4", AWAY, 21, counterpress=True),
]
# (source_commit, contract version, match, team, team name, player, player name, A, B, C)
EXPECTED_ROWS = [
    (COMMIT, 1, MATCH_ID, HOME, "Ünited", 11, "Çələbi, Ünal", 2, 1, 1),
    (COMMIT, 1, MATCH_ID, HOME, "Ünited", 12, "Bo", 0, 0, 0),
    (COMMIT, 1, MATCH_ID, HOME, "Ünited", 13, "", 1, 0, 0),
    (COMMIT, 1, MATCH_ID, AWAY, "City", 21, "Ana María", 1, 1, 1),
]


@pytest.fixture
def project(tmp_path, monkeypatch, source):
    """A project root with an ingested synthetic match and its metrics bundle."""
    source.responses[source_url(EVENTS_PATH)] = json.dumps(MATCH_EVENTS).encode("utf-8")
    (tmp_path / "pyproject.toml").write_text("")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "fetch_bytes", source.fetch)
    monkeypatch.setattr(cli, "url_exists", source.exists)
    assert cli.main(["ingest", "--commit", COMMIT, *SELECTION]) == 0
    assert cli.main(["metrics", "--manifest", MANIFEST]) == 0
    source.fetched.clear()
    source.checked.clear()
    return tmp_path


def edit_csv(project, change):
    """Rewrite the metrics CSV after `change(header, rows)` has altered it in place."""
    path = project / CSV_FILE
    table = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8"), newline="")))
    header, rows = table[0], table[1:]
    change(header, rows)
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows([header, *rows])
    path.write_bytes(buffer.getvalue().encode("utf-8"))


def edit_summary(project, change):
    path = project / SUMMARY_FILE
    summary = json.loads(path.read_text(encoding="utf-8"))
    change(summary)
    path.write_text(json.dumps(summary), encoding="utf-8")


def set_cell(column, value, row=0):
    def change(header, rows):
        rows[row][header.index(column)] = value

    return change


def build_fails(project, message):
    """The build raises with `message`, publishes nothing, and alters no input."""
    before = snapshot(project)
    with pytest.raises(analytics.AnalyticsError, match=message):
        analytics.build(project, project / MANIFEST)
    assert snapshot(project) == before
    assert files_under(project / "data" / "processed" / "analytics") == []


# --- a valid build --------------------------------------------------------


def test_parquet_rows_equal_the_validated_csv_rows(project):
    directory, _ = analytics.build(project, project / MANIFEST)
    _, rows = analytics.read_parquet(directory / analytics.PARQUET_FILE)
    assert rows == EXPECTED_ROWS


def test_parquet_has_the_documented_columns_and_explicit_types(project):
    directory, _ = analytics.build(project, project / MANIFEST)
    path = str(directory / analytics.PARQUET_FILE)
    schema, rows = analytics.read_parquet(path)
    assert schema == [
        ("source_commit", "VARCHAR"),
        ("metric_contract_version", "BIGINT"),
        ("match_id", "BIGINT"),
        ("team_id", "BIGINT"),
        ("team_name", "VARCHAR"),
        ("player_id", "BIGINT"),
        ("player_name", "VARCHAR"),
        ("pressure_event_count", "BIGINT"),
        ("counterpress_pressure_event_count", "BIGINT"),
        ("counterpress_flagged_event_count", "BIGINT"),
    ]
    assert [type(value) for value in rows[0]] == [str, int, int, int, str, int, str, int, int, int]
    # As stored in the file itself: 64-bit integers, and no column allows null.
    with duckdb.connect(":memory:") as connection:
        stored = connection.execute(
            "SELECT name, type, repetition_type FROM parquet_schema(?) WHERE type IS NOT NULL", [path]
        ).fetchall()
    assert all(repetition == "REQUIRED" for _, _, repetition in stored)
    assert {name: kind for name, kind, _ in stored}["player_id"] == "INT64"


def test_non_ascii_names_zero_counts_and_missing_names_survive(project):
    directory, _ = analytics.build(project, project / MANIFEST)
    _, rows = analytics.read_parquet(directory / analytics.PARQUET_FILE)
    by_player = {row[5]: row for row in rows}
    assert by_player[11][6] == "Çələbi, Ünal" and by_player[11][4] == "Ünited"
    assert by_player[12][7:] == (0, 0, 0)
    # A name missing in the source is an empty string in the CSV and stays one.
    assert by_player[13][6] == ""


def test_rows_are_stored_in_composite_key_order_whatever_the_csv_order(project):
    edit_csv(project, lambda header, rows: rows.reverse())
    directory, _ = analytics.build(project, project / MANIFEST)
    _, rows = analytics.read_parquet(directory / analytics.PARQUET_FILE)
    assert rows == EXPECTED_ROWS


def test_build_metadata_records_versions_inputs_and_totals(project):
    directory, returned = analytics.build(project, project / MANIFEST)
    metadata = json.loads((directory / analytics.METADATA_FILE).read_text(encoding="utf-8"))
    assert metadata == returned
    assert metadata["build_metadata_version"] == 2
    parquet_bytes = (directory / analytics.PARQUET_FILE).read_bytes()
    assert metadata["parquet_artifact"] == {
        "path": f"{ANALYTICS_DIR}/{analytics.PARQUET_FILE}",
        "sha256": hashlib.sha256(parquet_bytes).hexdigest(),
        "size_bytes": len(parquet_bytes),
    }
    assert metadata["analytical_schema_version"] == 1
    assert metadata["metric_contract_version"] == 1
    assert (metadata["source_commit"], metadata["match_id"]) == (COMMIT, MATCH_ID)
    assert metadata["row_count"] == 4
    assert metadata["metric_totals"] == dict(zip(METRIC_NAMES, (4, 2, 2)))
    assert metadata["duckdb_version"] == duckdb.__version__
    assert [item["path"] for item in metadata["consumed_metric_files"]] == [
        f"{METRICS_DIR}/player_match_metrics.csv",
        f"{METRICS_DIR}/diagnostics.json",
        f"{METRICS_DIR}/run_summary.json",
    ]
    assert len(metadata["verified_raw_inputs"]) == 4
    text = json.dumps(metadata)
    # Project-relative paths only, and nothing that changes from run to run.
    assert str(project) not in text and str(project).replace("\\", "\\\\") not in text
    assert not any("time" in key or "date" in key for key in metadata)


def test_build_writes_two_files_and_touches_nothing_else(project, source, capsys):
    before = snapshot(project)

    assert cli.main(["analytics", "--manifest", MANIFEST]) == 0

    after = snapshot(project)
    assert {path: after[path] for path in before} == before
    assert sorted(set(after) - set(before)) == sorted(
        f"{ANALYTICS_DIR}/{name}" for name in analytics.OUTPUT_FILES
    )
    assert source.fetched == [] and source.checked == []
    assert "Parquet: 4 rows, 10 columns" in capsys.readouterr().out


def test_two_builds_are_logically_identical(project, tmp_path_factory):
    results = []
    for _ in range(2):
        output_root = tmp_path_factory.mktemp("build")
        directory, metadata = analytics.build(project, project / MANIFEST, output_root=output_root)
        results.append((analytics.read_parquet(directory / analytics.PARQUET_FILE), metadata))
    (first_table, first_metadata), (second_table, second_metadata) = results
    assert first_table == second_table

    def logical(metadata):
        # The Parquet checksum describes bytes, which are not promised to
        # repeat. Everything else in the metadata must.
        return {key: value for key, value in metadata.items() if key != "parquet_artifact"}

    assert logical(first_metadata) == logical(second_metadata)
    assert first_metadata["parquet_artifact"]["path"] == second_metadata["parquet_artifact"]["path"]


def test_rebuild_replaces_the_previous_output(project):
    analytics.build(project, project / MANIFEST)
    first = snapshot(project / ANALYTICS_DIR)
    analytics.build(project, project / MANIFEST)
    assert {path: content for path, (content, _) in snapshot(project / ANALYTICS_DIR).items()} == {
        path: content for path, (content, _) in first.items()
    }
    assert files_under(project / "data" / "processed" / "analytics") == sorted(
        f"{COMMIT}/{MATCH_ID}/{name}" for name in analytics.OUTPUT_FILES
    )


# --- invalid inputs are rejected, never corrected -------------------------


def test_missing_required_column_is_rejected(project):
    def drop_player_id(header, rows):
        position = header.index("player_id")
        for line in (header, *rows):
            del line[position]

    edit_csv(project, drop_player_id)
    build_fails(project, "columns are")


def test_renamed_or_reordered_columns_are_rejected(project):
    edit_csv(project, lambda header, rows: header.__setitem__(2, "team"))
    build_fails(project, "columns are")


@pytest.mark.parametrize(
    "value, message",
    [
        ("1.0", "not an integer written in plain decimal digits"),
        ("two", "not an integer written in plain decimal digits"),
        ("+1", "not an integer written in plain decimal digits"),
        (" 1", "not an integer written in plain decimal digits"),
        ("01", "not an integer written in plain decimal digits"),
        ("", "is missing"),
        ("-1", "is negative"),
    ],
    ids=["decimal", "word", "plus sign", "space", "leading zero", "empty", "negative"],
)
def test_malformed_or_negative_count_is_rejected(project, value, message):
    edit_csv(project, set_cell("pressure_event_count", value))
    build_fails(project, f"pressure_event_count .*{message}")


@pytest.mark.parametrize("column", ["team_id", "player_id", "match_id"])
def test_identifier_with_leading_zeros_is_rejected_not_reinterpreted(project, column):
    # Identifiers are integers written canonically. "011" is not accepted as 11.
    def pad(header, rows):
        position = header.index(column)
        rows[0][position] = "0" + rows[0][position]

    edit_csv(project, pad)
    build_fails(project, f"{column} is '0")


@pytest.mark.parametrize("column", ["team_id", "player_id"])
def test_missing_identifier_is_rejected(project, column):
    edit_csv(project, set_cell(column, ""))
    build_fails(project, f"{column} is missing")


def test_duplicate_composite_key_is_rejected(project):
    edit_csv(project, lambda header, rows: rows.append(list(rows[0])))
    build_fails(project, "duplicate composite key for team 1, player 11")


def test_metric_inequality_violation_is_rejected(project):
    # counterpress_pressure_event_count may not exceed pressure_event_count.
    edit_csv(project, set_cell("counterpress_pressure_event_count", "3"))
    build_fails(project, "metric inequalities are violated")


def test_source_revision_mismatch_in_the_csv_is_rejected(project):
    edit_csv(project, set_cell("source_commit", "b" * 40))
    build_fails(project, "source_commit is")


def test_match_mismatch_in_the_csv_is_rejected(project):
    edit_csv(project, set_cell("match_id", "701"))
    build_fails(project, "match_id is 701, expected 700")


def test_summary_for_another_revision_is_rejected(project):
    edit_summary(project, lambda summary: summary.update(source_commit="b" * 40))
    build_fails(project, "run_summary.json: describes")


def test_summary_recording_other_source_hashes_is_rejected(project):
    edit_summary(project, lambda summary: summary["verified_inputs"][0].update(sha256="0" * 64))
    build_fails(project, "source hashes it records are not those of the manifest")


def test_summary_total_mismatch_is_rejected(project):
    edit_summary(project, lambda summary: summary["metric_totals"].update(pressure_event_count=99))
    build_fails(project, "records totals")


def test_csv_value_that_no_longer_matches_the_summary_is_rejected(project):
    # A valid-looking number: 2 -> 3 keeps every row-level rule intact.
    edit_csv(project, set_cell("pressure_event_count", "3"))
    build_fails(project, "records totals")


def test_row_count_mismatch_with_the_summary_is_rejected(project):
    edit_csv(project, lambda header, rows: rows.pop())
    build_fails(project, "eligible players but the CSV has 3 rows")


def test_missing_metrics_bundle_is_reported(project):
    (project / CSV_FILE).unlink()
    with pytest.raises(analytics.AnalyticsError, match="metrics output not found"):
        analytics.build(project, project / MANIFEST)


def test_failed_build_keeps_an_earlier_complete_output_and_leaves_no_partial_one(project):
    analytics.build(project, project / MANIFEST)
    earlier = snapshot(project / ANALYTICS_DIR)
    edit_csv(project, set_cell("pressure_event_count", "x"))

    with pytest.raises(analytics.AnalyticsError):
        analytics.build(project, project / MANIFEST)

    assert snapshot(project / ANALYTICS_DIR) == earlier
    assert files_under(project / "data" / "processed" / "analytics") == sorted(
        f"{COMMIT}/{MATCH_ID}/{name}" for name in analytics.OUTPUT_FILES
    )


# --- fixed queries --------------------------------------------------------


def test_team_totals_query_adds_up_the_three_counts_per_team(project):
    analytics.build(project, project / MANIFEST)
    columns, rows = analytics.run_query(project, project / MANIFEST, "team-totals")
    assert columns == ["team_id", "team_name", *METRIC_NAMES]
    assert rows == [(HOME, "Ünited", 3, 1, 1), (AWAY, "City", 1, 1, 1)]


def test_player_rows_query_lists_every_row_in_identifier_order(project):
    analytics.build(project, project / MANIFEST)
    columns, rows = analytics.run_query(project, project / MANIFEST, "player-rows")
    assert columns == ["team_id", "team_name", "player_id", "player_name", *METRIC_NAMES]
    assert [(row[0], row[2]) for row in rows] == [(1, 11), (1, 12), (1, 13), (2, 21)]


def test_team_player_counts_query_counts_eligible_and_zero_players(project):
    analytics.build(project, project / MANIFEST)
    _, rows = analytics.run_query(project, project / MANIFEST, "team-player-counts")
    # team, name, eligible, zero pressure, zero counterpress pressure, zero flagged
    assert rows == [(HOME, "Ünited", 3, 1, 2, 2), (AWAY, "City", 1, 0, 0, 0)]


def test_integrity_checks_query_reports_no_violation_and_detects_planted_ones(project, tmp_path):
    analytics.build(project, project / MANIFEST)
    _, rows = analytics.run_query(project, project / MANIFEST, "integrity-checks")
    assert dict(rows) == {
        "counterpress_pressure_exceeds_flagged": 0,
        "counterpress_pressure_exceeds_pressure": 0,
        "duplicate_composite_key": 0,
        "negative_count": 0,
    }

    # The same SQL on a deliberately broken file, written outside the build.
    broken = tmp_path / "broken.parquet"
    bad_rows = [
        (COMMIT, 1, MATCH_ID, 1, "T", 11, "A", 1, 2, 0),
        (COMMIT, 1, MATCH_ID, 1, "T", 11, "A", -1, -1, -1),
    ]
    analytics.write_parquet(bad_rows, broken)
    assert dict(analytics.query_file(broken, "integrity-checks")[1]) == {
        "counterpress_pressure_exceeds_flagged": 1,
        "counterpress_pressure_exceeds_pressure": 1,
        "duplicate_composite_key": 1,
        "negative_count": 1,
    }


def test_query_command_prints_a_table(project, capsys):
    assert cli.main(["analytics", "--manifest", MANIFEST]) == 0
    capsys.readouterr()
    assert cli.main(["query", "--manifest", MANIFEST, "--name", "team-totals"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ["team_id", "team_name", *METRIC_NAMES]
    assert lines[1].split() == ["1", "Ünited", "3", "1", "1"]
    assert lines[-1] == "(2 rows)"


def test_only_the_fixed_queries_can_be_run(project):
    analytics.build(project, project / MANIFEST)
    with pytest.raises(analytics.AnalyticsError, match="unknown query"):
        analytics.run_query(project, project / MANIFEST, "SELECT 1")
    with pytest.raises(SystemExit):
        cli.main(["query", "--manifest", MANIFEST, "--name", "SELECT 1"])


def test_query_before_any_build_is_refused(project, capsys):
    assert cli.main(["query", "--manifest", MANIFEST, "--name", "team-totals"]) == 1
    assert "no complete analytical output" in capsys.readouterr().err


def test_query_refuses_output_that_no_longer_matches_the_metrics_bundle(project):
    analytics.build(project, project / MANIFEST)
    with (project / CSV_FILE).open("ab") as handle:
        handle.write(b"\n")
    with pytest.raises(analytics.AnalyticsError, match="has changed since"):
        analytics.run_query(project, project / MANIFEST, "team-totals")


# --- the published file is verified before it is queried ------------------

RAW_EVENTS = f"data/raw/statsbomb/open-data/{COMMIT}/{EVENTS_PATH}"
PARQUET = f"{ANALYTICS_DIR}/{analytics.PARQUET_FILE}"
METADATA = f"{ANALYTICS_DIR}/{analytics.METADATA_FILE}"
QUERY = ["query", "--manifest", MANIFEST, "--name", "team-totals"]


@pytest.fixture
def built(project):
    """The project with its analytical output built once."""
    analytics.build(project, project / MANIFEST)
    return project


def edit_metadata(project, change):
    path = project / METADATA
    metadata = json.loads(path.read_text(encoding="utf-8"))
    change(metadata)
    path.write_text(json.dumps(metadata), encoding="utf-8")


def query_fails(project, capsys, message):
    """The query exits 1 with one clean error line and changes nothing on disk."""
    before = snapshot(project)
    capsys.readouterr()
    assert cli.main(QUERY) == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("error: ") and message in captured.err
    assert "Traceback" not in captured.err and captured.out == ""
    assert snapshot(project) == before


def test_unchanged_parquet_is_queried_successfully(built, capsys):
    assert cli.main(QUERY) == 0
    assert "(2 rows)" in capsys.readouterr().out


def test_valid_but_altered_parquet_fails_checksum_verification(built, capsys):
    # A well-formed Parquet file with one count changed: only the checksum can tell.
    altered = [(*row[:7], row[7] + 1, *row[8:]) for row in EXPECTED_ROWS]
    analytics.write_parquet(altered, built / PARQUET)
    assert analytics.read_parquet(built / PARQUET)[1] == altered

    query_fails(built, capsys, "does not match the checksum recorded when it was built")
    # The altered file is left where it is: a query never rebuilds or replaces.
    assert analytics.read_parquet(built / PARQUET)[1] == altered


def test_truncated_parquet_fails_checksum_verification(built, capsys):
    path = built / PARQUET
    path.write_bytes(path.read_bytes()[: path.stat().st_size // 2])
    query_fails(built, capsys, "does not match the checksum recorded when it was built")


def test_missing_parquet_is_reported(built, capsys):
    (built / PARQUET).unlink()
    query_fails(built, capsys, "the Parquet file is missing although its build metadata exists")


def test_metadata_from_before_checksums_requires_a_rebuild(built, capsys):
    def downgrade(metadata):
        del metadata["build_metadata_version"]
        artifact = metadata.pop("parquet_artifact")
        metadata["parquet_file"] = artifact["path"]

    edit_metadata(built, downgrade)
    query_fails(built, capsys, "was written before Parquet checksums were recorded")
    capsys.readouterr()
    assert cli.main(QUERY) == 1
    assert "`phaselens analytics --manifest`" in capsys.readouterr().err


@pytest.mark.parametrize(
    "change",
    [
        lambda metadata: metadata.pop("parquet_artifact"),
        lambda metadata: metadata["parquet_artifact"].pop("sha256"),
        lambda metadata: metadata["parquet_artifact"].update(size_bytes="3213"),
    ],
    ids=["no record", "no sha256", "size as text"],
)
def test_metadata_without_a_usable_checksum_record_is_refused(built, capsys, change):
    edit_metadata(built, change)
    query_fails(built, capsys, "no usable parquet_artifact record")


@pytest.mark.parametrize("version", [1, 3, "2"], ids=repr)
def test_unsupported_metadata_version_is_refused(built, capsys, version):
    edit_metadata(built, lambda metadata: metadata.update(build_metadata_version=version))
    query_fails(built, capsys, f"build metadata version {version!r} is not supported")


def test_metadata_pointing_at_another_file_or_match_is_refused(built, capsys):
    edit_metadata(built, lambda metadata: metadata["parquet_artifact"].update(path="README.md"))
    query_fails(built, capsys, "parquet_artifact path is not this match's Parquet file")
    edit_metadata(built, lambda metadata: metadata.update(match_id=701))
    query_fails(built, capsys, "describes another commit or match")


def test_rebuild_after_a_failed_verification_makes_the_query_work_again(built, capsys):
    (built / PARQUET).write_bytes(b"not a parquet file")
    assert cli.main(QUERY) == 1
    assert cli.main(["analytics", "--manifest", MANIFEST]) == 0
    capsys.readouterr()
    assert cli.main(QUERY) == 0


# --- DuckDB failures become clean errors ----------------------------------


def test_duckdb_failure_on_a_file_that_passes_the_checksum_is_a_clean_cli_error(built, capsys):
    # Garbage whose checksum the metadata records: verification passes, so the
    # failure comes from DuckDB itself and must be reported, not thrown.
    garbage = b"PAR1 this is not a real parquet file PAR1"
    (built / PARQUET).write_bytes(garbage)
    edit_metadata(
        built,
        lambda metadata: metadata["parquet_artifact"].update(
            sha256=hashlib.sha256(garbage).hexdigest(), size_bytes=len(garbage)
        ),
    )
    query_fails(built, capsys, "DuckDB could not query this file")


@pytest.mark.parametrize("reader", [analytics.read_parquet, lambda path: analytics.query_file(path, "team-totals")],
                         ids=["read_parquet", "query_file"])
def test_duckdb_failure_is_translated_by_the_handler_itself(tmp_path, reader):
    broken = tmp_path / "broken.parquet"
    broken.write_bytes(b"\x00" * 64)
    with pytest.raises(analytics.AnalyticsError, match="DuckDB could not (read|query) this file") as raised:
        reader(broken)
    assert isinstance(raised.value.__cause__, duckdb.Error)
    assert "Rebuild it with `phaselens analytics --manifest`" in str(raised.value)


def test_errors_that_are_not_duckdb_failures_are_not_swallowed(tmp_path):
    # A programming error inside the guarded block must surface unchanged.
    with pytest.raises(ZeroDivisionError):
        with analytics._duckdb_errors(tmp_path / "x.parquet", "read"):
            1 / 0


# --- raw inputs and the metrics bundle are still checked ------------------


@pytest.mark.parametrize("command", [["analytics", "--manifest", MANIFEST], QUERY], ids=["analytics", "query"])
def test_analytics_and_query_reject_an_altered_raw_input(built, source, capsys, command):
    (built / RAW_EVENTS).write_bytes(b'[{"id": "tampered"}]')
    before = snapshot(built)
    capsys.readouterr()

    assert cli.main(command) == 1

    assert "conflicts with its manifest record" in capsys.readouterr().err
    assert snapshot(built) == before
    assert source.fetched == []


@pytest.mark.parametrize("command", [["analytics", "--manifest", MANIFEST], QUERY], ids=["analytics", "query"])
def test_analytics_and_query_reject_a_missing_raw_input_without_downloading(built, source, capsys, command):
    (built / RAW_EVENTS).unlink()
    before = snapshot(built)
    capsys.readouterr()

    assert cli.main(command) == 1

    assert "not on disk" in capsys.readouterr().err
    assert snapshot(built) == before
    assert source.fetched == []


def test_changed_metrics_file_is_still_detected_at_query_time(built, capsys):
    with (built / SUMMARY_FILE).open("ab") as handle:
        handle.write(b" ")
    query_fails(built, capsys, "has changed since the analytical output was built")


def test_every_fixed_query_has_readable_sql():
    for name in analytics.QUERIES:
        sql = analytics.query_sql(name)
        assert sql.lstrip().startswith("--") and "player_match_metrics" in sql
