# PhaseLens demo guide

A local dashboard for looking at results the pipeline has already
prepared. Everything runs on your machine.

## What it does and does not do

It does:

- show the five-match pilot: team totals and player-match rows of three
  event counts, per match;
- show the final's three-sixty frames: for one chosen event, where the
  visible players were, and the spatial-context values around the
  event's actor;
- verify the prepared files with the pipeline's own checks before
  showing them.

It does not:

- download, ingest, rebuild, or write any data;
- rate, rank, or score players;
- show tracking data, movement, speed, or anything between events;
- name the anonymous players in a frame.

## Setup and launch

From the project root:

```
uv sync --group dashboard
uv run --group dashboard streamlit run src/phaselens/dashboard_app.py
```

Then open http://127.0.0.1:8501. The prepared data must already exist;
if it does not, the app says which command to run. On a first run
Streamlit may ask for an e-mail address in the terminal; it is optional
and Enter skips it.

## Stopping the server

Press Ctrl+C in the terminal where it runs. Closing the browser tab does
not stop it.

## Walkthrough

The page uses a dark theme with neutral cards; colour marks only the
teams (home blue, away orange), statuses, and the selected control. The
top bar holds, from left to right: the name, the two views ("Match
overview" and "360° moments"), a reload button (⟳, re-reads and
re-checks the files for your session), a "Guide" button, and a language
menu (English, Türkçe, Deutsch). On a narrow screen the buttons move
under the name.

**Guide.** Opens a window with three tabs: getting started, reading the
pitch (every symbol explained), and terms. The page stays as it was.

**Languages.** The menu changes the interface text: labels, notices,
statuses, words such as "not computed" and yes/no, and event-type and
position names. Team and player names are shown as the source records
them, and field names in the technical details stay in English.
Switching language keeps the selected match, filters, and action.

**Match overview** (default view)

1. Choose a match with the menu on the right of the header. The header
   shows competition, round, and date on the left, and the teams with
   the score as recorded in the source match list in the middle; a
   field the record does not hold is left out. Home is blue and away is
   orange throughout the app.
2. "Team comparison" pairs the two teams' counts row by row: home on
   the left, away on the right. Each bar is that team's share of the
   two teams' combined count in the row; with no events on either side
   both bars are empty.
3. "Players in this match" has one table per team, in team-id order,
   each listing that team's eligible players by player id. The order is
   not a ranking. Column headers are short ("CP" is counter-press);
   pointing at a header shows the full definition. The table heading
   names the team, so there is no team id column; Player ID is the last
   column. All rows show without scrolling; on a phone
   the player column stays in place while the counts scroll sideways.

**360° moments** (the final)

1. Narrow the actions by type, team, and player. The player list only
   offers players with an action of the chosen type for the chosen
   team. It is ordered from goalkeeper to attack and shows, as recorded
   in the events, the player's position, "Starting XI", and the match
   clock of any substitution ("on 67:19", "off 67:19"). No playing time
   is calculated; see "Player list" below.
2. Pick an action; the label shows match clock, half, action type, and
   player. The list opens on the first action that has a 360° snapshot.
   The ‹ and › buttons beside it step to the previous or next action in
   the filtered list, in its existing order; they are named "Previous
   action" and "Next action" for screen readers.
3. Above the pitch: the event player, their team, the action type, and
   the match clock. The pitch shows the snapshot, with a one-line legend
   under it that names only the symbols this picture contains:
   - the event player as a gold star, named on the pitch on a dark
     label;
   - the other visible players as dots in their team's colour;
   - a white ring around any entry with the keeper flag set;
   - the recorded action spot (`event.location`) as a white diamond;
   - an arrow for the attacking direction of the event player's team.
   One short line below says that only visible players are drawn and
   that units are not metres; the "Reading the pitch" tab of the Guide
   has the full explanation. An action without a snapshot shows the
   pitch, its spot, and a message instead of players.

   The pitch is interactive. Pointing at a player shows a tooltip with
   the team and teammate/opponent flag (plus "goalkeeper" when the keeper
   flag is set), the straight-line distance to the event player in
   source units, and the recorded position. Scrolling zooms, dragging
   moves the view, and a double-click resets it. The tooltip distance is
   computed for display from the two recorded positions and rounded like
   the other distances; it is not one of the saved context fields.
4. Switches above the pitch: dashed distance rings of 5, 10, and 20
   units around the event player, and the recorded camera view
   (`visible_area`). Their labels name these symbols, so the legend
   does not repeat them.
5. "Situation at this moment", beside the pitch (below it on narrower
   screens): whether a snapshot exists and the calculation status;
   three values — teammates in the picture, opponents in the picture,
   and the nearest opponent; a small table with the teammates and
   opponents inside each ring; and notices. A value that was not
   computed reads "not computed", never 0.
6. "Technical details: all fields" (an expander) starts with the
   distance between the player in the snapshot and the recorded action
   spot, with its notice, then holds every context field and whether
   the saved `spatial_context.csv` matches the recomputed values.

### Player list

What it uses, all from the verified events file:

| Shown | Source | Note |
|---|---|---|
| Position | The first `tactics.lineup` entry naming the player in a `Starting XI` or `Tactical Shift` event | A substitute's position is the one in the first later tactical shift; a player in no lineup shows "position not recorded" |
| "Starting XI" | Listed in a `Starting XI` lineup | |
| "on" / "off" and the time | `Substitution` events: `substitution.replacement` comes on, `player` goes off; the time is the event's `minute` and `second` | Shown as recorded, not converted to playing time |

The goalkeeper-to-attack order groups the recorded position names into
goalkeeper, defence, midfield, and attack (`POSITION_LINES` in
`dashboard_data.py`). It is a display convention, not a claim about a
player's role. Minutes played are not shown: the documented rules for
turning these times into playing time are missing (see "Prerequisites
for minutes played" in [schema profile](schema_profile.md)).

## Limitations to keep in mind

- **Not computed is not zero.** "Not computed" means there is no
  snapshot or the context could not be computed. 0 means it was
  computed and no qualifying visible player was found. Neither means
  nobody was there: only visible players are recorded.
- **Source units.** Coordinates, distances, and rings are in the
  source's pitch-grid units, not metres. The rings are drawn in those
  units and are not asserted to be physical distances.
- **Anonymity.** Apart from the event player, frame entries have no
  identity. The keeper ring is a flag, not a name.
- **Attacking direction.** The arrow follows the 360 specification,
  which orients every frame with the event player's team attacking from
  0 to 120 (p. 2). It is drawn only when a snapshot is drawn.
- **Unnormalized counts.** Totals are raw event counts. They are not
  adjusted for playing time, number of matches, or opportunities, and
  they are not measures of player or pressing quality.
- **Display rounding.** Coordinates and distances are shown to three
  decimals; a distance above 0 but below 0.001 shows as "<0.001".
  Calculations and saved files keep full precision.
- **Decoration.** The mowing stripes and the centre circle are
  decoration; they carry no data.
- **Loaded once per session.** Files changed on disk after loading are
  seen only after the reload button.
- **Local address only.** The server listens on 127.0.0.1. That limits
  who can connect; it is not a firewall.

## Manual browser checks

| Check | Status |
|---|---|
| Overview totals for the final | Passed (user, in a browser, earlier layout) |
| Starting XI event shows no frame and null values | Passed (user, in a browser, earlier layout) |
| Filtering Pressure events by Bellingham | Passed (user, in a browser, earlier layout) |
| Frame plot and visible-neighbour counts | Passed (user, in a browser, earlier layout) |
| Saved-context comparison | Passed (user, in a browser, earlier layout) |
| Distance rings switched off | Passed (user, in a browser) |
| Reload button | Passed (user, in a browser) |
| Dark layout, top bar, cards, pitch legend | Passed (user, in a browser) |
| Language menu: Türkçe and Deutsch, and back | Passed (user, in a browser) |
| Guide window and its three tabs | Passed (user, in a browser) |
| Team filter limits the player list; goalkeeper-to-attack order | Passed (user, in a browser) |
| Interactive pitch: tooltip, scroll zoom, drag, double-click reset | Passed (user, in a browser) |
| Previous / next action buttons | Passed (user, in a browser) |
| One table per team; column-header definitions | Passed (user, in a browser) |
| Layout at a narrow window (pitch scrolls inside its card) | Passed (user, in a browser) |

Rows marked "earlier layout" were checked before the M10 presentation
changes. Automated tests (an in-process app test and plot tests) and
headless-browser screenshots taken during development supplement these
checks; they do not replace a person using the page, so a new check
starts as "Pending" until someone runs it in a browser.
