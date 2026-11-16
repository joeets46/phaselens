# PhaseLens project brief

## Vision

Evaluate players' off-ball contributions across phases of play:

- Defensive transitions and counterpressing
- Pressing involvement
- Off-ball attacking movement and support
- Defensive positioning
- Physical metrics such as sprints, only when suitable data exists

This is the long-term direction. None of it is implemented.

## Current state

Milestones 0 to 11 are complete; M12 is in progress. The first
match ingested from StatsBomb Open Data, and the one most of the
documentation describes, is UEFA Euro 2024, Spain v England, 2024-07-14 (`match_id` 3943043),
read at upstream commit `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`.

Its match list, lineups, and events files have been profiled; the
findings are in the [schema profile](schema_profile.md). The provider's
specification was read for the fields the first metrics need; see
[provider semantics](provider_semantics.md). Three event counts are
implemented under the contract in the
[metric catalog](metric_catalog.md) and written as CSV and JSON. Their
status is `implemented_unvalidated`: tested against the contract, not
validated for football meaning. There is no rating, ranking, or
normalization by playing time.

The same counts are stored as one typed Parquet table and can be
queried with DuckDB through four fixed queries; see the
[analytical layer](analytical_layer.md). That layer changes no value.

A five-match pilot (the final, both semi-finals, and two quarter-finals
of Euro 2024, same commit) runs each match through the same steps and
combines the results into one table of 156 player-match rows. The
profile, metrics, and Parquet output of each match stay separate.

In M12 a second pilot, `pilots/euro2024_knockout_stage.json`, extends
this to the fifteen matches of the Euro 2024 knockout stage, chosen by
stage from the verified match list: 468 player-match rows, with
three-sixty data stored for all fifteen. The five-match pilot is kept
unchanged; its matches' files and outputs did not change. The dashboard
reads the fifteen-match pilot.

A local, read-only dashboard was completed in M9: it shows the pilot
results and the final's three-sixty frames and spatial context from
verified data, and never downloads or writes. M10 polished its
presentation only (layout, formatting, accessibility, and
documentation) and added no analytical feature. M11 added a read-only
`dashboard-check` command, a repeatable
[browser checklist](browser_checklist.md), a five-match Overview test,
new-user documentation, and selections that survive language changes;
it added no metric, data source, or analytical feature. See the
[demo guide](demo_guide.md).

## Starting point

A small local pipeline over one match. The goal of the first milestones
is to learn what the data contains, not to produce metrics.

## Data tiers

What each kind of data could support. Rows describe the data type in
general; what a specific source contains must be confirmed by inspection.

| Tier | What it records | What it cannot support |
|---|---|---|
| Event data | Discrete on-ball and some defensive actions, with time and location | Continuous movement, speed, positioning of players not involved in the event |
| Event data with positional snapshots | Positions of some players at the moment of an event | Movement between events, speed, full-pitch coverage |
| Tracking data | Positions of all players many times per second | Depends on provider; none in the project yet |

For the final, the three-sixty file has been retrieved and described
(Milestone 7): it holds positions of visible players at 2,882 of the
3,304 event moments, without player identities beyond the event's
actor. See [three-sixty frames](three_sixty.md).

## Metric classification

- **Observed:** a value recorded directly in the source data.
- **Derived:** computed deterministically from observed values, with no
  claim beyond them.
- **Proxy:** an indirect indicator standing in for something the data
  does not record. A proxy always carries a stated limitation.

## Architecture

| Layer | Location | Rule | State |
|---|---|---|---|
| Raw | `data/raw/` | Byte-for-byte copies of source files, never modified, not committed | Working |
| Provenance | `manifests/` | Records of where each raw file came from, committed | Working |
| Profile | `data/processed/profiles/` | Descriptive counts of a match's files, rebuildable from raw, not committed | Working |
| Metrics | `data/processed/metrics/` | Catalogued event counts per player as CSV and JSON, rebuildable from raw, not committed | Working |
| Analytical | `data/processed/analytics/` | One typed Parquet table of the metrics, queried with in-memory DuckDB, rebuildable, not committed | Working |

Every file of a run is read at one upstream commit SHA, never from a
moving branch, and is stored under a folder named after that commit.

Source-specific code is intended to stay separate from metric code, so
a tracking provider can be added later without rewriting metrics.

## Milestones

Each milestone starts only after explicit approval.

| ID | Goal | Done when | Status |
|---|---|---|---|
| M0 | Project skeleton | Repository, environment, and a passing test exist | Complete |
| M1 | Ingest one match | Metadata, lineups, and events are stored raw with a manifest | Complete |
| M2 | Inspect the event schema | Schema notes are written from the actual files | Complete |
| M3 | Choose answerable questions | First candidate rows are in the metric catalog | Complete |
| M4 | Initial metric implementation | The catalogued event counts are computed to CSV and JSON and reconcile with the source | Complete |
| M5 | Analytical storage | The player-match metrics are queryable in DuckDB via typed Parquet | Complete |
| M6 | Five-match pilot | Five matches run through the same pipeline and combine into one verified table | Complete |
| M7 | Three-sixty exploration | The final's three-sixty file is stored with provenance and its linkage, coverage, and structure are reported | Complete |
| M8 | Event-level spatial context | One row per event of the final with nearest-opponent distance and radius counts of visible players around the actor | Complete |
| M9 | Local dashboard | A read-only local app shows the pilot results and the final's frames and context from verified data | Complete |
| M10 | Dashboard presentation polish | UI/UX, formatting, radius-label placement, responsive layout, accessibility, and documentation are improved, with no new analytical feature | Complete |
| M11 | Dashboard usability, repeatability, and documentation | A read-only `dashboard-check` command, a repeatable browser checklist, a five-match Overview test, selections kept through language changes, and new-user documentation exist, with no new metric, data source, or analytical feature | Complete |
| M12 | Euro 2024 knockout stage | The fifteen knockout-stage matches are ingested and verified with their three-sixty data, and the dashboard, its checks, and the documentation cover them, with no new metric or analytical feature | In progress |

## Non-goals for now

- Overall player rating or confidence score
- Sprint, recovery-run, or distance metrics from event data
- Machine learning, orchestration, cloud infrastructure
- Hosted or shared dashboards (the local, read-only dashboard was
  completed in M9)

## Known limitations

- Five knockout matches support pipeline development, not conclusions
  about players.
- Event data is collected by human annotators using provider
  definitions; those definitions bound what any metric can mean.
- No parameter in this project has been validated against tracking data
  or expert judgement.
- The source data may not be redistributed or used commercially, and
  published analysis must credit StatsBomb. See
  [data sources](data_sources.md).
- Totals across matches are raw event counts, not normalized for
  playing time, number of matches, or opportunities.

- The schema is known from one match only. Provider definitions come
  from 2019 documents that do not cover every field in the files.
- The implemented metrics are event counts without any normalization
  by playing time, computed for one match, and not validated for
  football meaning.

## Open questions

- The questions the provider's documents leave unresolved, listed in
  [provider semantics](provider_semantics.md).
- What would count as validating the event counts, and against what
  reference?
- Which of the three-sixty questions marked "potentially supported" in
  [three-sixty frames](three_sixty.md) are worth pursuing, and with
  which explicit assumptions?
- Which vision areas can event data address at all, even as a proxy?
