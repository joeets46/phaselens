"""Preserve one match's source files and record where they came from.

Raw files are written once and never changed. The manifest is the
record of what was downloaded; on a later run it is the reference the
local files are checked against.
"""

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from phaselens import statsbomb
from phaselens.fetch import fetch_bytes, url_exists

MANIFEST_FORMAT_VERSION = 1
RAW_ROOT = "data/raw/statsbomb/open-data"
MANIFEST_ROOT = "manifests/statsbomb/open-data"

_FILE_RECORD_KEYS = {
    "source_path",
    "source_url",
    "local_path",
    "retrieved_at_utc",
    "sha256",
    "size_bytes",
}


class IngestError(Exception):
    """Ingestion stopped; the message says why."""


@dataclass
class IngestResult:
    manifest_path: Path
    manifest: dict
    manifest_written: bool
    # local path -> "downloaded", "reused" or "restored"
    file_statuses: dict


def manifest_path(project_root, commit_sha, match_id):
    return Path(project_root) / MANIFEST_ROOT / commit_sha / f"match_{match_id}.json"


def ingest_match(
    project_root,
    commit_sha,
    competition_id,
    season_id,
    match_id,
    fetch=fetch_bytes,
    exists=url_exists,
):
    """Download one match at one commit, or verify a previous download.

    Without a manifest for this match it is a first run: download,
    validate, publish, record. Files shared with a match already ingested
    at this commit are reused once verified against that match's manifest.
    With a manifest, the local files are checked against it and nothing is
    downloaded unless a file is missing.
    """
    project_root = Path(project_root)
    if not statsbomb.is_commit_sha(commit_sha):
        raise IngestError(
            f"{commit_sha!r} is not a full 40-character commit SHA; "
            "branch and tag names are not accepted because they move"
        )
    path = manifest_path(project_root, commit_sha, match_id)
    if path.exists():
        manifest = read_manifest(path)
        selection = {
            "competition_id": competition_id,
            "season_id": season_id,
            "match_id": match_id,
        }
        if manifest["source"]["commit_sha"] != commit_sha or manifest["selection"] != selection:
            raise IngestError(f"{path}: records a different commit or selection than requested")
        statuses = _verify_or_restore(project_root, manifest, fetch)
        return IngestResult(path, manifest, False, statuses)

    manifest, statuses = _download_and_record(
        project_root, path, commit_sha, competition_id, season_id, match_id, fetch, exists
    )
    return IngestResult(path, manifest, True, statuses)


def read_manifest(path):
    """Load a manifest and check it has the parts a rerun relies on."""
    try:
        manifest = json.loads(Path(path).read_bytes())
    except OSError as error:
        raise IngestError(f"{path}: cannot read manifest ({error})") from error
    except ValueError as error:
        raise IngestError(f"{path}: manifest is not valid JSON ({error})") from error
    try:
        version = manifest["manifest_format_version"]
        selection = manifest["selection"]
        complete = (
            statsbomb.is_commit_sha(manifest["source"]["commit_sha"])
            and all(
                isinstance(selection[key], int)
                for key in ("competition_id", "season_id", "match_id")
            )
            and all(_FILE_RECORD_KEYS <= entry.keys() for entry in manifest["files"])
            and "match_metadata" in manifest
            and "three_sixty_check" in manifest
        )
    except (KeyError, TypeError, AttributeError) as error:
        raise IngestError(f"{path}: not a valid manifest ({error!r})") from error
    if version != MANIFEST_FORMAT_VERSION:
        raise IngestError(f"{path}: unsupported manifest format version {version!r}")
    if not complete:
        raise IngestError(f"{path}: manifest is incomplete or has invalid values")
    return manifest


def read_verified_files(project_root, manifest):
    """Return {source_path: bytes} for a manifest's files, each verified.

    Reads local files only and never downloads. A missing file is an error
    here; restoring it is `ingest_match`'s job.
    """
    commit_sha = manifest["source"]["commit_sha"]
    selection = manifest["selection"]
    recorded = {entry["source_path"]: entry for entry in manifest["files"]}
    verified = {}
    for source_path in _source_paths(
        selection["competition_id"], selection["season_id"], selection["match_id"]
    ):
        entry = recorded.get(source_path)
        local_path = _local_path(commit_sha, source_path)
        if entry is None or entry["local_path"] != local_path:
            raise IngestError(f"manifest has no consistent record for {source_path}")
        local = Path(project_root) / local_path
        if not local.is_file():
            raise IngestError(
                f"{local}: recorded in the manifest but not on disk; "
                "`phaselens ingest --manifest` restores it"
            )
        data = local.read_bytes()
        _check_against_record(data, entry, f"{local}: local file")
        verified[source_path] = data
    return verified


def parse_json_array(data, source_url):
    """Parse a source file, which must be a non-empty JSON array of objects."""
    try:
        parsed = json.loads(data)
    except ValueError as error:
        raise IngestError(f"{source_url}: not valid JSON ({error})") from error
    if (
        not isinstance(parsed, list)
        or not parsed
        or not all(isinstance(item, dict) for item in parsed)
    ):
        raise IngestError(f"{source_url}: expected a non-empty JSON array of objects")
    return parsed


def publish(destination, data):
    """Create `destination` holding `data`, or fail leaving no file behind.

    The bytes go to a temporary sibling first. The final name appears only
    after the whole file is on disk, so a partial file is never visible
    under it.
    """
    if destination.exists():
        raise IngestError(f"{destination}: already exists; refusing to overwrite")
    temporary = destination.with_name(destination.name + ".part")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_bytes(data)
        os.replace(temporary, destination)
    except OSError as error:
        raise IngestError(f"{destination}: cannot write file ({error})") from error
    finally:
        temporary.unlink(missing_ok=True)


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _source_paths(competition_id, season_id, match_id):
    return [
        statsbomb.COMPETITIONS_PATH,
        statsbomb.matches_path(competition_id, season_id),
        statsbomb.lineups_path(match_id),
        statsbomb.events_path(match_id),
    ]


def _local_path(commit_sha, source_path):
    """Project-relative path: the upstream path under a per-commit folder."""
    return f"{RAW_ROOT}/{commit_sha}/{source_path}"


def _download_and_record(
    project_root, path, commit_sha, competition_id, season_id, match_id, fetch, exists
):
    source_paths = _source_paths(competition_id, season_id, match_id)
    competitions_path, matches_path, lineups_path, events_path = source_paths

    # A file already on disk is reused only if another manifest at this
    # commit records it and its bytes still match that record. This is
    # settled before any request is made.
    verified = {}
    for source_path in source_paths:
        local = project_root / _local_path(commit_sha, source_path)
        if local.exists():
            entry = _recorded_provenance(project_root, commit_sha, source_path)
            data = local.read_bytes()
            _check_against_record(data, entry, f"{local}: local file")
            verified[source_path] = (entry, data)

    # New files are downloaded and validated in memory first. Nothing is
    # written until every file and the three-sixty check have succeeded.
    files = []  # (manifest entry, bytes, "reused" or "downloaded")

    def obtain(source_path):
        url = statsbomb.source_url(commit_sha, source_path)
        if source_path in verified:
            # The record is carried over unchanged, retrieval time included.
            entry, data = verified[source_path]
            status = "reused"
        else:
            data = fetch(url)
            entry = {
                "source_path": source_path,
                "source_url": url,
                "local_path": _local_path(commit_sha, source_path),
                "retrieved_at_utc": _utc_now(),
                "sha256": hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data),
            }
            status = "downloaded"
        parsed = parse_json_array(data, url)
        files.append((entry, data, status))
        return parsed, url

    competitions, url = obtain(competitions_path)
    if not any(
        entry.get("competition_id") == competition_id and entry.get("season_id") == season_id
        for entry in competitions
    ):
        raise IngestError(
            f"{url}: no entry for competition {competition_id}, season {season_id}"
        )

    # The match must be in the list before anything specific to it is fetched.
    matches, url = obtain(matches_path)
    match = next((entry for entry in matches if entry.get("match_id") == match_id), None)
    if match is None:
        raise IngestError(f"{url}: no match with match_id {match_id}")
    match_metadata = _match_metadata(match, url)

    obtain(lineups_path)
    obtain(events_path)

    # A 404 means "absent" here only because this same commit has just
    # served this match's files; an unknown commit would also answer 404.
    three_sixty_url = statsbomb.source_url(commit_sha, statsbomb.three_sixty_path(match_id))
    three_sixty_present = exists(three_sixty_url)
    three_sixty_check = {
        "source_url": three_sixty_url,
        "method": "HEAD",
        "result": "present" if three_sixty_present else "absent",
        "checked_at_utc": _utc_now(),
        "downloaded": False,
    }

    manifest = {
        "manifest_format_version": MANIFEST_FORMAT_VERSION,
        "source": {
            "name": "StatsBomb Open Data",
            "repository_url": statsbomb.REPOSITORY_URL,
            "commit_sha": commit_sha,
        },
        "selection": {
            "competition_id": competition_id,
            "season_id": season_id,
            "match_id": match_id,
        },
        "match_metadata": match_metadata,
        "files": [entry for entry, _, _ in files],
        "three_sixty_check": three_sixty_check,
    }

    published = []
    try:
        for entry, data, status in files:
            if status == "downloaded":
                destination = project_root / entry["local_path"]
                publish(destination, data)
                published.append(destination)
        encoded = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
        publish(path, encoded)
    except BaseException:
        # Without a manifest the files written by this run would be
        # unverifiable leftovers. Reused files were not written here and stay.
        for destination in published:
            destination.unlink(missing_ok=True)
        raise
    return manifest, {entry["local_path"]: status for entry, _, status in files}


def _recorded_provenance(project_root, commit_sha, source_path):
    """The record that manifests at this commit hold for `source_path`.

    Raises if no manifest records the file, or if the records found do
    not agree with each other or with this commit's URL and local path.
    """
    folder = project_root / MANIFEST_ROOT / commit_sha
    source_url = statsbomb.source_url(commit_sha, source_path)
    local_path = _local_path(commit_sha, source_path)
    recorded = None
    recorded_in = None
    for manifest_file in sorted(folder.glob("match_*.json")):
        manifest = read_manifest(manifest_file)
        if manifest["source"]["commit_sha"] != commit_sha:
            raise IngestError(
                f"{manifest_file}: is filed under commit {commit_sha} but records "
                f"commit {manifest['source']['commit_sha']}"
            )
        for entry in manifest["files"]:
            if entry["source_path"] != source_path:
                continue
            if entry["source_url"] != source_url or entry["local_path"] != local_path:
                raise IngestError(
                    f"{manifest_file}: its record for {source_path} does not refer to "
                    "this commit's source URL and local path, so it cannot vouch for "
                    "the existing file"
                )
            if recorded is None:
                recorded, recorded_in = entry, manifest_file
                continue
            differing = sorted(key for key in _FILE_RECORD_KEYS if entry[key] != recorded[key])
            if differing:
                raise IngestError(
                    f"provenance records for {source_path} conflict: {recorded_in} and "
                    f"{manifest_file} disagree on {', '.join(differing)}. "
                    "Nothing was changed."
                )
    if recorded is None:
        raise IngestError(
            f"{project_root / local_path}: already exists but no manifest in {folder} "
            "records it, so it cannot be verified. It was not reused, overwritten, "
            "or deleted. Inspect it and move it away to download a fresh copy."
        )
    return dict(recorded)


def _match_metadata(match, source_url):
    """Identifying fields of the match, under the names the source uses."""
    try:
        return {
            "match_id": match["match_id"],
            "match_date": match["match_date"],
            "competition": {
                "competition_id": match["competition"]["competition_id"],
                "competition_name": match["competition"]["competition_name"],
            },
            "season": {
                "season_id": match["season"]["season_id"],
                "season_name": match["season"]["season_name"],
            },
            "home_team": {
                "home_team_id": match["home_team"]["home_team_id"],
                "home_team_name": match["home_team"]["home_team_name"],
            },
            "away_team": {
                "away_team_id": match["away_team"]["away_team_id"],
                "away_team_name": match["away_team"]["away_team_name"],
            },
        }
    except (KeyError, TypeError) as error:
        raise IngestError(
            f"{source_url}: match record lacks an expected field ({error!r})"
        ) from error


def _verify_or_restore(project_root, manifest, fetch):
    commit_sha = manifest["source"]["commit_sha"]
    selection = manifest["selection"]
    recorded = {entry["source_path"]: entry for entry in manifest["files"]}
    statuses = {}
    # Paths and URLs are recomputed, not taken from the manifest, so an
    # edited manifest cannot point the run at another place.
    for source_path in _source_paths(
        selection["competition_id"], selection["season_id"], selection["match_id"]
    ):
        entry = recorded.get(source_path)
        local_path = _local_path(commit_sha, source_path)
        url = statsbomb.source_url(commit_sha, source_path)
        if entry is None or entry["local_path"] != local_path or entry["source_url"] != url:
            raise IngestError(f"manifest has no consistent record for {source_path}")
        local = project_root / local_path
        if local.exists():
            _check_against_record(local.read_bytes(), entry, f"{local}: local file")
            statuses[local_path] = "reused"
        else:
            data = fetch(url)
            _check_against_record(data, entry, f"{url}: downloaded content")
            publish(local, data)
            statuses[local_path] = "restored"
    return statuses


def _check_against_record(data, entry, what):
    actual_sha256 = hashlib.sha256(data).hexdigest()
    if len(data) != entry["size_bytes"] or actual_sha256 != entry["sha256"]:
        raise IngestError(
            f"{what} conflicts with its manifest record: expected "
            f"{entry['size_bytes']} bytes with sha256 {entry['sha256']}, found "
            f"{len(data)} bytes with sha256 {actual_sha256}. Nothing was changed."
        )
