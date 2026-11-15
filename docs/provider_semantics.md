# Provider semantics

What the provider's own documentation says about the fields the first
metrics depend on. It covers a small set of questions and is not a
rewrite of the provider's specification.

Three kinds of statement are kept apart throughout:

- **Source value:** what is literally in the local file.
- **Serialization convention:** what a documented rule lets us infer
  from the file, such as the meaning of an absent key.
- **Match claim:** what happened on the pitch. Neither of the first
  two establishes this by itself.

## Documents consulted

All three were read at upstream commit
`4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`, the commit of the ingested
data. Links are pinned to it.

| Short name | Title and version, as printed | Pages | Read |
|---|---|---|---|
| Events v4.0.0 | "StatsBomb Open Events Structure and Data Specification v4.0.0", last updated 08 May 2019 | 32 | In full |
| Spec v1.1 | "StatsBomb Data Specification v1.1", last updated 13 May 2019 | 45 | Passages on the questions below only |
| Lineups v2.0.0 | "StatsBomb Open Lineups Specification v2.0.0", last updated 01 May 2019 | 2 | In full |

- Events v4.0.0: https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/doc/Open%20Data%20Events%20v4.0.0.pdf
  (SHA-256 `05de42cc76b0c9cd26213d8e5c72610cac7d4d92c9c2ac878073a565dbb6c44a`)
- Spec v1.1: https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/doc/StatsBomb%20Open%20Data%20Specification%20v1.1.pdf
  (SHA-256 `d5a8267939c5db35a9501b1a272cc9861a2bb3bef2f53c723d4a43ec1f5ef477`)
- Lineups v2.0.0: https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/doc/Open%20Data%20Lineups%20v2.0.0.pdf
  (SHA-256 `95cce126e28bd65b7b7c2530fdf9ae2bc4bf9ef512f4edecfe7da52dd07820ee`)

Reading limits:

- The text was extracted with `pdftotext`. Table columns come out
  interleaved, so each cited statement was matched to its row by
  context. Page numbers are the ones printed in each document.
- The two coordinate figures in Events v4.0.0 (pages 23 and 24) are
  images. They were extracted and viewed; their labels are quoted below.
- The upstream Matches, Competitions, and 360 Frames documents were
  not read.
- No current Hudl documentation was consulted. Everything here rests on
  the documents that accompany the pinned data.
- The documents are not stored in the project.

Applicability: the match record's `metadata.data_version` is `1.1.0`,
the data version both event documents describe. The documents date from
May 2019 and do not cover everything in the files; see "Differences".

## Answers

### What a Pressure event records

- Events v4.0.0, page 4, event type 17: "Applying pressure to an
  opposing player who's receiving, carrying or releasing the ball."
- Spec v1.1, page 29: pressure events "define a player pressuring an
  attacking player. They have a timestamp, location and duration."
- Spec v1.1, page 13: location and player "must always have a value";
  the location is where the player started to apply pressure, and the
  duration is how long the player kept applying it.
- Events v4.0.0, page 31, data version 1.0.1: "Pressure events all have
  a Duration."

Observed: all 327 Pressure events have a player, team, location, and
duration.

Match claim: a Pressure event is a collector's record that one player
pressured an opponent on the ball. The documents give no distance or
intensity threshold. What goes unrecorded is not stated.

### What `counterpress` means

Events v4.0.0, pages 1 and 30: "an attribute on various defensive
events, including: pressure, dribbled past, 50-50, duel, block,
interception, and foul committed (not offensive). These are pressing
actions within 5 seconds of an open play turnover."

The 5 seconds is the provider's window, applied before the data reaches
us. The documents do not say which team's turnover is meant, how an
open-play turnover is determined, or whether collectors or a rule set
the flag.

### Which event types can carry `counterpress`

| Type id | Type name | In the documented list | Has a `counterpress` row in its own table | Flagged events in the match |
|---|---|---|---|---|
| 17 | Pressure | Yes | Yes (Events p. 18, Spec p. 29) | 57 |
| 4 | Duel | Yes | Yes (Events p. 11, Spec p. 17) | 21 |
| 6 | Block | Yes | Yes (Events p. 10, Spec p. 15) | 9 |
| 39 | Dribbled Past | Yes | Yes (Events p. 11, Spec p. 17) | 4 |
| 10 | Interception | Yes | No (Events p. 15, Spec p. 24) | 2 |
| 22 | Foul Committed | Yes, "not offensive" | Yes (Events p. 12, Spec p. 18) | 1 |
| 33 | 50/50 | Yes | Yes (Events p. 9, Spec p. 14) | 0 |

The list is introduced with "including", so the documents do not state
that it is exhaustive. The counts in the table are from the final
(match 3943043), where no event outside these seven types carries the
flag.

**Observed in the five-match pilot.** Across the five pilot matches, 425
events have `counterpress` exactly `true`. Five of them are outside the
seven types: all are `Pass` events (type 30) whose `pass.type.name` is
"Interception" (match 3942752: one; 3942819: two; 3942226: two). What
the documents and the files show:

- Events v4.0.0 (p. 17) describes pass type 64 "Interception" as "One
  touch pass off an interception". Neither event document lists
  `counterpress` for `Pass`; the Spec v1.1 `Pass` section (pp. 26–27)
  does not mention it.
- In each case the related events are the opponent's incomplete pass
  and the recipient's ball receipt, plus, once, an opponent `Duel`
  without the flag. None of them is a supported type carrying the flag,
  and no separate `Interception` event (type 10) is among them.
- Of 28 `Pass` events with `pass.type.name` "Interception" in the five
  matches, 5 carry the flag.

Not established: whether the flag on these passes is intended, whether
it describes the interception part of a one-touch action, and why some
interception passes carry it and others do not. The flags are not
assumed to be errors. `counterpress_flagged_event_count` excludes these
events and reports their ids; see the [metric catalog](metric_catalog.md).

### What `under_pressure` means

- Events v4.0.0, page 8: "The action was performed while being
  pressured by an opponent."
- Events v4.0.0, page 29, Appendix 7: it is "calculated as every
  on-the-ball event that overlaps the duration of a pressure event".
- Events v4.0.0, page 1: the definition was expanded so that "events
  which are naturally performed under pressure like duels, dribbles
  etc, all pick up the attribute, even in the absence of an actual
  pressure event", and carries can be pressured by other defensive
  events too.

So `under_pressure` is computed by the provider from other events and
from the event's type. It is not an independent observation. This
explains why every Duel, Dribble, and several other types carry it in
the match.

### What an absent key means, field by field

There is no single rule. Each field is listed with what the documents
say about it.

| Field | Documented values | Statement about absence | Reading of an absent key |
|---|---|---|---|
| `counterpress` | TRUE | Spec v1.1 gives the constraint "Recorded only when true" in the tables that list it (pp. 14 to 18, 29). Events v4.0.0 lists only TRUE and says nothing more. | Convention: the provider did not flag the event. On a type outside the seven above, the attribute does not apply. |
| `under_pressure` | TRUE (Events p. 8) | None. Neither document says it is recorded only when true. | Inference, weaker than for `counterpress`: the provider's calculation did not mark the event. Based on TRUE being the only listed value and on the file holding only `true`. |
| `off_camera` | FALSE, TRUE (Events p. 8) | The two documents contradict each other; see "Differences". | Unresolved by documentation. The file matches the Events v4.0.0 statement: present on 25 events, always `true`. |
| `out` | TRUE | "Added if the outcome of the event is the ball going out of bounds" (Events p. 8). | Convention: the provider did not record the ball going out. |
| Type-specific flags described as "Added if ...", such as `ball_recovery.recovery_failure` | TRUE | "Added if" the condition holds. | Convention: the condition was not recorded. Only for flags the documents describe this way. |
| `player` | Object | "player object will only display if the event is tied to a specific player" (Events p. 8). | Convention: the event is not tied to one player. Not a defect. |
| `location` | Array | "only displays if the event has pitch coordinates" (Events p. 8). | Convention: the event has no pitch coordinates. |

In every row the reading concerns what the provider recorded. An absent
`counterpress` or `under_pressure` is not evidence that no pressing
happened.

The file itself holds only `true` for all 33 boolean fields and never
`false` or `null`. That is an observation about one match, not a rule.

### What a possession id represents

Events v4.0.0, page 6:

- `possession` "indicates the current unique possession in the game. A
  single possession denotes a period of play in which the ball is in
  play and a single team is in control of the ball."
- "A new possession can begin even if the same team has possession of
  the ball", for example when a blocked pass goes out for a throw-in
  for the same team.
- `possession_team` is "the team that started this possession in
  control of the ball", and it "will appear even on opposition events
  like tackles attempted during the possession".

This resolves two observations from the schema profile: the 50
possession changes with no change of team, and the 571 events whose
`team` differs from `possession_team`.

Not stated: the exact rule for when a team has "established control".

### Coordinates

- Frame: the figure on page 23 of Events v4.0.0 labels the corners
  (0,0) top left, (120,0) top right, (0,80) bottom left, and (120,80)
  bottom right, with the centre at (60,40) and goals on x = 0 and
  x = 120 between y = 36 and y = 44.
- Units: not labelled on the figure. `pass.length` is documented "in
  yards" (page 16). That the coordinates are yards is an inference from
  this, not a statement in the documents.
- Direction of play: not stated in either event document.
- Third component of `shot.end_location`: the field is documented as
  `[x,y]` or `[x,y,z]` (page 18). The figure on page 24, "Goal
  Coordinates", labels the goal frame from (120, 36, 0) to
  (120, 44, 2.67), so the third number is the height in that frame.

### Whether `related_events` is reciprocal

Events v4.0.0, page 8, gives an example: a shot may be related to a
goalkeeper event and a block, and "the corresponding events will have
the Id of the shot". The documents do not state reciprocity as a rule.
In the match, 1,514 of 4,934 references are not returned. Unresolved.

## Differences between the documents and the files

| Topic | Documents | Local files |
|---|---|---|
| Where `counterpress` sits | Listed inside each event type's object table | A top-level key on the event. No event has it nested, and no event has a `pressure` object. |
| `off_camera` | Events v4.0.0 p. 30: "only shows when TRUE". Spec v1.1 pp. 2 and 44: "a boolean on every event". | Present on 25 events only, always `true`. |
| Interception and `counterpress` | In the summary list, absent from the Interception attribute table | 2 Interception events carry it |
| Coordinate number type | "Array containing two integer values" | Floats, for example 0.6 |
| `metadata.xy_fidelity_version` | Not mentioned | Present in the match record, value `2` |
| Lineup `positions` and `cards` | Not mentioned. Lineups v2.0.0 describes `lineup` as the "players on the team sheet" and lists five player fields. | Present on every listed player |

## Still unresolved

- Which team's turnover starts the `counterpress` window, and whether
  the flag is collected or computed.
- Whether the list of seven `counterpress` event types is exhaustive,
  and what the flag means on the five `Pass` events with
  `pass.type.name` "Interception" observed in the pilot.
- An explicit serialization rule for `under_pressure`.
- Which `off_camera` statement is authoritative.
- Direction of play and coordinate units as explicit statements.
- Whether `related_events` is meant to be reciprocal.
- The meaning of lineup `positions` intervals, which no pinned document
  describes. This blocks any rule for time on the pitch.
- Whether newer provider documentation differs from these 2019
  documents. None was consulted.
