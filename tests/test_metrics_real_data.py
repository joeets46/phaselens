"""Reconcile the metrics of the ingested real match with an independent count.

The audit below counts qualifying source events with plain loops. It
shares no code with the metric aggregation and is written straight from
the contract in docs/metric_catalog.md. Nothing is written to disk.

The raw files are not in Git, so the tests are skipped when they are
absent. They never use the network.
"""

import json
from collections import Counter
from pathlib import Path

import pytest

from phaselens.ingest import read_manifest, read_verified_files
from phaselens.metrics import METRIC_NAMES, compute_match_metrics

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMMIT = "4b73468fc5b0f1950f9f66fada70ad3a4f9327cb"
MATCH_ID = 3943043
MANIFEST = PROJECT_ROOT / f"manifests/statsbomb/open-data/{COMMIT}/match_{MATCH_ID}.json"
EVENTS = PROJECT_ROOT / f"data/raw/statsbomb/open-data/{COMMIT}/data/events/{MATCH_ID}.json"

SUPPORTED = {4, 6, 10, 17, 22, 33, 39}
PRESSURE, COUNTERPRESS_PRESSURE, FLAGGED = METRIC_NAMES


@pytest.fixture(scope="module")
def real_match():
    if not MANIFEST.is_file() or not EVENTS.is_file():
        pytest.skip("the real match files are not on disk; `phaselens ingest --manifest` restores them")
    manifest = read_manifest(MANIFEST)
    files = read_verified_files(PROJECT_ROOT, manifest)
    matches = json.loads(files["data/matches/55/282.json"])
    match = next(entry for entry in matches if entry["match_id"] == MATCH_ID)
    events = json.loads(files[f"data/events/{MATCH_ID}.json"])
    return events, match


def audit(events):
    """Count source events that meet each metric's conditions, split by attribution."""
    attributed = Counter()      # (team id, metric) -> events with a team and a player
    in_source = Counter()       # metric -> every event meeting the conditions
    without_player = []         # ids of qualifying events lacking a player or a team
    offensive_and_flagged = []  # ids of offensive fouls that carry the flag
    flagged_unsupported = []    # ids of flagged events of a type outside the supported set
    for event in events:
        type_id = event["type"]["id"]
        flagged = "counterpress" in event and event["counterpress"] is True
        offensive = type_id == 22 and event.get("foul_committed", {}).get("offensive") is True
        if flagged and type_id not in SUPPORTED:
            flagged_unsupported.append(event["id"])
        if flagged and offensive:
            offensive_and_flagged.append(event["id"])
        qualifies = {
            PRESSURE: type_id == 17,
            COUNTERPRESS_PRESSURE: type_id == 17 and flagged,
            FLAGGED: type_id in SUPPORTED and flagged and not offensive,
        }
        if not any(qualifies.values()):
            continue
        team_id = event.get("team", {}).get("id")
        player_id = event.get("player", {}).get("id")
        has_owner = isinstance(team_id, int) and isinstance(player_id, int)
        if not has_owner:
            without_player.append(event["id"])
        for metric, met in qualifies.items():
            if met:
                in_source[metric] += 1
                if has_owner:
                    attributed[(team_id, metric)] += 1
    return attributed, in_source, without_player, offensive_and_flagged, flagged_unsupported


def test_player_totals_reconcile_with_an_independent_count_per_team(real_match):
    events, match = real_match
    attributed, _, _, _, _ = audit(events)
    result = compute_match_metrics(events, match)

    from_rows = Counter()
    for row in result.rows:
        for metric in METRIC_NAMES:
            from_rows[(row["team_id"], metric)] += row[metric]

    team_ids = {row["team_id"] for row in result.rows}
    assert team_ids == {match["home_team"]["home_team_id"], match["away_team"]["away_team_id"]}
    for team_id in team_ids:
        for metric in METRIC_NAMES:
            assert from_rows[(team_id, metric)] == attributed[(team_id, metric)], (team_id, metric)


def test_every_qualifying_source_event_is_counted_or_accounted_for(real_match):
    events, match = real_match
    _, in_source, without_player, offensive_and_flagged, flagged_unsupported = audit(events)
    result = compute_match_metrics(events, match)

    # Exclusions are reported by id, and the audit finds the same ids.
    assert result.diagnostics["unattributed_event"] == without_player
    assert result.diagnostics["offensive_foul_with_counterpress"] == offensive_and_flagged
    assert result.diagnostics["counterpress_true_outside_supported_types"] == flagged_unsupported

    # Source events = events counted for players + events without an owner.
    by_id = {event["id"]: event for event in events}
    for metric in METRIC_NAMES:
        counted = sum(row[metric] for row in result.rows)
        unowned = sum(
            1 for event_id in without_player if _qualifies(by_id[event_id], metric)
        )
        assert in_source[metric] == counted + unowned, metric


def test_rows_are_the_starting_lineups_plus_replacements(real_match):
    events, match = real_match
    expected = set()
    for event in events:
        if event["type"]["id"] == 35:
            expected |= {(event["team"]["id"], entry["player"]["id"]) for entry in event["tactics"]["lineup"]}
        if event["type"]["id"] == 19:
            expected.add((event["team"]["id"], event["substitution"]["replacement"]["id"]))
    result = compute_match_metrics(events, match)

    assert [(row["team_id"], row["player_id"]) for row in result.rows] == sorted(expected)
    for row in result.rows:
        assert 0 <= row[COUNTERPRESS_PRESSURE] <= row[PRESSURE]
        assert row[COUNTERPRESS_PRESSURE] <= row[FLAGGED]


def _qualifies(event, metric):
    type_id = event["type"]["id"]
    flagged = "counterpress" in event and event["counterpress"] is True
    offensive = type_id == 22 and event.get("foul_committed", {}).get("offensive") is True
    return {
        PRESSURE: type_id == 17,
        COUNTERPRESS_PRESSURE: type_id == 17 and flagged,
        FLAGGED: type_id in SUPPORTED and flagged and not offensive,
    }[metric]
