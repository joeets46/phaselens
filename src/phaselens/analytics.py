"""A typed Parquet copy of the player-match metrics, queried with DuckDB.

This layer changes no metric value. It validates the metrics output
bundle, writes its rows to Parquet with explicit types, and reads the
file back to confirm every row survived unchanged. See
docs/analytical_layer.md.
"""

import csv
import hashlib
import io
import json
import os
import re
import shutil
from contextlib import contextmanager
from importlib import resources
from pathlib import Path

import duckdb

from phaselens import metrics
from phaselens.ingest import read_manifest, read_verified_files

ANALYTICAL_SCHEMA_VERSION = 1
# Version of build_metadata.json itself. Version 2 added the checksum of
# the Parquet file; metadata without a version predates it.
BUILD_METADATA_VERSION = 2
ANALYTICS_ROOT = "data/processed/analytics"
PARQUET_FILE = "player_match_metrics.parquet"
METADATA_FILE = "build_metadata.json"
OUTPUT_FILES = (PARQUET_FILE, METADATA_FILE)
TABLE = "player_match_metrics"
PARQUET_COMPRESSION = "snappy"

# Every column and its DuckDB type. No type is inferred from the CSV.
COLUMNS = (
    ("source_commit", "VARCHAR"),
    ("metric_contract_version", "BIGINT"),
    ("match_id", "BIGINT"),
    ("team_id", "BIGINT"),
    ("team_name", "VARCHAR"),
    ("player_id", "BIGINT"),
    ("player_name", "VARCHAR"),
    *((name, "BIGINT") for name in metrics.METRIC_NAMES),
)
COMPOSITE_KEY = ("source_commit", "metric_contract_version", "match_id", "team_id", "player_id")
CSV_COLUMNS = (
    "source_commit",
    "match_id",
    "team_id",
    "team_name",
    "player_id",
    "player_name",
    *metrics.METRIC_NAMES,
)

# Fixed queries, each a SQL file shipped with the package. Nothing else
# can be run through this module.
QUERIES = {
    "player-rows": "player_rows.sql",
    "team-totals": "team_totals.sql",
    "team-player-counts": "team_player_counts.sql",
    "integrity-checks": "integrity_checks.sql",
}

# Integers are accepted in one spelling only: decimal digits, no sign, no
# leading zeros, no spaces. "007" is rejected, not read as 7.
_CANONICAL_INTEGER = re.compile(r"0|[1-9][0-9]*")


class AnalyticsError(Exception):
    """The inputs or the built file failed a check; nothing was published."""


# --- build ----------------------------------------------------------------


def build(project_root, manifest_file, output_root=None):
    """Validate the metrics bundle of a match and publish its Parquet copy.

    Inputs are read under `project_root`. Outputs go under `output_root`,
    which is the project root unless a test says otherwise. Files are
    built in a temporary folder and moved into place only after every
    check has passed.
    """
    project_root = Path(project_root)
    output_root = Path(output_root) if output_root is not None else project_root
    bundle = load_bundle(project_root, manifest_file)
    relative_directory = f"{ANALYTICS_ROOT}/{bundle['source_commit']}/{bundle['match_id']}"
    directory = output_root / relative_directory
    building = directory.with_name(directory.name + ".building")

    shutil.rmtree(building, ignore_errors=True)
    try:
        building.mkdir(parents=True)
        write_parquet(bundle["rows"], building / PARQUET_FILE)
        _check_written_file(building / PARQUET_FILE, bundle["rows"])
        artifact = artifact_record(
            building / PARQUET_FILE, f"{relative_directory}/{PARQUET_FILE}"
        )
        metadata = {
            "build_metadata_version": BUILD_METADATA_VERSION,
            "analytical_schema_version": ANALYTICAL_SCHEMA_VERSION,
            "metric_contract_version": bundle["metric_contract_version"],
            "source_commit": bundle["source_commit"],
            "match_id": bundle["match_id"],
            "table": TABLE,
            # Checksum of the file as checked above. A query verifies the
            # published file against it. It records what was built; it is
            # not a signature.
            "parquet_artifact": artifact,
            "parquet_compression": PARQUET_COMPRESSION,
            "columns": [{"name": name, "type": kind} for name, kind in COLUMNS],
            "composite_key": list(COMPOSITE_KEY),
            "row_count": len(bundle["rows"]),
            "metric_totals": totals_of(bundle["rows"]),
            "consumed_metric_files": bundle["consumed_metric_files"],
            "verified_raw_inputs": bundle["verified_raw_inputs"],
            "duckdb_version": duckdb.__version__,
        }
        (building / METADATA_FILE).write_bytes(_json_bytes(metadata))

        # The metadata file marks a complete result, so it leaves first and
        # arrives last.
        directory.mkdir(parents=True, exist_ok=True)
        (directory / METADATA_FILE).unlink(missing_ok=True)
        os.replace(building / PARQUET_FILE, directory / PARQUET_FILE)
        if artifact_record(directory / PARQUET_FILE, artifact["path"]) != artifact:
            raise AnalyticsError(
                f"{directory / PARQUET_FILE}: the published file differs from the file "
                "that was checked; no build metadata was published"
            )
        os.replace(building / METADATA_FILE, directory / METADATA_FILE)
    finally:
        shutil.rmtree(building, ignore_errors=True)
    return directory, metadata


def artifact_record(path, relative_path):
    """Path, SHA-256 and size of a file, as stored in the build metadata."""
    data = Path(path).read_bytes()
    return {
        "path": relative_path,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
    }


def load_bundle(project_root, manifest_file):
    """Read and validate the metrics bundle the manifest's match points to.

    What this establishes, and what it does not, is set out in
    docs/analytical_layer.md under "Verification".
    """
    project_root = Path(project_root)
    manifest = read_manifest(manifest_file)
    commit_sha = manifest["source"]["commit_sha"]
    match_id = manifest["selection"]["match_id"]

    # The raw inputs are checked against the manifest first.
    read_verified_files(project_root, manifest)
    raw_inputs = [
        {key: entry[key] for key in ("local_path", "sha256", "size_bytes")}
        for entry in manifest["files"]
    ]

    relative = f"{metrics.METRICS_ROOT}/{commit_sha}/{match_id}"
    contents, consumed = {}, []
    for name in metrics.OUTPUT_FILES:
        path = project_root / relative / name
        if not path.is_file():
            raise AnalyticsError(
                f"{path}: metrics output not found; `phaselens metrics --manifest` writes it"
            )
        contents[name] = path.read_bytes()
        consumed.append(
            {
                "path": f"{relative}/{name}",
                "sha256": hashlib.sha256(contents[name]).hexdigest(),
                "size_bytes": len(contents[name]),
            }
        )

    summary = json_object(contents["run_summary.json"], "run_summary.json")
    diagnostics = json_object(contents["diagnostics.json"], "diagnostics.json")
    contract_version = summary.get("metric_contract_version")
    if not _is_integer(contract_version) or contract_version < 1:
        raise AnalyticsError("run_summary.json: metric_contract_version is not a positive integer")
    for name, document in (("run_summary.json", summary), ("diagnostics.json", diagnostics)):
        found = (
            document.get("metric_contract_version"),
            document.get("source_commit"),
            document.get("match_id"),
        )
        if found != (contract_version, commit_sha, match_id):
            raise AnalyticsError(
                f"{name}: describes contract version, commit and match {found}, but the "
                f"manifest and summary give {(contract_version, commit_sha, match_id)}"
            )
    if summary.get("verified_inputs") != raw_inputs:
        raise AnalyticsError(
            "run_summary.json: the source hashes it records are not those of the "
            "manifest's raw inputs; the metrics were computed from other files"
        )
    recorded = {
        item.get("name"): item.get("count")
        for item in diagnostics.get("diagnostics", [])
        if isinstance(item, dict)
    }
    if recorded != summary.get("diagnostic_totals"):
        raise AnalyticsError("diagnostics.json and run_summary.json disagree on diagnostic counts")

    rows = validate_rows(contents["player_match_metrics.csv"], commit_sha, match_id, contract_version)
    reconcile(rows, summary)
    return {
        "source_commit": commit_sha,
        "match_id": match_id,
        "metric_contract_version": contract_version,
        "rows": rows,
        "consumed_metric_files": consumed,
        "verified_raw_inputs": raw_inputs,
    }


def validate_rows(csv_bytes, commit_sha, match_id, contract_version):
    """Turn the metrics CSV into typed rows, or raise on the first defect.

    Returns tuples in COLUMNS order, sorted by the composite key. Nothing
    is corrected: a value that is not acceptable as written is an error.
    """
    try:
        text = csv_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise AnalyticsError(f"metrics CSV: not valid UTF-8 ({error})") from error
    reader = csv.reader(io.StringIO(text, newline=""))
    header = next(reader, None)
    if header != list(CSV_COLUMNS):
        raise AnalyticsError(
            f"metrics CSV: columns are {header}, expected exactly {list(CSV_COLUMNS)}"
        )
    rows, seen = [], set()
    for line, values in enumerate(reader, 2):
        where = f"metrics CSV line {line}"
        if len(values) != len(CSV_COLUMNS):
            raise AnalyticsError(f"{where}: has {len(values)} fields, expected {len(CSV_COLUMNS)}")
        record = dict(zip(CSV_COLUMNS, values))
        if record["source_commit"] != commit_sha:
            raise AnalyticsError(
                f"{where}: source_commit is {record['source_commit']!r}, expected {commit_sha!r}"
            )
        row_match_id = _integer(record["match_id"], f"{where}: match_id")
        if row_match_id != match_id:
            raise AnalyticsError(f"{where}: match_id is {row_match_id}, expected {match_id}")
        team_id = _integer(record["team_id"], f"{where}: team_id")
        player_id = _integer(record["player_id"], f"{where}: player_id")
        pressure, counterpress_pressure, flagged = (
            _integer(record[name], f"{where}: {name}") for name in metrics.METRIC_NAMES
        )
        if not (counterpress_pressure <= pressure and counterpress_pressure <= flagged):
            raise AnalyticsError(
                f"{where}: metric inequalities are violated "
                f"({pressure}, {counterpress_pressure}, {flagged})"
            )
        key = (team_id, player_id)
        if key in seen:
            raise AnalyticsError(
                f"{where}: duplicate composite key for team {team_id}, player {player_id}"
            )
        seen.add(key)
        rows.append(
            (
                commit_sha,
                contract_version,
                match_id,
                team_id,
                record["team_name"],
                player_id,
                record["player_name"],
                pressure,
                counterpress_pressure,
                flagged,
            )
        )
    if not rows:
        raise AnalyticsError("metrics CSV: has no rows")
    return sorted(rows, key=key_of)


def reconcile(rows, summary):
    """Check the CSV's row count and totals against the run summary."""
    if summary.get("eligible_player_count") != len(rows):
        raise AnalyticsError(
            f"run_summary.json records {summary.get('eligible_player_count')} eligible "
            f"players but the CSV has {len(rows)} rows"
        )
    if summary.get("metric_totals") != totals_of(rows):
        raise AnalyticsError(
            f"run_summary.json records totals {summary.get('metric_totals')} but the CSV "
            f"adds up to {totals_of(rows)}"
        )
    by_team = {}
    for row in rows:
        by_team.setdefault(row[_position("team_id")], []).append(row)
    expected_teams = [
        {
            "team_id": team_id,
            "eligible_player_count": len(team_rows),
            "metric_totals": totals_of(team_rows),
        }
        for team_id, team_rows in sorted(by_team.items())
    ]
    recorded_teams = [
        {key: team.get(key) for key in ("team_id", "eligible_player_count", "metric_totals")}
        for team in summary.get("teams", [])
        if isinstance(team, dict)
    ]
    if recorded_teams != expected_teams:
        raise AnalyticsError("run_summary.json and the CSV disagree on per-team counts or totals")


def write_parquet(rows, path):
    """Write typed rows to one Parquet file, sorted by the composite key."""
    definitions = ", ".join(f"{name} {kind} NOT NULL" for name, kind in COLUMNS)
    placeholders = ", ".join("?" for _ in COLUMNS)
    with _duckdb_errors(path, "write", hint=""), duckdb.connect(":memory:") as connection:
        connection.execute("SET threads = 1")
        connection.execute(f"CREATE TABLE {TABLE} ({definitions})")
        connection.executemany(f"INSERT INTO {TABLE} VALUES ({placeholders})", rows)
        ordered = connection.sql(f"SELECT * FROM {TABLE} ORDER BY {', '.join(COMPOSITE_KEY)}")
        ordered.write_parquet(str(path), compression=PARQUET_COMPRESSION)


def read_parquet(path):
    """Return ([(column, type)], rows) as stored in a Parquet file, in file order."""
    with _duckdb_errors(path, "read"), duckdb.connect(":memory:") as connection:
        relation = connection.read_parquet(str(path))
        schema = list(zip(relation.columns, (str(kind) for kind in relation.types)))
        return schema, relation.fetchall()


_REBUILD = "Rebuild it with `phaselens analytics --manifest`."


@contextmanager
def _duckdb_errors(path, action, hint=_REBUILD):
    """Report a DuckDB failure on `path` as an AnalyticsError.

    Only DuckDB's own exceptions are translated. Anything else is a
    programming error and is left to surface as it is.
    """
    try:
        yield
    except duckdb.Error as error:
        detail = (str(error).strip().splitlines() or ["no detail given"])[0]
        raise AnalyticsError(
            f"{path}: DuckDB could not {action} this file "
            f"({type(error).__name__}: {detail}) {hint}".rstrip()
        ) from error


def _check_written_file(path, rows):
    """Read the new file back: schema, order and every value must match."""
    schema, stored = read_parquet(path)
    if schema != list(COLUMNS):
        raise AnalyticsError(f"the written Parquet schema is {schema}, expected {list(COLUMNS)}")
    if stored != rows:
        raise AnalyticsError("the written Parquet rows differ from the validated CSV rows")
    violations = [row for row in query_file(path, "integrity-checks")[1] if row[1] != 0]
    if violations:
        raise AnalyticsError(f"the written Parquet file fails integrity checks: {violations}")


# --- queries --------------------------------------------------------------


def run_query(project_root, manifest_file, name):
    """Run one of the fixed queries against a match's published Parquet file.

    Returns (column names, rows). The file is read only after
    `verify_published` has passed. A query never rebuilds or replaces anything.
    """
    if name not in QUERIES:
        raise AnalyticsError(f"unknown query {name!r}; choose one of {', '.join(QUERIES)}")
    _, _, parquet = verify_published(project_root, manifest_file)
    return query_file(parquet, name)


def verify_published(project_root, manifest_file):
    """Check a match's published output and everything it was built from.

    The raw inputs against the manifest, the metrics files against the
    hashes recorded at build time, and the Parquet file against its
    recorded checksum. Returns (manifest, build metadata, Parquet path).
    Nothing is rebuilt or replaced.
    """
    project_root = Path(project_root)
    manifest = read_manifest(manifest_file)
    commit_sha = manifest["source"]["commit_sha"]
    match_id = manifest["selection"]["match_id"]
    relative_directory = f"{ANALYTICS_ROOT}/{commit_sha}/{match_id}"
    directory = project_root / relative_directory
    if not (directory / METADATA_FILE).is_file():
        raise AnalyticsError(
            f"{directory}: no complete analytical output; `phaselens analytics --manifest` builds it"
        )
    metadata = _checked_metadata(directory / METADATA_FILE, relative_directory, commit_sha, match_id)

    read_verified_files(project_root, manifest)
    raw_inputs = [
        {key: entry[key] for key in ("local_path", "sha256", "size_bytes")}
        for entry in manifest["files"]
    ]
    if metadata["verified_raw_inputs"] != raw_inputs:
        raise AnalyticsError(
            f"{directory / METADATA_FILE}: was built from other raw inputs than the "
            f"manifest records. {_REBUILD}"
        )
    for consumed in metadata["consumed_metric_files"]:
        source = project_root / consumed["path"]
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != consumed["sha256"]:
            raise AnalyticsError(
                f"{consumed['path']} has changed since the analytical output was built. {_REBUILD}"
            )

    artifact = metadata["parquet_artifact"]
    parquet = directory / PARQUET_FILE
    if not parquet.is_file():
        raise AnalyticsError(
            f"{parquet}: the Parquet file is missing although its build metadata exists. {_REBUILD}"
        )
    found = artifact_record(parquet, artifact["path"])
    if found != artifact:
        raise AnalyticsError(
            f"{parquet}: does not match the checksum recorded when it was built "
            f"(recorded {artifact['size_bytes']} bytes, sha256 {artifact['sha256']}; found "
            f"{found['size_bytes']} bytes, sha256 {found['sha256']}). Nothing was changed. {_REBUILD}"
        )
    return manifest, metadata, parquet


def _checked_metadata(path, relative_directory, commit_sha, match_id):
    """Load build metadata and require the version and fields a query relies on."""
    metadata = json_object(path.read_bytes(), METADATA_FILE)
    version = metadata.get("build_metadata_version")
    if version is None:
        raise AnalyticsError(
            f"{path}: was written before Parquet checksums were recorded, so the "
            f"Parquet file cannot be verified. {_REBUILD}"
        )
    if version != BUILD_METADATA_VERSION:
        raise AnalyticsError(
            f"{path}: build metadata version {version!r} is not supported; this program "
            f"reads version {BUILD_METADATA_VERSION}. {_REBUILD}"
        )
    artifact = metadata.get("parquet_artifact")
    consumed = metadata.get("consumed_metric_files")
    expected_consumed = [
        f"{metrics.METRICS_ROOT}/{commit_sha}/{match_id}/{name}" for name in metrics.OUTPUT_FILES
    ]
    problem = None
    if (metadata.get("source_commit"), metadata.get("match_id")) != (commit_sha, match_id):
        problem = "it describes another commit or match than the manifest"
    elif not (
        isinstance(artifact, dict)
        and isinstance(artifact.get("sha256"), str)
        and _is_integer(artifact.get("size_bytes"))
    ):
        problem = "it has no usable parquet_artifact record (path, sha256, size_bytes)"
    elif artifact.get("path") != f"{relative_directory}/{PARQUET_FILE}":
        problem = "its parquet_artifact path is not this match's Parquet file"
    elif not isinstance(metadata.get("verified_raw_inputs"), list):
        problem = "it has no verified_raw_inputs list"
    elif not (
        isinstance(consumed, list)
        and all(isinstance(item, dict) and isinstance(item.get("sha256"), str) for item in consumed)
        and [item.get("path") for item in consumed] == expected_consumed
    ):
        problem = "its consumed_metric_files are not this match's three metrics files"
    if problem:
        raise AnalyticsError(f"{path}: {problem}. {_REBUILD}")
    return metadata


def query_sql(name, sql_files=QUERIES):
    """The SQL text of a fixed query from `sql_files` (name -> file in sql/)."""
    return resources.files("phaselens").joinpath("sql", sql_files[name]).read_text(encoding="utf-8")


def query_file(parquet_path, name, sql_files=QUERIES):
    """Run a fixed query against one Parquet file; returns (column names, rows)."""
    with _duckdb_errors(parquet_path, "query"), duckdb.connect(":memory:") as connection:
        connection.read_parquet(str(parquet_path)).create_view(TABLE)
        result = connection.execute(query_sql(name, sql_files))
        return [column[0] for column in result.description], result.fetchall()


# --- small helpers --------------------------------------------------------


def _integer(text, what):
    if _CANONICAL_INTEGER.fullmatch(text):
        return int(text)
    if text == "":
        raise AnalyticsError(f"{what} is missing")
    if re.fullmatch(r"-[0-9]+", text):
        raise AnalyticsError(f"{what} is negative ({text!r})")
    raise AnalyticsError(
        f"{what} is {text!r}, not an integer written in plain decimal digits "
        "without sign, spaces or leading zeros"
    )


def _is_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _position(column):
    return [name for name, _ in COLUMNS].index(column)


def key_of(row):
    return tuple(row[_position(column)] for column in COMPOSITE_KEY)


def totals_of(rows):
    return {name: sum(row[_position(name)] for row in rows) for name in metrics.METRIC_NAMES}


def json_object(data, name):
    try:
        value = json.loads(data)
    except ValueError as error:
        raise AnalyticsError(f"{name}: not valid JSON ({error})") from error
    if not isinstance(value, dict):
        raise AnalyticsError(f"{name}: expected a JSON object")
    return value


def _json_bytes(value):
    return json.dumps(value, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
