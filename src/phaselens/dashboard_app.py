"""Local PhaseLens dashboard. Run from the project root:

    uv run --group dashboard streamlit run src/phaselens/dashboard_app.py

Reads prepared local data only. It never ingests, rebuilds, writes, or
downloads anything, and shows observed event context, not player
quality and not tracking. Interface text comes from `dashboard_i18n`;
team and player names are shown as recorded.
"""

from collections import Counter
from html import escape
from pathlib import Path

import streamlit as st

from phaselens import dashboard_data as data
from phaselens.dashboard_i18n import DEFAULT_LANGUAGE, EVENT_TYPES, LANGUAGES, source_name, t
from phaselens.dashboard_pitch import ACTOR, BACKGROUND, OPPONENT, TEAMMATE, UNKNOWN_TEAM, WIDTH, pitch_chart

VIEWS = ("overview", "explorer")
HOME, AWAY = TEAMMATE, OPPONENT  # one colour per side, the same in every view
RING_LABELS = ("5u", "10u", "20u")  # suffixes of the saved context columns
# Colour is kept for team identity, status, and the selected control only;
# cards are neutral. Keyed containers get the documented class
# `st-key-<key>`, and `.pl-*` are this file's own HTML. The rest is the
# theme in .streamlit/config.toml. No external fonts, images, or scripts.
# Rows of cards wrap instead of squeezing: the pitch card never shrinks
# below the chart, so the context card moves under it when the row is too
# narrow, and on a phone the chart scrolls sideways inside its card.
STYLE = f"""
<style>
.st-key-topbar {{ background: {BACKGROUND}; border: 1px solid #2a3558; border-radius: 14px; padding: 0.5rem 1rem; }}
.pl-brand {{ font-size: 1.4rem; font-weight: 800; color: #ffffff; line-height: 1.1; white-space: nowrap; }}
.pl-tagline {{ font-size: 0.72rem; color: #94a3b8; line-height: 1.3; white-space: nowrap; }}
[class*="st-key-card"] {{ background: {BACKGROUND}; border-radius: 14px; }}
.st-key-moment_row > div:has(> .st-key-card_pitch) {{ flex: 1 1 calc({WIDTH}px + 2.5rem);
    min-width: min(100%, calc({WIDTH}px + 2.5rem)); }}
.st-key-moment_row > div:has(> .st-key-card_context) {{ flex: 3 1 18rem; min-width: min(100%, 18rem); }}
.st-key-team_tables > div:has(> [class*="st-key-team_table_"]) {{ flex: 1 1 36rem; min-width: min(100%, 36rem); }}
.st-key-filter_row > div:has(> .st-key-event_nav) {{ flex: 2.4 1 22rem; min-width: min(100%, 22rem); }}
.st-key-filter_row > .st-key-type, .st-key-filter_row > .st-key-team {{ flex: 1 1 9rem; min-width: min(100%, 9rem); }}
.st-key-filter_row > .st-key-player {{ flex: 1.5 1 12rem; min-width: min(100%, 12rem); }}
.st-key-event_nav > .st-key-event {{ flex: 1 1 0; min-width: 0; }}
.st-key-event_prev button p, .st-key-event_next button p {{ position: absolute; width: 1px; height: 1px;
    overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }}  /* named for screen readers, shown as icons */
.st-key-pitch_toggles {{ column-gap: 1.5rem; row-gap: 0.2rem; }}
.st-key-pitch_scroll {{ overflow-x: auto; align-items: safe center; }}
.pl-meta {{ color: #94a3b8; font-size: 0.78rem; font-weight: 600; letter-spacing: 0.02em; }}
.pl-teams {{ display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 1rem; }}
.pl-team {{ font-weight: 700; font-size: 1.15rem; display: flex; align-items: center; gap: 0.5rem; }}
.pl-team.home {{ justify-content: flex-end; text-align: right; }}
.pl-dot {{ width: 0.75rem; height: 0.75rem; border-radius: 50%; display: inline-block; flex: none; }}
.pl-side {{ font-size: 0.65rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: #94a3b8; }}
.pl-score {{ font-size: 1.6rem; font-weight: 800; font-variant-numeric: tabular-nums; color: #ffffff; padding: 0 0.3rem; }}
.pl-note {{ text-align: center; font-size: 0.72rem; color: #94a3b8; margin-top: 0.1rem; }}
.pl-rows {{ max-width: 46rem; margin: 0 auto; }}
.pl-row {{ margin: 0.7rem 0; }}
.pl-row-head {{ display: grid; grid-template-columns: 3.5rem 1fr 3.5rem; font-size: 0.92rem; align-items: center; }}
.pl-row-head .v {{ font-weight: 800; font-variant-numeric: tabular-nums; font-size: 1.1rem; }}
.pl-row-head .v.home {{ color: {HOME}; }}
.pl-row-head .v.away {{ text-align: right; color: {AWAY}; }}
.pl-row-head .l {{ text-align: center; color: #cbd5e1; }}
.pl-bars {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 5px; }}
.pl-bar {{ height: 10px; background: #222c4d; border-radius: 6px; overflow: hidden; display: flex; }}
.pl-bar.home {{ justify-content: flex-end; }}
.pl-bar span {{ display: block; height: 100%; border-radius: 6px; }}
.pl-bar.home span {{ background: {HOME}; }}
.pl-bar.away span {{ background: {AWAY}; }}
.pl-table-head {{ display: flex; align-items: center; gap: 0.5rem; font-weight: 700; font-size: 1rem; }}
.pl-moment {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem 0.8rem; }}
.pl-moment .who {{ font-size: 1.15rem; font-weight: 800; color: #ffffff; }}
.pl-moment .what {{ color: #cbd5e1; font-size: 0.95rem; }}
.pl-kv {{ display: grid; grid-template-columns: 1fr auto; column-gap: 0.8rem; row-gap: 0.5rem; font-size: 0.92rem;
         align-items: center; }}
.pl-kv .k {{ color: #94a3b8; }}
.pl-kv .v {{ font-weight: 700; text-align: right; font-variant-numeric: tabular-nums; color: #f1f5f9; }}
.pl-chip {{ display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.08rem 0.65rem; border-radius: 999px;
           font-weight: 700; font-size: 0.85rem; color: #ffffff; }}
.pl-chip.ok {{ background: #166534; }}
.pl-chip.none {{ background: #334155; }}
.pl-chip.warn {{ background: #92400e; }}
.pl-chip.team {{ background: #222c4d; color: #e6e9f5; border: 1px solid #2a3558; }}
.pl-tiles {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.5rem; margin: 0.8rem 0; }}
.pl-tile {{ background: #1a2342; border: 1px solid #2a3558; border-radius: 10px; padding: 0.5rem 0.65rem; }}
.pl-tile .n {{ display: flex; align-items: baseline; gap: 0.35rem; font-size: 1.45rem; font-weight: 800; line-height: 1.2;
              color: #ffffff; font-variant-numeric: tabular-nums; }}
.pl-tile .n .pl-dot {{ align-self: center; }}
.pl-tile .n small {{ font-size: 0.75rem; font-weight: 600; color: #94a3b8; }}
.pl-tile .n.na {{ font-size: 0.9rem; font-weight: 600; color: #cbd5e1; }}
.pl-tile .l {{ font-size: 0.75rem; color: #94a3b8; margin-top: 0.15rem; line-height: 1.25; }}
.pl-radii-title {{ font-size: 0.8rem; color: #94a3b8; margin-bottom: 0.2rem; }}
table.pl-radii {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; margin: 0; }}
table.pl-radii th, table.pl-radii td {{ padding: 0.3rem 0.5rem; border: 0; border-bottom: 1px solid #2a3558;
    text-align: right; background: transparent; }}
table.pl-radii th:first-child, table.pl-radii td:first-child {{ text-align: left; color: #94a3b8; font-weight: 400; }}
table.pl-radii th {{ font-size: 0.8rem; font-weight: 600; color: #cbd5e1; }}
table.pl-radii th span {{ display: inline-flex; align-items: center; gap: 0.35rem; }}
table.pl-radii td {{ font-weight: 700; font-variant-numeric: tabular-nums; color: #f1f5f9; }}
.pl-legend {{ display: flex; flex-wrap: wrap; gap: 0.25rem 1.1rem; font-size: 0.8rem; color: #cbd5e1; margin: 0.2rem 0; }}
.pl-legend span.i {{ display: inline-flex; align-items: center; gap: 0.35rem; white-space: nowrap; }}
.pl-sym {{ font-size: 0.95rem; }}
</style>
"""


def lang():
    return st.session_state.get("lang", DEFAULT_LANGUAGE)


@st.cache_data(scope="session", show_spinner=False)
def _overview(project_root, generation):
    """Session-scoped: removed when this browser session disconnects; never on disk."""
    return data.load_overview(project_root)


@st.cache_data(scope="session", show_spinner=False)
def _explorer(project_root, generation):
    return data.load_explorer(project_root)


def _load(loader, root, spinner):
    try:
        with st.spinner(t(spinner, lang())):
            return loader(str(root), st.session_state.generation)
    except data.DashboardDataError as error:
        st.error(t("error_title", lang()))
        if error.command:
            st.markdown(t("error_command", lang(), command=f"`{error.command}`"))
        with st.expander(t("error_details", lang())):
            st.code(str(error), language=None)
        st.stop()


def _dot(colour):
    return f'<span class="pl-dot" style="background:{colour}"></span>'


def _chip(text, chip):
    return f'<span class="pl-chip {chip}">{escape(text)}</span>'


def _team_chip(text, colour):
    """Neutral chip with the team's colour as a dot, so the text keeps its contrast."""
    return f'<span class="pl-chip team">{_dot(colour)}{escape(text)}</span>'


def _key_values(pairs):
    """Rows of label and value; a value is plain text or ready-made chip HTML (marked by a tuple)."""
    cells = "".join(
        f'<div class="k">{escape(key)}</div><div class="v">{value[0] if isinstance(value, tuple) else escape(value)}</div>'
        for key, value in pairs
    )
    st.markdown(f'<div class="pl-kv">{cells}</div>', unsafe_allow_html=True)


def _legend(items):
    """The pitch symbols in one short line, as (symbol HTML, text) pairs; the Guide explains them in full."""
    rows = "".join(f'<span class="i"><span class="pl-sym">{symbol}</span>{escape(text)}</span>' for symbol, text in items)
    st.markdown(f'<div class="pl-legend">{rows}</div>', unsafe_allow_html=True)


def show_guide(language):
    use, pitch, terms = st.tabs([t("guide_tab_use", language), t("guide_tab_pitch", language),
                                 t("guide_tab_terms", language)])
    use.markdown(t("guide_use", language))
    pitch.markdown(t("guide_pitch", language))
    terms.markdown(t("guide_terms", language))


def match_header(key, summary=None, choose=None):
    """Competition, stage, teams, score and date, only as far as the verified record holds them.

    One row: the details on the left, teams and score in the middle, and,
    when `choose` is given, the match selector on the right; `choose`
    draws it and returns the chosen match summary.
    """
    language = lang()
    with st.container(border=True, key=f"card_header_{key}"):
        details, middle_column, picker = st.columns([1, 1.4, 1.2], vertical_alignment="center")
        if choose is not None:
            with picker:
                summary = choose()
        competition = " ".join(part for part in (summary["competition"], summary["season"]) if part)
        meta = " · ".join(part for part in (competition, summary["stage"], summary["date"]) if part)
        has_score = summary["home_score"] is not None and summary["away_score"] is not None
        middle = f'{summary["home_score"]} – {summary["away_score"]}' if has_score else "v"

        def team(side, colour):
            name = escape(summary[f"{side}_team"] or "")
            inner = f"{name} {_dot(colour)}" if side == "home" else f"{_dot(colour)} {name}"
            return (f'<div class="pl-team {side}"><div><div class="pl-side">{escape(t(side, language))}</div>'
                    f"<div>{inner}</div></div></div>")

        note = f'<div class="pl-note">{escape(t("score_note", language))}</div>' if has_score else ""
        details.markdown(f'<div class="pl-meta">{escape(meta)}</div>', unsafe_allow_html=True)
        middle_column.markdown(
            f'<div class="pl-teams">{team("home", HOME)}'
            f'<div class="pl-score">{escape(middle)}</div>{team("away", AWAY)}</div>{note}',
            unsafe_allow_html=True,
        )
    return summary


def overview_view(root):
    language = lang()
    loaded = _load(_overview, root, "loading_overview")
    by_id = {m["match_id"]: m for m in loaded["matches"]}
    summary = match_header("overview", choose=lambda: by_id[st.selectbox(
        t("match", language), list(by_id), format_func=lambda m: by_id[m]["label"], key="match",
        label_visibility="collapsed")])

    with st.container(border=True, key="card_compare"):
        st.subheader(t("team_comparison", language))
        html = []
        for row in data.comparison_rows(loaded["team_totals"], summary):
            home = "–" if row["home"] is None else str(row["home"])
            away = "–" if row["away"] is None else str(row["away"])
            html.append(
                f'<div class="pl-row"><div class="pl-row-head"><div class="v home">{home}</div>'
                f'<div class="l">{escape(t("metric_" + row["metric"], language))}</div>'
                f'<div class="v away">{away}</div></div>'
                f'<div class="pl-bars"><div class="pl-bar home"><span style="width:{row["home_share"] * 100:.1f}%">'
                f'</span></div><div class="pl-bar away"><span style="width:{row["away_share"] * 100:.1f}%">'
                f"</span></div></div></div>"
            )
        st.markdown(f'<div class="pl-rows">{"".join(html)}</div>', unsafe_allow_html=True)
        st.caption(t("comparison_note", language))

    with st.container(border=True, key="card_players"):
        st.subheader(t("player_rows", language))
        players = [r for r in loaded["player_rows"] if r["match_id"] == summary["match_id"]]
        sides = {summary["home_team_id"]: ("home", HOME), summary["away_team_id"]: ("away", AWAY)}
        # The heading names each table's team, so there is no team column. The
        # widths add up to less than the narrowest table (36rem in the style).
        columns = {
            # Pinned, so on a phone the name stays while the counts scroll sideways.
            "player_name": st.column_config.TextColumn(t("col_player", language), width=260, pinned=True),
            **{metric: st.column_config.NumberColumn(t("short_" + metric, language), help=t("help_" + metric, language),
                                                     format="%d", width=76)
               for metric in data.METRIC_LABELS},
            "player_id": st.column_config.NumberColumn(t("col_player_id", language), format="%d", width=80),
        }
        # One table per team, in team-id order; rows keep their player-id order. Not a ranking.
        with st.container(horizontal=True, gap="medium", key="team_tables"):
            for team_id in sorted({r["team_id"] for r in players}):
                rows = [r for r in players if r["team_id"] == team_id]
                side, colour = sides.get(team_id, (None, UNKNOWN_TEAM))
                label = f' <span class="pl-side">{escape(t(side, language))}</span>' if side else ""
                with st.container(key=f"team_table_{team_id}"):
                    st.markdown(f'<div class="pl-table-head">{_dot(colour)}{escape(str(rows[0]["team_name"]))}'
                                f"{label}</div>", unsafe_allow_html=True)
                    st.dataframe(rows, hide_index=True, height=35 * (len(rows) + 1) + 3,
                                 column_order=["player_name", *data.METRIC_LABELS, "player_id"],
                                 column_config=columns)
        st.caption(t("player_rows_note", language))
    st.caption(t("footer", language, commit=loaded["source_commit"][:8], match=summary["match_id"]))


def _status_chip(status, language):
    chip = "ok" if status == "computed" else "none" if status == "no_frame" else "warn"
    return (_chip(data.status_text(status, language), chip),)


# A selector's user choice is kept under "<key>_choice", apart from the
# selector's own state: when the language changes, the selector's labels
# change, and the browser can then send back a label that no longer matches
# any option, which resets the selector or leaves its old label on screen.
# The selector is restored from the kept choice before it is created.
EVENT_CHOICE = "event_choice"
_MISSING = object()


def _remember(key):
    """A selector's on_change: the user picked a value."""
    st.session_state[f"{key}_choice"] = st.session_state.get(key)


def _restore(key, options, default):
    """Set a selector's value before it exists, so it shows that value in the active language.

    The value is the user's kept choice when it is still an option, else the
    selector's current value when it is still an option, else `default`.
    """
    for candidate in (st.session_state.get(f"{key}_choice", _MISSING), st.session_state.get(key, _MISSING)):
        if candidate is not _MISSING and candidate in options:
            st.session_state[key] = candidate
            return
    st.session_state[key] = default


def _step_event(ids, position):
    """Prev/next: select a neighbour in the filtered list, in its existing order."""
    st.session_state["event"] = st.session_state[EVENT_CHOICE] = ids[position]


def _unique_labels(events, language):
    """One distinct label per action, in list order.

    The selector identifies an option by its label, so two actions with the
    same label (both teams' Starting XI, for example) could not be told
    apart. A repeated label gets the team's name, as recorded, and if it is
    still repeated, its position among the repeats.
    """
    labels = {e["id"]: data.event_label(e, language) for e in events}
    repeated = Counter(labels.values())
    for e in events:
        if repeated[labels[e["id"]]] > 1:
            labels[e["id"]] += f" · {(e.get('team') or {}).get('name') or '–'}"
    repeated, seen = Counter(labels.values()), Counter()
    for e in events:
        base = labels[e["id"]]
        if repeated[base] > 1:
            seen[base] += 1
            labels[e["id"]] = f"{base} ({seen[base]})"
    return labels


def explorer_view(root):
    language = lang()
    loaded = _load(_explorer, root, "loading_explorer")
    summary = loaded["summary"]
    match_header("explorer", summary)
    team_names = {summary["home_team_id"]: summary["home_team"], summary["away_team_id"]: summary["away_team"]}
    team_colours = {summary["home_team_id"]: HOME, summary["away_team_id"]: AWAY}
    squad = data.squad(loaded["events"])

    with st.container(border=True, key="card_filters"):
        st.subheader(t("filters", language))
        with st.container(horizontal=True, vertical_alignment="bottom", key="filter_row"):
            everything = data.filter_options(loaded["events"])
            types = [None, *everything["types"]]
            _restore("type", types, None)  # None is "All actions"
            type_name = st.selectbox(
                t("event_type", language), types, key="type", on_change=_remember, args=("type",),
                format_func=lambda v: t("all_types", language) if v is None else source_name(EVENT_TYPES, v, language))
            teams = dict(everything["teams"])
            _restore("team", [None, *teams], None)  # None is "Both teams"
            team_id = st.selectbox(t("event_team", language), [None, *teams], key="team",
                                   on_change=_remember, args=("team",),
                                   format_func=lambda v: t("all_teams", language) if v is None else str(teams[v]))
            players = [None, *(pid for pid, _ in data.filter_options(loaded["events"], type_name, team_id)["players"])]
            # A player without actions of the chosen type and team falls back to "All players".
            _restore("player", players, None)
            player_id = st.selectbox(
                t("event_player", language), players, key="player", on_change=_remember, args=("player",),
                format_func=lambda v: t("all_players", language) if v is None else data.player_label(squad[v], language))
            events = data.filter_events(loaded["events"], type_name, team_id, player_id)
            if events:
                by_id = {e["id"]: e for e in events}
                labels = _unique_labels(events, language)
                # Open on the first action that has a snapshot, so the pitch is not empty by default.
                first_frame = next((i for i, e in enumerate(events)
                                    if loaded["context_by_event"][e["id"]]["frame_available"]), 0)
                ids = list(by_id)
                # The default is the first action with a snapshot.
                _restore("event", by_id, ids[first_frame])
                with st.container(horizontal=True, vertical_alignment="bottom", wrap=False, key="event_nav"):
                    event = by_id[st.selectbox(t("event_pick", language, count=len(events)), ids,
                                               format_func=lambda i: labels[i], key="event",
                                               on_change=_remember, args=("event",))]
                    position = ids.index(event["id"])
                    st.button(t("event_prev", language), icon=":material/chevron_left:", help=t("event_prev", language),
                              key="event_prev", disabled=position == 0, on_click=_step_event, args=(ids, position - 1))
                    st.button(t("event_next", language), icon=":material/chevron_right:", help=t("event_next", language),
                              key="event_next", disabled=position == len(ids) - 1, on_click=_step_event,
                              args=(ids, position + 1))
        if not events:
            st.info(t("no_events", language))
            return

    row = loaded["context_by_event"][event["id"]]
    frames = loaded["frames_by_event"].get(event["id"], [])
    event_team = (event.get("team") or {}).get("id")
    other_team = next((team for team in team_names if team != event_team), None)
    own_colour, other_colour = team_colours.get(event_team, HOME), team_colours.get(other_team, AWAY)
    own_name = team_names.get(event_team) or (event.get("team") or {}).get("name")
    player = (event.get("player") or {}).get("name") or t("no_player", language)
    type_text = source_name(EVENT_TYPES, (event.get("type") or {}).get("name"), language)
    time_text = f"{data.match_clock(event)} · {data.half_text(event.get('period'), language)}"

    def fmt(column):
        return data.format_value(column, row[column], language)

    def distance(column):
        value = fmt(column)
        return value if row[column] is None else f"{value} {t('units', language)}"

    # The player-to-action-spot distance is a diagnostic, so its notice is
    # shown with the technical details; the notices themselves are unchanged.
    spot_notice = (t("notice_distance", language, distance=data.format_distance(row["actor_event_distance"], language))
                   if row["actor_event_distance"] is not None else None)
    notices = data.notices(row, frames, language)

    moment_row = st.container(horizontal=True, gap="medium", key="moment_row")
    with moment_row, st.container(border=True, key="card_pitch"):
        with st.container(horizontal=True, vertical_alignment="center", horizontal_alignment="distribute",
                          key="moment_head"):
            st.markdown(
                f'<div class="pl-moment"><span class="who">{escape(player)}</span>'
                f'{_team_chip(str(own_name), own_colour)}'
                f'<span class="what">{escape(type_text)} · {escape(time_text)}</span></div>',
                unsafe_allow_html=True, width="content",
            )
            with st.container(horizontal=True, width="content", key="pitch_toggles"):
                show_radii = st.toggle(t("toggle_radii", language), value=True, key="radii")
                show_area = st.toggle(t("toggle_area", language), value=False, key="area")
        chart = pitch_chart(event, frames, radii=loaded["radii"] if show_radii else (), show_visible_area=show_area,
                            language=language, colours={"teammate": own_colour, "opponent": other_colour},
                            team_names={"teammate": own_name, "opponent": team_names.get(other_team)})
        with st.container(key="pitch_scroll"):
            st.altair_chart(chart, width="content", key="pitch", alt=t("pitch_alt", language, player=player))
        # Name only the symbols this picture can contain; the switches name the rings and the camera view.
        entries = frames[0].get("freeze_frame") if len(frames) == 1 else None
        entries = [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []
        items = []
        if len(frames) == 1:
            items += [
                (f'<span style="color:{ACTOR}">★</span>', t("lg_actor", language, player=player)),
                (f'<span style="color:{own_colour}">●</span>', t("lg_teammates", language, team=own_name)),
                (f'<span style="color:{other_colour}">●</span>',
                 t("lg_opponents", language, team=team_names.get(other_team))),
            ]
        if any(e.get("actor") is not True and not isinstance(e.get("teammate"), bool) for e in entries):
            items.append((f'<span style="color:{UNKNOWN_TEAM}">▲</span>', t("lg_unknown", language)))
        if any(e.get("keeper") is True for e in entries):
            items.append(("◯", t("lg_keeper", language)))
        items.append(("◇", t("lg_event_location", language)))
        if len(frames) == 1:
            items.append(("➜", t("lg_direction", language, team=own_name)))
        _legend(items)
        note = [t("pitch_note", language)]
        if len(frames) == 1:
            note.append(t("pitch_hint", language))
        if show_area:
            note.append(t("area_note", language))
        st.caption(" ".join(note))

    # The pitch card's heading already names the player, team, action, and time.
    with moment_row, st.container(border=True, key="card_context"):
        st.subheader(t("context", language))
        _key_values([
            (t("kv_frame", language), (_chip(t("frame_yes", language), "ok"),) if row["frame_available"]
             else (_chip(t("frame_no", language), "none"),)),
            (t("kv_status", language), _status_chip(row["calculation_status"], language)),
        ])

        def tile(column, label, colour=None, units=False):
            value = fmt(column)
            if row[column] is None:  # not computed: words, never a number
                number = f'<div class="n na">{escape(value)}</div>'
            else:
                suffix = f"<small>{escape(t('units', language))}</small>" if units else ""
                number = f'<div class="n">{_dot(colour) if colour else ""}{escape(value)}{suffix}</div>'
            return f'<div class="pl-tile">{number}<div class="l">{escape(t(label, language))}</div></div>'

        rings = "".join(
            f"<tr><td>{escape(label.rstrip('u'))} {escape(t('units', language))}</td>"
            f"<td>{escape(fmt(f'visible_teammates_within_{label}'))}</td>"
            f"<td>{escape(fmt(f'visible_opponents_within_{label}'))}</td></tr>"
            for label in RING_LABELS
        )
        st.markdown(
            '<div class="pl-tiles">'
            + tile("visible_teammates", "tile_teammates", own_colour)
            + tile("visible_opponents", "tile_opponents", other_colour)
            + tile("nearest_visible_opponent_distance", "tile_nearest", units=True)
            + f'</div><div class="pl-radii-title">{escape(t("radius_title", language))}</div>'
            f'<table class="pl-radii"><thead><tr><th>{escape(t("col_radius", language))}</th>'
            f'<th><span>{_dot(own_colour)}{escape(t("col_teammates", language))}</span></th>'
            f'<th><span>{_dot(other_colour)}{escape(t("col_opponents", language))}</span></th></tr></thead>'
            f"<tbody>{rings}</tbody></table>",
            unsafe_allow_html=True,
        )
        for level, text in notices:
            if text != spot_notice:
                getattr(st, level)(text)

    with st.expander(t("diagnostics", language)):
        _key_values([(t("kv_actor_event", language), distance("actor_event_distance"))])
        for level, text in notices:
            if text == spot_notice:
                getattr(st, level)(text)
        st.dataframe([{t("field", language): column, t("value", language): fmt(column)}
                      for column in loaded["context_columns"]], hide_index=True)
        status, differing = data.compare_with_saved(row, loaded["saved_csv"])
        detail = loaded["saved_csv"]["detail"]
        st.caption(t("saved_csv", language, status=t("cmp_" + status, language),
                     detail=(": " + ", ".join(differing) if differing else "") + (f" ({detail})" if detail else "")))
        st.caption(t("rounding_note", language))
    st.caption(t("footer", language, commit=loaded["commit_sha"][:8], match=loaded["match_id"])
               + " " + t("explorer_scope", language))


def main():
    st.set_page_config(page_title="PhaseLens", page_icon="⚽", layout="wide")
    st.html(STYLE)
    st.session_state.setdefault("generation", 0)
    st.session_state.setdefault("lang", DEFAULT_LANGUAGE)
    language = lang()
    root = Path.cwd()
    # Two groups pushed to the edges; on a narrow screen the right group wraps under the left one.
    with st.container(horizontal=True, vertical_alignment="center", horizontal_alignment="distribute", key="topbar"):
        with st.container(horizontal=True, vertical_alignment="center", width="content", gap="medium"):
            # One line per part of the subtitle, so it never breaks mid-phrase.
            tagline = "".join(f'<div class="pl-tagline">{escape(part)}</div>'
                              for part in t("subtitle", language).split(" · "))
            st.html(f'<div class="pl-brand-block"><div class="pl-brand">⚽ PhaseLens</div>{tagline}</div>',
                    width="content")
            view = st.segmented_control(
                t("view", language), VIEWS, default=VIEWS[0], required=True, label_visibility="collapsed",
                format_func=lambda v: t(f"view_{v}", language), key="view")
        with st.container(horizontal=True, vertical_alignment="center", width="content"):
            if st.button("", icon=":material/refresh:", help=t("reload", language), key="reload"):
                st.session_state.generation += 1
            if st.button(t("guide", language), icon=":material/info:", key="guide"):
                st.dialog(t("guide_title", language), width="large")(show_guide)(language)
            st.selectbox(t("language", language), list(LANGUAGES), format_func=LANGUAGES.get, key="lang",
                         label_visibility="collapsed", icon=":material/language:", width=140)
    if not (root / "pyproject.toml").is_file():
        st.error(t("wrong_root", language))
        st.stop()
    if view == VIEWS[0]:
        overview_view(root)
    else:
        explorer_view(root)


main()
