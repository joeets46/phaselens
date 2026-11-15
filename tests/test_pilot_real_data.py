"""The combined pilot table equals its five per-match metric outputs.

Built into a temporary folder, so nothing in the project is written.
Skipped when the pilot's inputs or per-match outputs are not on disk:
they are not in Git. No network is used.
"""

import csv
import io
from collections import Counter
from pathlib import Path

import pytest

from phaselens import analytics, pilot
from phaselens.metrics import METRIC_NAMES

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PILOT_FILE = PROJECT_ROOT / "pilots/euro2024_knockout_pilot.json"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    if not PILOT_FILE.is_file():
        pytest.skip("the pilot definition is not on disk")
    definition = pilot.load_pilot(PROJECT_ROOT, PILOT_FILE)
    commit = definition["source_commit"]
    for match_id in definition["match_ids"]:
        needed = [
            f"manifests/statsbomb/open-data/{commit}/match_{match_id}.json",
            f"data/raw/statsbomb/open-data/{commit}/data/events/{match_id}.json",
            f"data/processed/metrics/{commit}/{match_id}/player_match_metrics.csv",
            f"data/processed/analytics/{commit}/{match_id}/{analytics.METADATA_FILE}",
        ]
        if not all((PROJECT_ROOT / path).is_file() for path in needed):
            pytest.skip(f"match {match_id} has not been run; `phaselens pilot --file` runs it")
    directory, metadata = pilot.build_combined(
        PROJECT_ROOT, definition, output_root=tmp_path_factory.mktemp("pilot")
    )
    return definition, directory / analytics.PARQUET_FILE, metadata


def csv_rows(commit, match_id):
    """A match's metrics CSV read with the csv module alone."""
    path = PROJECT_ROOT / f"data/processed/metrics/{commit}/{match_id}/player_match_metrics.csv"
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"), newline="")))


def test_combined_rows_and_totals_equal_the_per_match_csv_files(built):
    definition, parquet, metadata = built
    _, rows = analytics.read_parquet(parquet)
    rows_per_match = Counter(row[2] for row in rows)
    for match_id in definition["match_ids"]:
        expected = csv_rows(definition["source_commit"], match_id)
        assert rows_per_match[match_id] == len(expected), match_id
        for position, name in enumerate(METRIC_NAMES, 7):
            combined = sum(row[position] for row in rows if row[2] == match_id)
            assert combined == sum(int(record[name]) for record in expected), (match_id, name)
    assert metadata["row_count"] == len(rows) == sum(rows_per_match.values())
    assert [c["match_id"] for c in metadata["components"]] == definition["match_ids"]


def test_combined_table_passes_its_integrity_checks(built):
    _, parquet, _ = built
    checks = analytics.query_file(parquet, "integrity-checks", pilot.PILOT_QUERIES)[1]
    assert all(violations == 0 for _, violations in checks)
