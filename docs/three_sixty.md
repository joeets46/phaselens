# Three-sixty frames: the final

What the three-sixty file of one match contains, and what it can and
cannot support. Nothing here is a metric.

| Item | Value |
|---|---|
| Match | UEFA Euro 2024 final, `match_id` 3943043 |
| Upstream commit | `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb` |
| Source file | `data/three-sixty/3943043.json`, 7,008,694 bytes |
| Companion manifest | `manifests/statsbomb/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/match_3943043.three_sixty.json` |
| Report | `data/processed/three_sixty/<commit>/3943043/summary.json` and `coverage.csv` (not in Git) |

## Commands

```
uv run phaselens three-sixty-ingest --manifest manifests/statsbomb/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/match_3943043.json
uv run phaselens three-sixty-profile --manifest manifests/statsbomb/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/match_3943043.json
```

`three-sixty-ingest` first verifies the match's event files against
their manifest. Without a companion manifest, it confirms the pinned
path with a HEAD request, downloads the file, checks that it is a JSON
array of objects, stores the bytes unchanged, and then writes the
companion manifest. With one, it checks that the companion still
belongs to the same commit, match, location, and events file, and
verifies the local bytes against it; nothing is requested unless the
file is missing, in which case it is downloaded again from the same
URL and accepted only if its hash matches.

The match manifest is not changed. The companion records the frames
file's URL, local path, retrieval time, SHA-256, and size, and binds
them to the match manifest's path and the events file's SHA-256 and
size.

`three-sixty-profile` never downloads. It verifies the events file and
the frames file, then writes the report. Identical inputs give
byte-identical output.

## A. Officially documented semantics

Source: "Open Data 360 Frames Specification v1.0.0", marked "StatsBomb
API - last updated 17 November 2021", 3 pages, at
https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/doc/Open%20Data%20360%20Frames%20v1.0.0%20(1).pdf
(SHA-256 `dd15b0d0075bcb6c4758f3d111745d3c09b8bdde68c9bd8e9dea2fad2e1924fc`,
175,991 bytes). Read as extracted text; the table columns interleave,
so rows were matched by context. The document is not stored in the
project.

- The file is an array of frame objects with `event_uuid`,
  `visible_area`, and `freeze_frame` (p. 1).
- `event_uuid` is "the unique identifier for the event matching this
  freeze frame". This is the linking field.
- `visible_area` is a polygon "visible to the camera", written as
  `[X1 Y1 X2 Y2 … Xn Yn X1 Y1]`, "a closed loop". It "can also be empty
  where the camera was not on the pitch". "Player locations may be
  outside the visible area where these were manually placed."
- `freeze_frame` entries "will not contain player identification,
  beyond their team (except for the player performing the current
  event who will be marked as the actor)".
- Each entry has `location` `[x, y]`, "oriented in the same direction
  as the linked event (i.e. the actor's team attacking 0 to 120 on the
  X axis)"; `teammate` (same team as the actor); `actor` (the player
  performing the event); `keeper` (the player is a keeper) (p. 2).
- Notes (p. 3): the data comes mostly from broadcast video; not all 22
  players will be visible; `visible_area` will not be available for
  every frame; not all events receive a frame; some events will lack an
  actor; `keeper` can, rarely, refer to the actor's own keeper without
  `teammate` being set.

Usage terms: the document contains none. At the same commit, the
repository README lists `three-sixty` among the data its Terms &
Conditions apply to, and the user agreement covers "StatsBomb Data"
provided through the repository without naming three-sixty data
separately. The raw file is kept out of Git. See
[data sources](data_sources.md); this is not a legal assessment.

## B. Observations from this match

From the report. Denominators are stated.

**Linkage** (`event_uuid` against event `id`):

| Measure | Count |
|---|---|
| Three-sixty records | 2,882 |
| Distinct `event_uuid` values | 2,882 |
| Duplicate keys | 0 |
| Records whose key is no event in the file | 0 |
| Distinct events with a record | 2,882 |
| Events without a record | 422 of 3,304 |

**Event coverage** (distinct events with a record, out of the events
of each group):

| Group | Covered |
|---|---|
| All events | 2,882 of 3,304 (87.23%) |
| Spain / England | 1,780 of 2,015 / 1,102 of 1,289 |
| Period 1 / Period 2 | 1,494 of 1,694 / 1,388 of 1,610 |
| Pass / Ball Receipt* / Carry | 767 of 915 / 802 of 876 / 700 of 757 |
| Pressure | 275 of 327 |
| Goal Keeper | 13 of 30 |
| Shot, 50/50, Interception, Shield, Error | every event |
| Starting XI, Substitution, Tactical Shift, Half Start, Half End, Injury Stoppage, Referee Ball-Drop | no event |

The full table is `coverage.csv`. This is coverage of events, not of
match time: frames exist only at event moments.

**Structure:**

- Every record has the three documented keys and a `freeze_frame` list
  of 6 to 22 entries; 47,480 entries in total.
- Every entry has `location`, `teammate`, `actor`, and `keeper`. Each
  flag is `true` or `false`; no null, missing, or other value occurs.
- Every `location` is two numbers. x runs from −2.0 to 123.0 and y from
  −7.5 to 86.0: 32 entries lie outside 0–120 on x and 377 outside 0–80
  on y.
- Every `visible_area` is a numeric list of 8 to 14 values whose first
  point is repeated at the end. No record has an empty or missing one.
  This checks shape only, not that the polygon is valid or what part
  of the pitch it covers.

**Identity:**

- Every record has exactly one entry with `actor` true.
- 913 records have one entry with `keeper` true, 1,969 have none, and
  none has two. Of the 913, 500 also have `teammate` true and 413
  false.
- No entry or record has a key beyond the documented ones. There is no
  player identifier.

**Actor position against the event location** (2,882 records, all
comparable: one actor, two-number locations on both sides):

| Difference, in source pitch units | Records |
|---|---|
| Exactly 0 | 104 |
| Over 0 up to 0.5 | 2,609 |
| Over 0.5 up to 10 | 5 |
| Over 10 | 164 |

The median difference is 0.000002. The buckets are a reporting choice
of this project, not a provider tolerance, and differences are not
converted to metres. The documentation states that frame coordinates
follow the linked event's orientation, so the two are comparable in
principle.

The 164 records over 10 units are Ball Receipt* (78), Duel (29),
Dispossessed (19), Foul Won (15), Dribble (10), Dribbled Past (9),
50/50 (2), and Carry (2). A one-off check outside the report found that
mirroring the actor position (120 − x, 80 − y) brings 18 of them within
0.5 units, so a direction flip does not explain most of them. They are
not treated as annotation errors.

## C. Unresolved

- Why 164 actor positions lie more than 10 units from their event's
  location, mostly on event types that come in pairs.
- What a coordinate outside 0–120 or 0–80 represents: a manually placed
  player, a position off the pitch, or something else.
- Whether an entry outside `visible_area` was placed manually; the
  report does not test points against polygons.
- Whether the keeper entry is the actor's own keeper when `teammate` is
  false, as the notes say can rarely happen.
- How positions were obtained for each frame, and how precise they are.
- Whether these observations hold for other matches.

## Event-level spatial context (Milestone 8)

```
uv run phaselens three-sixty-context --manifest manifests/statsbomb/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/match_3943043.json
```

Offline. It verifies the events and frames files as `three-sixty-profile`
does, then writes `spatial_context.csv` and
`spatial_context_summary.json` beside the report. It does not rewrite
the report files. Identical inputs give byte-identical output.

The table has one row per source event and two families of exploratory
indicators around the frame's actor. Definitions, statuses, and
parameters are in the [metric catalog](metric_catalog.md), section
"Exploratory event-level indicators". In short:

- the distance from the actor to the nearest visible opponent entry;
- counts of visible teammate and opponent entries within 5, 10, and 20
  source units of the actor, boundary included.

What the indicators mean and do not mean:

- Distances are in the source's pitch-coordinate units. They are not
  asserted to be metres or yards.
- The radii are exploratory parameters, not football standards.
- Counts cover the frame's included entries: visible players, as the
  provider recorded them. They are not counts of full teams. Zero means
  no qualifying entry was observed, not that nobody was there.
- `visible_area` is not used. A radius circle can extend beyond the
  visible area, where players may exist unobserved; no visibility
  correction or extrapolation is made.
- Nothing about player, pressure, or support quality is inferred.

Observed for the final (from the summary):

| Measure | Value |
|---|---|
| Rows | 3,304, one per event |
| `computed` | 2,882 |
| `no_frame` | 422 |
| Any other status | 0 |
| Entries excluded from a computed row | 0 |
| Non-actor entries outside 0–120 × 0–80 (kept, flagged) | 408 |
| Rows whose actor is outside 0–120 × 0–80 (kept, flagged) | 1 |
| Computed rows without any visible opponent | 0 |
| Events without a location (actor-to-event distance null) | 26 |

The 164 records whose actor lies more than 10 units from the event
location (section B) are computed like any other, with the actor as
origin; their `actor_event_distance` shows the difference.

## Analytical questions

**Supported by this source**

- For an event with a frame: where were the visible players of each
  side, relative to the actor, at that moment?
- How many visible teammates and opponents were in the frame, and how
  does that vary by event type?
- Which events have a frame at all, by type, team, and period.

**Potentially supported, with explicit assumptions**

- Visible opponents or teammates within a distance of the actor at an
  event, such as a Pressure. Needs a named distance parameter (a
  hypothesis) and must count only what is visible.
- Spatial context of the event player, using the actor position, or
  the event location where the two agree.
- Keeper position at an event, where `keeper` is set, accepting the
  documented rare ambiguity about which keeper it is.

**Not supported by this source**

- Positioning of a specific non-actor player: entries carry no player
  identity, and matching positions across frames would be a guess.
- Movement between events, speed, distance covered, sprints, or
  running intensity: frames are snapshots at event moments only.
- Full-pitch or full-team positioning: not all players are visible, and
  an unobserved player is not an absent one.
- Off-ball positioning between events, when no event and so no frame
  exists.
