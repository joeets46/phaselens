"""The analytical copy of the ingested real match equals its metrics bundle.

Built into a temporary folder, so nothing in the project is written.
Skipped when the raw files or the metrics bundle are not on disk: they
are not in Git. No network is used.
"""

import csv
import io
import json
from pathlib import Path

import pytest

from phaselens import analytics
from phaselens.metrics import METRIC_NAMES

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMMIT = "4b73468fc5b0f1950f9f66fada70ad3a4f9327cb"
MATCH_ID = 3943043
MANIFEST = PROJECT_ROOT / f"manifests/statsbomb/open-data/{COMMIT}/match_{MATCH_ID}.json"
EVENTS = PROJECT_ROOT / f"data/raw/statsbomb/open-data/{COMMIT}/data/events/{MATCH_ID}.json"
METRICS_DIR = PROJECT_ROOT / f"data/processed/metrics/{COMMIT}/{MATCH_ID}"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    if not MANIFEST.is_file() or not EVENTS.is_file():
        pytest.skip("the real match files are not on disk; `phaselens ingest --manifest` restores them")
    if not (METRICS_DIR / "player_match_metrics.csv").is_file():
        pytest.skip("the real metrics bundle is not on disk; `phaselens metrics --manifest` writes it")
    directory, metadata = analytics.build(
        PROJECT_ROOT, MANIFEST, output_root=tmp_path_factory.mktemp("analytics")
    )
    return directory / analytics.PARQUET_FILE, metadata


def csv_rows():
    """The metrics CSV read with the csv module alone, converted with int()."""
    text = (METRICS_DIR / "player_match_metrics.csv").read_text(encoding="utf-8")
    records = list(csv.DictReader(io.StringIO(text, newline="")))
    return [
        (
            record["source_commit"], int(record["match_id"]), int(record["team_id"]),
            record["team_name"], int(record["player_id"]), record["player_name"],
            *(int(record[name]) for name in METRIC_NAMES),
        )
        for record in records
    ]


def test_every_parquet_row_equals_its_csv_row(built):
    parquet_path, metadata = built
    _, rows = analytics.read_parquet(parquet_path)
    # Drop the contract version column, which the CSV does not carry.
    without_version = [(row[0], *row[2:]) for row in rows]
    assert without_version == sorted(csv_rows(), key=lambda row: (row[2], row[4]))
    assert {row[1] for row in rows} == {metadata["metric_contract_version"]}
    assert metadata["row_count"] == len(rows)


def test_sql_team_totals_equal_the_metrics_summary(built):
    parquet_path, metadata = built
    summary = json.loads((METRICS_DIR / "run_summary.json").read_text(encoding="utf-8"))
    _, rows = analytics.query_file(parquet_path, "team-totals")
    from_sql = {row[0]: dict(zip(METRIC_NAMES, row[2:])) for row in rows}
    assert from_sql == {team["team_id"]: team["metric_totals"] for team in summary["teams"]}
    assert metadata["metric_totals"] == summary["metric_totals"]


def test_integrity_checks_find_nothing(built):
    parquet_path, _ = built
    assert all(violations == 0 for _, violations in analytics.query_file(parquet_path, "integrity-checks")[1])
