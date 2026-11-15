"""Describe what one ingested match's files contain.

Read-only and offline. The inputs are the raw files a manifest records,
verified against it first. Nothing here scores players or computes
metrics: it counts what is present, and reports what it cannot explain.
"""

import csv
import io
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from phaselens import statsbomb
from phaselens.ingest import IngestError, parse_json_array, read_manifest, read_verified_files

PROFILE_FORMAT_VERSION = 1
PROFILE_ROOT = "data/processed/profiles"
OUTPUT_FILES = ("summary.json", "event_types.csv", "field_presence.csv", "quality_findings.json")

ALL_EVENTS = "(all events)"
MISSING = "(missing)"

# Event types and fields related to off-ball activity, under the names
# found in the match profiled in Milestone 2. They are looked up, not
# assumed: one that a match lacks is reported with a count of zero.
OFF_BALL_EVENT_TYPES = (
    "Pressure",
    "Ball Recovery",
    "Interception",
    "Duel",
    "50/50",
    "Block",
    "Clearance",
    "Dribbled Past",
)
OFF_BALL_FIELDS = (
    "under_pressure",
    "counterpress",
    "duel.type.name",
    "duel.outcome.name",
    "interception.outcome.name",
    "ball_recovery.recovery_failure",
    "50_50.outcome.name",
)

# Working expectation of the shape check, not a provider rule: a
# coordinate is a list of two numbers. Three numbers are reported as an
# open question, anything else as a warning.
_PLAIN_COORDINATE_LENGTH = 2
_EXTENDED_COORDINATE_LENGTH = 3

_MAX_EXAMPLES = 5
_TIMESTAMP = re.compile(r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})")
_CLOCK = re.compile(r"\d{2,3}:\d{2}")
_ABSENT = object()


# --- entry point ----------------------------------------------------------


def profile_match(project_root, manifest_file):
    """Verify a manifest's files, profile them, and write the outputs."""
    project_root = Path(project_root)
    manifest = read_manifest(manifest_file)
    commit_sha = manifest["source"]["commit_sha"]
    selection = manifest["selection"]
    match_id = selection["match_id"]

    files = read_verified_files(project_root, manifest)

    def parsed(source_path):
        return parse_json_array(files[source_path], source_path)

    matches_path = statsbomb.matches_path(selection["competition_id"], selection["season_id"])
    matches = parsed(matches_path)
    match = next((entry for entry in matches if entry.get("match_id") == match_id), None)
    if match is None:
        raise IngestError(f"{matches_path}: no match with match_id {match_id}")
    lineups = parsed(statsbomb.lineups_path(match_id))
    events = parsed(statsbomb.events_path(match_id))

    profile = build_profile(events, lineups, match)
    profile["summary"] = {
        "profile_format_version": PROFILE_FORMAT_VERSION,
        "inputs": {
            "commit_sha": commit_sha,
            "selection": selection,
            "verified_files": [
                {key: entry[key] for key in ("local_path", "sha256", "size_bytes")}
                for entry in manifest["files"]
            ],
        },
        **profile["summary"],
    }
    directory = project_root / PROFILE_ROOT / commit_sha / str(match_id)
    write_profile(directory, profile)
    return directory, profile


def build_profile(events, lineups, match):
    """Everything the profile reports, computed from parsed inputs."""
    return {
        "summary": {
            "events": event_structure(events),
            "list_fields": list_fields(events),
            "coordinate_fields": coordinate_fields(events),
            "off_ball": off_ball_availability(events),
            "lineups": lineup_structure(lineups, events),
            "participation_events": participation_events(events),
        },
        "event_types": event_type_rows(events),
        "field_presence": field_presence(events),
        "findings": quality_findings(events, lineups, match),
    }


def write_profile(directory, profile):
    """Write the four output files. Same inputs give the same bytes."""
    directory.mkdir(parents=True, exist_ok=True)
    outputs = {
        "summary.json": _json_bytes(profile["summary"]),
        "event_types.csv": _csv_bytes(profile["event_types"]),
        "field_presence.csv": _csv_bytes(profile["field_presence"]),
        "quality_findings.json": _json_bytes(profile["findings"]),
    }
    for name in OUTPUT_FILES:
        (directory / name).write_bytes(outputs[name])


def _json_bytes(value):
    return json.dumps(value, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"


def _csv_bytes(rows):
    buffer = io.StringIO()
    if rows:
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


# --- small helpers --------------------------------------------------------


def _get(value, path):
    """Follow a dotted path through nested objects; _ABSENT if it ends early."""
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return _ABSENT
        value = value[key]
    return value


def _has(value, path):
    """True when the path exists and its value is not null."""
    found = _get(value, path)
    return found is not _ABSENT and found is not None


def _kind(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    return "object"


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _label(value):
    """A value as a table label; anything that is not a plain scalar is spelled out."""
    if value is _ABSENT:
        return MISSING
    if value is None:
        return "(null)"
    if isinstance(value, (bool, int, float, str)):
        return value
    return f"({_kind(value)})"


def _type_name(event):
    return _label(_get(event, "type.name"))


def _team_id(event):
    return _label(_get(event, "team.id"))


def _player_id(event):
    return _label(_get(event, "player.id"))


def _is_id(value):
    """Usable as an identifier: a string or an integer."""
    return isinstance(value, (str, int)) and not isinstance(value, bool)


def _events_by_id(events):
    return {event["id"]: event for event in events if _is_id(event.get("id"))}


def _references(events):
    """(event, target id) for every usable entry of every related_events list."""
    return [
        (event, target)
        for event in events
        if isinstance(event.get("related_events"), list)
        for target in event["related_events"]
        if _is_id(target)
    ]


def _lists(event, target):
    """True when `event` names `target` in its related_events."""
    related = event.get("related_events")
    return isinstance(related, list) and target in related


def _ranked(counter):
    """Counts as a list, largest first; ties in a fixed order."""
    ordered = sorted(counter.items(), key=lambda item: (-item[1], str(item[0])))
    return [{"value": value, "count": count} for value, count in ordered]


def _percent(part, whole):
    return round(100 * part / whole, 2) if whole else 0.0


def _walk(value, prefix=""):
    """Yield (path, value) for every key of nested objects. Lists are not entered."""
    for key, child in value.items():
        path = f"{prefix}.{key}" if prefix else key
        yield path, child
        if isinstance(child, dict):
            yield from _walk(child, path)


def _seconds(timestamp):
    """Seconds in an HH:MM:SS.mmm string, or None if it has another form."""
    match = _TIMESTAMP.fullmatch(timestamp) if isinstance(timestamp, str) else None
    if match is None:
        return None
    hours, minutes, seconds, millis = (int(part) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def _by_period(events):
    """Events grouped by period, each group in file order."""
    groups = defaultdict(list)
    for event in events:
        groups[_label(_get(event, "period"))].append(event)
    return sorted(
        groups.items(),
        key=lambda item: (0, item[0], "") if _is_number(item[0]) else (1, 0, str(item[0])),
    )


# --- event structure ------------------------------------------------------


def event_structure(events):
    """Counts, identifiers, ordering, time and possession fields as observed."""
    ids = [event["id"] for event in events if _is_id(event.get("id"))]
    indexes = [
        event["index"]
        for event in events
        if isinstance(event.get("index"), int) and not isinstance(event.get("index"), bool)
    ]
    possessions = [event["possession"] for event in events if _is_number(event.get("possession"))]
    possession_changes = [
        (before, after)
        for before, after in zip(events, events[1:])
        if _has(before, "possession")
        and _has(after, "possession")
        and before["possession"] != after["possession"]
    ]
    return {
        "event_count": len(events),
        "by_type": _ranked(Counter(_type_name(event) for event in events)),
        "by_team": _ranked(Counter(_label(_get(event, "team.name")) for event in events)),
        "by_period": [
            {"period": period, "events": len(group)} for period, group in _by_period(events)
        ],
        "ids": {
            "events_with_usable_id": len(ids),
            "distinct_ids": len(set(ids)),
            "id_kinds": _ranked(Counter(_kind(event.get("id")) for event in events if "id" in event)),
        },
        "index": {
            "events_with_integer_index": len(indexes),
            "distinct": len(set(indexes)),
            "min": min(indexes, default=None),
            "max": max(indexes, default=None),
            "ascending_in_file_order": indexes == sorted(indexes),
            "contiguous_from_1": indexes == list(range(1, len(indexes) + 1)),
        },
        "identifiers": {
            "events_with_team_id": sum(_has(event, "team.id") for event in events),
            "events_with_player_id": sum(_has(event, "player.id") for event in events),
            "events_without_player_id_by_type": _ranked(
                Counter(_type_name(event) for event in events if not _has(event, "player.id"))
            ),
        },
        "time": {
            "value_kinds": {
                field: _ranked(Counter(_kind(_get(event, field)) for event in events if field in event))
                for field in ("timestamp", "minute", "second", "period")
            },
            "timestamps_in_HH_MM_SS_mmm_form": sum(
                _seconds(event.get("timestamp")) is not None for event in events
            ),
            "by_period": [_period_times(period, group) for period, group in _by_period(events)],
        },
        "possession": {
            "events_with_possession": sum(_has(event, "possession") for event in events),
            "events_with_possession_team_id": sum(
                _has(event, "possession_team.id") for event in events
            ),
            "distinct_possession_values": len(set(possessions)),
            "min": min(possessions, default=None),
            "max": max(possessions, default=None),
            "non_decreasing_in_file_order": possessions == sorted(possessions),
            "value_changes_between_consecutive_events": len(possession_changes),
            "value_changes_where_possession_team_also_changes": sum(
                _get(before, "possession_team.id") != _get(after, "possession_team.id")
                for before, after in possession_changes
            ),
            "events_where_team_differs_from_possession_team": sum(
                _has(event, "team.id")
                and _has(event, "possession_team.id")
                and event["team"]["id"] != event["possession_team"]["id"]
                for event in events
            ),
        },
    }


def _period_times(period, group):
    seconds = [_seconds(event.get("timestamp")) for event in group]
    parsed = [value for value in seconds if value is not None]
    minutes = [event["minute"] for event in group if _is_number(event.get("minute"))]
    # How the minute/second pair relates to the timestamp is observed here,
    # not assumed: the distinct differences are listed.
    offsets = Counter(
        event["minute"] * 60 + event["second"] - int(value)
        for event, value in zip(group, seconds)
        if value is not None
        and _is_number(event.get("minute"))
        and _is_number(event.get("second"))
    )
    with_timestamp = [event for event, value in zip(group, seconds) if value is not None]
    return {
        "period": period,
        "events": len(group),
        "first_timestamp": with_timestamp[0]["timestamp"] if with_timestamp else None,
        "largest_timestamp": (
            max(with_timestamp, key=lambda event: _seconds(event["timestamp"]))["timestamp"]
            if with_timestamp
            else None
        ),
        "largest_timestamp_seconds": max(parsed, default=None),
        "min_minute": min(minutes, default=None),
        "max_minute": max(minutes, default=None),
        "clock_minus_timestamp_seconds": _ranked(offsets)[:_MAX_EXAMPLES],
        "distinct_clock_minus_timestamp_values": len(offsets),
    }


def event_type_rows(events):
    """One row per event type, with how often common top-level fields occur."""
    groups = defaultdict(list)
    for event in events:
        groups[_type_name(event)].append(event)
    rows = []
    for name, group in sorted(groups.items(), key=lambda item: (-len(item[1]), str(item[0]))):
        type_ids = sorted({str(_label(_get(event, "type.id"))) for event in group})
        rows.append(
            {
                "event_type": name,
                "type_id": "|".join(type_ids),
                "events": len(group),
                "percent_of_all_events": _percent(len(group), len(events)),
                "with_player": sum(_has(event, "player.id") for event in group),
                "with_location": sum(_has(event, "location") for event in group),
                "with_duration": sum(_has(event, "duration") for event in group),
                "with_related_events": sum(_has(event, "related_events") for event in group),
                "with_under_pressure": sum(_has(event, "under_pressure") for event in group),
                "with_counterpress": sum(_has(event, "counterpress") for event in group),
            }
        )
    return rows


# --- field presence -------------------------------------------------------


def field_presence(events):
    """Non-null, null and missing counts per field path, overall and per type.

    The denominator of a row is the number of events in its scope. Within
    an event type only paths seen in that type get a row, so a field that
    another type carries is simply not listed: absence there is structure,
    not a defect.
    """
    denominators = Counter()
    kinds = defaultdict(Counter)
    for event in events:
        scopes = (ALL_EVENTS, _type_name(event))
        for scope in scopes:
            denominators[scope] += 1
        for path, value in _walk(event):
            for scope in scopes:
                kinds[(scope, path)][_kind(value)] += 1
    rows = []
    for scope, path in sorted(kinds, key=lambda key: (key[0] != ALL_EVENTS, str(key[0]), key[1])):
        counts = kinds[(scope, path)]
        denominator = denominators[scope]
        null = counts["null"]
        non_null = sum(counts.values()) - null
        rows.append(
            {
                "scope": scope,
                "field_path": path,
                "denominator": denominator,
                "non_null": non_null,
                "null": null,
                "missing": denominator - non_null - null,
                "percent_non_null": _percent(non_null, denominator),
                "value_kinds": "|".join(sorted(kind for kind in counts if kind != "null")),
            }
        )
    return rows


def list_fields(events):
    """List-valued fields described as lists, without expanding their elements."""
    fields = {}
    for event in events:
        for path, value in _walk(event):
            if not isinstance(value, list):
                continue
            field = fields.setdefault(
                path, {"events": 0, "lengths": Counter(), "kinds": Counter(), "keys": set()}
            )
            field["events"] += 1
            field["lengths"][len(value)] += 1
            for item in value:
                field["kinds"][_kind(item)] += 1
                if isinstance(item, dict):
                    field["keys"].update(item)
    return [
        {
            "field_path": path,
            "events": field["events"],
            "min_length": min(field["lengths"]),
            "max_length": max(field["lengths"]),
            "element_kinds": sorted(field["kinds"]),
            "element_keys": sorted(field["keys"]),
        }
        for path, field in sorted(fields.items())
    ]


# --- coordinates ----------------------------------------------------------


def _coordinates(value, prefix=""):
    """Yield (path, value) for fields named like a location, at any depth.

    Detection is by name: `location` or `*_location`. Lists of objects are
    entered and marked with [] in the path.
    """
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            if key == "location" or key.endswith("_location"):
                yield path, child
            else:
                yield from _coordinates(child, path)
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                yield from _coordinates(item, f"{prefix}[]")


def _is_numeric_list(value):
    return isinstance(value, list) and all(_is_number(item) for item in value)


def coordinate_fields(events):
    """Shape and observed range of each coordinate-bearing field.

    The ranges are what this file contains. They do not establish pitch
    dimensions, units, or direction of play.
    """
    fields = {}
    for event in events:
        seen = set()
        for path, value in _coordinates(event):
            field = fields.setdefault(
                path,
                {
                    "events": 0,
                    "values": 0,
                    "lengths": Counter(),
                    "not_a_list": 0,
                    "with_non_numeric_element": 0,
                    "low": {},
                    "high": {},
                    "types": Counter(),
                },
            )
            field["values"] += 1
            if path not in seen:
                seen.add(path)
                field["events"] += 1
                field["types"][_type_name(event)] += 1
            if not isinstance(value, list):
                field["not_a_list"] += 1
                continue
            field["lengths"][len(value)] += 1
            if not _is_numeric_list(value):
                field["with_non_numeric_element"] += 1
                continue
            for position, number in enumerate(value):
                field["low"][position] = min(field["low"].get(position, number), number)
                field["high"][position] = max(field["high"].get(position, number), number)
    return [
        {
            "field_path": path,
            "events": field["events"],
            "values": field["values"],
            "list_lengths": [
                {"length": length, "count": count}
                for length, count in sorted(field["lengths"].items())
            ],
            "not_a_list": field["not_a_list"],
            "with_non_numeric_element": field["with_non_numeric_element"],
            "observed_ranges": [
                {"component": position, "min": field["low"][position], "max": field["high"][position]}
                for position in sorted(field["low"])
            ],
            "event_types": _ranked(field["types"]),
        }
        for path, field in sorted(fields.items())
    ]


# --- off-ball-relevant data -----------------------------------------------


def off_ball_availability(events):
    """Where event types and fields related to off-ball activity occur.

    These are counts of what annotators recorded. They are not measures of
    pressing quality, positioning, intensity, or off-ball value.
    """
    by_id = _events_by_id(events)
    references = _references(events)
    event_types = []
    for name in OFF_BALL_EVENT_TYPES:
        group = [event for event in events if _type_name(event) == name]
        related = Counter(
            _type_name(by_id[target])
            for event, target in references
            if _type_name(event) == name and target in by_id
        )
        event_types.append(
            {
                "event_type": name,
                "events": len(group),
                "with_counterpress": sum(_has(event, "counterpress") for event in group),
                "with_under_pressure": sum(_has(event, "under_pressure") for event in group),
                "with_duration": sum(_has(event, "duration") for event in group),
                "with_related_events": sum(_has(event, "related_events") for event in group),
                "team_differs_from_possession_team": sum(
                    _has(event, "team.id")
                    and _has(event, "possession_team.id")
                    and event["team"]["id"] != event["possession_team"]["id"]
                    for event in group
                ),
                "related_event_types": _ranked(related),
            }
        )
    fields = []
    for path in OFF_BALL_FIELDS:
        carrying = [event for event in events if _has(event, path)]
        fields.append(
            {
                "field_path": path,
                "events": len(carrying),
                "values": _ranked(Counter(_label(_get(event, path)) for event in carrying)),
                "event_types": _ranked(Counter(_type_name(event) for event in carrying)),
            }
        )
    return {
        "event_types": event_types,
        "fields": fields,
        "related_events": {
            "events_with_related_events": sum(_has(event, "related_events") for event in events),
            "references": len(references),
            "references_to_ids_not_in_file": sum(target not in by_id for _, target in references),
            "references_not_returned_by_target": sum(
                target in by_id and not _lists(by_id[target], event.get("id"))
                for event, target in references
            ),
        },
    }


# --- lineups and participation --------------------------------------------


def _records(value):
    """The objects in a list; an empty list for anything else."""
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _key_kinds(records):
    """For a list of objects: each key, how many carry it, and its value kinds."""
    kinds = defaultdict(Counter)
    for record in records:
        for key, value in record.items():
            kinds[key][_kind(value)] += 1
    return [
        {"key": key, "records": sum(counts.values()), "of": len(records), "kinds": dict(sorted(counts.items()))}
        for key, counts in sorted(kinds.items())
    ]


def _lineup_player_ids(lineups):
    """{team_id: set of player_id} as listed in the lineups file."""
    return {
        _label(team.get("team_id", _ABSENT)): {
            _label(player.get("player_id", _ABSENT)) for player in _records(team.get("lineup"))
        }
        for team in lineups
    }


def _event_player_ids(events):
    """{team id: set of player id} over events that carry both."""
    players = defaultdict(set)
    for event in events:
        if _has(event, "team.id") and _has(event, "player.id"):
            players[_team_id(event)].add(_player_id(event))
    return players


def lineup_structure(lineups, events):
    """What the lineups file holds about identity, positions and cards."""
    event_players = _event_player_ids(events)
    players, intervals, cards, teams = [], [], [], []
    for team in lineups:
        team_players = _records(team.get("lineup"))
        with_intervals = {
            _label(player.get("player_id", _ABSENT))
            for player in team_players
            if _records(player.get("positions"))
        }
        with_events = event_players.get(_label(team.get("team_id", _ABSENT)), set())
        teams.append(
            {
                "team_id": _label(team.get("team_id", _ABSENT)),
                "team_name": _label(team.get("team_name", _ABSENT)),
                "players_listed": len(team_players),
                "players_with_position_interval": len(with_intervals),
                "players_without_position_interval": len(team_players) - len(with_intervals),
                "players_with_events": len(with_events),
                "players_with_events_but_no_position_interval": len(with_events - with_intervals),
                "players_with_position_interval_but_no_events": len(with_intervals - with_events),
            }
        )
        players.extend(team_players)
        for player in team_players:
            intervals.extend(_records(player.get("positions")))
            cards.extend(_records(player.get("cards")))

    def values(records, key):
        return _ranked(Counter(_label(record.get(key, _ABSENT)) for record in records))

    def clock_forms(key):
        forms = Counter()
        for interval in intervals:
            value = interval.get(key, _ABSENT)
            if isinstance(value, str) and _CLOCK.fullmatch(value):
                forms["MM:SS string"] += 1
            elif value is None or value is _ABSENT:
                forms[_label(value)] += 1
            else:
                forms["other"] += 1
        return _ranked(forms)

    return {
        "team_entries": len(lineups),
        "team_keys": _key_kinds(lineups),
        "teams": teams,
        "player_keys": _key_kinds(players),
        "position_interval_count": len(intervals),
        "position_interval_keys": _key_kinds(intervals),
        "position_interval_values": {
            "start_reason": values(intervals, "start_reason"),
            "end_reason": values(intervals, "end_reason"),
            "from_period": values(intervals, "from_period"),
            "to_period": values(intervals, "to_period"),
            "from_form": clock_forms("from"),
            "to_form": clock_forms("to"),
        },
        "card_count": len(cards),
        "card_keys": _key_kinds(cards),
        "card_values": {
            "card_type": values(cards, "card_type"),
            "reason": values(cards, "reason"),
        },
    }


def participation_events(events):
    """Event types and fields that bear on who was on the pitch, and when."""

    def of_type(name):
        return [event for event in events if _type_name(event) == name]

    substitutions = of_type("Substitution")
    card_values = defaultdict(Counter)
    for event in events:
        for path, value in _walk(event):
            if path.endswith("card.name"):
                card_values[path][_label(value)] += 1
    return {
        "starting_xi_events": len(of_type("Starting XI")),
        "starting_xi_lineup_sizes": _ranked(
            Counter(len(_records(_get(event, "tactics.lineup"))) for event in of_type("Starting XI"))
        ),
        "tactical_shift_events": len(of_type("Tactical Shift")),
        "substitution_events": len(substitutions),
        "substitutions_with_replacement_id": sum(
            _has(event, "substitution.replacement.id") for event in substitutions
        ),
        "substitution_outcomes": _ranked(
            Counter(_label(_get(event, "substitution.outcome.name")) for event in substitutions)
        ),
        "card_fields_in_events": [
            {"field_path": path, "values": _ranked(counts)}
            for path, counts in sorted(card_values.items())
        ],
        "period_boundary_events": [
            {
                "event_type": _type_name(event),
                "period": _label(_get(event, "period")),
                "team_id": _label(_get(event, "team.id")),
                "timestamp": _label(_get(event, "timestamp")),
                "minute": _label(_get(event, "minute")),
                "second": _label(_get(event, "second")),
            }
            for event in events
            if _type_name(event) in ("Half Start", "Half End")
        ],
    }


# --- consistency checks ---------------------------------------------------


def quality_findings(events, lineups, match):
    """Limited consistency checks. Nothing is corrected; everything is reported.

    Categories: `pass` (checked, nothing found), `error`, `warning`,
    `expected_absence` (structural, not a defect) and `unresolved`
    (observed, but its meaning needs documentation or more data).
    """
    findings = []

    def report(check, found_category, examples, checked, note):
        examples = sorted(str(example) for example in examples)
        findings.append(
            {
                "check": check,
                "category": found_category if examples else "pass",
                "count": len(examples),
                "checked": checked,
                "note": note,
                "examples": examples[:_MAX_EXAMPLES],
            }
        )

    def event_ref(event):
        return f"index {_label(_get(event, 'index'))} id {_label(_get(event, 'id'))}"

    # Identifiers.
    id_counts = Counter(event["id"] for event in events if _is_id(event.get("id")))
    report(
        "duplicate_event_ids", "error",
        [event_id for event_id, count in id_counts.items() if count > 1],
        len(id_counts), "Distinct ids that occur on more than one event.",
    )
    report(
        "events_without_usable_id", "error",
        [event_ref(event) for event in events if not _is_id(event.get("id"))],
        len(events), "Events whose id is missing, null, or not a string or integer.",
    )

    # Teams and players against the match record and the lineups file.
    match_teams = {
        _label(_get(match, "home_team.home_team_id")),
        _label(_get(match, "away_team.away_team_id")),
    }
    with_team = [event for event in events if _has(event, "team.id")]
    report(
        "event_team_not_in_match", "error",
        [event_ref(event) for event in with_team if _team_id(event) not in match_teams],
        len(with_team), "Event team id is neither the home nor the away team of the match record.",
    )
    lineup_players = _lineup_player_ids(lineups)
    with_player = [event for event in with_team if _has(event, "player.id")]
    report(
        "event_player_not_in_team_lineup", "warning",
        {
            f"team {_team_id(event)} player {_player_id(event)}"
            for event in with_player
            if _player_id(event) not in lineup_players.get(_team_id(event), set())
        },
        len(with_player), "Distinct (team, player) pairs in events that the team's lineup does not list.",
    )

    # Events without a player: structural when a whole type lacks one.
    player_presence = defaultdict(Counter)
    for event in events:
        player_presence[_type_name(event)][_has(event, "player.id")] += 1
    without_player = [event for event in events if not _has(event, "player.id")]
    report(
        "events_without_player_in_types_that_never_have_one", "expected_absence",
        [event_ref(event) for event in without_player if not player_presence[_type_name(event)][True]],
        len(events), "No event of these types carries a player, so the absence looks structural.",
    )
    report(
        "events_without_player_in_types_that_usually_have_one", "unresolved",
        [event_ref(event) for event in without_player if player_presence[_type_name(event)][True]],
        len(events), "Some events of the type carry a player and these do not.",
    )

    # Related events.
    by_id = _events_by_id(events)
    references = _references(events)
    report(
        "related_event_id_not_in_file", "warning",
        [f"{event_ref(event)} -> {target}" for event, target in references if target not in by_id],
        len(references), "References in related_events to an id no event in this file has.",
    )

    # Coordinate shapes.
    coordinates = [
        (event, path, value) for event in events for path, value in _coordinates(event)
    ]
    report(
        "unexpected_coordinate_shape", "warning",
        [
            f"{event_ref(event)} {path}"
            for event, path, value in coordinates
            if not _is_numeric_list(value)
            or len(value) not in (_PLAIN_COORDINATE_LENGTH, _EXTENDED_COORDINATE_LENGTH)
        ],
        len(coordinates), "Coordinate values that are not a list of two or three numbers.",
    )
    report(
        "three_component_coordinates", "unresolved",
        [
            f"{event_ref(event)} {path}"
            for event, path, value in coordinates
            if _is_numeric_list(value) and len(value) == _EXTENDED_COORDINATE_LENGTH
        ],
        len(coordinates), "Coordinates with a third number; its meaning needs provider documentation.",
    )

    # Order and time, judged inside each period: timestamps restart per period.
    periods = [event["period"] for event in events if isinstance(event.get("period"), int)]
    report(
        "period_decreases_in_file_order", "warning",
        [f"position {position}" for position, (before, after) in enumerate(zip(periods, periods[1:]), 1) if after < before],
        len(periods), "A later event in the file belongs to an earlier period.",
    )
    timestamp_drops, clock_drops, index_drops, unparsed, pairs = [], [], [], [], 0
    for _, group in _by_period(events):
        unparsed.extend(event_ref(event) for event in group if _seconds(event.get("timestamp")) is None)
        for before, after in zip(group, group[1:]):
            pairs += 1
            before_time, after_time = _seconds(before.get("timestamp")), _seconds(after.get("timestamp"))
            if before_time is not None and after_time is not None and after_time < before_time:
                timestamp_drops.append(event_ref(after))
            before_clock, after_clock = _clock(before), _clock(after)
            if before_clock is not None and after_clock is not None and after_clock < before_clock:
                clock_drops.append(event_ref(after))
            if _is_number(before.get("index")) and _is_number(after.get("index")) and after["index"] <= before["index"]:
                index_drops.append(event_ref(after))
    report(
        "timestamp_not_in_HH_MM_SS_mmm_form", "warning", unparsed, len(events),
        "Timestamps that are missing or have another form; they are left out of the time checks.",
    )
    report(
        "timestamp_decreases_within_period", "warning", timestamp_drops, pairs,
        "Consecutive events of one period where the timestamp goes backwards.",
    )
    report(
        "minute_second_decreases_within_period", "warning", clock_drops, pairs,
        "Consecutive events of one period where the minute and second pair goes backwards.",
    )
    report(
        "index_not_increasing_within_period", "warning", index_drops, pairs,
        "Consecutive events of one period where index does not increase.",
    )

    # Boolean fields that only ever say true.
    bool_values = defaultdict(set)
    for event in events:
        for path, value in _walk(event):
            if isinstance(value, bool):
                bool_values[path].add(value)
    report(
        "boolean_fields_only_ever_true", "unresolved",
        [path for path, seen in bool_values.items() if seen == {True}],
        len(bool_values),
        "These fields appear only with the value true. Whether absence means false "
        "or not recorded cannot be told from the file.",
    )
    report(
        "related_events_not_returned_by_target", "unresolved",
        [
            f"{event_ref(event)} -> {target}"
            for event, target in references
            if target in by_id and not _lists(by_id[target], event.get("id"))
        ],
        len(references), "A lists B in related_events but B does not list A.",
    )

    # Lineups.
    listed = [
        (_label(team.get("team_id", _ABSENT)), player)
        for team in lineups
        for player in _records(team.get("lineup"))
    ]
    report(
        "lineup_players_without_position_interval", "unresolved",
        [
            f"team {team_id} player {_label(player.get('player_id', _ABSENT))}"
            for team_id, player in listed
            if not _records(player.get("positions"))
        ],
        len(listed),
        "Listed players with no position interval. The file does not say why; "
        "do not assume every listed player took part.",
    )
    starters_by_event = {
        _team_id(event): {
            _label(_get(entry, "player.id")) for entry in _records(_get(event, "tactics.lineup"))
        }
        for event in events
        if _type_name(event) == "Starting XI"
    }
    starters_by_lineup = {
        team_id: {
            _label(player.get("player_id", _ABSENT))
            for listed_team, player in listed
            if listed_team == team_id
            and any(
                interval.get("start_reason") == "Starting XI"
                for interval in _records(player.get("positions"))
            )
        }
        for team_id in {team_id for team_id, _ in listed}
    }
    report(
        "starting_xi_event_differs_from_lineup_intervals", "warning",
        [
            f"team {team_id}"
            for team_id in set(starters_by_event) | set(starters_by_lineup)
            if starters_by_event.get(team_id) != starters_by_lineup.get(team_id)
        ],
        len(set(starters_by_event) | set(starters_by_lineup)),
        "Teams whose Starting XI event names different players than the lineup "
        "intervals that start with reason 'Starting XI'.",
    )
    return findings


def _clock(event):
    """The (minute, second) pair of an event, or None if either is not a number."""
    minute, second = event.get("minute"), event.get("second")
    return (minute, second) if _is_number(minute) and _is_number(second) else None
