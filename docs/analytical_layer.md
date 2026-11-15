# Analytical layer

A typed Parquet copy of the player-match metrics, queried with DuckDB.

This layer adds no metric and changes no value. It takes the three
event counts that `phaselens metrics` already wrote, checks them,
stores them with explicit types, and offers a few fixed SQL queries.
The metrics keep their status of `implemented_unvalidated`; see the
[metric catalog](metric_catalog.md).

## Commands

Run from the project root. Neither needs the network.

```
uv run phaselens analytics --manifest manifests/statsbomb/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/match_3943043.json
uv run phaselens query --manifest manifests/statsbomb/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/match_3943043.json --name team-totals
```

`analytics` builds the output. `query` runs one of four fixed queries
and prints the result as a table. A query only reads: it never
rebuilds or replaces a file, even when a check fails.

## Input contract

The manifest names the match and the upstream commit. From them the
build finds:

| Input | Location | Used for |
|---|---|---|
| Four raw files | `data/raw/...`, as the manifest records | Verified against the manifest; not otherwise read |
| `player_match_metrics.csv` | `data/processed/metrics/<commit_sha>/<match_id>/` | The rows |
| `run_summary.json` | Same folder | Contract version, recorded source hashes, row count, totals |
| `diagnostics.json` | Same folder | Consistency with the summary |

The metric contract version comes from `run_summary.json`. It is not
assumed.

## Verification

Four different kinds of assurance are involved. This layer provides
the first two, relies on an earlier stage for the third, and does not
provide the fourth.

| Kind | Provided here | In short |
|---|---|---|
| Structural and total reconciliation | Yes, at build time | The CSV is well-formed and agrees with its summary on counts and totals |
| File integrity | Yes, at build and query time | Files still have the bytes that were recorded for them |
| Recalculation from raw events | No | Done by `phaselens metrics` and its tests, not repeated here |
| Authenticity | No | Nothing is signed; consistent edits are not detectable |

### Structural and total reconciliation (build)

The build stops at the first failed check and corrects nothing.

1. `run_summary.json` and `diagnostics.json` name the manifest's commit
   and match, share one contract version, and agree on diagnostic
   counts.
2. The CSV has exactly the expected columns, in order.
3. Every row carries the manifest's commit and match id.
4. Identifiers and counts are integers written in plain decimal digits.
   Missing, negative, and non-integer values are rejected.
5. No `(team_id, player_id)` pair occurs twice.
6. On every row,
   `counterpress_pressure_event_count <= pressure_event_count` and
   `counterpress_pressure_event_count <= counterpress_flagged_event_count`.
7. The row count, the three totals, and each team's player count and
   totals equal those in `run_summary.json`.
8. After writing, the Parquet file is read back: its schema, row
   order, and every value equal the validated CSV rows, and the
   integrity-check query reports no violation.

What reconciliation does not catch: the summary holds totals, not
individual rows. An edit to the CSV alone passes the build when it
keeps the row count and every team's totals and still satisfies rules
2 to 6. Examples that pass:

- swapping the three counts of two players of the same team;
- replacing a `player_name` or `team_name`;
- replacing a `player_id` with an id not otherwise in the file.

### File integrity (build and query)

| File | Checked against | When |
|---|---|---|
| Raw files | SHA-256 and size in the manifest | Build and query |
| Source hashes in `run_summary.json` | The manifest's raw file records | Build |
| Raw input hashes in the build metadata | The manifest's raw file records | Query |
| The three metrics files | SHA-256 recorded in the build metadata | Query |
| `player_match_metrics.parquet` | SHA-256 and size recorded in the build metadata | Query |

Before a query reads the Parquet file, the file must exist and its
actual SHA-256 and size must equal the recorded ones. A valid but
altered file, a truncated file, and a missing file are all refused,
with a message that says to rebuild.

An integrity check detects a change relative to a recorded checksum.
It says nothing about whether the recorded state was right.

### Recalculation from raw events (not done here)

This layer never recomputes a metric. That the counts follow from the
raw events is established elsewhere: by the acceptance tests of
`phaselens metrics` and by the reconciliation of its output with an
independent count of the source events. A CSV that passes the checks
above has not thereby been shown to match the raw events.

### Authenticity (not provided)

Nothing in this project is signed. The checksums are stored beside the
files they describe, so they protect against accidental change and
against a change to one file only. They do not prove who produced a
file or that it is the original. Someone who changes:

- the CSV and its summary consistently, then rebuilds; or
- the Parquet file and the checksum in its build metadata together; or
- a raw file and its manifest record together

passes every check. The manifest is the root of trust for the raw
files and is itself only as trustworthy as its storage; committing it
to version control is what would give it a history.

One further limit: a query hashes the Parquet file and then lets
DuckDB read it. A change between those two moments is not detected.

## Output

Written to `data/processed/analytics/<commit_sha>/<match_id>/`, which
Git ignores.

| File | Content |
|---|---|
| `player_match_metrics.parquet` | One row per eligible team and player |
| `build_metadata.json` | What was built, from what, with which versions, and the checksum of the Parquet file |

### Schema

Analytical schema version 1. Types are declared in code; nothing is
inferred from the CSV. Every column is written as not nullable.

| Column | DuckDB type | Parquet type | Role |
|---|---|---|---|
| `source_commit` | `VARCHAR` | byte array | Key |
| `metric_contract_version` | `BIGINT` | 64-bit integer | Key |
| `match_id` | `BIGINT` | 64-bit integer | Key |
| `team_id` | `BIGINT` | 64-bit integer | Key |
| `team_name` | `VARCHAR` | byte array | Label |
| `player_id` | `BIGINT` | 64-bit integer | Key |
| `player_name` | `VARCHAR` | byte array | Label |
| `pressure_event_count` | `BIGINT` | 64-bit integer | Count |
| `counterpress_pressure_event_count` | `BIGINT` | 64-bit integer | Count |
| `counterpress_flagged_event_count` | `BIGINT` | 64-bit integer | Count |

Composite key:
`(source_commit, metric_contract_version, match_id, team_id, player_id)`.
Rows are stored sorted by it. The order is by identifier and is not a
ranking.

Nullability is enforced when the file is written: the table is created
with `NOT NULL` on every column, so a null value stops the build. It is
not re-checked when the file is read; the checksum is what protects
the published file afterwards.

### Identifiers and names

- Identifiers are integers, as in the source. In the CSV they must be
  written canonically: digits only, no sign, no spaces, no leading
  zeros. A value such as `011` is rejected, not read as 11, because
  accepting it would let two spellings name one key.
- Names are labels and are never part of a key. Queries group by id and
  carry the name along.
- A name that is missing in the source is an empty string in the CSV.
  It stays an empty string in Parquet and is not turned into null.

### Build metadata

`build_metadata.json` is at format version 2, recorded in its
`build_metadata_version` field.

| Field | Content |
|---|---|
| `build_metadata_version` | `2` |
| `analytical_schema_version`, `metric_contract_version` | Versions of the table schema and of the metric contract |
| `source_commit`, `match_id` | What the output belongs to |
| `parquet_artifact` | `path` (relative to the project root), `sha256`, and `size_bytes` of the Parquet file as published |
| `consumed_metric_files` | Path, SHA-256, and size of each metrics file that was read |
| `verified_raw_inputs` | Path, SHA-256, and size of each raw file, as in the manifest |
| `columns`, `composite_key`, `row_count`, `metric_totals` | The table's shape and totals |
| `duckdb_version`, `parquet_compression` | How the file was written |

Paths are relative to the project root. The file holds no timestamp
and no machine-specific path.

**Version 2 and the rebuild requirement.** Version 2 added
`build_metadata_version` and `parquet_artifact`, and removed the
earlier `parquet_file` path. Metadata written before that has no
version field and no checksum, so the Parquet file beside it cannot be
verified. `query` refuses such output, and refuses any version other
than 2, with a message that says to rebuild:

```
uv run phaselens analytics --manifest manifests/statsbomb/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/match_3943043.json
```

Older metadata is never treated as verified, and nothing is rebuilt
automatically.

### Publishing

Files are written to a temporary sibling folder and moved into place
only after every check has passed. `build_metadata.json` is removed
first and arrives last, so its presence marks a complete result. After
the Parquet file is moved, its checksum is taken again and must equal
the one about to be recorded.

If a build fails, nothing new is published and an earlier complete
output is left as it was. The build never writes to the metrics folder.

## How DuckDB queries the Parquet file

There is no database server and no database file. Each command opens an
in-memory DuckDB connection, exposes the Parquet file as a view named
`player_match_metrics`, runs one SQL statement, and closes.

The SQL lives in `src/phaselens/sql/` as plain files that can be read
and reused. Only these four can be run; the command does not accept
SQL text.

| `--name` | SQL file | Returns |
|---|---|---|
| `player-rows` | `player_rows.sql` | Every player row, ordered by team id and player id |
| `team-totals` | `team_totals.sql` | The three counts summed per team |
| `team-player-counts` | `team_player_counts.sql` | Eligible players per team, and how many have a zero for each count |
| `integrity-checks` | `integrity_checks.sql` | Violations of key uniqueness, non-negative counts, and the two inequalities; all should be 0 |

None of these ranks players. The counts are not normalized by playing
time and are not measures of pressing quality.

### Errors

A failed check, and a DuckDB failure while writing, reading, or
querying a Parquet file, are reported as one line beginning `error:`
and exit status 1. Only DuckDB's own exceptions are translated this
way. Any other exception is a programming error and is shown in full.

## Reproducibility

Two kinds are kept apart.

- **Logical reproducibility** is required: the same inputs give the
  same schema, the same typed rows in the same order, the same totals,
  and the same build metadata apart from the `sha256` and `size_bytes`
  of the Parquet file. A test enforces it.
- **Physical reproducibility**, meaning identical Parquet bytes and
  therefore an identical checksum in the metadata, is not promised.
  Parquet files embed the writer's version, and encoding choices can
  change between DuckDB releases.

Observed on 2026-11-15 with DuckDB 2.0.0 and the locked environment:
two builds of the ingested match in separate processes produced
byte-identical Parquet files and byte-identical metadata. This is an
observation about one environment, not a guarantee.

## Why there is no persistent database

One table of 29 rows does not need one. A `.duckdb` file would be a
second copy of the data to keep in step with the Parquet file, with
its own format and versioning. The Parquet file is the single stored
form, and DuckDB reads it directly whenever a query runs. A persistent
database becomes worth considering when there are several tables to
join or the data no longer fits comfortable in-memory reads.

## Limitations

- One table, one match. Source events are not stored in Parquet.
- Reconciliation compares totals, so a CSV-only edit that keeps them
  can pass the build.
- Checksums detect change relative to what was recorded. They are not
  signatures and do not establish authenticity.
- Metrics are not recomputed here.
- Byte-identical output across DuckDB versions is not promised.
- A failed build leaves an earlier output in place.
- The metrics remain `implemented_unvalidated`.
