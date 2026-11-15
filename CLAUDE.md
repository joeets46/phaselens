# PhaseLens

Football analytics data platform focused on players' off-ball
contributions across phases of play. Early stage: an event-data
foundation on StatsBomb Open Data, designed to extend to tracking data
later. Current milestone and status are in `docs/project_brief.md`.

## Working style

- The user is learning data engineering. Work in small increments and
  explain what each step achieves.
- Explain in Azerbaijani. Use English for code identifiers, commit
  messages, and documentation files.
- Approval covers one milestone at a time. Stop at the end of a
  milestone and wait for approval before starting the next.
- Do not commit, add a remote, push, or change global Git configuration
  unless asked.

## Methodological rules

- Event data does not measure all off-ball movement. Never imply it does.
- Classify every metric as `observed`, `derived`, or `proxy`
  (definitions in `docs/metric_catalog.md`).
- Never label an event-derived proxy as a measured sprint, recovery run,
  or complete off-ball performance.
- Never invent fields or assume coverage. Confirm against the raw files.
- All weights, time windows, thresholds, and scoring formulas are
  unvalidated hypotheses. Name them as parameters and record them in the
  catalog; do not hard-code them as facts.
- Do not implement an overall rating or a confidence score.
- Record limitations in the catalog entry of the metric they affect.
- In documentation, keep what works today separate from what is planned.
- A metric is implemented only from its contract in
  `docs/metric_catalog.md`: formula, eligibility, diagnostics, and
  acceptance cases. Change the contract first, then the code.
- What a field means comes from `docs/provider_semantics.md`, with a
  page reference. An absent key has no single meaning: follow the
  per-field table there, and never coerce a flag value.
- Keep three things apart: a value in the source, an inference from a
  documented convention, and a claim about the real match.

## Data rules

- `data/raw/` is immutable. Never edit, reformat, or re-save a raw file.
- `data/raw/` and `data/processed/` contents are never committed.
- Provenance records go in `manifests/`, which is committed. Only
  `phaselens ingest` writes them; never edit one by hand.
- Never fabricate a manifest or sample data.
- Derived data must be rebuildable from raw.
- Read source files at a pinned commit SHA, never from a branch.
- A raw file already on disk is reused only when a manifest at the same
  commit records it and its SHA-256 and size match. Never adopt,
  overwrite, or delete a raw file that no manifest records.
- Registration, redistribution, and commercial-use questions about the
  source are unresolved (`docs/data_sources.md`). Do not register
  accounts, publish data, or give legal assurances.
- StatsBomb Open Data may not be redistributed or used commercially,
  and published analysis must credit StatsBomb. Never commit or publish
  raw data. Details and links: `docs/data_sources.md`.
- The canonical source repository is `hudl/open-data`; the old
  `statsbomb/open-data` address only redirects to it.

## Stack limits

Allowed: Python, local JSON, Parquet, DuckDB, pytest. DuckDB is the
only runtime dependency in use.
Not yet: PostgreSQL, Docker, dbt, Airflow, Spark, Kafka, cloud
infrastructure, machine learning, dashboards.
Add a dependency only when the current milestone needs it.

## Environment

- uv manages the virtual environment and dependencies. Do not use pip
  directly.
- Use the Python 3.13 already installed. If it is incompatible with
  something, stop and explain; do not install another Python version.
- `uv.lock` is committed.

## Commands

```
uv sync                # create or update .venv from uv.lock
uv run pytest          # run the tests
uv add <package>       # add a runtime dependency
uv add --dev <package> # add a development dependency

uv run phaselens competitions                 # list competition-seasons, saves nothing
uv run phaselens matches --commit <sha> --competition-id <id> --season-id <id>
uv run phaselens ingest --manifest <path>     # verify or restore a recorded match
uv run phaselens profile --manifest <path>    # describe a match's files, offline
uv run phaselens metrics --manifest <path>    # catalogued event counts, offline
uv run phaselens analytics --manifest <path>  # typed Parquet copy of the metrics
uv run phaselens query --manifest <path> --name <query>  # one of four fixed SQL queries
```

Metric outputs go to `data/processed/metrics/<commit>/<match_id>/` and
must stay byte-identical for identical inputs. The metric code follows
contract version 1 in `docs/metric_catalog.md`; a contract violation
stops the run instead of being worked around.

The analytical layer (`docs/analytical_layer.md`) copies the metrics
to Parquet and must never change a value or write to the metrics
folder. Types are declared, not inferred. Queries are fixed SQL files
in `src/phaselens/sql/`; do not add a way to run arbitrary SQL. Require
identical rows, schema, and totals between builds; do not promise
identical Parquet bytes. A query verifies the Parquet file against the
checksum in `build_metadata.json` (format version 2) and must never
rebuild or replace anything. Checksums detect change; never describe
them as proof of authenticity.

Runtime dependency: `duckdb` only. No pandas or pyarrow.

Profile outputs go to `data/processed/profiles/<commit>/<match_id>/`
and must stay byte-identical for identical inputs. What the ingested
match contains is in `docs/schema_profile.md`; check field names there
before using one. The profiler only describes: no metrics, no
per-player figures, no minutes played.

Tests must not use the network; `tests/conftest.py` blocks it.
The standard library covers HTTP, JSON, and hashing; do not add
`requests` or similar.
