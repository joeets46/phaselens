# Browser checklist

Repeatable manual checks of the local dashboard. Run them after a
change to the dashboard and record the result below with the commit
hash. Automated tests (in-process app tests and plot tests) do not
replace these checks: they do not render the page in a browser.

## Before you start

1. From the project root: `uv sync --group dashboard`, then
   `uv run phaselens dashboard-check`. It must print "Ready.".
2. Start a fresh server:
   `uv run --group dashboard streamlit run src/phaselens/dashboard_app.py`.
   Stop any older server first; a running server can keep an older
   module.
3. Open http://127.0.0.1:8501 in a desktop browser window at least
   1440 px wide, in English.

Widths: **W** = 1440 px or wider, **M** = about 1024 px, **N** = about
390 px (narrow window or the browser's device toolbar).

## Checks

### Match overview

| ID | Action | Expected result | Width |
|---|---|---|---|
| BC-01 | Choose each pilot match in the header menu (all fifteen) | Each shows its teams, score, three comparison rows, and two team tables (Player ID last); no error | W, M |
| BC-02 | Point at the headers "Pressures", "CP pressures", and "CP events" | Each shows its full definition, ending "Raw count, not a rating." | W |

### 360° moments

Switch to "360° moments" first.

| ID | Action | Expected result | Width |
|---|---|---|---|
| BC-03 | Point at an orange or blue dot on the pitch | A tooltip shows the team and "teammate" or "opponent", the distance to the event player in units, and the position (x, y); the star's tooltip names the event player | W |
| BC-04 | Scroll over the pitch, then drag it, then double-click it | Scrolling zooms, dragging moves the view, and a double-click restores the original view; nothing spills outside the pitch card | W |
| BC-05 | Choose an action, then switch the language menu to Türkçe, then Deutsch, then English | Headings change ("Aksiyon bul", "Aktion finden", "Find an action"); the chosen action, filters, and view stay selected through every switch; the action menu shows its label in the active language; team and player names never change | W |
| BC-06 | Press "Guide" and open its three tabs, then close it | "Getting started", "Reading the pitch", and "Terms" each show text; the pitch tab explains the gold star; closing leaves the page as it was | W |
| BC-07 | Press › three times, then ‹ once; go to the first action in a list and look at ‹ | The action label and pitch follow each step through the filtered list in match order; ‹ is disabled at the first action and › at the last; a screen reader names them "Previous action" and "Next action" | W |
| BC-08 | Set "Action type" to Starting XI, then choose the second action in the list | The pitch shows "No 360° snapshot for this action"; the context card shows "not available", "no 360° snapshot", and "not computed" values, never 0. The two Starting XI actions are listed with their team names ("· Spain", "· England"), and choosing the second one shows England | W |
| BC-09 | Switch "Distance rings" off and on | The dashed 5/10/20 rings disappear and return; the ring table in the context card is unchanged | W |
| BC-10 | Switch "Camera view" on and off | A light dashed area appears and disappears; while on, the line under the pitch adds that the camera view is as recorded and not checked | W |
| BC-11 | Press ⟳ | The page reloads the data and shows the same view without an error | W |
| BC-12 | Look at the three filters before choosing anything; then, with "Action type" on All actions, set "Team" to Spain and open "Player" | The filters first read "All actions", "Both teams", and "All players" (never an empty "Choose an option"). Only Spain players are offered, from the goalkeeper (Unai Simón Mendibil) to attack, with recorded positions and substitution times | W |
| BC-13 | Narrow the window to about 1024 px, then to about 390 px | At 1024 px the context card moves under the pitch with no overlap; at 390 px the page does not scroll sideways, the pitch scrolls sideways inside its card, and the player tables keep the name column in place | M, N |
| BC-14 | In Türkçe, set "Action type" to Top kazanma, "Team" to Spain, and "Player" to Rodrigo; then switch to English, Deutsch, Türkçe, and English | Every filter keeps its value through every switch, and the menus show it in the active language: "Ball Recovery", "Ballgewinn", "Top kazanma"; the player's recorded position also changes language ("Right Defensive Midfield", "Rechter defensiver Mittelfeldspieler", "Sağ ön libero"); "Spain" stays as recorded | W |
| BC-15 | In "360° moments", open the match menu in the header; choose a match other than the final, then switch to Türkçe and back to English | The menu lists only the pilot's matches with verified 360° data, final first (all fifteen at this commit); a match without it is never offered; the chosen match loads, its teams appear in the header and its actions in the action list, and it stays chosen through the language switches | W |

## Results

Record one table per run. Use "Passed", "Failed (with a note)", or
"Not run". Name how the run was made: by a person in a browser, or by
an automated headless browser. Confirmations made by the user in a
browser before this checklist existed, including the tooltip, zoom, and
language-menu checks, are summarized under "Manual browser checks" in
the [demo guide](demo_guide.md).

The commit hashes below refer to the history as published. Before the
first push, the history was rewritten to replace the author e-mail
address; nothing else changed. The runs were recorded against the
earlier hashes `ee60672` (now `4428f02`), `e79c454` (now `214a946`),
and `1d452a0` (now `f38508f`).

### Run 1

- Commit: `4428f02` plus the uncommitted M11 working tree
- Date: 2026-11-16
- Browser: Chrome (headless), driven through the DevTools Protocol
- Run by: automated headless run (Claude); not a person in a browser

| ID | Result | Note |
|---|---|---|
| BC-01 | Passed | Five matches, two tables each, no error |
| BC-02 | Passed | All three header definitions appeared on hover |
| BC-03 | Passed | Dot: "England · teammate", "Distance to Kobbie Mainoo 15.112", position; star names Kobbie Mainoo |
| BC-04 | Passed | Scroll and drag changed the view; double-click restored it exactly |
| BC-05 | **Failed** | Headings changed and filters stayed; the chosen action stayed after the first switch but returned to the default action at the second switch. The action menu also shows the previous language's label for one step. Fixed before run 2 |
| BC-06 | Passed | Three tabs with text; closed cleanly |
| BC-07 | Passed | Stepped through the list; ‹ and › disabled at the ends; accessible names "Previous action" and "Next action" |
| BC-08 | Passed | Pitch message and "not computed" values; no 0 shown |
| BC-09 | Passed | Three dashed rings off and on; ring table unchanged |
| BC-10 | Passed | Camera area and its note appeared and disappeared |
| BC-11 | Passed | Same view and action after reload; no error |
| BC-12 | Passed | 15 Spain players, from Unai Simón Mendibil (Goalkeeper) |
| BC-13 | Passed | No overlap at 1024 px; at 390 px no page scroll sideways, pitch and tables scroll in place. The pinned name column was not checked (the table is drawn on a canvas) |

### Run 2

- Commit: `4428f02` plus the uncommitted M11 working tree, after the
  BC-05 fix
- Date: 2026-11-16
- Browser: Chrome (headless), driven through the DevTools Protocol
- Run by: automated headless run (Claude); not a person in a browser

| ID | Result | Note |
|---|---|---|
| BC-01 | Passed | Five matches, two tables each, no error |
| BC-02 | Passed | All three header definitions appeared on hover |
| BC-03 | Passed | Dot and star tooltips as expected |
| BC-04 | Passed | Scroll and drag changed the view; double-click restored it exactly |
| BC-05 | Passed | The chosen action stayed through Türkçe, Deutsch, and English, with its label in each language; also checked for an action chosen from the menu, with ›, and the default action |
| BC-06 | Passed | Three tabs with text; closed cleanly |
| BC-07 | Passed | Stepped through the list; ‹ and › disabled at the ends; accessible names present |
| BC-08 | Passed | Pitch message and "not computed" values; both Starting XI actions listed with team names, and England could be chosen and kept through a language switch |
| BC-09 | Passed | Three dashed rings off and on; ring table unchanged |
| BC-10 | Passed | Camera area and its note appeared and disappeared |
| BC-11 | Passed | Same view and action after reload; no error |
| BC-12 | Passed | 15 Spain players, from Unai Simón Mendibil (Goalkeeper) |
| BC-13 | Passed | No overlap at 1024 px; at 390 px no page scroll sideways, pitch and tables scroll in place. The pinned name column was not checked (the table is drawn on a canvas) |

Seen in this run but outside BC-05's scope: after a language switch the
"Action type" menu can keep showing the previous language's name of
the chosen type (for example "Pressure" in Türkçe) until it is changed;
the filter itself is kept.

### Run 3

- Commit: `4428f02` plus the uncommitted M11 working tree, after the
  filter language fix
- Date: 2026-11-16
- Browser: Chrome (headless), driven through the DevTools Protocol
- Run by: automated headless run (Claude); not a person in a browser

| ID | Result | Note |
|---|---|---|
| BC-01 | Passed | Five matches, two tables each, no error |
| BC-02 | Passed | All three header definitions appeared on hover |
| BC-03 | Passed | Dot and star tooltips as expected |
| BC-04 | Passed | Scroll and drag changed the view; double-click restored it exactly |
| BC-05 | Passed | The chosen action stayed through Türkçe, Deutsch, and English, with its label in each language |
| BC-06 | Passed | Three tabs with text; closed cleanly |
| BC-07 | Passed | Stepped through the list; ‹ and › disabled at the ends; accessible names present |
| BC-08 | Passed | Pitch message and "not computed" values; both Starting XI actions listed with team names; England chosen and kept |
| BC-09 | Passed | Three dashed rings off and on; ring table unchanged |
| BC-10 | Passed | Camera area and its note appeared and disappeared |
| BC-11 | Passed | Same view and action after reload; no error |
| BC-12 | Passed | 15 Spain players, from Unai Simón Mendibil (Goalkeeper) |
| BC-13 | Passed | No overlap at 1024 px; at 390 px no page scroll sideways, pitch and tables scroll in place. The pinned name column was not checked (the table is drawn on a canvas) |
| BC-14 | Passed | Type, team, and player kept through four switches; type names and the player's position shown in each language |

The "Action type" label issue noted under run 2 is fixed; the player
filter had the same defect (its value was lost at the second switch)
and is fixed with it.

### Run 4 — by the user in a browser

- Commit: `4428f02` plus the uncommitted M11 working tree, after the
  BC-05, BC-08, and BC-14 fixes
- Date: 2026-11-16
- Browser: the user's desktop browser
- Run by: the user, in a browser; only the checks below marked
  "Passed" were run

| ID | Result | Note |
|---|---|---|
| BC-01 | Not run | |
| BC-02 | Not run | |
| BC-03 | Not run | |
| BC-04 | Not run | |
| BC-05 | Passed | |
| BC-06 | Not run | |
| BC-07 | Not run | |
| BC-08 | Passed | |
| BC-09 | Not run | |
| BC-10 | Not run | |
| BC-11 | Not run | |
| BC-12 | Not run | |
| BC-13 | Not run | |
| BC-14 | Passed | |

### Run 5

- Commit: `214a946` plus the uncommitted M12 working tree (15-match
  pilot, Explorer match menu)
- Date: 2026-11-17
- Browser: Chrome (headless), driven through the DevTools Protocol
- Run by: automated headless run (Claude); not a person in a browser

| ID | Result | Note |
|---|---|---|
| BC-01 | Passed | All fifteen matches, two tables each, no error |
| BC-02 | Passed | All three header definitions appeared on hover |
| BC-03 | Passed | Dot and star tooltips as expected |
| BC-04 | Passed | Scroll and drag changed the view; double-click restored it exactly |
| BC-05 | Passed | The chosen action stayed through Türkçe, Deutsch, and English, with its label in each language |
| BC-06 | Passed | Three tabs with text; closed cleanly |
| BC-07 | Passed | Stepped through the list; ‹ and › disabled at the ends; accessible names present |
| BC-08 | Passed | Pitch message and "not computed" values; both Starting XI actions listed with team names |
| BC-09 | Passed | Three dashed rings off and on; ring table unchanged |
| BC-10 | Passed | Camera area and its note appeared and disappeared |
| BC-11 | Passed | Same view and action after reload; no error |
| BC-12 | Passed | 15 Spain players, from Unai Simón Mendibil (Goalkeeper); the filters' "All …" labels were checked on a screenshot |
| BC-13 | Passed | No overlap at 1024 px; at 390 px no page scroll sideways, pitch and tables scroll in place. The pinned name column was not checked (the table is drawn on a canvas) |
| BC-14 | Passed | Type, team, and player kept through four switches, labelled in each language |
| BC-15 | Passed | Fifteen matches listed, final first; Switzerland v Italy chosen, its teams in the header, kept through Türkçe and English |

Found and fixed during this run: since M11, the filters opened on an
empty "Choose an option" instead of "All actions", "Both teams", and
"All players", because the "All" choice was stored as no value. The
"All" option now has its own value, and an app test checks the three
labels in each language.

### Run 6 — by the user in a browser

- Commit: `f38508f` (then HEAD), served from http://127.0.0.1:8501
- Date: 2026-11-17
- Browser: Chrome
- Run by: the user, in a browser; only the checks below marked
  "Passed" were run

| ID | Result | Note |
|---|---|---|
| BC-01 | Passed | |
| BC-02 | Not run | |
| BC-03 | Passed | |
| BC-04 | Not run | |
| BC-05 | Not run | |
| BC-06 | Not run | |
| BC-07 | Not run | |
| BC-08 | Not run | |
| BC-09 | Not run | |
| BC-10 | Not run | |
| BC-11 | Not run | |
| BC-12 | Not run | |
| BC-13 | Passed | |
| BC-14 | Not run | |
| BC-15 | Passed | |
