"""The first three event-count metrics.

The contract is docs/metric_catalog.md, "Shared contract (version 1)".
Each value is a count of events the provider recorded for one player in
one match. None is a rating, and none measures pressing quality.
"""

import csv
import io
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from phaselens import statsbomb
from phaselens.ingest import IngestError, parse_json_array, read_manifest, read_verified_files

METRIC_CONTRACT_VERSION = 1
METRICS_ROOT = "data/processed/metrics"
OUTPUT_FILES = ("player_match_metrics.csv", "diagnostics.json", "run_summary.json")
METRIC_NAMES = (
    "pressure_event_count",
    "counterpress_pressure_event_count",
    "counterpress_flagged_event_count",
)

# Event type ids and names from the provider's event specification.
PRESSURE = 17
SUBSTITUTION = 19
FOUL_COMMITTED = 22
STARTING_XI = 35
# The types this contract supports for the counterpress flag. It is not
# claimed to be the provider's complete list.
SUPPORTED_COUNTERPRESS_TYPES = {
    4: "Duel",
    6: "Block",
    10: "Interception",
    PRESSURE: "Pressure",
    FOUL_COMMITTED: "Foul Committed",
    33: "50/50",
    39: "Dribbled Past",
}
_DOCUMENTED_TYPE_NAMES = {
    **SUPPORTED_COUNTERPRESS_TYPES,
    SUBSTITUTION: "Substitution",
    STARTING_XI: "Starting XI",
}

# Diagnostics never stop a run. Each lists the ids of the events concerned.
DIAGNOSTICS = {
    "unattributed_event": (
        "An event passes a metric's conditions but has no usable player.id or team.id. "
        "It is counted for no player."
    ),
    "counterpress_true_outside_supported_types": (
        "counterpress is exactly true on an event type outside the supported set. "
        "The event is excluded."
    ),
    "counterpress_explicit_false": "counterpress is false. It counts as not flagged.",
    "counterpress_null": "counterpress is null. It counts as not flagged.",
    "counterpress_non_boolean": (
        "counterpress holds a value that is not a boolean or null. It is not coerced "
        "and counts as not flagged."
    ),
    "offensive_foul_with_counterpress": (
        "A Foul Committed event has foul_committed.offensive and counterpress both "
        "exactly true, which the specification does not provide for. It is excluded "
        "from counterpress_flagged_event_count."
    ),
    "offensive_flag_unexpected_value": (
        "foul_committed.offensive is present on a Foul Committed event and is not "
        "exactly true. The event is treated as not offensive."
    ),
    "type_name_differs_from_documented": (
        "A matched event type id carries a type.name other than the documented one. "
        "The event is matched by id."
    ),
}

LIMITATIONS = (
    "Each value is a count of events the provider recorded. It is not a rating and "
    "does not measure pressing quality, intensity, or off-ball value.",
    "The counting unit is one event, not a pressing episode or sequence.",
    "Counts are not normalized by time on the pitch. No rule for minutes played is "
    "implemented.",
    "A zero means the events file holds no qualifying event for a player it places "
    "on the pitch. It says nothing about how long the player was on it.",
    "Eligibility comes from Starting XI lineups and substitution replacements in the "
    "events file. It is the participation contract supported today, not a general rule.",
    "The counterpress flag and its 5-second window are the provider's. Which team's "
    "turnover starts the window is undocumented.",
    "The supported counterpress type set may not be the provider's complete list.",
    "One match. Values are not comparable across players or matches.",
    "The code is tested against its contract. The metrics are not validated for "
    "football meaning.",
)

_ABSENT = object()


class MetricError(Exception):
    """The inputs do not satisfy the metric contract; nothing was written."""


@dataclass
class MatchMetrics:
    # One dict per eligible (team id, player id) pair, sorted by those ids.
    rows: list
    # Diagnostic name -> ids of the events concerned, in file order.
    diagnostics: dict


def compute_for_manifest(project_root, manifest_file):
    """Verify a manifest's files, compute the metrics, and write the outputs.

    Everything is validated and computed in memory first. Output files are
    written only after that has succeeded.
    """
    project_root = Path(project_root)
    manifest = read_manifest(manifest_file)
    commit_sha = manifest["source"]["commit_sha"]
    selection = manifest["selection"]
    match_id = selection["match_id"]

    files = read_verified_files(project_root, manifest)
    matches_path = statsbomb.matches_path(selection["competition_id"], selection["season_id"])
    events_path = statsbomb.events_path(match_id)
    matches = parse_json_array(files[matches_path], matches_path)
    match = next((entry for entry in matches if entry.get("match_id") == match_id), None)
    if match is None:
        raise IngestError(f"{matches_path}: no match with match_id {match_id}")
    events = parse_json_array(files[events_path], events_path)

    result = compute_match_metrics(events, match)
    summary = run_summary(result, commit_sha, match_id, manifest["files"], [matches_path, events_path])
    outputs = {
        "player_match_metrics.csv": _csv_bytes(
            [{"source_commit": commit_sha, "match_id": match_id, **row} for row in result.rows]
        ),
        "diagnostics.json": _json_bytes(
            {
                "metric_contract_version": METRIC_CONTRACT_VERSION,
                "source_commit": commit_sha,
                "match_id": match_id,
                "diagnostics": [
                    {
                        "name": name,
                        "raised_when": description,
                        "count": len(result.diagnostics[name]),
                        "event_ids": result.diagnostics[name],
                    }
                    for name, description in DIAGNOSTICS.items()
                ],
            }
        ),
        "run_summary.json": _json_bytes(summary),
    }
    directory = project_root / METRICS_ROOT / commit_sha / str(match_id)
    directory.mkdir(parents=True, exist_ok=True)
    for name in OUTPUT_FILES:
        (directory / name).write_bytes(outputs[name])
    return directory, summary


def compute_match_metrics(events, match):
    """Count the three metrics for every eligible player of one match."""
    _require_unique_ids(events)
    eligible, team_names = _eligible_players(events, _match_team_ids(match))
    counts = {pair: [0, 0, 0] for pair in eligible}
    diagnostics = {name: [] for name in DIAGNOSTICS}
    outside_eligible = []

    for event in events:
        type_id = _integer(_get(event, "type.id"))
        documented_name = _DOCUMENTED_TYPE_NAMES.get(type_id)
        if documented_name is not None and _get(event, "type.name") != documented_name:
            diagnostics["type_name_differs_from_documented"].append(event["id"])

        flagged = _counterpress(event, diagnostics)
        supported = type_id in SUPPORTED_COUNTERPRESS_TYPES
        if flagged and not supported:
            diagnostics["counterpress_true_outside_supported_types"].append(event["id"])
        offensive = type_id == FOUL_COMMITTED and _offensive(event, diagnostics)
        if offensive and flagged:
            diagnostics["offensive_foul_with_counterpress"].append(event["id"])

        contribution = (
            int(type_id == PRESSURE),
            int(type_id == PRESSURE and flagged),
            int(supported and flagged and not offensive),
        )
        if not any(contribution):
            continue
        pair = (_integer(_get(event, "team.id")), _integer(_get(event, "player.id")))
        if None in pair:
            diagnostics["unattributed_event"].append(event["id"])
        elif pair not in eligible:
            outside_eligible.append(event["id"])
        else:
            for position, value in enumerate(contribution):
                counts[pair][position] += value

    if outside_eligible:
        raise MetricError(
            f"{len(outside_eligible)} countable event(s) belong to a player outside the "
            "eligible set (Starting XI lineups and substitution replacements); "
            f"first event ids: {', '.join(map(str, outside_eligible[:5]))}"
        )

    rows = []
    for team_id, player_id in sorted(eligible):
        values = counts[(team_id, player_id)]
        if not (0 <= values[1] <= values[0] and values[1] <= values[2]):
            raise MetricError(
                f"internal inconsistency for team {team_id} player {player_id}: {values}"
            )
        rows.append(
            {
                "team_id": team_id,
                "team_name": team_names[team_id],
                "player_id": player_id,
                "player_name": eligible[(team_id, player_id)],
                **dict(zip(METRIC_NAMES, values)),
            }
        )
    return MatchMetrics(rows, diagnostics)


def run_summary(result, commit_sha, match_id, verified_files, source_paths_read):
    """The run described in one object. It holds no timestamp, so it is repeatable."""
    teams = {}
    for row in result.rows:
        team = teams.setdefault(
            row["team_id"],
            {
                "team_id": row["team_id"],
                "team_name": row["team_name"],
                "eligible_player_count": 0,
                "metric_totals": dict.fromkeys(METRIC_NAMES, 0),
            },
        )
        team["eligible_player_count"] += 1
        for name in METRIC_NAMES:
            team["metric_totals"][name] += row[name]
    return {
        "metric_contract_version": METRIC_CONTRACT_VERSION,
        "source_commit": commit_sha,
        "match_id": match_id,
        "verified_inputs": [
            {key: entry[key] for key in ("local_path", "sha256", "size_bytes")}
            for entry in verified_files
        ],
        "source_paths_read": source_paths_read,
        "counting_unit": "event",
        "eligible_player_count": len(result.rows),
        "metric_totals": {
            name: sum(row[name] for row in result.rows) for name in METRIC_NAMES
        },
        "teams": [teams[team_id] for team_id in sorted(teams)],
        "diagnostic_totals": {name: len(ids) for name, ids in result.diagnostics.items()},
        "limitations": list(LIMITATIONS),
    }


# --- contract checks ------------------------------------------------------


def _require_unique_ids(events):
    counts = Counter()
    for position, event in enumerate(events, 1):
        event_id = event.get("id")
        if not isinstance(event_id, (str, int)) or isinstance(event_id, bool):
            raise MetricError(f"the event at position {position} has no usable id")
        counts[event_id] += 1
    duplicated = [event_id for event_id, count in counts.items() if count > 1]
    if duplicated:
        raise MetricError(
            f"{len(duplicated)} event id(s) occur more than once; nothing is deduplicated. "
            f"First ids: {', '.join(map(str, duplicated[:5]))}"
        )


def _match_team_ids(match):
    home = _integer(_get(match, "home_team.home_team_id"))
    away = _integer(_get(match, "away_team.away_team_id"))
    if home is None or away is None or home == away:
        raise MetricError("the match record does not give two different integer team ids")
    return {home, away}


def _eligible_players(events, team_ids):
    """P(c, m): the (team id, player id) pairs the events file places on the pitch.

    Returns {pair: player name} and {team id: team name}. A name is a label
    taken from the first record that names the id, in file order.
    """
    player_names = {}
    team_names = {}
    starting_events = Counter()
    for event in events:
        type_id = _integer(_get(event, "type.id"))
        if type_id not in (STARTING_XI, SUBSTITUTION):
            continue
        kind = _DOCUMENTED_TYPE_NAMES[type_id]
        team_id = _integer(_get(event, "team.id"))
        if team_id not in team_ids:
            raise MetricError(
                f"event {event['id']}: this {kind} event does not belong to one of the "
                f"match's teams {sorted(team_ids)}"
            )
        if type_id == STARTING_XI:
            starting_events[team_id] += 1
            team_names.setdefault(team_id, _text(_get(event, "team.name")))
            players = _get(event, "tactics.lineup")
            if not isinstance(players, list) or not players:
                raise MetricError(
                    f"event {event['id']}: Starting XI has no non-empty tactics.lineup array"
                )
            players = [_get(entry, "player") for entry in players]
        else:
            players = [_get(event, "substitution.replacement")]
        for player in players:
            player_id = _integer(_get(player, "id"))
            if player_id is None:
                raise MetricError(
                    f"event {event['id']}: this {kind} event names a player without an "
                    "integer id"
                )
            player_names.setdefault((team_id, player_id), _text(_get(player, "name")))

    for team_id in sorted(team_ids):
        if starting_events[team_id] != 1:
            raise MetricError(
                f"team {team_id} has {starting_events[team_id]} Starting XI events; "
                "exactly one is required"
            )
    teams_of_player = defaultdict(set)
    for team_id, player_id in player_names:
        teams_of_player[player_id].add(team_id)
    conflicting = sorted(player_id for player_id, teams in teams_of_player.items() if len(teams) > 1)
    if conflicting:
        raise MetricError(
            f"player id(s) {', '.join(map(str, conflicting[:5]))} are eligible for both teams"
        )
    return player_names, team_names


def _counterpress(event, diagnostics):
    """True only when the top-level counterpress key holds exactly true."""
    if "counterpress" not in event:
        return False
    value = event["counterpress"]
    if value is True:
        return True
    if value is False:
        name = "counterpress_explicit_false"
    elif value is None:
        name = "counterpress_null"
    else:
        name = "counterpress_non_boolean"
    diagnostics[name].append(event["id"])
    return False


def _offensive(event, diagnostics):
    """True only when foul_committed.offensive holds exactly true."""
    value = _get(event, "foul_committed.offensive")
    if value is True:
        return True
    if value is not _ABSENT:
        diagnostics["offensive_flag_unexpected_value"].append(event["id"])
    return False


# --- small helpers --------------------------------------------------------


def _get(value, path):
    """Follow a dotted path through nested objects; _ABSENT if it ends early."""
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return _ABSENT
        value = value[key]
    return value


def _integer(value):
    """The value if it is an integer and not a boolean, else None."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _text(value):
    return value if isinstance(value, str) else ""


def _json_bytes(value):
    return json.dumps(value, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"


def _csv_bytes(rows):
    buffer = io.StringIO()
    columns = ["source_commit", "match_id", "team_id", "team_name", "player_id", "player_name"]
    writer = csv.DictWriter(buffer, fieldnames=[*columns, *METRIC_NAMES], lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")
