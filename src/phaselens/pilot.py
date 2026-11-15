"""A fixed set of matches run through the per-match pipeline, then combined.

A pilot definition file names the matches. Each match goes through the
same steps as a single match: ingest, profile, metrics, analytics. Only
when all of them succeed are their verified Parquet files joined into
one table. See docs/analytical_layer.md, "Five-match pilot".
"""

import json
import os
import re
import shutil
from collections import Counter
from pathlib import Path

import duckdb

from phaselens import analytics, metrics, statsbomb
from phaselens.analytics import AnalyticsError
from phaselens.fetch import FetchError, fetch_bytes, url_exists
from phaselens.ingest import IngestError, ingest_match, manifest_path
from phaselens.profile import profile_match

PILOT_FORMAT_VERSION = 1
COMBINED_METADATA_VERSION = 1
PILOTS_FOLDER = "pilots"
PILOT_KEYS = (
    "name",
    "definition_path",
    "source_commit",
    "competition_id",
    "season_id",
    "match_ids",
)

# Fixed queries for the combined table. Every one keeps matches apart.
PILOT_QUERIES = {
    "player-rows": "pilot_player_rows.sql",
    "team-totals": "pilot_team_totals.sql",
    "team-player-counts": "pilot_team_player_counts.sql",
    "integrity-checks": "pilot_integrity_checks.sql",
}

_NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
_RERUN = "Run `phaselens pilot --file` again to rebuild it."


class PilotError(Exception):
    """The pilot definition, a match, or the combined output failed a check."""


# --- definition -----------------------------------------------------------


def load_pilot(project_root, pilot_file):
    """Read and validate a pilot definition. Its name is the file name."""
    path = Path(pilot_file)
    try:
        relative = path.resolve().relative_to(Path(project_root).resolve()).as_posix()
    except ValueError as error:
        raise PilotError(f"{path}: a pilot definition must be inside the project") from error
    try:
        definition = json.loads(path.read_bytes())
    except OSError as error:
        raise PilotError(f"{path}: cannot read the pilot definition ({error})") from error
    except ValueError as error:
        raise PilotError(f"{path}: the pilot definition is not valid JSON ({error})") from error
    if not isinstance(definition, dict):
        raise PilotError(f"{path}: expected a JSON object")
    if definition.get("pilot_format_version") != PILOT_FORMAT_VERSION:
        raise PilotError(f"{path}: pilot_format_version must be {PILOT_FORMAT_VERSION}")
    if not _NAME.fullmatch(path.stem):
        raise PilotError(f"{path}: the file name may hold only lower-case letters, digits, '_' and '-'")
    if not statsbomb.is_commit_sha(definition.get("source_commit")):
        raise PilotError(f"{path}: source_commit must be a full 40-character commit SHA")
    for key in ("competition_id", "season_id"):
        if not _is_integer(definition.get(key)):
            raise PilotError(f"{path}: {key} must be an integer")
    match_ids = definition.get("match_ids")
    if not (isinstance(match_ids, list) and match_ids and all(_is_integer(m) for m in match_ids)):
        raise PilotError(f"{path}: match_ids must be a non-empty list of integers")
    repeated = sorted({match_id for match_id in match_ids if match_ids.count(match_id) > 1})
    if repeated:
        raise PilotError(f"{path}: match_ids lists {repeated} more than once")
    return {
        "name": path.stem,
        "definition_path": relative,
        "source_commit": definition["source_commit"],
        "competition_id": definition["competition_id"],
        "season_id": definition["season_id"],
        "match_ids": list(match_ids),
    }


def combined_relative_directory(pilot):
    return f"{analytics.ANALYTICS_ROOT}/{pilot['source_commit']}/{PILOTS_FOLDER}/{pilot['name']}"


# --- run ------------------------------------------------------------------


def run_pilot(project_root, pilot_file, fetch=fetch_bytes, exists=url_exists, report=None):
    """Run every match of the pilot in order, then build the combined output.

    Stops at the first match that fails: later matches are not touched and
    no combined output is built. `report` receives each match's result as
    soon as it is done. Returns (per-match results, combined metadata).
    """
    project_root = Path(project_root)
    pilot = load_pilot(project_root, pilot_file)
    results = []
    for match_id in pilot["match_ids"]:
        result = _run_match(project_root, pilot, match_id, fetch, exists)
        results.append(result)
        if report is not None:
            report(result)
    try:
        _, metadata = build_combined(project_root, pilot)
    except (PilotError, AnalyticsError) as error:
        raise _failure(project_root, pilot, "the combined output", "combine", error) from error
    return results, metadata


def _run_match(project_root, pilot, match_id, fetch, exists):
    """The four per-match steps, unchanged. A failure names the match and step."""
    stage = "ingest"
    try:
        ingested = ingest_match(
            project_root,
            pilot["source_commit"],
            pilot["competition_id"],
            pilot["season_id"],
            match_id,
            fetch=fetch,
            exists=exists,
        )
        stage = "profile"
        _, profile = profile_match(project_root, ingested.manifest_path)
        stage = "metrics"
        _, summary = metrics.compute_for_manifest(project_root, ingested.manifest_path)
        stage = "analytics"
        _, built = analytics.build(project_root, ingested.manifest_path)
    except (FetchError, IngestError, metrics.MetricError, AnalyticsError) as error:
        raise _failure(project_root, pilot, f"match {match_id}", stage, error) from error
    return {
        "match_id": match_id,
        "source_files": dict(sorted(Counter(ingested.file_statuses.values()).items())),
        "events_by_period": profile["summary"]["events"]["by_period"],
        "eligible_player_count": summary["eligible_player_count"],
        "metric_totals": summary["metric_totals"],
        "diagnostics_raised": {
            name: count for name, count in summary["diagnostic_totals"].items() if count
        },
        "row_count": built["row_count"],
    }


def _failure(project_root, pilot, where, stage, error):
    relative = combined_relative_directory(pilot)
    parts = [f"{where} failed at stage {stage}: {error}"]
    if stage != "combine":
        parts.append("Matches after it were not processed.")
    parts.append("No combined output was built in this run.")
    if (Path(project_root) / relative / analytics.METADATA_FILE).is_file():
        parts.append(
            f"An older combined output from an earlier run remains at {relative}/. It was "
            "not produced by this run. `phaselens pilot-query` checks it against the current "
            "per-match outputs before every use and refuses it if they no longer match."
        )
    return PilotError(" ".join(parts))


# --- combined output ------------------------------------------------------


def build_combined(project_root, pilot, output_root=None):
    """Join the verified per-match tables of a pilot into one Parquet file.

    Each match's published output is verified as a query would verify it,
    then read. Inputs are read under `project_root`; outputs go under
    `output_root`, the project root unless a test says otherwise. Files
    are published only after every check has passed.
    """
    project_root = Path(project_root)
    output_root = Path(output_root) if output_root is not None else project_root
    components, parts = [], []
    for match_id in pilot["match_ids"]:
        component, parquet = _verified_component(project_root, pilot, match_id)
        schema, rows = analytics.read_parquet(parquet)
        if schema != list(analytics.COLUMNS):
            raise PilotError(f"match {match_id}: its Parquet schema is not the documented one")
        components.append(component)
        parts.append(rows)
    rows = combine(components, parts, pilot["source_commit"])

    relative = combined_relative_directory(pilot)
    directory = output_root / relative
    building = directory.with_name(directory.name + ".building")
    parquet_name, metadata_name = analytics.PARQUET_FILE, analytics.METADATA_FILE
    shutil.rmtree(building, ignore_errors=True)
    try:
        building.mkdir(parents=True)
        analytics.write_parquet(rows, building / parquet_name)
        schema, stored = analytics.read_parquet(building / parquet_name)
        if schema != list(analytics.COLUMNS) or stored != rows:
            raise PilotError("the written combined Parquet file differs from the combined rows")
        checks = analytics.query_file(building / parquet_name, "integrity-checks", PILOT_QUERIES)[1]
        violations = [check for check in checks if check[1] != 0]
        if violations:
            raise PilotError(f"the combined Parquet file fails integrity checks: {violations}")
        artifact = analytics.artifact_record(building / parquet_name, f"{relative}/{parquet_name}")
        metadata = {
            "combined_metadata_version": COMBINED_METADATA_VERSION,
            "pilot": {key: pilot[key] for key in PILOT_KEYS},
            "analytical_schema_version": analytics.ANALYTICAL_SCHEMA_VERSION,
            "metric_contract_version": components[0]["metric_contract_version"],
            "table": analytics.TABLE,
            # Checksum of the combined file as checked above; not a signature.
            "combined_artifact": artifact,
            "columns": [{"name": name, "type": kind} for name, kind in analytics.COLUMNS],
            "composite_key": list(analytics.COMPOSITE_KEY),
            "row_count": len(rows),
            "metric_totals": analytics.totals_of(rows),
            "components": components,
            "duckdb_version": duckdb.__version__,
        }
        (building / metadata_name).write_bytes(_json_bytes(metadata))

        # The metadata file marks a complete result: it leaves first, arrives last.
        directory.mkdir(parents=True, exist_ok=True)
        (directory / metadata_name).unlink(missing_ok=True)
        os.replace(building / parquet_name, directory / parquet_name)
        if analytics.artifact_record(directory / parquet_name, artifact["path"]) != artifact:
            raise PilotError(
                f"{directory / parquet_name}: the published file differs from the file that "
                "was checked; no combined metadata was published"
            )
        os.replace(building / metadata_name, directory / metadata_name)
    finally:
        shutil.rmtree(building, ignore_errors=True)
    return directory, metadata


def combine(components, parts, commit_sha):
    """Join verified per-match rows into one sorted table, or raise on a conflict.

    Every row must carry the pilot's commit, its own match id and its match's
    contract version; all matches must share one contract version; no
    composite key may occur twice; each match's rows must reconcile with its
    build metadata, and the whole with the sum of the matches.
    """
    versions = sorted({component["metric_contract_version"] for component in components})
    if len(versions) != 1:
        raise PilotError(f"the matches were built under different metric contract versions {versions}")
    rows, seen = [], set()
    for component, part in zip(components, parts, strict=True):
        match_id = component["match_id"]
        for row in part:
            if row[0] != commit_sha:
                raise PilotError(
                    f"match {match_id}: a row carries source_commit {row[0]!r}, not the pilot's {commit_sha!r}"
                )
            if row[2] != match_id or row[1] != component["metric_contract_version"]:
                raise PilotError(
                    f"match {match_id}: a row carries match {row[2]} and contract version {row[1]}"
                )
            key = analytics.key_of(row)
            if key in seen:
                raise PilotError(f"duplicate composite key {key}")
            seen.add(key)
        if len(part) != component["row_count"] or analytics.totals_of(part) != component["metric_totals"]:
            raise PilotError(
                f"match {match_id}: its {len(part)} rows and totals {analytics.totals_of(part)} do not "
                f"reconcile with its build metadata ({component['row_count']} rows, "
                f"totals {component['metric_totals']})"
            )
        rows.extend(part)
    expected_totals = {
        name: sum(component["metric_totals"][name] for component in components)
        for name in metrics.METRIC_NAMES
    }
    if len(rows) != sum(c["row_count"] for c in components) or analytics.totals_of(rows) != expected_totals:
        raise PilotError("the combined rows do not reconcile with the sum of the matches")
    return sorted(rows, key=analytics.key_of)


def _verified_component(project_root, pilot, match_id):
    """Verify one match's published output; return its record and Parquet path."""
    manifest_file = manifest_path(project_root, pilot["source_commit"], match_id)
    if not manifest_file.is_file():
        raise PilotError(f"match {match_id}: no manifest at {manifest_file}. {_RERUN}")
    manifest, metadata, parquet = analytics.verify_published(project_root, manifest_file)
    selection = {
        "competition_id": pilot["competition_id"],
        "season_id": pilot["season_id"],
        "match_id": match_id,
    }
    if manifest["source"]["commit_sha"] != pilot["source_commit"] or manifest["selection"] != selection:
        raise PilotError(f"match {match_id}: its manifest records another commit or selection than the pilot")
    build_metadata = parquet.parent / analytics.METADATA_FILE
    component = {
        "match_id": match_id,
        "manifest": manifest_file.relative_to(project_root).as_posix(),
        "build_metadata": analytics.artifact_record(
            build_metadata, build_metadata.relative_to(project_root).as_posix()
        ),
        "parquet_artifact": metadata["parquet_artifact"],
        "metric_contract_version": metadata["metric_contract_version"],
        "row_count": metadata["row_count"],
        "metric_totals": metadata["metric_totals"],
    }
    return component, parquet


# --- queries --------------------------------------------------------------


def run_pilot_query(project_root, pilot_file, name):
    """Run one fixed pilot query on the combined output, after verifying it.

    Checks, in order: the combined metadata belongs to this exact pilot
    definition; every match's published output passes the same verification
    as a single-match query and is the one the combined output was built
    from; the combined Parquet file matches its recorded checksum.
    """
    project_root = Path(project_root)
    if name not in PILOT_QUERIES:
        raise PilotError(f"unknown pilot query {name!r}; choose one of {', '.join(PILOT_QUERIES)}")
    pilot = load_pilot(project_root, pilot_file)
    relative = combined_relative_directory(pilot)
    metadata_path = project_root / relative / analytics.METADATA_FILE
    if not metadata_path.is_file():
        raise PilotError(f"{relative}: no complete combined output. {_RERUN}")
    metadata = _checked_combined_metadata(metadata_path, pilot, relative)

    recorded = {component["match_id"]: component for component in metadata["components"]}
    for match_id in pilot["match_ids"]:
        component, _ = _verified_component(project_root, pilot, match_id)
        if component != recorded[match_id]:
            raise PilotError(
                f"match {match_id}: its published output is not the one the combined output "
                f"was built from. {_RERUN}"
            )

    artifact = metadata["combined_artifact"]
    parquet = project_root / relative / analytics.PARQUET_FILE
    if not parquet.is_file():
        raise PilotError(f"{parquet}: the combined Parquet file is missing. {_RERUN}")
    found = analytics.artifact_record(parquet, artifact["path"])
    if found != artifact:
        raise PilotError(
            f"{parquet}: does not match the checksum recorded when it was built "
            f"(recorded {artifact['size_bytes']} bytes, sha256 {artifact['sha256']}; found "
            f"{found['size_bytes']} bytes, sha256 {found['sha256']}). Nothing was changed. {_RERUN}"
        )
    return analytics.query_file(parquet, name, PILOT_QUERIES)


def _checked_combined_metadata(path, pilot, relative):
    metadata = analytics.json_object(path.read_bytes(), path.name)
    version = metadata.get("combined_metadata_version")
    if version != COMBINED_METADATA_VERSION:
        raise PilotError(
            f"{path}: combined metadata version {version!r} is not supported; this program "
            f"reads version {COMBINED_METADATA_VERSION}. {_RERUN}"
        )
    if metadata.get("pilot") != {key: pilot[key] for key in PILOT_KEYS}:
        raise PilotError(
            f"{path}: was built for another pilot definition; its commit, competition, season "
            f"or match set differs from {pilot['definition_path']}. {_RERUN}"
        )
    components = metadata.get("components")
    if not (
        isinstance(components, list)
        and all(isinstance(component, dict) for component in components)
        and [component.get("match_id") for component in components] == pilot["match_ids"]
    ):
        raise PilotError(f"{path}: its components are not the pilot's matches. {_RERUN}")
    artifact = metadata.get("combined_artifact")
    if not (
        isinstance(artifact, dict)
        and artifact.get("path") == f"{relative}/{analytics.PARQUET_FILE}"
        and isinstance(artifact.get("sha256"), str)
        and _is_integer(artifact.get("size_bytes"))
    ):
        raise PilotError(f"{path}: it has no usable combined_artifact record. {_RERUN}")
    return metadata


# --- small helpers --------------------------------------------------------


def _is_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _json_bytes(value):
    return json.dumps(value, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
