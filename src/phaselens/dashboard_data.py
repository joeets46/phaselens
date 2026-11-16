"""Read-only data access for the local dashboard.

Imports only the standard library and existing PhaseLens modules, so the
pipeline never depends on the dashboard group. Every loader verifies its
inputs with the existing checks and never writes, ingests, or rebuilds.
"""

import csv
import io
from pathlib import Path

from phaselens import analytics, pilot, statsbomb, three_sixty
from phaselens.dashboard_i18n import DEFAULT_LANGUAGE, EVENT_TYPES, POSITIONS, TEXT, source_name, t
from phaselens.fetch import FetchError
from phaselens.ingest import (
    IngestError,
    manifest_path,
    parse_json_array,
    read_manifest,
    read_verified_files,
)
from phaselens.metrics import METRIC_NAMES, MetricError

# Short display names. The approved label of the third count states its
# supported-type scope.
METRIC_LABELS = {
    "pressure_event_count": "Pressure events",
    "counterpress_pressure_event_count": "Pressure events flagged as counterpress",
    "counterpress_flagged_event_count": "Counterpress-flagged events — supported types",
}

PILOT_FILE = "pilots/euro2024_knockout_stage.json"
FINAL_COMMIT = "4b73468fc5b0f1950f9f66fada70ad3a4f9327cb"
FINAL_MATCH_ID = 3943043
FINAL_MANIFEST = f"manifests/statsbomb/open-data/{FINAL_COMMIT}/match_{FINAL_MATCH_ID}.json"

# The failures the existing checks raise. Anything else is a programming
# error and is not caught here.
_CHECK_ERRORS = (
    analytics.AnalyticsError,
    pilot.PilotError,
    IngestError,
    MetricError,
    FetchError,
    three_sixty.ThreeSixtyError,
)


class DashboardDataError(Exception):
    """Data could not be loaded and verified; the message says what to run.

    `command` holds that command on its own, so the interface can show it
    in the selected language.
    """

    def __init__(self, message, command=None):
        super().__init__(message)
        self.command = command


# --- view 1: five-match overview ------------------------------------------


def load_overview(project_root, pilot_file=PILOT_FILE):
    """Pilot team totals and player-match rows, after the pilot query checks.

    Each query runs the full published-pilot verification: raw files,
    metrics files, per-match Parquet files, and the combined file.
    """
    project_root = Path(project_root)
    path = project_root / pilot_file
    try:
        definition = pilot.load_pilot(project_root, path)
        team_columns, team_rows = pilot.run_pilot_query(project_root, path, "team-totals")
        player_columns, player_rows = pilot.run_pilot_query(project_root, path, "player-rows")
        matches = [
            match_summary(project_root, manifest_path(project_root, definition["source_commit"], match_id))
            for match_id in definition["match_ids"]
        ]
    except _CHECK_ERRORS as error:
        command = f"uv run phaselens pilot --file {pilot_file}"
        raise DashboardDataError(
            f"{error}\n\nThe overview needs the verified five-match pilot output. "
            f"Run `{command}` and reload.",
            command=command,
        ) from error
    return {
        "source_commit": definition["source_commit"],
        "matches": matches,
        "team_totals": [dict(zip(team_columns, row)) for row in team_rows],
        "player_rows": [dict(zip(player_columns, row)) for row in player_rows],
    }


def match_summary(project_root, manifest_file):
    """Header facts for one match, from its verified match-list record.

    A field the record does not hold, or holds in an unexpected form, is
    None and is not shown; nothing is filled in.
    """
    manifest = read_manifest(manifest_file)
    files = read_verified_files(project_root, manifest)
    selection = manifest["selection"]
    source_path = statsbomb.matches_path(selection["competition_id"], selection["season_id"])
    record = next(
        (m for m in parse_json_array(files[source_path], source_path) if m.get("match_id") == selection["match_id"]),
        None,
    )
    if record is None:
        raise IngestError(f"{source_path}: no match with match_id {selection['match_id']}")

    def text(*path):
        value = record
        for key in path:
            value = value.get(key) if isinstance(value, dict) else None
        return value if isinstance(value, str) and value else None

    def number(key):
        value = record.get(key)
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None

    def team_id(side):
        value = (record.get(f"{side}_team") or {}).get(f"{side}_team_id")
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    summary = {
        "match_id": selection["match_id"],
        "competition": text("competition", "competition_name"),
        "season": text("season", "season_name"),
        "stage": text("competition_stage", "name"),
        "date": text("match_date"),
        "home_team": text("home_team", "home_team_name"),
        "away_team": text("away_team", "away_team_name"),
        "home_team_id": team_id("home"),
        "away_team_id": team_id("away"),
        "home_score": number("home_score"),
        "away_score": number("away_score"),
    }
    parts = [f"{summary['home_team']} v {summary['away_team']}", summary["stage"], summary["date"]]
    summary["label"] = " · ".join(part for part in parts if part)
    return summary


def comparison_rows(team_totals, summary):
    """Paired home/away values per metric for one match, with bar shares.

    A share is the team's count divided by the two teams' combined count
    for that metric, so the two bars of a row add up to the whole. When
    both counts are zero, or a team has no row, both shares are 0.
    """
    by_team = {
        row["team_id"]: row for row in team_totals if row.get("match_id") == summary["match_id"]
    }
    home, away = by_team.get(summary["home_team_id"]), by_team.get(summary["away_team_id"])
    rows = []
    for metric in METRIC_NAMES:
        home_value = home[metric] if home else None
        away_value = away[metric] if away else None
        total = (home_value or 0) + (away_value or 0)
        rows.append(
            {
                "metric": metric,
                "label": METRIC_LABELS[metric],
                "home": home_value,
                "away": away_value,
                "home_share": (home_value / total) if total and home_value is not None else 0.0,
                "away_share": (away_value / total) if total and away_value is not None else 0.0,
            }
        )
    return rows


# --- view 2: 360 explorer -------------------------------------------------


def explorer_matches(project_root, pilot_file=PILOT_FILE):
    """The pilot's matches whose three-sixty data verifies, in pilot order.

    A match is listed only when its companion manifest exists and its
    recorded file passes `three_sixty.verified_inputs` with at least one
    frame. A match without a companion manifest has no three-sixty data
    here and is left out. A match whose companion manifest exists but does
    not verify is left out too, and returned under "problems" with the
    command that restores it, so it is never hidden silently.
    """
    project_root = Path(project_root)
    try:
        definition = pilot.load_pilot(project_root, project_root / pilot_file)
    except _CHECK_ERRORS as error:
        command = f"uv run phaselens pilot --file {pilot_file}"
        raise DashboardDataError(
            f"{error}\n\nThe explorer lists the pilot's matches with three-sixty data. Run `{command}` and reload.",
            command=command,
        ) from error
    matches, problems = [], []
    for match_id in definition["match_ids"]:
        manifest_file = manifest_path(project_root, definition["source_commit"], match_id)
        relative = manifest_file.relative_to(project_root).as_posix()
        if not three_sixty.companion_path(project_root, definition["source_commit"], match_id).is_file():
            continue
        command = f"uv run phaselens three-sixty-ingest --manifest {relative}"
        try:
            _, _, _, frames, _ = three_sixty.verified_inputs(project_root, manifest_file)
            summary = match_summary(project_root, manifest_file)
        except _CHECK_ERRORS as error:
            problems.append({"match_id": match_id, "manifest": relative, "detail": str(error), "command": command})
            continue
        if not frames:
            problems.append({"match_id": match_id, "manifest": relative, "detail": "the three-sixty file holds no frame",
                             "command": command})
            continue
        matches.append({"match_id": match_id, "manifest": relative, "label": summary["label"], "frames": len(frames)})
    if not matches and not problems:
        first = manifest_path(project_root, definition["source_commit"], definition["match_ids"][0])
        command = f"uv run phaselens three-sixty-ingest --manifest {first.relative_to(project_root).as_posix()}"
        raise DashboardDataError(
            f"No match of {pilot_file} has three-sixty data. Run `{command}` and reload.", command=command)
    return {"source_commit": definition["source_commit"], "matches": matches, "problems": problems}


def load_explorer(project_root, manifest_file=FINAL_MANIFEST):
    """Verified events and frames, and the M8 context recomputed in memory.

    The displayed context values come from `build_spatial_context` on the
    verified inputs. The saved CSV is read only for an optional comparison.
    """
    project_root = Path(project_root)
    try:
        context, _, _, frames, events = three_sixty.verified_inputs(project_root, project_root / manifest_file)
        rows, columns, _ = three_sixty.build_spatial_context(
            frames, events, context["commit_sha"], context["match_id"]
        )
    except _CHECK_ERRORS as error:
        command = f"uv run phaselens three-sixty-ingest --manifest {manifest_file}"
        raise DashboardDataError(
            f"{error}\n\nThe explorer needs the final's verified events and three-sixty files. "
            f"Run `{command}` and reload.",
            command=command,
        ) from error
    frames_by_event = {}
    for frame in frames:
        key = frame.get(three_sixty.LINK_FIELD)
        if isinstance(key, str):
            frames_by_event.setdefault(key, []).append(frame)
    saved_path = (
        project_root / three_sixty.REPORT_ROOT / context["commit_sha"] / str(context["match_id"])
        / "spatial_context.csv"
    )
    try:
        summary = match_summary(project_root, project_root / manifest_file)
    except _CHECK_ERRORS as error:
        command = f"uv run phaselens ingest --manifest {manifest_file}"
        raise DashboardDataError(
            f"{error}\n\nThe final's match list could not be verified. Run `{command}` and reload.",
            command=command,
        ) from error
    return {
        "commit_sha": context["commit_sha"],
        "match_id": context["match_id"],
        "summary": summary,
        "events": events,
        "frames_by_event": frames_by_event,
        "context_by_event": {row["event_id"]: row for row in rows},
        "context_columns": columns,
        "radii": list(three_sixty.CONTEXT_RADII),
        "saved_csv": read_saved_context(saved_path, columns),
    }


def read_saved_context(path, columns):
    """The saved context CSV, for comparison only. Never raises.

    Returns {"status": ..., "rows": {event_id: row}, "duplicates": set, "detail": str}.
    """
    result = {"status": "ok", "rows": {}, "duplicates": set(), "detail": ""}
    if not Path(path).is_file():
        return {**result, "status": "absent", "detail": f"{path} does not exist"}
    try:
        text = Path(path).read_bytes().decode("utf-8")
        reader = csv.DictReader(io.StringIO(text, newline=""))
        if reader.fieldnames != columns:
            return {**result, "status": "unreadable", "detail": "its columns differ from the current definition"}
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                return {**result, "status": "unreadable", "detail": "a row has the wrong number of fields"}
            event_id = row["event_id"]
            if event_id in result["rows"]:
                result["duplicates"].add(event_id)
            result["rows"][event_id] = row
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        return {**result, "status": "unreadable", "detail": str(error)}
    return result


def compare_with_saved(row, saved):
    """How the saved CSV row of one event compares with the recomputed row.

    Returns (status, differing columns). The recomputed row is never changed.
    """
    if saved["status"] != "ok":
        return saved["status"], []
    event_id = row["event_id"]
    if event_id in saved["duplicates"]:
        return "duplicate rows in saved CSV", []
    if event_id not in saved["rows"]:
        return "event missing from saved CSV", []
    stored = saved["rows"][event_id]
    differing = [
        column for column in row if three_sixty.context_csv_value(row[column]) != stored[column]
    ]
    return ("matches saved CSV" if not differing else "differs from saved CSV"), differing


# --- filters and labels ---------------------------------------------------


def _name(value, key):
    return value.get(key) if isinstance(value, dict) else None


# Back-to-front display order of the position names recorded in
# `tactics.lineup`. A display convention only: it sorts the player list
# and makes no claim about a player's role. Unknown names sort last.
POSITION_LINES = (
    ("Goalkeeper",),
    ("Right Back", "Right Center Back", "Center Back", "Left Center Back", "Left Back",
     "Right Wing Back", "Left Wing Back"),
    ("Right Defensive Midfield", "Center Defensive Midfield", "Left Defensive Midfield",
     "Right Midfield", "Right Center Midfield", "Center Midfield", "Left Center Midfield", "Left Midfield",
     "Right Attacking Midfield", "Center Attacking Midfield", "Left Attacking Midfield"),
    ("Right Wing", "Left Wing", "Right Center Forward", "Center Forward", "Striker",
     "Left Center Forward", "Secondary Striker"),
)
_POSITION_RANK = {name: (line, rank) for line, names in enumerate(POSITION_LINES) for rank, name in enumerate(names)}
_UNRANKED = (len(POSITION_LINES), 0)


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def match_clock(event):
    """'MM:SS' from the event's `minute` and `second`; the timestamp if either is missing."""
    minute, second = event.get("minute"), event.get("second")
    if _integer(minute) and _integer(second):
        return f"{minute:02d}:{second:02d}"
    return str(event.get("timestamp"))


def half_text(period, language=DEFAULT_LANGUAGE):
    return t(f"half_{period}", language) if period in (1, 2) else t("period_n", language, period=period)


def squad(events):
    """What the events record about each player's place in the team.

    - position: the first `tactics.lineup` entry naming the player, in a
      Starting XI or Tactical Shift event, in source order;
    - starter: listed in a Starting XI lineup;
    - on / off: match clock of the Substitution events that bring the
      player on (`substitution.replacement`) or take them off (`player`).

    Values are shown as recorded; no playing time is calculated from them.
    """
    players = {}

    def entry(player, team_id):
        return players.setdefault(player["id"], {
            "id": player["id"], "name": player.get("name"), "team_id": team_id,
            "position": None, "starter": False, "on": [], "off": [],
        })

    for e in events:
        type_name = _name(e.get("type"), "name")
        team_id = _name(e.get("team"), "id")
        if type_name in ("Starting XI", "Tactical Shift"):
            lineup = _name(e.get("tactics"), "lineup")
            for item in lineup if isinstance(lineup, list) else []:
                if not isinstance(item, dict) or _name(item.get("player"), "id") is None:
                    continue
                info = entry(item["player"], team_id)
                if info["position"] is None:
                    info["position"] = _name(item.get("position"), "name")
                info["starter"] = info["starter"] or type_name == "Starting XI"
        elif type_name == "Substitution":
            replacement = _name(e.get("substitution"), "replacement")
            if _name(e.get("player"), "id") is not None:
                entry(e["player"], team_id)["off"].append(match_clock(e))
            if _name(replacement, "id") is not None:
                entry(replacement, team_id)["on"].append(match_clock(e))
    for e in events:
        if _name(e.get("player"), "id") is not None:
            entry(e["player"], _name(e.get("team"), "id"))
    return players


def _player_order(players, team_names):
    def key(player_id):
        info = players.get(player_id) or {}
        line, rank = _POSITION_RANK.get(info.get("position"), _UNRANKED)
        return (str(team_names.get(info.get("team_id"))), line, rank, str(info.get("name")), str(player_id))
    return key


def filter_options(events, type_name=None, team_id=None):
    """Choices for the event filters, built from the events themselves.

    Players are limited to those with an event matching the chosen type
    and team, ordered by team, then from goalkeeper to attack.
    """
    types = sorted({_name(e.get("type"), "name") for e in events} - {None})
    teams = sorted({(_name(e.get("team"), "id"), _name(e.get("team"), "name")) for e in events if isinstance(e.get("team"), dict)},
                   key=lambda team: (str(team[1]), str(team[0])))
    players = squad(events)
    scoped = {_name(e.get("player"), "id") for e in filter_events(events, type_name, team_id)} - {None}
    ordered = sorted(scoped, key=_player_order(players, dict(teams)))
    return {"types": types, "teams": teams, "players": [(pid, players[pid]["name"]) for pid in ordered]}


def player_label(info, language=DEFAULT_LANGUAGE):
    """Name, position, and when the player started, came on, or went off, as recorded."""
    position = info.get("position")
    parts = [str(info.get("name")),
             source_name(POSITIONS, position, language) if position else t("no_position", language)]
    if info.get("starter"):
        parts.append(t("started", language))
    parts += [t("sub_on", language, time=time) for time in info.get("on", [])]
    parts += [t("sub_off", language, time=time) for time in info.get("off", [])]
    return " · ".join(parts)


def filter_events(events, type_name=None, team_id=None, player_id=None):
    """Events matching every filter that is set, in source order."""
    return [
        e for e in events
        if (type_name is None or _name(e.get("type"), "name") == type_name)
        and (team_id is None or _name(e.get("team"), "id") == team_id)
        and (player_id is None or _name(e.get("player"), "id") == player_id)
    ]


def event_label(event, language=DEFAULT_LANGUAGE):
    return t(
        "event_label",
        language,
        time=match_clock(event),
        half=half_text(event.get("period"), language),
        type=source_name(EVENT_TYPES, _name(event.get("type"), "name"), language),
        player=_name(event.get("player"), "name") or t("no_player", language),
    )


def status_text(status, language=DEFAULT_LANGUAGE):
    """A calculation status in words; an unknown status is shown as recorded."""
    return t(f"status_{status}", language) if f"status_{status}" in TEXT else str(status)


def notices(row, frames, language=DEFAULT_LANGUAGE):
    """Short contextual notices for one event. Neutral wording; nothing is called an error."""
    found = []
    status = row["calculation_status"]
    if status == "no_frame":
        found.append(("info", t("notice_no_frame", language)))
    elif status != "computed":
        shown = f"{status_text(status, language)} ({status})"
        found.append(("warning", t("notice_not_computed", language, status=shown)))
    if row.get("context_has_excluded_entries"):
        found.append(("warning", t("notice_excluded", language, count=row["entries_excluded_from_context"])))
    outside = (row.get("entries_outside_frame_convention") or 0) + bool(row.get("actor_outside_frame_convention"))
    if outside:
        found.append(("info", t("notice_outside", language, count=outside)))
    if row.get("actor_event_distance") is not None:
        found.append(("info", t("notice_distance", language,
                                distance=format_distance(row["actor_event_distance"], language))))
    if len(frames) > 1:
        found.append(("warning", t("notice_duplicates", language, count=len(frames))))
    return found


# --- display formatting ---------------------------------------------------
# Presentation only: values are formatted as text for the screen. The
# numbers in memory, the calculations and the saved outputs keep full
# precision.

NULL_TEXT = TEXT["null"][DEFAULT_LANGUAGE]
DISTANCE_COLUMNS = frozenset({"actor_event_distance", "nearest_visible_opponent_distance"})
COORDINATE_COLUMNS = frozenset({"event_x", "event_y", "actor_x", "actor_y"})


def format_distance(value, language=DEFAULT_LANGUAGE):
    """Three decimals; a distance above 0 but below 0.001 shows as '<0.001'."""
    if value is None:
        return t("null", language)
    if 0 < value < 0.001:
        return "<0.001"
    return f"{value:.3f}"


def format_value(column, value, language=DEFAULT_LANGUAGE):
    """Text for one context value: null, booleans, integers, three-decimal floats."""
    if value is None:
        return t("null", language)
    if isinstance(value, bool):
        return t("true" if value else "false", language)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if column in DISTANCE_COLUMNS:
            return format_distance(value, language)
        if column in COORDINATE_COLUMNS or not value.is_integer():
            return f"{value:.3f}"
        return str(int(value))
    return str(value)
