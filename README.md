# PhaseLens

A football analytics data platform for studying players' off-ball
contributions across phases of play.

**Status:** Milestone 12 (the whole Euro 2024 knockout stage) is
complete. The fifteen knockout-stage matches of UEFA Euro 2024 are
stored locally as unmodified source files, each is profiled, three
event counts are computed per match against a written contract, and the
per-match results are combined into one typed Parquet table queried
with DuckDB. For every one of the fifteen, the three-sixty positional
snapshots are stored with a companion manifest, and an exploratory
event-level table of visible players around each event's actor is
derived from them; the final is the match they are described for in
detail. A local dashboard shows these results. The counts are tested for
correctness, not validated for football meaning. No player has been
rated or ranked.

## What exists today

- A command line tool, `phaselens`, that lists what StatsBomb Open Data
  offers and downloads one match per run, or a pilot's matches, at one
  pinned upstream commit
- Byte-for-byte local copies of the source files of fifteen matches:
  events, lineups, and the three-sixty file of each match, plus two
  shared files (47 files)
- A provenance manifest recording where each file came from, its
  SHA-256, its size, and when it was retrieved
- Repeat runs that verify the local files against the manifest instead
  of downloading again
- An offline profiler that counts what the match's files contain and
  runs a limited set of consistency checks
- Tests that run without internet access
- Documentation: project brief, data source notes, the schema profile
  of the final with the elements first seen in the fifteen-match pilot,
  and what the provider's specification says
  about the fields the first metrics use
- A metric catalog holding the contract for three event counts: exact
  formulas, eligibility, diagnostics, and acceptance cases
- An offline command that computes those three counts per player for
  an ingested match and writes CSV and JSON
- A typed Parquet copy of those counts and four fixed SQL queries run
  with DuckDB
- The three-sixty file of each knockout-stage match, stored with a
  companion manifest, and an offline report of how it links to the
  events and what it contains

## Three-sixty frames

```
uv run phaselens three-sixty-ingest --manifest manifests/statsbomb/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/match_3943043.json
uv run phaselens three-sixty-profile --manifest manifests/statsbomb/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/match_3943043.json
```

The first downloads the match's three-sixty file once and afterwards
only verifies it; the match manifest is not changed. The commands are
shown for the final; they are run the same way for every match whose
manifest records `three_sixty_check.result` as "present" (all fifteen
knockout-stage matches; see [three-sixty frames](docs/three_sixty.md)). The second writes
a report to `data/processed/three_sixty/<commit_sha>/<match_id>/`
without any network access.

```
uv run phaselens three-sixty-context --manifest manifests/statsbomb/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/match_3943043.json
```

This writes `spatial_context.csv`, one row per event: for events with
a frame, the distance from the actor to the nearest visible opponent
and the counts of visible teammates and opponents within 5, 10, and 20
source units. These are exploratory indicators about observed players,
not full-team counts, player ratings, or measures of pressure. The frames are snapshots of visible
players at event moments, without player identities except the
event's actor. What they can and cannot support is in
[three-sixty frames](docs/three_sixty.md).

## Local dashboard

A small Streamlit app for looking at results already prepared on disk.
Its packages are in a separate dependency group, so the pipeline does
not need them.

```
uv sync --group dashboard
uv run phaselens dashboard-check
uv run --group dashboard streamlit run src/phaselens/dashboard_app.py
```

Run all three from the project root, then open http://127.0.0.1:8501.
Stop the server with Ctrl+C in that terminal.

`dashboard-check` runs the dashboard's own loaders without Streamlit:
it reads and verifies the prepared files, never downloads or writes,
and works offline. It prints "Ready." and exits with 0 when both views
can open; otherwise it names the command to run for each missing input
and exits with 1. How to prepare the inputs, in order, is in "Data
preparation" in the [demo guide](docs/demo_guide.md), which also has a
walkthrough. Repeatable manual checks are in the
[browser checklist](docs/browser_checklist.md).

- **Match overview:** a header with the match details, the teams and
  the score as recorded in the verified match list, and a match menu;
  the two teams' counts as paired comparison rows; and one player table
  per team (Player ID last, short column headers with their full
  definitions on hover), read through the verified pilot queries. All
  fifteen pilot matches are available.
- **360° moments:** a match menu in the header lists only the pilot's
  matches whose three-sixty data verified (companion manifest, file
  hash, and frames); a match without it is not offered. A match is
  loaded when it is chosen. Pick an action
  by type, team, and player (the player list follows the team and runs
  from goalkeeper to attack, with recorded positions and substitution
  times), or step through the list with ‹ and ›. The pitch shows the
  visible players of the snapshot in team colours, the named event
  player, the recorded action spot, and the attacking direction, with
  optional 5/10/20-unit rings and the recorded camera view; beside it
  (or below it on a narrow window) are the action's spatial-context
  values and ring counts. All fields are in an expander.
- **Languages and guide:** the interface is available in English,
  Turkish, and German (menu at the top right), using common football
  terms in each language. Team and player names are shown as recorded;
  event types and positions are translated. A "Guide" button explains
  how to use the page, every symbol on the pitch, and the terms.

What the app does and does not do:

- It reads prepared local data and verifies it with the existing
  checks before showing it. It never downloads, ingests, rebuilds, or
  writes anything; missing data produces a message naming the command
  to run.
- Context values are recomputed in memory from the verified events and
  frames. The saved `spatial_context.csv` is only compared against
  them.
- Data is verified once per browser session and kept in memory for
  that session. Changes on disk after loading are seen only after
  pressing the reload button (⟳).
- It shows observed event context: anonymous visible players at event
  moments, in source coordinate units. It is not tracking data and
  says nothing about player quality.
- Coordinates and distances are rounded to three decimals on screen only
  ("<0.001" for a distance above 0 but below 0.001); calculations and
  saved files keep full precision.
- `.streamlit/config.toml` turns off Streamlit's usage statistics and
  binds the server to 127.0.0.1. That limits who can connect; it is not
  a firewall and does not block outgoing traffic. The app itself loads
  no external images, fonts, scripts, or data.

### Troubleshooting

| Symptom | What to do |
|---|---|
| The page says data could not be loaded and verified | Run the command it names (or `uv run phaselens dashboard-check`), then press ⟳ |
| `ModuleNotFoundError: No module named 'streamlit'` | A plain `uv sync` removed the dashboard group; run `uv sync --group dashboard` |
| "Port 8501 is not available" | Another server is running; stop it with Ctrl+C in its terminal, or add `--server.port 8502` |
| An error such as `AttributeError` after the code changed | The running server kept an older module; stop it with Ctrl+C and start it again |
| The terminal asks for an e-mail address on the first run | Optional; press Enter to skip |
| A change to the files on disk does not appear | Data is verified once per session; press ⟳ |

## What is planned

Milestone 12 is complete: it extended the pilot, its three-sixty data,
and the dashboard to the fifteen knockout-stage matches, with the same
verification, and added no metric or analytical feature. No further
milestone is approved. The long-term direction is in the
[project brief](docs/project_brief.md); none of it beyond what is
listed above is implemented.

## What this project does not claim

- It does not measure sprints, recovery runs, or complete off-ball
  performance. Event data does not record continuous player movement.
- It does not produce an overall player rating or a confidence score.
- It does not treat any threshold, time window, or weight as a
  validated standard.

## Principles

1. Every metric is classified as **observed**, **derived**, or **proxy**.
2. Raw data is preserved unmodified; every later table can be rebuilt
   from it.
3. Fields and coverage are confirmed by inspection, never assumed.
4. Limitations are documented next to the metric they apply to.

## Getting started

Requires Python 3.13 or later and [uv](https://docs.astral.sh/uv/).
The only runtime dependency is DuckDB; pytest is used for development.
The optional `dashboard` group adds Streamlit and Matplotlib. The
interactive pitch uses Altair, which Streamlit installs; Matplotlib
only measures the width of the event player's name label on the pitch.

```
uv sync          # create .venv and install the locked dependencies
uv run pytest    # run the tests (no internet needed)
```

## The first ingested match

| Item | Value, as recorded in the source |
|---|---|
| Competition | UEFA Euro (`competition_id` 55) |
| Season | 2024 (`season_id` 282) |
| Match | Spain v England, 2024-07-14 (`match_id` 3943043) |
| Upstream commit | `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb` |
| Manifest | `manifests/statsbomb/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/match_3943043.json` |
| Three-sixty file | Downloaded in Milestone 7, with its own companion manifest |

Why this match: it is the only match of its season whose stage is
"Final" in the source, so the choice is unambiguous; it is widely
reported, so its teams, date, and score are easy to check against
public records; and the source marks both its event data and its
three-sixty data as available, which keeps later options open. The
other fourteen matches are listed in `pilots/euro2024_knockout_stage.json`.

## Reproducing the download

Run from the project root. The data folder is not in Git, so a fresh
clone has the manifest but no data. This restores the four files and
checks each against the SHA-256 in the manifest:

```
uv run phaselens ingest --manifest manifests/statsbomb/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/match_3943043.json
```

When the files are already present, the same command only verifies
them. It makes no network request and changes nothing.

## Ingesting from scratch

These are the commands that produced the current data.

```
uv run phaselens competitions
uv run phaselens matches --commit 4b73468fc5b0f1950f9f66fada70ad3a4f9327cb --competition-id 55 --season-id 282
uv run phaselens ingest --commit 4b73468fc5b0f1950f9f66fada70ad3a4f9327cb --competition-id 55 --season-id 282 --match-id 3943043
```

- `competitions` and `matches` only print a listing; they save nothing.
- Without `--commit`, a command resolves the current head of the
  upstream `master` branch once and prints the SHA. Pass that SHA to
  the following commands so that everything is read at one revision.
- `--commit` accepts only a full 40-character SHA, never a branch name.
- A command that fails prints `error: ...` and exits with status 1.

### What `ingest` guarantees

- All four files are downloaded and validated in memory before anything
  is written. A failed run leaves no files behind.
- An existing raw file is never overwritten.
- If a local file differs from its manifest record, the run stops and
  reports the conflict without changing anything.
- The match must appear in the competition-season's match list before
  its lineups or events are requested.

### Files shared between matches

Every match of a competition-season at one commit shares
`competitions.json` and the match list. When a match is ingested and
one of these is already on disk, it is reused only if all of this holds:

1. Another manifest at the same commit records the same source path,
   with this commit's source URL and local path.
2. All manifests that record it agree with each other.
3. The file's SHA-256 and size match that record.

The new manifest then carries the existing record unchanged. The file
is not rewritten, and its recorded retrieval time stays the original
one. If any condition fails, the run stops and the file is left as
found: not reused, not overwritten, not deleted.

This behaviour is covered by offline tests with synthetic data, and the
five-match pilot uses it: four matches were ingested after the final at
the same commit, each reusing the verified shared files. The
fifteen-match pilot did the same for ten more matches, each downloading
its events and lineups and reusing the two shared files.

## Profiling the match

Run from the project root. It needs no network.

```
uv run phaselens profile --manifest manifests/statsbomb/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/match_3943043.json
```

The command checks every raw file against the manifest first and stops
if one is missing or differs. It never downloads and never changes the
raw files or the manifest. It writes four files to
`data/processed/profiles/<commit_sha>/<match_id>/`:

| File | Content |
|---|---|
| `summary.json` | Event counts, time and possession observations, list and coordinate fields, off-ball-relevant data, lineups |
| `event_types.csv` | One row per event type |
| `field_presence.csv` | Non-null, null, and missing counts per field path, overall and per event type, with denominators |
| `quality_findings.json` | Result of each consistency check: pass, error, warning, expected absence, or unresolved |

Running it again on the same inputs produces the same bytes. The
findings for the ingested match are written up in the
[schema profile](docs/schema_profile.md).

The profiler describes; it does not evaluate. It computes no metric,
no per-player figure, and no minutes played.

## Computing the metrics

Run from the project root. It needs no network.

```
uv run phaselens metrics --manifest manifests/statsbomb/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/match_3943043.json
```

The command checks every raw file against the manifest, validates the
inputs against the metric contract, and only then writes three files
to `data/processed/metrics/<commit_sha>/<match_id>/`. Running it again
on the same inputs produces the same bytes. The outputs are not in Git.

| File | Content |
|---|---|
| `player_match_metrics.csv` | One row per eligible team and player |
| `diagnostics.json` | Each diagnostic with its count and event ids |
| `run_summary.json` | Contract version, inputs and their hashes, eligible player count, totals, diagnostic totals, limitations |

### The three counts

The full contract is in the [metric catalog](docs/metric_catalog.md).

| Column | Counts, per player in one match |
|---|---|
| `pressure_event_count` | Pressure events |
| `counterpress_pressure_event_count` | Pressure events whose `counterpress` flag is exactly `true` |
| `counterpress_flagged_event_count` | Events of seven supported types whose `counterpress` flag is exactly `true`, except offensive fouls |

The other columns are `source_commit`, `match_id`, `team_id`,
`team_name`, `player_id`, and `player_name`. Ids are the keys. Names
are labels taken from the events file and are never used for matching.
Rows are sorted by team id and then player id, which is not a ranking.

The counting unit is one event. It is not a pressing episode or
sequence: one passage of play can produce several counted events.

### Who gets a row, and what a zero means

A row exists for every player the events file places on the pitch: the
players in each team's Starting XI lineup and the players who come on
in a Substitution event. Team-sheet players who never enter get no row.

A zero means the file holds no qualifying event for such a player. It
says nothing about how long the player was on the pitch.

### Exclusions and diagnostics

- A qualifying event with no usable player or team is counted for no
  one and listed in `diagnostics.json`.
- A `counterpress` flag on an unsupported event type is excluded and
  listed. So is an offensive foul that carries the flag.
- A flag that is `false`, `null`, or not a boolean counts as not
  flagged and is listed. No value is coerced.
- The run stops, writing nothing, on a duplicate event id, a missing or
  malformed Starting XI, a player eligible for both teams, or a
  countable event from a player outside the eligible set.

### Why these are not pressing ratings

Each value counts what the provider's collectors recorded under the
provider's definitions. It does not measure how well, how hard, or how
usefully a player pressed, and it cannot see pressing that was not
logged. The counts are not normalized by playing time, because no
reliable rule for time on the pitch exists yet, so they cannot be
compared between players. They are classified as `derived`, and their
status is `implemented_unvalidated`: the code matches its contract, and
nothing more is claimed.

### Result for the final

29 eligible players. Totals over all players: 327 Pressure events, 57
of them flagged as counterpress, and 94 flagged events across the
supported types. No diagnostic was raised. These totals equal an
independent count of the source events.

## Querying the metrics with DuckDB

Run from the project root, after `phaselens metrics`. Neither command
needs the network.

```
uv run phaselens analytics --manifest manifests/statsbomb/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/match_3943043.json
uv run phaselens query --manifest manifests/statsbomb/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/match_3943043.json --name team-totals
```

`analytics` validates the metrics output, writes
`player_match_metrics.parquet` and `build_metadata.json` to
`data/processed/analytics/<commit_sha>/<match_id>/`, and reads the
Parquet file back to confirm every row equals the CSV. It changes no
metric value and never writes to the metrics folder.

`query` runs one fixed query: `player-rows`, `team-totals`,
`team-player-counts`, or `integrity-checks`. The SQL is in
`src/phaselens/sql/`. Arbitrary SQL is not accepted, and no query ranks
players.

Before a query reads the Parquet file, it checks the raw files against
the manifest, the metrics files against the hashes recorded at build
time, and the Parquet file against the SHA-256 and size recorded in
`build_metadata.json`. If anything is missing or differs, it stops
with an `error:` line and exit status 1. It never rebuilds or replaces
a file. Output built before these checksums existed must be rebuilt
with the `analytics` command.

There is no database file. Each command opens an in-memory DuckDB
connection over the Parquet file. Identical inputs give identical rows,
schema, and totals; identical Parquet bytes were observed here but are
not promised across DuckDB versions. Details, including what the
validation does and does not guarantee, are in the
[analytical layer](docs/analytical_layer.md) document.

## Pilots

```
uv run phaselens pilot --file pilots/euro2024_knockout_stage.json
uv run phaselens pilot-query --file pilots/euro2024_knockout_stage.json --name team-totals
```

`pilots/euro2024_knockout_stage.json` names the fifteen matches of the
Euro 2024 knockout stage (round of 16 to the final), chosen by stage
from the verified match list; the dashboard reads it. `pilot` runs them
one after another through the same per-match steps, then combines their
verified Parquet tables into one table of 468 player-match rows. The
original five-match pilot, `pilots/euro2024_knockout_pilot.json` (the
final, both semi-finals, and two quarter-finals; 156 rows), is kept
unchanged as the record of that earlier run. It stops at the first failing match, names the match
and the step, and builds no combined output in that run. A rerun
downloads nothing that is already verified on disk.

`pilot-query` runs one of four fixed pilot queries (`player-rows`,
`team-totals`, `team-player-counts`, `integrity-checks`). They keep
matches apart: a team or player has one row per match. Totals are raw
event counts, not normalized for playing time, number of matches, or
opportunities.

Selection rule, observed periods, verification, and limitations are in
the [analytical layer](docs/analytical_layer.md) document.

## Repository layout

| Path | Purpose | In Git |
|---|---|---|
| `src/phaselens/` | Python package: `fetch`, `statsbomb`, `ingest`, `profile`, `metrics`, `analytics`, `pilot`, `three_sixty`, `cli`, the dashboard modules `dashboard_data`, `dashboard_i18n`, `dashboard_pitch`, `dashboard_app`, and the SQL files in `sql/` | Yes |
| `.streamlit/config.toml` | Dashboard server settings (usage statistics off, local address) and colour theme | Yes |
| `pilots/` | Pilot definitions: which matches a pilot runs | Yes |
| `tests/` | pytest tests with synthetic fixtures | Yes |
| `docs/` | Project brief, data sources, schema profile, provider semantics, metric catalog, analytical layer | Yes |
| `manifests/` | Provenance records for downloaded data | Yes |
| `data/raw/` | Unmodified source files | No |
| `data/processed/` | Derived files: profile outputs, metric outputs, and the Parquet copy | No |
| `pyproject.toml`, `uv.lock` | Project definition and locked dependency versions | Yes |

Raw files are stored under a folder named after the upstream commit,
at their upstream path:

```
data/raw/statsbomb/open-data/<commit_sha>/data/competitions.json
data/raw/statsbomb/open-data/<commit_sha>/data/matches/<competition_id>/<season_id>.json
data/raw/statsbomb/open-data/<commit_sha>/data/lineups/<match_id>.json
data/raw/statsbomb/open-data/<commit_sha>/data/events/<match_id>.json
```

## Limitations

- Fifteen real matches have been ingested: the knockout stage of one
  tournament at one commit.
- A raw file that no manifest records is never adopted. If a run is
  killed between writing files and writing its manifest, the leftover
  files must be inspected and moved away by hand.
- `retrieved_at_utc` is the original retrieval time. Later
  verifications and restorations are not logged anywhere.
- Ingestion validates only that each file is a non-empty JSON array of
  objects.
- The written schema profile describes the final; the profiler ran on
  all fifteen matches, but their outputs are written up only for the
  elements listed in the schema profile. Fields and event types that did
  not occur are unobserved, not absent from the source.
- The profiler's checks test internal consistency, not whether events
  were logged correctly.
- Provider definitions were read from three 2019 specification
  documents at the pinned commit. They leave several questions open,
  including direction of play and the meaning of lineup position
  intervals; see [provider semantics](docs/provider_semantics.md). No
  newer provider documentation was consulted.
- The metrics are per-match counts for the fifteen pilot matches,
  without normalization by playing time, and are not validated for
  football meaning.
- Player eligibility uses the Starting XI and substitution events. It
  is the participation contract supported today, not a general rule,
  and it has been exercised on fifteen real matches.
- The analytical layer holds one table per match and one combined
  table per pilot. Its checks show
  that the Parquet file equals the metrics CSV, that the CSV agrees
  with its summary on counts and totals, and that files still have the
  bytes recorded for them. A CSV edit that keeps every team's totals
  can pass the build. Checksums are not signatures: none of this
  proves where a file came from.
- Three-sixty data has been retrieved for all fifteen matches and
  described in detail for the final only; per-match coverage is in
  [three-sixty frames](docs/three_sixty.md). Its positional entries carry no player identity beyond the
  actor, cover visible players at event moments, and say nothing about
  movement between events.
- Resolving the latest commit uses the unauthenticated GitHub API,
  which is rate limited. Passing `--commit` avoids that request.
- Fifteen knockout matches of one tournament support pipeline
  development, not conclusions about players or teams.

## Documentation

- [Project brief](docs/project_brief.md)
- [Data sources](docs/data_sources.md)
- [Schema profile](docs/schema_profile.md)
- [Provider semantics](docs/provider_semantics.md)
- [Metric catalog](docs/metric_catalog.md)
- [Analytical layer](docs/analytical_layer.md)
- [Three-sixty frames](docs/three_sixty.md)
- [Demo guide](docs/demo_guide.md)
- [Browser checklist](docs/browser_checklist.md)
- [Data model](docs/data_model.md)
- [Manifest format](manifests/README.md)

## Data source and attribution

Data comes from StatsBomb Open Data, published at
https://github.com/hudl/open-data (formerly
https://github.com/statsbomb/open-data).

It is not open-source data. Its user agreement describes the data as
provided for research and analysis, says it may not be redistributed or
commercially exploited, and requires published analysis to credit
StatsBomb with their logo. The raw files are therefore kept out of Git.

This is a reading of the published text, not a legal assessment.
Registration, the exact scope of the redistribution and commercial-use
terms, and the effect of the repository's move are unresolved; see
[data sources](docs/data_sources.md). Read the agreement itself before
publishing anything.
