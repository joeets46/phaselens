# Schema profile: one match

What the locally stored files of one match contain, as counted by
`phaselens profile`. Every number below comes from that command's
output. Nothing here is a metric, and nothing generalises beyond this
match.

Observations and meanings are kept apart. Everything in this document
is an observation from the files, except passages that begin with
"Documentation:". Those were added in Milestone 3 and state what the
provider's specification says; the references are in
[provider semantics](provider_semantics.md).

## Input and command

| Item | Value |
|---|---|
| Match | UEFA Euro 2024, Spain v England, 2024-07-14 (`match_id` 3943043) |
| Upstream commit | `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb` |
| Inputs | The match list, lineups, and events files recorded in the manifest |
| Not used | Three-sixty data (not downloaded) |

```
uv run phaselens profile --manifest manifests/statsbomb/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/match_3943043.json
```

The command first checks each raw file's SHA-256 and size against the
manifest, makes no network request, and writes four files to
`data/processed/profiles/<commit_sha>/<match_id>/`:

| File | Content |
|---|---|
| `summary.json` | Counts, time and possession observations, list and coordinate fields, off-ball-relevant data, lineups |
| `event_types.csv` | One row per event type |
| `field_presence.csv` | Non-null, null, and missing counts per field path, overall and per event type |
| `quality_findings.json` | Result of each consistency check |

The outputs are not in Git. Running the command again reproduces them
byte for byte.

## Event structure

- 3,304 events in 27 event types; 2,015 for Spain and 1,289 for England.
- Two periods: 1,694 events in period 1 and 1,610 in period 2.
- `id` is a string on every event, and all 3,304 are distinct.
- `index` runs from 1 to 3,304 without gaps, in file order.
- 19 field paths are on every event: `id`, `index`, `period`,
  `timestamp`, `minute`, `second`, `type`, `team`, `possession`,
  `possession_team`, `play_pattern`, and their `id`/`name` children.
- `player` and `position` are on 3,289 events. The 15 without belong to
  five types in which no event has a player (Half Start, Half End,
  Starting XI, Tactical Shift, Referee Ball-Drop).
- No field in the events file ever holds an explicit null. A field is
  either present with a value or missing.

Documentation: the `player` object is present only when an event is
tied to a specific player, so its absence on those 15 events is by
design.

Largest event types: Pass 915, Ball Receipt* 876, Carry 757,
Pressure 327, Ball Recovery 69, Duel 68. The full list is in
`event_types.csv`.

### Time

- `timestamp` is a string of the form `HH:MM:SS.mmm` on every event.
  It restarts at `00:00:00.000` in each period.
- `minute` and `second` are integers. They do not restart: in period 2
  they equal the timestamp plus 2,700 seconds on every event, and in
  period 1 they equal the timestamp.
- Period 1 runs to `00:47:02.704` (`minute` 47) and period 2 starts at
  `minute` 45, so minutes 45 to 47 occur in both periods. A minute and
  second pair identifies a moment only together with `period`.

Documentation: `minute` is the clock minute and "resets to 45 at
half-time, 90 at the start of extra time". `period` is "the part of
the match the timestamp relates to".

### Possession

- `possession` is an integer on every event, with 147 distinct values
  from 1 to 147, and it never decreases in file order.
- It changes 146 times between consecutive events. In 96 of those the
  `possession_team` also changes; in 50 it does not. A new possession
  number is therefore not the same thing as a change of team.
- On 571 events `team` differs from `possession_team`.

Documentation: a new possession "can begin even if the same team has
possession of the ball", for example after a blocked pass goes out for
that team's throw-in. `possession_team` is the team that started the
possession and appears on the opposition's events too. Both
observations above follow from this.

## Field availability by event type

`field_presence.csv` has 1,039 rows: 165 field paths over all events
and 874 rows scoped to one event type. Each row gives its denominator,
which is the number of events in its scope. Within a type, only paths
seen in that type are listed. A field that only other types carry is a
structural absence, not a defect.

Selected types, with fields beyond the 19 common ones. The number after
a field is how many events of that type carry it:

| Event type | Events | Type-specific or optional fields |
|---|---|---|
| Pressure | 327 | `duration` 327, `location` 327, `related_events` 307, `counterpress` 57 |
| Ball Recovery | 69 | `related_events` 32, `under_pressure` 12, `ball_recovery.recovery_failure` 3 |
| Duel | 68 | `duel.type` 68, `under_pressure` 68, `duel.outcome` 35, `counterpress` 21 |
| Clearance | 42 | `under_pressure` 42, `related_events` 29 |
| Block | 41 | `related_events` 33, `counterpress` 9 |
| Dribbled Past | 11 | `related_events` 11, `counterpress` 4 |
| 50/50 | 8 | `50_50.outcome` 8, `under_pressure` 8 |
| Interception | 5 | `interception.outcome` 5, `counterpress` 2 |
| Carry | 757 | `carry.end_location` 757, `under_pressure` 258 |
| Ball Receipt* | 876 | `under_pressure` 69, `ball_receipt.outcome` 105; no `duration` |

## Coordinates

Fields are found by name (`location` or `*_location`). The list-field
table in `summary.json` confirms these are the only all-numeric lists.

| Field path | Values | List length | Observed range per component | Event types |
|---|---|---|---|---|
| `location` | 3,278 | 2 | 0.6 to 120.0; 0.1 to 80.0 | 21 types; absent from 26 events of 6 types |
| `pass.end_location` | 915 | 2 | 2.0 to 120.0; 0.1 to 80.0 | Pass |
| `carry.end_location` | 757 | 2 | 3.0 to 118.2; 1.1 to 78.2 | Carry |
| `shot.end_location` | 25 | 2 (10 values), 3 (15 values) | 92.2 to 120.0; 29.3 to 49.3; 0.1 to 5.0 | Shot |
| `goalkeeper.end_location` | 16 | 2 | 1.0 to 13.4; 30.4 to 47.3 | Goal Keeper |
| `shot.freeze_frame[].location` | 325 in 25 events | 2 | 81.3 to 119.7; 1.2 to 69.0 | Shot |

Directly observed: every coordinate is a list of floats, and none has
an unexpected shape.

Not established by these files: pitch dimensions, units, the origin,
whether direction of play is normalised, and what the third component
of `shot.end_location` is. Observed minima and maxima do not settle
any of these.

Documentation: the specification's pitch figure runs from (0,0) at the
top left to (120,80) at the bottom right, with goals on x = 0 and
x = 120. The third component of `shot.end_location` is the height in
the goal frame, which the figure labels up to 2.67. Units and direction
of play are not stated explicitly and remain unresolved.

## Off-ball-relevant data

Each row states what the file records, not what the provider's
definition is. Definitions need provider documentation.

| Name or path | Occurrences | What it directly records | What it does not establish |
|---|---|---|---|
| Event type `Pressure` | 327 events | That a pressure was logged for a player and team, with time, location, and `duration` | Pressing quality or intensity, its effect, distance to the opponent, pressures that were not logged, team shape |
| `counterpress` | 94 events: Pressure 57, Duel 21, Block 9, Dribbled Past 4, Interception 2, Foul Committed 1 | A flag, only ever `true`, on events of six types | The rule behind the flag; that an unflagged event was not a counterpress; team-level counterpressing |
| `under_pressure` | 712 events in 13 types, largest Carry 258, Pass 174 | A flag, only ever `true`, on some events of those types | Who applied the pressure, how close, or for how long. It is on every Duel, Clearance, Dribble, Dispossessed, 50/50, and Shield event, so it may be set by rule for some types |
| Event type `Ball Recovery` | 69 events; `ball_recovery.recovery_failure` on 3 | That a recovery was logged for a player at a time and location | How the ball became loose, or what the player did beforehand |
| Event type `Interception` | 5 events; `interception.outcome.name` on all | The logged interception and one of three outcome labels | Anticipation or positioning before the event |
| Event type `Duel` | 68 events; `duel.type.name` Tackle 35, Aerial Lost 33; `duel.outcome.name` on 35 | The duel type, and an outcome label on about half | Why 33 duels have no outcome; contests that were not logged as duels |
| Event types `Block`, `Clearance`, `Dribbled Past`, `50/50` | 41, 42, 11, 8 events | That the action was logged, with player, time, and location | Anything about the player outside the moment of the event |
| `possession`, `possession_team` | Every event | A possession number and the team credited with it | A rule for when a possession starts or ends |
| `related_events` | 3,192 events; 4,934 references | Ids of other events in the same file; every reference resolves | The kind of relation. 1,514 references are not returned by the target event |
| `shot.freeze_frame` | 25 shots; 325 entries with `location`, `player`, `position`, `teammate` | Where listed players were at the moment of a shot | Positions at any other moment; whether every player is listed |

Of the 327 Pressure events, 289 have a `team` different from
`possession_team` and 38 do not. Linked event types for Pressure are
mostly Carry (266), Pass (158), and Ball Receipt* (69).

Documentation: a Pressure event records "applying pressure to an
opposing player who's receiving, carrying or releasing the ball".
`counterpress` marks "pressing actions within 5 seconds of an open play
turnover" on seven documented event types and is recorded only when
true. `under_pressure` is computed by the provider from overlapping
pressure events and from the event's type, which is why whole types
carry it. A shot freeze frame lists "relevant players", not necessarily
all of them.

### What these files cannot measure

- Continuous position, speed, distance covered, sprints, or running
  intensity. A player's location exists only where an event was logged
  for that player, plus the shot freeze frames.
- Runs, support movement, or defensive positioning that produced no
  logged event.
- Pressing as a whole. Pressure events are what annotators logged
  under the provider's definition.

## Lineups and participation

The lineups file has one entry per team with `team_id`, `team_name`,
and `lineup`. Each of the 50 listed players (Spain 24, England 26) has
`player_id`, `player_name`, `player_nickname` (null for 26),
`jersey_number`, `country`, `cards`, and `positions`.

| What | Where | Observed |
|---|---|---|
| Identity and team | Lineup entries; `player.id` and `team.id` on events | Every event player is listed in that team's lineup |
| Starting lineups | `Starting XI` events with `tactics.lineup`; position intervals with `start_reason` "Starting XI" | 2 events of 11 players; 22 intervals; both sources name the same players |
| Substitutions | `Substitution` events with `substitution.replacement` and `substitution.outcome`; intervals with "Substitution - On/Off" reasons | 7 events (Tactical 6, Injury 1); 7 "On" and 7 "Off" intervals |
| Position changes | `Tactical Shift` events with `tactics`; intervals with reason "Tactical Shift" | 3 events; 10 intervals start and 10 end with that reason |
| Position intervals | `positions[]`: `position`, `from`, `to`, `from_period`, `to_period`, `start_reason`, `end_reason` | 39 intervals; `from` is an `MM:SS` string on all; `to` and `to_period` are null on 22; `end_reason` is "Final Whistle" on 22 |
| Cards | `cards[]` in lineups; `foul_committed.card.name` on events | 4 cards in each source, all "Yellow Card" |
| Dismissals | Not observed: no other card value and no dismissal reason appears | Their representation is unknown |
| Period boundaries | `Half Start` and `Half End` events, one per team and period | Period ends at `00:47:02.704` and `00:49:01.689` |

29 listed players have at least one position interval and 21 have
none. The same 29 are exactly the players who appear in events. The
files do not say why the other 21 have no interval, so a listed player
must not be assumed to have taken part.

Documentation: the lineups specification describes `lineup` as the
"players on the team sheet". It does not describe `positions` or
`cards` at all, so the meaning of a position interval is undocumented.
The events specification lists "Second Yellow" and "Red Card" card
values and `Player Off` and `Player On` event types; none occurs here.

### Prerequisites for minutes played

No minutes were calculated. A reliable calculation would need the
position intervals and the period boundary events above, plus rules
that these files do not supply:

1. How to turn an interval's `MM:SS` and `from_period` into elapsed
   time, given that the minute clock repeats 45 to 47 across periods.
2. What end time a null `to` stands for. The period 2 `Half End`
   timestamp is the obvious candidate but is not stated.
3. Whether stoppage time counts, and how it is bounded.
4. How dismissals, extra time, and penalty shoot-outs appear. None is
   observed in these files.
5. How to combine a player's several intervals, which are split at
   each tactical shift.
6. What to do if the two teams' `Half End` events disagree. They agree
   here.

## Quality findings

18 checks ran: 13 found nothing, 1 is an expected structural absence,
and 4 are unresolved observations. There were no errors or warnings.

| Category | Check | Count | Of |
|---|---|---|---|
| pass | Duplicate event ids; events without an id | 0 | 3,304 events |
| pass | Event team not one of the match's two teams | 0 | 3,304 events |
| pass | Event player not in that team's lineup | 0 | 3,289 events |
| pass | Events without a player, in types that usually have one | 0 | 3,304 events |
| pass | Related event id not in the file | 0 | 4,934 references |
| pass | Coordinate that is not a list of 2 or 3 numbers | 0 | 5,316 values |
| pass | Timestamp not in `HH:MM:SS.mmm` form; period going backwards in file order | 0 | 3,304 events |
| pass | Timestamp, minute and second, or index going backwards within a period | 0 | 3,302 consecutive pairs |
| pass | Starting XI event differs from lineup intervals | 0 | 2 teams |
| expected absence | Events without a player, in types that never have one | 15 | 3,304 events |
| unresolved | Coordinates with a third component | 15 | 5,316 values |
| unresolved | Boolean fields that only ever hold `true` | 33 | 33 boolean fields |
| unresolved | References not returned by the target event | 1,514 | 4,934 references |
| unresolved | Listed players without a position interval | 21 | 50 players |

Limits of these checks:

- They test internal consistency, not correctness. Whether an event
  happened as logged cannot be checked from the files.
- "Expected" is judged from this match alone: a type counts as never
  having a player because none of its events here has one.
- The coordinate check uses a working expectation of two or three
  numbers, not a provider rule.
- All 33 boolean fields only hold `true`. What a missing flag means
  differs by field and is set out in
  [provider semantics](provider_semantics.md); there is no single rule.

Documentation explains two of the four unresolved rows: the third
coordinate component is the goal-frame height, and several flags are
documented as recorded only when true. The profiler still reports them
as unresolved because its code was not changed in Milestone 3.

## Questions for provider documentation

These were raised in Milestone 2. Three of the upstream format
documents were read in Milestone 3; answers and page references are in
[provider semantics](provider_semantics.md).

| Question | Status after Milestone 3 |
|---|---|
| Coordinate origin and extent; third component of `shot.end_location` | Resolved from the specification's figures |
| Coordinate units; direction of play | Unresolved: not stated explicitly |
| Definitions of a Pressure event, `counterpress`, and `under_pressure` | Resolved; `under_pressure` is derived by rule |
| Whether a missing boolean flag means false | Answered per field; unresolved for `off_camera`, weaker for `under_pressure` |
| When `possession` increments; `possession_team` against `team` | Resolved, except the exact rule for "established control" |
| Why many `related_events` links are one-directional | Unresolved |
| What `duration` means per event type; why Ball Receipt* has none | Partly: "the length in seconds the event lasted", "if relevant" |
| Clock of lineup `from` and `to`; meaning of a null `to` | Unresolved: lineup `positions` are undocumented |
| Whether every player is in a shot freeze frame | Resolved: "relevant players" only |

## Candidate questions for Milestone 3

These were questions to assess, not metrics. The first two led to the
three event counts in the [metric catalog](metric_catalog.md), which
are now implemented with status `implemented_unvalidated`: tested
against their contract, not validated for football meaning. The other
questions remain open.

- Can logged Pressure events be counted per player in a way that is
  honest about being a count of logged events?
- Can `counterpress`-flagged events be related to the preceding change
  of possession without knowing the provider's rule?
- What can `related_events` say about which action a pressure was
  applied to?
- Do shot freeze frames support any question about positioning, given
  they exist only for 25 moments?
- Is a rule for time on pitch settled enough to compare players?
- Would three-sixty data change which questions are answerable?

## Limits of profiling one match

- Absence here is not absence in the source. Event types and fields
  that did not occur, such as dismissals, extra time, and penalties,
  are simply unobserved.
- Counts describe this match and are not rates or norms.
- The field list is what this file contains, not the provider's full
  schema.
- A check that passes here may fail on another match.
