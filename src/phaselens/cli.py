"""Command line interface: discover, ingest, profile, count events, and query."""

import argparse
import sys
from collections import Counter
from pathlib import Path

from phaselens import analytics, metrics, statsbomb
from phaselens.fetch import FetchError, fetch_bytes, url_exists
from phaselens.ingest import (
    IngestError,
    ingest_match,
    manifest_path,
    parse_json_array,
    read_manifest,
)
from phaselens.profile import OUTPUT_FILES, profile_match


def main(argv=None):
    # Names in the source contain non-ASCII characters; never crash on a
    # console that cannot display one.
    sys.stdout.reconfigure(errors="replace")
    args = _build_parser().parse_args(argv)
    try:
        args.handler(args)
    except (FetchError, IngestError, metrics.MetricError, analytics.AnalyticsError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="phaselens",
        description="PhaseLens: ingest and profile StatsBomb Open Data matches.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commit_help = (
        "full upstream commit SHA to read from; "
        f"if omitted, the current head of {statsbomb.DEFAULT_REF} is resolved and printed"
    )

    competitions = commands.add_parser(
        "competitions", help="list available competition-seasons (saves nothing)"
    )
    competitions.add_argument("--commit", help=commit_help)
    competitions.set_defaults(handler=_list_competitions)

    matches = commands.add_parser(
        "matches", help="list the matches of one competition-season (saves nothing)"
    )
    matches.add_argument("--competition-id", type=int, required=True)
    matches.add_argument("--season-id", type=int, required=True)
    matches.add_argument("--commit", help=commit_help)
    matches.set_defaults(handler=_list_matches)

    ingest = commands.add_parser(
        "ingest", help="download one match, or verify a previous download"
    )
    ingest.add_argument("--manifest", help="repeat the ingestion recorded in this manifest")
    ingest.add_argument("--competition-id", type=int)
    ingest.add_argument("--season-id", type=int)
    ingest.add_argument("--match-id", type=int)
    ingest.add_argument("--commit", help=commit_help)
    ingest.set_defaults(handler=_ingest)

    profile = commands.add_parser(
        "profile", help="describe the contents of an ingested match (offline, read-only)"
    )
    profile.add_argument("--manifest", required=True, help="manifest of the match to profile")
    profile.set_defaults(handler=_profile)

    match_metrics = commands.add_parser(
        "metrics", help="count the catalogued event metrics for an ingested match (offline)"
    )
    match_metrics.add_argument("--manifest", required=True, help="manifest of the match")
    match_metrics.set_defaults(handler=_metrics)

    build = commands.add_parser(
        "analytics", help="build the typed Parquet copy of a match's metrics (offline)"
    )
    build.add_argument("--manifest", required=True, help="manifest of the match")
    build.set_defaults(handler=_analytics)

    query = commands.add_parser(
        "query", help="run one of the fixed SQL queries on a match's Parquet file (offline)"
    )
    query.add_argument("--manifest", required=True, help="manifest of the match")
    query.add_argument("--name", required=True, choices=sorted(analytics.QUERIES))
    query.set_defaults(handler=_query)
    return parser


def _pinned_commit(args):
    if args.commit:
        return args.commit
    commit_sha = statsbomb.resolve_commit(fetch_bytes)
    print(f"Resolved {statsbomb.DEFAULT_REF} to upstream commit {commit_sha}")
    return commit_sha


def _fetch_listing(commit_sha, source_path):
    if not statsbomb.is_commit_sha(commit_sha):
        raise IngestError(f"{commit_sha!r} is not a full 40-character commit SHA")
    url = statsbomb.source_url(commit_sha, source_path)
    return parse_json_array(fetch_bytes(url), url)


def _list_competitions(args):
    commit_sha = _pinned_commit(args)
    competitions = _fetch_listing(commit_sha, statsbomb.COMPETITIONS_PATH)
    competitions.sort(
        key=lambda entry: (str(entry.get("competition_name")), str(entry.get("season_name")))
    )
    print(f"{'competition_id':>14} {'season_id':>9}  competition_name / season_name")
    for entry in competitions:
        print(
            f"{entry.get('competition_id')!s:>14} {entry.get('season_id')!s:>9}  "
            f"{entry.get('competition_name')} / {entry.get('season_name')}"
        )
    print(f"{len(competitions)} competition-seasons at commit {commit_sha}")


def _list_matches(args):
    commit_sha = _pinned_commit(args)
    matches = _fetch_listing(
        commit_sha, statsbomb.matches_path(args.competition_id, args.season_id)
    )
    matches.sort(key=lambda entry: (str(entry.get("match_date")), str(entry.get("match_id"))))
    print(f"{'match_id':>9}  match_date  home_team_name v away_team_name")
    for entry in matches:
        home = (entry.get("home_team") or {}).get("home_team_name")
        away = (entry.get("away_team") or {}).get("away_team_name")
        print(f"{entry.get('match_id')!s:>9}  {entry.get('match_date')}  {home} v {away}")
    print(f"{len(matches)} matches at commit {commit_sha}")


def _project_root():
    project_root = Path.cwd()
    if not (project_root / "pyproject.toml").is_file():
        raise IngestError("run this command from the project root (no pyproject.toml here)")
    return project_root


def _profile(args):
    project_root = _project_root()
    directory, profile = profile_match(project_root, args.manifest)
    summary = profile["summary"]
    print(f"Upstream commit: {summary['inputs']['commit_sha']}")
    print(f"Verified against the manifest: {len(summary['inputs']['verified_files'])} files")
    events = summary["events"]
    print(
        f"Events: {events['event_count']} in {len(events['by_type'])} event types, "
        f"{len(events['by_period'])} periods"
    )
    categories = Counter(finding["category"] for finding in profile["findings"])
    print(
        "Checks: "
        + ", ".join(f"{count} {category}" for category, count in sorted(categories.items()))
    )
    for finding in profile["findings"]:
        if finding["category"] != "pass":
            print(f"  {finding['category']:<17} {finding['check']} ({finding['count']})")
    print(f"Written to {directory.relative_to(project_root).as_posix()}/")
    for name in OUTPUT_FILES:
        print(f"  {name}")


def _metrics(args):
    project_root = _project_root()
    directory, summary = metrics.compute_for_manifest(project_root, args.manifest)
    print(f"Upstream commit: {summary['source_commit']}")
    print(f"Verified against the manifest: {len(summary['verified_inputs'])} files")
    print(f"Metric contract version: {summary['metric_contract_version']}")
    print(f"Eligible players: {summary['eligible_player_count']} (counting unit: event)")
    for team in summary["teams"]:
        totals = ", ".join(f"{name} {team['metric_totals'][name]}" for name in metrics.METRIC_NAMES)
        print(
            f"  team {team['team_id']} {team['team_name']}: "
            f"{team['eligible_player_count']} players; {totals}"
        )
    raised = {name: count for name, count in summary["diagnostic_totals"].items() if count}
    print(f"Diagnostics raised: {len(raised)} of {len(summary['diagnostic_totals'])}")
    for name, count in raised.items():
        print(f"  {name} ({count})")
    print(f"Written to {directory.relative_to(project_root).as_posix()}/")
    for name in metrics.OUTPUT_FILES:
        print(f"  {name}")


def _analytics(args):
    project_root = _project_root()
    directory, metadata = analytics.build(project_root, args.manifest)
    print(f"Upstream commit: {metadata['source_commit']}")
    print(f"Verified against the manifest: {len(metadata['verified_raw_inputs'])} raw files")
    print(
        f"Metrics bundle checked: {len(metadata['consumed_metric_files'])} files, "
        f"contract version {metadata['metric_contract_version']}"
    )
    print(
        f"Parquet: {metadata['row_count']} rows, {len(metadata['columns'])} columns, "
        f"read back and compared with the CSV (DuckDB {metadata['duckdb_version']})"
    )
    print(f"Written to {directory.relative_to(project_root).as_posix()}/")
    for name in analytics.OUTPUT_FILES:
        print(f"  {name}")


def _query(args):
    columns, rows = analytics.run_query(_project_root(), args.manifest, args.name)
    table = [columns, *([str(value) for value in row] for row in rows)]
    widths = [max(len(line[position]) for line in table) for position in range(len(columns))]
    for line in table:
        print("  ".join(value.ljust(width) for value, width in zip(line, widths)).rstrip())
    print(f"({len(rows)} rows)")


def _ingest(args):
    project_root = _project_root()

    if args.manifest:
        others = (args.commit, args.competition_id, args.season_id, args.match_id)
        if any(value is not None for value in others):
            raise IngestError("--manifest cannot be combined with the other ingest options")
        manifest = read_manifest(args.manifest)
        commit_sha = manifest["source"]["commit_sha"]
        selection = manifest["selection"]
        expected = manifest_path(project_root, commit_sha, selection["match_id"])
        if Path(args.manifest).resolve() != expected.resolve():
            raise IngestError(f"{args.manifest}: a manifest for this match belongs at {expected}")
        competition_id, season_id, match_id = (
            selection["competition_id"],
            selection["season_id"],
            selection["match_id"],
        )
    else:
        competition_id, season_id, match_id = args.competition_id, args.season_id, args.match_id
        if competition_id is None or season_id is None or match_id is None:
            raise IngestError(
                "give --competition-id, --season-id and --match-id, or --manifest"
            )
        commit_sha = _pinned_commit(args)

    result = ingest_match(
        project_root, commit_sha, competition_id, season_id, match_id,
        fetch=fetch_bytes, exists=url_exists,
    )
    _print_result(project_root, result)


def _print_result(project_root, result):
    manifest = result.manifest
    match = manifest["match_metadata"]
    print(f"Upstream commit: {manifest['source']['commit_sha']}")
    print(
        f"Match {match['match_id']}: {match['home_team']['home_team_name']} v "
        f"{match['away_team']['away_team_name']}, {match['match_date']} "
        f"({match['competition']['competition_name']} {match['season']['season_name']})"
    )
    for entry in manifest["files"]:
        print(f"  {result.file_statuses[entry['local_path']]:<10} {entry['local_path']}")
        print(
            f"             sha256 {entry['sha256']}  {entry['size_bytes']} bytes  "
            f"retrieved {entry['retrieved_at_utc']}"
        )
    check = manifest["three_sixty_check"]
    print(
        f"Three-sixty file: {check['result']} "
        f"(checked {check['checked_at_utc']}, not downloaded)"
    )
    relative = result.manifest_path.relative_to(project_root).as_posix()
    print(f"Manifest: {relative} ({'written' if result.manifest_written else 'unchanged'})")
