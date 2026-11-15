"""Three-sixty frames for one ingested match: retrieval and an offline report.

A three-sixty file holds positional snapshots linked to events. It is
kept beside the match's event files, with its own companion manifest, so
the match manifest stays unchanged. The report counts what the file
contains; it scores nothing. See docs/three_sixty.md.
"""

import csv
import hashlib
import io
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from phaselens import statsbomb
from phaselens.fetch import fetch_bytes, url_exists
from phaselens.ingest import (
    RAW_ROOT,
    check_against_record,
    manifest_path,
    parse_json_array,
    publish,
    read_manifest,
    read_verified_files,
)

COMPANION_FORMAT_VERSION = 1
REPORT_FORMAT_VERSION = 1
REPORT_ROOT = "data/processed/three_sixty"
REPORT_FILES = ("summary.json", "coverage.csv")

# The linking field, as the format specification defines it: "the unique
# identifier for the event matching this freeze frame".
LINK_FIELD = "event_uuid"
DOCUMENTED_RECORD_KEYS = ("event_uuid", "visible_area", "freeze_frame")
DOCUMENTED_ENTRY_KEYS = ("location", "teammate", "actor", "keeper")
FLAGS = ("teammate", "actor", "keeper")

# Buckets for reporting actor-to-event location differences, in the
# source's own pitch-coordinate units. A display choice of this project,
# not a provider tolerance. Differences are not converted to metres.
DIFFERENCE_BUCKETS = (0.5, 1.0, 2.0, 5.0, 10.0)

_FILE_KEYS = ("source_path", "source_url", "local_path", "retrieved_at_utc", "sha256", "size_bytes")
_MISSING = "(missing)"
_MAX_EXAMPLES = 5
_ABSENT = object()


class ThreeSixtyError(Exception):
    """Retrieval or reporting stopped; nothing was published."""


def companion_path(project_root, commit_sha, match_id):
    return Path(project_root) / "manifests/statsbomb/open-data" / commit_sha / (
        f"match_{match_id}.three_sixty.json"
    )


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- retrieval ------------------------------------------------------------


def ingest_three_sixty(project_root, manifest_file, fetch=fetch_bytes, exists=url_exists):
    """Download a match's three-sixty file once, or verify the earlier download.

    Without a companion manifest: confirm the pinned path with a HEAD
    request, download, validate, publish the raw bytes, then write the
    companion manifest. With one: check that it still belongs to the
    verified event source, then verify the local file against it; nothing
    is requested unless the file is missing. Returns (status, companion).
    """
    project_root = Path(project_root)
    context = _event_source(project_root, manifest_file)
    path = companion_path(project_root, context["commit_sha"], context["match_id"])
    local = project_root / context["local_path"]

    if path.exists():
        companion = read_companion(path, context)
        record = companion["file"]
        if local.exists():
            check_against_record(local.read_bytes(), record, f"{local}: local file")
            return "reused", companion
        data = fetch(context["source_url"])
        check_against_record(data, record, f"{context['source_url']}: downloaded content")
        publish(local, data)
        return "restored", companion

    if local.exists():
        raise ThreeSixtyError(
            f"{local}: already exists but no companion manifest records it; refusing to "
            "overwrite or adopt it. Inspect it and move it away to download a fresh copy."
        )
    checked_at = _utc_now()
    if not exists(context["source_url"]):
        raise ThreeSixtyError(
            f"{context['source_url']}: HTTP 404 at the pinned commit, although the match "
            "manifest recorded the file as present"
        )
    data = fetch(context["source_url"])
    retrieved_at = _utc_now()
    parse_json_array(data, context["source_url"])

    companion = {
        "companion_format_version": COMPANION_FORMAT_VERSION,
        "kind": "three_sixty_frames",
        "source": {
            "name": "StatsBomb Open Data",
            "repository_url": statsbomb.REPOSITORY_URL,
            "commit_sha": context["commit_sha"],
        },
        "match_id": context["match_id"],
        "event_source": context["event_source"],
        "head_check": {"method": "HEAD", "result": "present", "checked_at_utc": checked_at},
        "file": {
            "source_path": context["source_path"],
            "source_url": context["source_url"],
            "local_path": context["local_path"],
            "retrieved_at_utc": retrieved_at,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
        },
    }
    publish(local, data)
    try:
        publish(path, _json_bytes(companion))
    except BaseException:
        # Without its companion manifest the raw file could not be verified.
        local.unlink(missing_ok=True)
        raise
    return "downloaded", companion


def read_companion(path, context):
    """Load a companion manifest and require that it belongs to `context`."""
    try:
        companion = json.loads(Path(path).read_bytes())
    except OSError as error:
        raise ThreeSixtyError(f"{path}: cannot read companion manifest ({error})") from error
    except ValueError as error:
        raise ThreeSixtyError(f"{path}: companion manifest is not valid JSON ({error})") from error
    if not isinstance(companion, dict):
        raise ThreeSixtyError(f"{path}: expected a JSON object")
    version = companion.get("companion_format_version")
    if version != COMPANION_FORMAT_VERSION:
        raise ThreeSixtyError(
            f"{path}: companion format version {version!r} is not supported; this program "
            f"reads version {COMPANION_FORMAT_VERSION}"
        )
    record = companion.get("file")
    if not (
        isinstance(record, dict)
        and all(key in record for key in _FILE_KEYS)
        and isinstance(record["sha256"], str)
        and _is_integer(record["size_bytes"])
    ):
        raise ThreeSixtyError(f"{path}: its file record is incomplete")
    expected = {
        "commit": context["commit_sha"],
        "match": context["match_id"],
        "path": (context["source_path"], context["source_url"], context["local_path"]),
    }
    found = {
        "commit": (companion.get("source") or {}).get("commit_sha"),
        "match": companion.get("match_id"),
        "path": (record["source_path"], record["source_url"], record["local_path"]),
    }
    if found != expected:
        raise ThreeSixtyError(f"{path}: records another commit, match or file location than expected")
    if companion.get("event_source") != context["event_source"]:
        raise ThreeSixtyError(
            f"{path}: is bound to another event source than the verified match manifest "
            "records; the frames cannot be linked to these events"
        )
    return companion


def _event_source(project_root, manifest_file):
    """The verified match manifest and the event file the frames link to."""
    manifest = read_manifest(manifest_file)
    commit_sha = manifest["source"]["commit_sha"]
    match_id = manifest["selection"]["match_id"]
    expected = manifest_path(project_root, commit_sha, match_id)
    if Path(manifest_file).resolve() != expected.resolve():
        raise ThreeSixtyError(f"{manifest_file}: a manifest for this match belongs at {expected}")
    files = read_verified_files(project_root, manifest)
    check = manifest["three_sixty_check"]
    source_path = statsbomb.three_sixty_path(match_id)
    source_url = statsbomb.source_url(commit_sha, source_path)
    if check.get("result") != "present" or check.get("source_url") != source_url:
        raise ThreeSixtyError(
            f"{manifest_file}: does not record a three-sixty file as present at {source_url}"
        )
    events_path = statsbomb.events_path(match_id)
    events_record = next(entry for entry in manifest["files"] if entry["source_path"] == events_path)
    return {
        "commit_sha": commit_sha,
        "match_id": match_id,
        "source_path": source_path,
        "source_url": source_url,
        "local_path": f"{RAW_ROOT}/{commit_sha}/{source_path}",
        "events_bytes": files[events_path],
        "event_source": {
            "match_manifest": expected.relative_to(project_root).as_posix(),
            "events_file": {key: events_record[key] for key in ("local_path", "sha256", "size_bytes")},
        },
    }


# --- report ---------------------------------------------------------------


def profile_three_sixty(project_root, manifest_file):
    """Verify the match's events and frames offline, then write the report.

    Never downloads: a missing or changed frames file is an error.
    """
    project_root = Path(project_root)
    context, path, companion, frames, events = verified_inputs(project_root, manifest_file)
    report = build_report(frames, events)
    summary = {
        "report_format_version": REPORT_FORMAT_VERSION,
        "inputs": {
            "commit_sha": context["commit_sha"],
            "match_id": context["match_id"],
            "companion_manifest": path.relative_to(project_root).as_posix(),
            "three_sixty_file": companion["file"],
            "events_file": context["event_source"]["events_file"],
        },
        **report["summary"],
    }
    directory = project_root / REPORT_ROOT / context["commit_sha"] / str(context["match_id"])
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "summary.json").write_bytes(_json_bytes(summary))
    (directory / "coverage.csv").write_bytes(_csv_bytes(report["coverage"]))
    return directory, summary


def verified_inputs(project_root, manifest_file):
    """Events and frames, both verified against their manifests, offline.

    Returns (context, companion path, companion, frames, events).
    """
    context = _event_source(project_root, manifest_file)
    path = companion_path(project_root, context["commit_sha"], context["match_id"])
    if not path.is_file():
        raise ThreeSixtyError(
            f"{path}: no companion manifest; `phaselens three-sixty-ingest --manifest` retrieves the file"
        )
    companion = read_companion(path, context)
    local = project_root / context["local_path"]
    if not local.is_file():
        raise ThreeSixtyError(
            f"{local}: recorded in the companion manifest but not on disk; "
            "`phaselens three-sixty-ingest --manifest` restores it"
        )
    data = local.read_bytes()
    check_against_record(data, companion["file"], f"{local}: local file")
    frames = parse_json_array(data, context["local_path"])
    events = parse_json_array(context["events_bytes"], context["event_source"]["events_file"]["local_path"])
    return context, path, companion, frames, events


def build_report(frames, events):
    """Linkage, coverage, structure and actor locations, from parsed inputs."""
    events_by_id = {}
    for event in events:
        if isinstance(event.get("id"), str):
            events_by_id.setdefault(event["id"], event)
    linkage, matched_ids = _linkage(frames, events, events_by_id)
    coverage = _coverage(events, matched_ids)
    return {
        "summary": {
            "link_field": LINK_FIELD,
            "linkage": linkage,
            "coverage_overall": coverage[0],
            "structure": _structure(frames),
            "identity": _identity(frames),
            "actor_location_comparison": _actor_comparison(frames, events_by_id),
        },
        "coverage": coverage,
    }


def _linkage(frames, events, events_by_id):
    keys = [frame.get(LINK_FIELD, _ABSENT) for frame in frames]
    usable = [key for key in keys if isinstance(key, str)]
    counts = Counter(usable)
    duplicated = sorted(key for key, count in counts.items() if count > 1)
    unmatched_records = [key for key in usable if key not in events_by_id]
    matched_ids = {key for key in counts if key in events_by_id}
    events_with_a_record = sum(event.get("id") in matched_ids for event in events)
    return {
        "records": len(frames),
        "records_with_usable_key": len(usable),
        "records_with_missing_key": sum(key is _ABSENT for key in keys),
        "records_with_null_key": sum(key is None for key in keys),
        "records_with_non_string_key": sum(
            key is not _ABSENT and key is not None and not isinstance(key, str) for key in keys
        ),
        "distinct_keys": len(counts),
        "duplicate_keys": len(duplicated),
        "records_sharing_a_duplicate_key": sum(counts[key] for key in duplicated),
        "duplicate_key_examples": duplicated[:_MAX_EXAMPLES],
        "unmatched_records": len(unmatched_records),
        "unmatched_key_examples": sorted(set(unmatched_records))[:_MAX_EXAMPLES],
        "distinct_matched_events": len(matched_ids),
        "events_in_file": len(events),
        "events_without_a_record": len(events) - events_with_a_record,
    }, matched_ids


def _coverage(events, matched_ids):
    """Rows of (grouping, value, events, events with a record, percent).

    Numerators count distinct events, so duplicate records cannot inflate
    them. Denominators are the events of the group in the events file.
    """
    groups = defaultdict(lambda: [0, 0])

    def add(grouping, value, event):
        cell = groups[(grouping, value)]
        cell[0] += 1
        cell[1] += event.get("id") in matched_ids

    for event in events:
        add("all events", "all", event)
        add("event type", _label(_get(event, "type.name")), event)
        add("team", _label(_get(event, "team.name")), event)
        add("period", _label(_get(event, "period")), event)
    order = {"all events": 0, "event type": 1, "team": 2, "period": 3}
    rows = []
    for (grouping, value), (total, covered) in sorted(
        groups.items(), key=lambda item: (order[item[0][0]], -item[1][0], str(item[0][1]))
    ):
        rows.append(
            {
                "grouping": grouping,
                "value": value,
                "events": total,
                "events_with_360_record": covered,
                "percent": round(100 * covered / total, 2) if total else 0.0,
            }
        )
    return rows


def _structure(frames):
    record_keys = Counter()
    entry_keys = Counter()
    frame_lengths = Counter()
    frame_shapes = Counter()
    flags = {flag: Counter() for flag in FLAGS}
    location_shapes = Counter()
    low, high = {}, {}
    visible = Counter()
    visible_lengths = Counter()
    entries = 0
    for frame in frames:
        record_keys.update(frame.keys())
        visible[_visible_area_shape(frame)] += 1
        area = frame.get("visible_area")
        if isinstance(area, list):
            visible_lengths[len(area)] += 1
        positions = frame.get("freeze_frame", _ABSENT)
        if positions is _ABSENT:
            frame_shapes["missing"] += 1
            continue
        if not isinstance(positions, list):
            frame_shapes["null" if positions is None else "not a list"] += 1
            continue
        frame_shapes["list"] += 1
        frame_lengths[len(positions)] += 1
        for entry in positions:
            if not isinstance(entry, dict):
                location_shapes["entry is not an object"] += 1
                continue
            entries += 1
            entry_keys.update(entry.keys())
            for flag in FLAGS:
                flags[flag][_flag_value(entry, flag)] += 1
            location = entry.get("location", _ABSENT)
            shape = _location_shape(location)
            location_shapes[shape] += 1
            if shape == "two numbers":
                for axis, value in zip("xy", location):
                    low[axis] = min(low.get(axis, value), value)
                    high[axis] = max(high.get(axis, value), value)
    return {
        "record_keys": _counts(record_keys),
        "freeze_frame": {
            "records_by_shape": _counts(frame_shapes),
            "entries": entries,
            "entries_per_record": _distribution(frame_lengths),
            "entry_keys": _counts(entry_keys),
            "flags": {flag: _counts(values) for flag, values in flags.items()},
            "location_shapes": _counts(location_shapes),
            "location_ranges": {axis: [low[axis], high[axis]] for axis in sorted(low)},
        },
        "visible_area": {
            # A structural check only: it does not show that the polygon is
            # valid, nor that the visible part covers the whole pitch.
            "records_by_shape": _counts(visible),
            "list_lengths": _distribution(visible_lengths),
        },
    }


def _identity(frames):
    """What the entries say about who a positioned player is.

    Actor and keeper are flags on a position; neither is a player id. Keys
    beyond the documented four are listed as unresolved candidates.
    """
    actors = Counter()
    keepers = Counter()
    keeper_teammate = Counter()
    other_entry_keys = Counter()
    other_record_keys = Counter()
    for frame in frames:
        other_record_keys.update(key for key in frame if key not in DOCUMENTED_RECORD_KEYS)
        positions = frame.get("freeze_frame")
        if not isinstance(positions, list):
            actors["no freeze_frame list"] += 1
            continue
        entries = [entry for entry in positions if isinstance(entry, dict)]
        actors[_how_many(sum(entry.get("actor") is True for entry in entries))] += 1
        keepers[_how_many(sum(entry.get("keeper") is True for entry in entries))] += 1
        for entry in entries:
            other_entry_keys.update(key for key in entry if key not in DOCUMENTED_ENTRY_KEYS)
            if entry.get("keeper") is True:
                keeper_teammate[_flag_value(entry, "teammate")] += 1
    return {
        "records_by_actor_entries": _counts(actors),
        "records_by_keeper_entries": _counts(keepers),
        "keeper_entries_by_teammate_flag": _counts(keeper_teammate),
        "undocumented_entry_keys": _counts(other_entry_keys),
        "undocumented_record_keys": _counts(other_record_keys),
    }


def _actor_comparison(frames, events_by_id):
    """Actor position against the linked event's location, record by record.

    Compared only for records linked to an event, with exactly one
    actor-marked entry, and a two-number location on both sides.
    """
    outcome = Counter()
    distances = []
    exact_by_type = defaultdict(lambda: [0, 0])
    for frame in frames:
        event = events_by_id.get(frame.get(LINK_FIELD)) if isinstance(frame.get(LINK_FIELD), str) else None
        if event is None:
            outcome["record not linked to an event"] += 1
            continue
        positions = frame.get("freeze_frame")
        actors = [e for e in positions if isinstance(e, dict) and e.get("actor") is True] if isinstance(positions, list) else []
        if not actors:
            outcome["no actor-marked entry"] += 1
            continue
        if len(actors) > 1:
            outcome["more than one actor-marked entry"] += 1
            continue
        actor_location = actors[0].get("location", _ABSENT)
        event_location = event.get("location", _ABSENT)
        if _location_shape(actor_location) != "two numbers":
            outcome["actor location missing or malformed"] += 1
            continue
        if event_location is _ABSENT:
            outcome["event has no location"] += 1
            continue
        if _location_shape(event_location) != "two numbers":
            outcome["event location malformed"] += 1
            continue
        outcome["compared"] += 1
        distance = math.hypot(actor_location[0] - event_location[0], actor_location[1] - event_location[1])
        distances.append(distance)
        cell = exact_by_type[_label(_get(event, "type.name"))]
        cell[0] += 1
        cell[1] += distance == 0
    distances.sort()
    return {
        "records_by_outcome": _counts(outcome),
        "compared": len(distances),
        "exact_matches": sum(distance == 0 for distance in distances),
        "distance_quantiles": _quantiles(distances),
        "distance_buckets": _buckets(distances),
        "by_event_type": [
            {"event_type": name, "compared": compared, "exact_matches": exact}
            for name, (compared, exact) in sorted(exact_by_type.items(), key=lambda item: (-item[1][0], str(item[0])))
        ],
        "units": "source pitch-coordinate units; not converted to metres",
    }


# --- spatial context (Milestone 8) ----------------------------------------

# Exploratory event-level indicators around a frame's actor. Contract in
# docs/metric_catalog.md, "Exploratory event-level indicators".
CONTEXT_DEFINITION_VERSION = 1
# Exploratory radii in source pitch-coordinate units, not metres and not
# a football standard. The boundary is inclusive: distance <= R.
CONTEXT_RADII = (5.0, 10.0, 20.0)
# The pitch frame drawn in the event specification. Diagnostic only:
# never used to filter, clamp or correct a coordinate.
FRAME_CONVENTION = {"x": (0.0, 120.0), "y": (0.0, 80.0)}
CONTEXT_FILES = ("spatial_context.csv", "spatial_context_summary.json")
CONTEXT_STATUSES = (
    "computed",
    "no_frame",
    "duplicate_frames",
    "freeze_frame_malformed",
    "actor_selection_ambiguous",
    "no_actor",
    "multiple_actors",
    "actor_location_invalid",
)


def validate_radii(radii):
    """Finite, positive, unique numbers, returned in ascending order."""
    try:
        values = list(radii)
    except TypeError as error:
        raise ThreeSixtyError(f"radii must be a sequence of numbers, not {radii!r}") from error
    if not values:
        raise ThreeSixtyError("at least one radius is required")
    for value in values:
        if not (_is_number(value) and math.isfinite(value) and value > 0):
            raise ThreeSixtyError(f"radius {value!r} is not a finite positive number")
    if len(set(values)) != len(values):
        raise ThreeSixtyError(f"radii {values} contain a repeated value")
    return tuple(sorted(float(value) for value in values))


def radius_label(radius):
    """5.0 -> '5u', 2.5 -> '2p5u'. 'u' stands for source coordinate units."""
    return f"{int(radius)}u" if radius.is_integer() else f"{radius}u".replace(".", "p")


def context_columns(radii=CONTEXT_RADII):
    columns = [
        "source_commit", "match_id", "event_id", "event_index", "period",
        "event_type_id", "event_type_name", "team_id", "player_id",
        "frame_available", "calculation_status", "visible_area_status", "visible_entries",
        "event_location_status", "event_x", "event_y",
        "actor_x", "actor_y", "actor_event_distance", "actor_outside_frame_convention",
        "entries_location_invalid", "entries_teammate_flag_invalid",
        "entries_excluded_from_context", "context_has_excluded_entries",
        "entries_outside_frame_convention", "visible_opponent_keeper_entries",
        "visible_teammates", "visible_opponents", "nearest_visible_opponent_distance",
    ]
    for radius in validate_radii(radii):
        label = radius_label(radius)
        columns += [f"visible_teammates_within_{label}", f"visible_opponents_within_{label}"]
    return columns


def build_spatial_context(frames, events, commit_sha, match_id, radii=CONTEXT_RADII):
    """One row per source event, plus the counts the summary reports.

    Rejects duplicate or unusable event ids rather than writing ambiguous
    rows. Frames link to events through `event_uuid`.
    """
    radii = validate_radii(radii)
    ids = Counter()
    for position, event in enumerate(events, 1):
        if not isinstance(event.get("id"), str):
            raise ThreeSixtyError(f"the event at position {position} has no usable id")
        ids[event["id"]] += 1
    repeated = sorted(event_id for event_id, count in ids.items() if count > 1)
    if repeated:
        raise ThreeSixtyError(
            f"{len(repeated)} source event id(s) occur more than once, e.g. {repeated[:3]}; "
            "rows would be ambiguous"
        )
    frames_by_event = defaultdict(list)
    unusable_keys = 0
    for frame in frames:
        key = frame.get(LINK_FIELD)
        if isinstance(key, str):
            frames_by_event[key].append(frame)
        else:
            unusable_keys += 1
    columns = context_columns(radii)
    rows = [
        _context_row(event, frames_by_event.get(event["id"], []), commit_sha, match_id, radii, columns)
        for event in events
    ]
    frame_counts = {
        "records": len(frames),
        "records_linked_to_an_event": sum(len(v) for k, v in frames_by_event.items() if k in ids),
        "records_not_linked_to_an_event": sum(len(v) for k, v in frames_by_event.items() if k not in ids),
        "records_with_unusable_key": unusable_keys,
    }
    return rows, columns, frame_counts


def _context_row(event, matched, commit_sha, match_id, radii, columns):
    row = dict.fromkeys(columns)
    row.update(
        source_commit=commit_sha,
        match_id=match_id,
        event_id=event["id"],
        event_index=_scalar(event.get("index", _ABSENT)),
        period=_scalar(_get(event, "period")),
        event_type_id=_scalar(_get(event, "type.id")),
        event_type_name=_scalar(_get(event, "type.name")),
        team_id=_scalar(_get(event, "team.id")),
        player_id=_scalar(_get(event, "player.id")),
        frame_available=bool(matched),
    )
    event_location = event.get("location", _ABSENT)
    event_point = event_location if _valid_point(event_location) else None
    row["event_location_status"] = (
        "missing" if event_location is _ABSENT else "valid" if event_point else "invalid"
    )
    if event_point:
        row["event_x"], row["event_y"] = event_point

    if not matched:
        row["calculation_status"] = "no_frame"
        return row
    if len(matched) > 1:
        row["calculation_status"] = "duplicate_frames"
        return row
    frame = matched[0]
    row["visible_area_status"] = _context_area_status(frame)
    positions = frame.get("freeze_frame", _ABSENT)
    if not isinstance(positions, list):
        row["calculation_status"] = "freeze_frame_malformed"
        return row
    row["visible_entries"] = len(positions)
    # The actor is known only if every entry says, as an exact boolean,
    # whether it is the actor. Otherwise a malformed entry could be it.
    if any(not isinstance(p, dict) or not isinstance(p.get("actor", _ABSENT), bool) for p in positions):
        row["calculation_status"] = "actor_selection_ambiguous"
        return row
    actors = [p for p in positions if p["actor"] is True]
    if not actors:
        row["calculation_status"] = "no_actor"
        return row
    if len(actors) > 1:
        row["calculation_status"] = "multiple_actors"
        return row
    actor = actors[0]
    actor_location = actor.get("location", _ABSENT)
    if not _valid_point(actor_location):
        row["calculation_status"] = "actor_location_invalid"
        return row

    ax, ay = actor_location
    row.update(actor_x=ax, actor_y=ay, actor_outside_frame_convention=_outside_frame(actor_location))
    if event_point:
        row["actor_event_distance"] = math.hypot(ax - event_point[0], ay - event_point[1])
    location_invalid = teammate_invalid = excluded = outside = opponent_keepers = 0
    teammates, opponents = [], []
    for entry in positions:
        if entry is actor:
            continue
        bad_location = not _valid_point(entry.get("location", _ABSENT))
        bad_flag = not isinstance(entry.get("teammate", _ABSENT), bool)
        location_invalid += bad_location
        teammate_invalid += bad_flag
        if bad_location or bad_flag:
            excluded += 1
            continue
        x, y = entry["location"]
        outside += _outside_frame(entry["location"])
        distance = math.hypot(x - ax, y - ay)
        if entry["teammate"] is True:
            teammates.append(distance)
        else:
            opponents.append(distance)
            opponent_keepers += entry.get("keeper") is True
    row.update(
        calculation_status="computed",
        entries_location_invalid=location_invalid,
        entries_teammate_flag_invalid=teammate_invalid,
        entries_excluded_from_context=excluded,
        context_has_excluded_entries=excluded > 0,
        entries_outside_frame_convention=outside,
        visible_opponent_keeper_entries=opponent_keepers,
        visible_teammates=len(teammates),
        visible_opponents=len(opponents),
        nearest_visible_opponent_distance=min(opponents) if opponents else None,
    )
    for radius in radii:
        label = radius_label(radius)
        row[f"visible_teammates_within_{label}"] = sum(d <= radius for d in teammates)
        row[f"visible_opponents_within_{label}"] = sum(d <= radius for d in opponents)
    return row


def context_summary(rows, frame_counts, radii=CONTEXT_RADII):
    """Status counts and diagnostic totals. Diagnostic totals may overlap."""
    radii = validate_radii(radii)
    computed = [row for row in rows if row["calculation_status"] == "computed"]
    statuses = Counter(row["calculation_status"] for row in rows)
    return {
        "context_definition_version": CONTEXT_DEFINITION_VERSION,
        "parameters": {
            "radii": list(radii),
            "radius_boundary": "inclusive: distance <= radius",
            "units": "source pitch-coordinate units; not asserted to be metres",
            "frame_convention": {axis: list(bounds) for axis, bounds in FRAME_CONVENTION.items()},
            "frame_convention_use": "diagnostic flag only; no coordinate is filtered, clamped or corrected",
        },
        "rows": len(rows),
        "rows_with_frame": sum(row["frame_available"] for row in rows),
        "calculation_status_counts": {status: statuses.get(status, 0) for status in CONTEXT_STATUSES},
        "frames": frame_counts,
        "event_location_status_counts": dict(sorted(Counter(row["event_location_status"] for row in rows).items())),
        "diagnostics_over_computed_rows": {
            "rows_with_excluded_entries": sum(row["context_has_excluded_entries"] for row in computed),
            "entries_excluded_from_context": sum(row["entries_excluded_from_context"] for row in computed),
            "entries_location_invalid": sum(row["entries_location_invalid"] for row in computed),
            "entries_teammate_flag_invalid": sum(row["entries_teammate_flag_invalid"] for row in computed),
            "note": "one entry can be both location-invalid and teammate-flag-invalid; "
                    "entries_excluded_from_context counts distinct excluded entries",
            "entries_outside_frame_convention": sum(row["entries_outside_frame_convention"] for row in computed),
            "rows_with_actor_outside_frame_convention": sum(row["actor_outside_frame_convention"] for row in computed),
            "rows_without_any_visible_opponent": sum(row["visible_opponents"] == 0 for row in computed),
        },
        "csv_serialization": {"null": "empty field", "boolean": "true or false", "float": "shortest round-trip decimal"},
    }


def write_spatial_context(project_root, manifest_file, radii=CONTEXT_RADII):
    """Verify events and frames offline, then write the context table and its summary."""
    project_root = Path(project_root)
    context, path, companion, frames, events = verified_inputs(project_root, manifest_file)
    rows, columns, frame_counts = build_spatial_context(
        frames, events, context["commit_sha"], context["match_id"], radii
    )
    summary = {
        "inputs": {
            "commit_sha": context["commit_sha"],
            "match_id": context["match_id"],
            "companion_manifest": path.relative_to(project_root).as_posix(),
            "three_sixty_file": companion["file"],
            "events_file": context["event_source"]["events_file"],
        },
        **context_summary(rows, frame_counts, radii),
        "columns": columns,
    }
    directory = project_root / REPORT_ROOT / context["commit_sha"] / str(context["match_id"])
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "spatial_context.csv").write_bytes(_context_csv_bytes(rows, columns))
    (directory / "spatial_context_summary.json").write_bytes(_json_bytes(summary))
    return directory, summary


def _valid_point(value):
    """Exactly two finite numbers. Booleans, strings, NaN and infinity are not."""
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(_is_number(v) and math.isfinite(v) for v in value)
    )


def _outside_frame(point):
    (x_low, x_high), (y_low, y_high) = FRAME_CONVENTION["x"], FRAME_CONVENTION["y"]
    return not (x_low <= point[0] <= x_high and y_low <= point[1] <= y_high)


def _context_area_status(frame):
    area = frame.get("visible_area", _ABSENT)
    if area is _ABSENT:
        return "missing"
    if isinstance(area, list) and not area:
        return "empty"
    if (
        isinstance(area, list)
        and len(area) >= 4
        and len(area) % 2 == 0
        and all(_is_number(v) and math.isfinite(v) for v in area)
        and area[:2] == area[-2:]
    ):
        return "closed_numeric"
    return "malformed"


def _scalar(value):
    """A plain value for an identity column, or None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (str, int)) or (isinstance(value, float) and math.isfinite(value)):
        return value
    return None


def context_csv_value(value):
    """A context value as written to spatial_context.csv: null is empty, booleans true/false."""
    if value is None:
        return ""
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, float):
        return repr(value)
    return str(value)


def _context_csv_bytes(rows, columns):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([context_csv_value(row[column]) for column in columns])
    return buffer.getvalue().encode("utf-8")


# --- small helpers --------------------------------------------------------


def _get(value, path):
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return _ABSENT
        value = value[key]
    return value


def _label(value):
    if value is _ABSENT or value is None:
        return _MISSING
    return value if isinstance(value, (str, int)) and not isinstance(value, bool) else f"({type(value).__name__})"


def _is_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _flag_value(entry, flag):
    value = entry.get(flag, _ABSENT)
    if value is _ABSENT:
        return "missing"
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "invalid"


def _location_shape(location):
    if location is _ABSENT:
        return "missing"
    if location is None:
        return "null"
    if not isinstance(location, list):
        return "not a list"
    if not all(_is_number(value) for value in location):
        return "non-numeric element"
    return "two numbers" if len(location) == 2 else f"{len(location)} numbers"


def _visible_area_shape(frame):
    area = frame.get("visible_area", _ABSENT)
    if area is _ABSENT:
        return "missing"
    if area is None:
        return "null"
    if not isinstance(area, list):
        return "not a list"
    if not area:
        return "empty list"
    if not all(_is_number(value) for value in area):
        return "non-numeric element"
    if len(area) % 2:
        return "odd number of values"
    if len(area) >= 4 and area[:2] == area[-2:]:
        return "even numeric, first point repeated at the end"
    return "even numeric, first point not repeated at the end"


def _how_many(count):
    return "zero" if count == 0 else "one" if count == 1 else "more than one"


def _counts(counter):
    return [{"value": value, "count": count} for value, count in sorted(counter.items(), key=lambda item: (-item[1], str(item[0])))]


def _distribution(counter):
    if not counter:
        return {"min": None, "max": None, "values": []}
    return {
        "min": min(counter),
        "max": max(counter),
        "values": [{"value": value, "count": count} for value, count in sorted(counter.items())],
    }


def _quantiles(values):
    if not values:
        return {}

    def at(fraction):  # nearest rank
        return round(values[max(0, math.ceil(fraction * len(values)) - 1)], 6)

    return {"min": round(values[0], 6), "p50": at(0.5), "p90": at(0.9), "p99": at(0.99), "max": round(values[-1], 6)}


def _buckets(values):
    edges = (0.0, *DIFFERENCE_BUCKETS)
    rows = [{"bucket": "exactly 0", "count": sum(value == 0 for value in values)}]
    for lower, upper in zip(edges, edges[1:]):
        rows.append({"bucket": f"over {lower} up to {upper}", "count": sum(lower < value <= upper for value in values)})
    rows.append({"bucket": f"over {edges[-1]}", "count": sum(value > edges[-1] for value in values)})
    return rows


def _json_bytes(value):
    return json.dumps(value, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"


def _csv_bytes(rows):
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=["grouping", "value", "events", "events_with_360_record", "percent"], lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")
