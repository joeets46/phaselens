# Manifests

Provenance records for downloaded data. This folder is tracked in Git;
the data files it describes are not.

A manifest is written by `phaselens ingest` and never by hand. It is
written once. Later runs read it to verify the local files and do not
change it.

## Location

```
manifests/statsbomb/open-data/<commit_sha>/match_<match_id>.json
```

## Format (version 1)

| Field | Meaning |
|---|---|
| `manifest_format_version` | `1` |
| `source.repository_url` | Canonical repository the files came from |
| `source.commit_sha` | The one upstream commit every file was read at |
| `selection` | `competition_id`, `season_id`, `match_id` that were requested |
| `match_metadata` | Identifying fields of the match, copied from the source match list under the source's own field names |
| `files[]` | One record per downloaded file, see below |
| `three_sixty_check` | Whether a three-sixty file exists for the match at this commit; the file itself is not downloaded |

Each `files[]` record:

| Field | Meaning |
|---|---|
| `source_path` | Path inside the upstream repository |
| `source_url` | URL the bytes were read from, pinned to the commit |
| `local_path` | Where the file is stored, relative to the project root |
| `retrieved_at_utc` | When this source file was originally retrieved, in UTC; see below |
| `sha256` | SHA-256 of the file's bytes |
| `size_bytes` | Size of the file in bytes |

## What `retrieved_at_utc` means

It is the time of the original recorded retrieval of that source file:
the download that first produced the record. It is not the time of the
latest verification, and it is never updated.

- **Verification.** A later run that finds the file on disk and checks
  it against the record leaves the timestamp alone.
- **Restoration.** If the local file is missing, it is downloaded again
  from the same pinned URL and accepted only if its SHA-256 and size
  equal the record. The manifest is not changed, so the timestamp still
  names the original retrieval and says nothing about when the file was
  restored. Restorations are not logged.
- **Shared files.** `competitions.json` and a match list are shared by
  the matches of a competition-season. When a second match at the same
  commit reuses such a file, its manifest carries the first match's
  record unchanged, including this timestamp.

## Shared files across manifests

A file already on disk is reused for a new match only when another
manifest in the same commit folder records the same `source_path` with
this commit's `source_url` and `local_path`, all such records agree,
and the file's SHA-256 and size match. Otherwise the run stops and the
file is left as found. A file that no manifest records is never adopted.

## Current manifests

| Manifest | Match |
|---|---|
| `statsbomb/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/match_3943043.json` | UEFA Euro 2024, Spain v England, 2024-07-14 |
