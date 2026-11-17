# Metric catalog

The single register of every metric in PhaseLens. A metric does not
exist in code until it has an entry here.

**Status:** three event counts are implemented under contract
version 1. They are tested against that contract and are not validated
for football meaning.

## Columns

Each metric is written as its own table, one row per column, because
the cells are long.

| Column | Meaning |
|---|---|
| `metric_name` | Unique snake_case identifier, same as in code |
| `label` | Optional short human-readable name for tables and slides; not used in code |
| `description` | Optional one-sentence statement of what is counted |
| `grain` | What one output row describes |
| `required_data` | Source, files, and fields needed, confirmed to exist |
| `classification` | `observed`, `derived`, or `proxy` |
| `definition` | Exact computation, including every parameter |
| `eligibility` | Which rows exist, including when a zero is reported |
| `limitations` | What the metric does not capture or may misrepresent |
| `source_reference` | Provider documentation the definition relies on |
| `acceptance_cases` | Synthetic cases the implementation is tested against |
| `validation_status` | See below |

## Classification

- `observed`: recorded directly in the source data.
- `derived`: computed deterministically from observed values.
- `proxy`: an indirect indicator of something the data does not record.

## Validation status

| Status | Meaning |
|---|---|
| `hypothesis` | Proposed; not implemented |
| `implemented_unvalidated` | Code exists and is tested for correctness, not for meaning |
| `validated` | Checked against an independent reference, which is named in the entry |
| `rejected` | Found unsuitable; kept for the record with the reason |

A passing unit test proves the code matches the definition. It does not
validate the metric.

## Rules

1. Name a proxy for what it counts, not for what it stands in for.
2. Every threshold, window, or weight appears in `definition` as a named
   parameter and is a hypothesis until the entry says `validated`.
3. `required_data` lists only fields confirmed in the raw files.
4. No overall rating and no confidence score.

## Catalog

| metric_name | classification | validation_status |
|---|---|---|
| [`pressure_event_count`](#pressure_event_count) | `derived` | `implemented_unvalidated` |
| [`counterpress_pressure_event_count`](#counterpress_pressure_event_count) | `derived` | `implemented_unvalidated` |
| [`counterpress_flagged_event_count`](#counterpress_flagged_event_count) | `derived` | `implemented_unvalidated` |

All three are counts of events the provider recorded. Reading any of
them as pressing quality, intensity, or off-ball value would be a
`proxy` interpretation. That interpretation is not implemented and is
not claimed.

Exploratory event-level indicators from three-sixty frames are listed
separately, under
[Exploratory event-level indicators](#exploratory-event-level-indicators).

`implemented_unvalidated` means the code passes the acceptance cases
below and reconciles with an independent count of the source events.
It does not mean the counts have been shown to reflect anything about
how well a player presses.

## Implementation and outputs

Code: `src/phaselens/metrics.py`. Tests: `tests/test_metrics.py` for the
acceptance cases and `tests/test_metrics_real_data.py` for the
reconciliation with the ingested match.

```
uv run phaselens metrics --manifest <manifest_path>
```

The command verifies the raw files against the manifest, validates the
contract, and only then writes three files to
`data/processed/metrics/<commit_sha>/<match_id>/`. The same inputs
give the same bytes; no file holds a timestamp.

`player_match_metrics.csv` has one row per pair in `P(c, m)`, sorted
by `team_id` and then `player_id`. The order is not a ranking.

| Column | Content |
|---|---|
| `source_commit` | Upstream commit SHA of the inputs |
| `match_id` | Match id |
| `team_id` | Key: the team's id |
| `team_name` | Label: `team.name` of that team's Starting XI event |
| `player_id` | Key: the player's id |
| `player_name` | Label: the name beside the player's id in the first record that makes the pair eligible, in file order |
| `pressure_event_count` | Events, per the definition below |
| `counterpress_pressure_event_count` | Events, per the definition below |
| `counterpress_flagged_event_count` | Events, per the definition below: counterpress-flagged events within the supported types only |

Names are descriptive only. They are never used to match or join.

`diagnostics.json` lists every diagnostic with its count and event
ids. `run_summary.json` holds the contract version, source commit,
match id, verified input hashes, eligible player count, totals per
metric and per team, diagnostic totals, and the limitations.

## Shared contract (version 1)

The three metrics share everything in this section. Field meanings and
page references are in [provider semantics](provider_semantics.md).
Change this contract first, then the code, and raise the version.

### Notation

- `c`: upstream commit SHA. `m`: `match_id`.
- `E(c, m)`: the event objects in `data/events/<m>.json` at commit `c`,
  after the file has been verified against its manifest.
- For an event `e`: `type(e)` is `e.type.id`, `team(e)` is `e.team.id`,
  and `player(e)` is `e.player.id`.
- `cp(e)` is 1 when `e` has a top-level key `counterpress` whose JSON
  value is exactly `true`, and 0 in every other case.
- `off(e)` is 1 when `type(e) = 22` and `e.foul_committed.offensive` is
  exactly `true`, and 0 in every other case.
- `1[x]` is 1 when `x` holds and 0 otherwise.

### Grain

One row per `(c, m, t, p)`: source revision, match, team id, player id.
The team is the event's `team.id`. Ids are the keys; names are labels.
Rows are never summed across matches or revisions by these definitions.

### Counting unit

The unit is one event object. It is not a pressing episode, sequence,
or spell: consecutive events by one player are counted separately, and
one passage of play can produce several counted events.

### Event types

Types are matched on `type.id`, using the ids in the provider's
specification. The supported set of types for `counterpress` is:

`S = {17 Pressure, 4 Duel, 6 Block, 10 Interception, 22 Foul Committed, 33 50/50, 39 Dribbled Past}`

`S` is the set this contract supports. It is not claimed to be the
provider's complete list. An event with `counterpress` exactly `true`
whose type is outside `S` is excluded and reported in a diagnostic.

If an event's `type.name` is not the documented name for its id, the
event is still matched by id and a diagnostic is raised. This applies
to the seven types in `S` and to `35 Starting XI` and `19 Substitution`.

### Flag values

Only the JSON value `true` counts. No value is coerced, and general
truthiness is never used.

| `counterpress` on the event | `cp(e)` | Diagnostic |
|---|---|---|
| `true` | 1 | None |
| Key absent | 0 | None. The provider records the flag only when true. |
| `false` | 0 | Yes: explicit false is not expected |
| `null` | 0 | Yes |
| Anything else, such as `"true"` or `1` | 0 | Yes |

Counting an absent key as 0 states what the provider recorded. It is
not a claim that no counterpressing took place.

### Offensive fouls

The specification attaches `counterpress` to Foul Committed events that
are not offensive, and describes `foul_committed.offensive` as "added
if the foul was committed while in possession of the ball".

| `foul_committed.offensive` on a Foul Committed event | `off(e)` | Effect |
|---|---|---|
| `true` | 1 | Excluded from `counterpress_flagged_event_count`. If `counterpress` is also exactly `true`, a semantic-conflict diagnostic is raised. |
| Key absent | 0 | Not excluded, following the documented "added if" convention |
| `false`, `null`, or anything else | 0 | Not excluded; a diagnostic reports the unexpected value |

The last row is this project's assumption: the documents describe only
the value `true`. The source is never altered.

### Attribution

An event that passes a metric's conditions but has no usable
`player.id` or `team.id` belongs to no row. It is not counted for any
player and is reported in a diagnostic with its event id. For Pressure
events the specification says the player always has a value, so such
an event would indicate a source defect.

### Eligibility and zero rows

This is the participation contract supported today. It fits the files
profiled so far and is not a general rule for every football dataset.

The eligible set `P(c, m)` holds the `(t, p)` pairs that the events
file places on the pitch:

- every `player.id` in the `tactics.lineup` of a team's `Starting XI`
  event, with that event's `team.id`;
- every `substitution.replacement.id` of a `Substitution` event, with
  that event's `team.id`.

Repeated membership is deduplicated: a pair has one row however often
it is named.

A row exists for every pair in `P(c, m)` and for no one else. A value
is 0 when no event meets the metric's conditions. A zero says the file
holds no such event for a player it places on the pitch. It says
nothing about how long the player was on it.

Not used for eligibility: the team sheet in the lineups file, and
whether a player has counted events.

### Conditions that stop the run

Each stops the calculation with an error and no output files:

1. An event id occurs more than once, or an event has no usable id.
   Nothing is deduplicated.
2. The match record does not give two different integer team ids.
3. A match team does not have exactly one `Starting XI` event, or that
   event's `tactics.lineup` is not a non-empty array of entries that
   each have an integer `player.id`. The number of entries is not
   checked.
4. A `Starting XI` or `Substitution` event has a `team.id` that is not
   one of the match's two teams, or a `Substitution` event has no
   integer `substitution.replacement.id`.
5. One player id is eligible for both teams.
6. An event that would otherwise be counted belongs to a `(t, p)` pair
   outside `P(c, m)`. It is not dropped silently.
7. A raw input file is missing or differs from its manifest record.

### Diagnostics

Reported with a count and the event ids, in file order. None stops the
run.

| Diagnostic | Raised when |
|---|---|
| `unattributed_event` | An event passes a metric's conditions but has no usable `player.id` or `team.id` |
| `counterpress_true_outside_supported_types` | `counterpress` is exactly `true` on a type outside `S` |
| `counterpress_explicit_false` | `counterpress` is `false` |
| `counterpress_null` | `counterpress` is `null` |
| `counterpress_non_boolean` | `counterpress` holds any other value |
| `offensive_foul_with_counterpress` | A Foul Committed event has both flags exactly `true`; it is excluded |
| `offensive_flag_unexpected_value` | `foul_committed.offensive` is present on a Foul Committed event and is not exactly `true` |
| `type_name_differs_from_documented` | A matched type id carries another `type.name` |

### Not part of these definitions

No time window of our own, success label, per-90 or per-minute
normalization, rating, percentile, ranking, confidence score, or
minutes played. The only window involved is the provider's own
5 seconds inside the `counterpress` flag.

## pressure_event_count

| Column | Value |
|---|---|
| `metric_name` | `pressure_event_count` |
| `grain` | `(c, m, t, p)` |
| `required_data` | Events file: `id`, `type.id`, `type.name`, `team.id`, `player.id`. For eligibility: `tactics.lineup[].player.id` on Starting XI events and `substitution.replacement.id`. Match list: the two team ids. All confirmed in the ingested match; all fifteen pilot matches ran under the contract with no stop condition and no unattributed event. |
| `classification` | `derived` |
| `definition` | `sum over e in E(c, m) of 1[type(e) = 17] * 1[team(e) = t] * 1[player(e) = p]` |
| `eligibility` | Rows for `P(c, m)`; zero reported |
| `limitations` | Counts what collectors logged as a Pressure event under the provider's definition. No distance or intensity threshold is documented. Says nothing about pressing that was not logged, its effect, or team shape. Not comparable between players without time on the pitch, which is not available. Computed per match; the pilots cover five and fifteen knockout matches of one tournament. |
| `source_reference` | Events v4.0.0 p. 4 (type 17), p. 31 (duration); Spec v1.1 pp. 13, 29 |
| `acceptance_cases` | 1, 2, 4, 6, 7, 9, 10, 11, 12, 14 to 22, 26 |
| `validation_status` | `implemented_unvalidated` |

## counterpress_pressure_event_count

| Column | Value |
|---|---|
| `metric_name` | `counterpress_pressure_event_count` |
| `grain` | `(c, m, t, p)` |
| `required_data` | As `pressure_event_count`, plus the top-level `counterpress` key |
| `classification` | `derived` |
| `definition` | `sum over e in E(c, m) of 1[type(e) = 17] * cp(e) * 1[team(e) = t] * 1[player(e) = p]` |
| `eligibility` | Rows for `P(c, m)`; zero reported |
| `limitations` | Everything under `pressure_event_count`. The flag is the provider's: "pressing actions within 5 seconds of an open play turnover". Which team's turnover, and how the flag is set, are undocumented. It is a subset of Pressure events, not a count of counterpressing sequences. |
| `source_reference` | Events v4.0.0 pp. 1, 18, 30; Spec v1.1 p. 29 ("Recorded only when true") |
| `acceptance_cases` | 1, 2, 4, 6, 7, 9, 10, 11 |
| `validation_status` | `implemented_unvalidated` |

## counterpress_flagged_event_count

| Column | Value |
|---|---|
| `metric_name` | `counterpress_flagged_event_count` |
| `label` | Counterpress-flagged events — supported types |
| `description` | Count of counterpress-flagged events within the contract's supported event types, excluding offensive fouls. |
| `grain` | `(c, m, t, p)` |
| `required_data` | As `counterpress_pressure_event_count`, plus `foul_committed.offensive` |
| `classification` | `derived` |
| `definition` | `sum over e in E(c, m) of 1[type(e) in S] * cp(e) * (1 - off(e)) * 1[team(e) = t] * 1[player(e) = p]` |
| `eligibility` | Rows for `P(c, m)`; zero reported |
| `limitations` | Adds up events of seven different kinds, from pressures to fouls, so a total hides its mix. One passage of play can contribute several events for one player. `S` is the supported set and may not be the provider's complete list; a flagged event of any other type is excluded and reported. Not a count of counterpressing sequences. |
| `source_reference` | Events v4.0.0 pp. 1, 9 to 12, 18, 30; Spec v1.1 pp. 14 to 18, 29 |
| `acceptance_cases` | 2, 3, 4, 5, 6, 7, 8, 10, 11, 13, 23, 24, 25 |
| `validation_status` | `implemented_unvalidated` |

For every row:
`0 <= counterpress_pressure_event_count <= pressure_event_count` and
`counterpress_pressure_event_count <= counterpress_flagged_event_count`.

### Scope observed in the five-match pilot

The identifier says "flagged events", but the metric does not count
every flagged event. In the five matches of the pilot:

| Events with `counterpress` exactly `true` | Count |
|---|---|
| In the events files | 425 |
| Included by this metric | 420 |
| Excluded: offensive fouls | 0 |
| Excluded: type outside `S` | 5 |

All five excluded events are `Pass` events (type 30) with
`pass.type.name` "Interception": one in match 3942752, two in 3942819,
two in 3942226. The `counterpress_true_outside_supported_types`
diagnostic of each match lists their event ids.

What the flag means on these events is unresolved; see
[provider semantics](provider_semantics.md). They are not treated as
annotation errors, and nothing here implies that every interception
pass should carry the flag.

All of these figures count events, not unique pressing episodes.

## M12: 15-match knockout-stage dataset

Milestone 12 adds a second pilot, `pilots/euro2024_knockout_stage.json`:
the fifteen matches of the Euro 2024 knockout stage, the original five
included. It runs the same contract (version 1) through the same code.
No metric definition, calculation, aggregation rule, verification rule,
or dashboard metric changed. The fifteen-match dataset is an additional
dataset for validation and coverage checks, and the one the dashboard
reads; it does not replace the original pilot and does not alter what
any metric means.

Verified totals of the combined fifteen-match table (from the pilot run
and the fixed pilot queries; integrity checks: 0 violations):

| Item | Value |
|---|---|
| Knockout-stage matches | 15 |
| Player-match rows | 468 |
| `pressure_event_count`, all rows | 4,345 |
| `counterpress_pressure_event_count`, all rows | 812 |
| `counterpress_flagged_event_count`, all rows | 1,370 |

These sums over all rows check the combined table against the per-match
outputs. They are not team or player totals: the definitions above never
add rows across matches, and the pilot queries keep matches apart.

For `counterpress_flagged_event_count`, the same breakdown as in the
five-match pilot:

| Events with `counterpress` exactly `true` | Count |
|---|---|
| In the events files | 1,405 |
| Included by this metric | 1,370 |
| Excluded: offensive fouls | 0 |
| Excluded: type outside `S` | 35 |

All 35 excluded events are `Pass` events with `pass.type.name`
"Interception", as in the five-match pilot, and no `counterpress` value
other than `true` occurred.

Unchanged: `pressure_event_count`, `counterpress_pressure_event_count`,
and `counterpress_flagged_event_count`, with their grain and
eligibility; the rule that rows are never summed across matches; the
contract checks that stop a run; and the dashboard's calculations and
presentation rules.

The fifteen matches contain provider data elements that none of the
original five contains: the event types `Own Goal Against` and
`Own Goal For`, and the keys `shot.saved_to_post`,
`shot.saved_off_target`, `shot.open_goal`, `shot.follows_dribble`,
`goalkeeper.shot_saved_to_post`, `goalkeeper.penalty_saved_to_post`, and
`goalkeeper.shot_saved_off_target`. They are observed data elements, not
metrics. The metric contract and the dashboard's calculations do not use
them. Where and how often they occur is in the
[schema profile](schema_profile.md).

The original five-match pilot, `pilots/euro2024_knockout_pilot.json`, is
unchanged. Its matches' source files, manifests, and outputs kept their
bytes when the fifteen-match pilot ran, and its totals still hold:
156 player-match rows; 1,425 / 244 / 420 for the three counts; 0
integrity violations. The five-match figures in "Scope observed in the
five-match pilot" stay as recorded.

## Exploratory event-level indicators

Context definition version 1. Implemented in
`src/phaselens/three_sixty.py`, written by `phaselens three-sixty-context`
to `data/processed/three_sixty/<commit_sha>/<match_id>/spatial_context.csv`,
and tested in `tests/test_three_sixty_context.py`. These are not player
metrics: they describe the visible surroundings of one event's actor,
and nothing here aggregates them per player.

| Column | Value |
|---|---|
| `grain` | One row per source event `(c, m, event_id)`; duplicate event ids stop the run |
| `required_data` | Events file: `id`, `index`, `period`, `type`, `team.id`, `player.id`, `location`. Three-sixty file: `event_uuid`, `freeze_frame[]` with `location`, `teammate`, `actor`, `keeper`; `visible_area`. Confirmed in the final |
| `classification` | `derived`. Reading them as pressure, support, or positioning quality would be a `proxy` interpretation, not implemented |
| `source_reference` | 360 Frames v1.0.0 pp. 1–3; see [three-sixty frames](three_sixty.md) |
| `validation_status` | `implemented_unvalidated` |

### Definitions

For a source event with exactly one linked frame:

- A valid point is a list of exactly two finite numbers. Booleans,
  strings, NaN, and infinity are not numbers here; nothing is coerced.
- The frame's actor `a` is its one entry whose `actor` is exactly
  `true`. `actor` must be an exact boolean on every entry.
- `E` is every other entry whose `location` is a valid point and whose
  `teammate` is an exact boolean. Other entries are excluded and
  counted.
- `d(e) = hypot(e.x − a.x, e.y − a.y)`, in source units.
- Teammates `T = {e ∈ E : teammate = true}`; opponents
  `O = {e ∈ E : teammate = false}`. The provider defines `teammate` as
  playing on the actor's team. Keepers are counted by this flag like
  anyone else.

| Indicator | Definition |
|---|---|
| `nearest_visible_opponent_distance` | `min d(e)` over `O`: the nearest valid, observed opponent entry included in the calculation. Null when `O` is empty |
| `visible_teammates`, `visible_opponents` | `|T|`, `|O|` |
| `visible_teammates_within_{R}u` | `|{e ∈ T : d(e) <= R}|` |
| `visible_opponents_within_{R}u` | `|{e ∈ O : d(e) <= R}|` |

Parameters: `R` ∈ {5, 10, 20} source units, boundary inclusive. They
are exploratory, not validated, and the units are not asserted to be
metres. Radii must be finite, positive, and unique.

### Status and missing values

| `calculation_status` | When | Indicators |
|---|---|---|
| `computed` | One frame, unambiguous single actor with a valid location | Filled |
| `no_frame` | No frame links to the event | Null |
| `duplicate_frames` | More than one frame links to the event | Null |
| `freeze_frame_malformed` | `freeze_frame` is not a list | Null |
| `actor_selection_ambiguous` | An entry is not an object, or its `actor` is not an exact boolean | Null |
| `no_actor`, `multiple_actors` | Zero or several entries with `actor` true | Null |
| `actor_location_invalid` | The actor's `location` is not a valid point | Null |

- `frame_available` separates an event without a frame from a frame
  with zero observed neighbours. Null means not computed; 0 means
  computed and none counted.
- Uncomputed rows keep the event's identity and location. Only fields
  that can be established are filled; for example, `visible_entries` is
  set when `freeze_frame` is a list.
- `entries_excluded_from_context` counts distinct excluded entries, and
  `context_has_excluded_entries` marks computed rows that have any.
  Zero counts on such a row mean no qualifying valid entry, not a fully
  measured frame.
- `entries_location_invalid` and `entries_teammate_flag_invalid` can
  overlap: one entry with both problems counts in both. Their sum is
  not a count of distinct entries.

### Diagnostic fields, never filters

- `actor_event_distance`: actor position against the event's
  `location`; null when the event has no valid location. A large value
  is not treated as an error and does not exclude the row.
- `actor_outside_frame_convention`, `entries_outside_frame_convention`:
  points outside 0–120 × 0–80, the pitch frame drawn in Events v4.0.0.
  Such points are kept in every calculation, not clamped or flipped.
- `visible_opponent_keeper_entries`: included opponent entries with
  `keeper` true. The 360 specification notes that, rarely, a keeper
  flag refers to the actor's own keeper without `teammate` being set.
- `visible_area_status`: shape only (`closed_numeric`, `missing`,
  `empty`, `malformed`); the area is not used in any calculation.

### Limitations

- Frames show visible players at event moments. Counts are of observed
  entries, not full teams, and an unobserved player is not absent.
- Radius circles can extend past the visible area; there is no
  visibility correction.
- Entries carry no identity beyond the actor, so no neighbour is
  attributed to a named player.
- Computed for each of the fifteen knockout-stage matches; the
  observations in section B of [three-sixty frames](three_sixty.md) are
  for the final only. No aggregation into player scores, rankings, or
  per-90 values.

## Acceptance cases

Synthetic events for one eligible player, unless the case says
otherwise. A, B, and C are the contributions to
`pressure_event_count`, `counterpress_pressure_event_count`, and
`counterpress_flagged_event_count`.

| Case | Input | A | B | C | Outcome |
|---|---|---|---|---|---|
| 1 | Pressure, no `counterpress` key | 1 | 0 | 0 | Counted |
| 2 | Pressure, `counterpress: true` | 1 | 1 | 1 | Counted |
| 3 | Duel, `counterpress: true` | 0 | 0 | 1 | Counted |
| 4 | Pressure, `counterpress: true`, no `player` | 0 | 0 | 0 | Diagnostic: unattributed event |
| 5 | Pass, `counterpress: true` | 0 | 0 | 0 | Diagnostic: flag outside `S` |
| 6 | Pressure, `counterpress: false` | 1 | 0 | 0 | Diagnostic: explicit false |
| 7 | Pressure, `counterpress: null` | 1 | 0 | 0 | Diagnostic: null flag |
| 8 | Duel, no `counterpress` key | 0 | 0 | 0 | Not counted |
| 9 | Pressure, `counterpress: "true"` or `1` | 1 | 0 | 0 | Diagnostic: non-boolean flag |
| 10 | Two events sharing one `id` | | | | Run stops |
| 11 | Starting player with no qualifying event | 0 | 0 | 0 | Zero row |
| 12 | Player only on the team sheet | | | | No row |
| 13 | Foul Committed, both flags `true` | 0 | 0 | 0 | Excluded; diagnostic: semantic conflict |
| 14 | `type.id` 17 with another `type.name` | 1 | 0 | 0 | Diagnostic: name differs |
| 15 | Substitution replacement with no qualifying event | 0 | 0 | 0 | Zero row |
| 16 | Player named twice for the same team | | | | One row |
| 17 | A match team without a Starting XI event | | | | Run stops |
| 18 | Starting XI with an empty or malformed lineup | | | | Run stops |
| 19 | Two Starting XI events for one team | | | | Run stops |
| 20 | One player id eligible for both teams | | | | Run stops |
| 21 | Pressure by a player outside `P(c, m)` | | | | Run stops |
| 22 | Pass by a player outside `P(c, m)` | 0 | 0 | 0 | No row and no error |
| 23 | Foul Committed, `counterpress: true`, no `offensive` key | 0 | 0 | 1 | Counted |
| 24 | Foul Committed, `offensive: true`, no `counterpress` key | 0 | 0 | 0 | Not counted, no diagnostic |
| 25 | Foul Committed, `counterpress: true`, `offensive: false` | 0 | 0 | 1 | Counted; diagnostic: unexpected value |
| 26 | Event without a usable `id` | | | | Run stops |

Cases 6, 7, 9, and 25 have not been seen in real data. They define
what happens if a future input contains them.
