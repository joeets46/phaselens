"""Exercise the Streamlit script with Streamlit's own AppTest, in-process.

This runs the app script and its widgets without a browser or a server;
it does not show that the browser interface renders correctly. Skipped
unless the dashboard group is installed and the real prepared data is on
disk. The app only reads, so the data is left unchanged.
"""

import re
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from phaselens import dashboard_data as data  # noqa: E402
from phaselens import pilot, statsbomb, three_sixty  # noqa: E402
from phaselens.ingest import manifest_path, parse_json_array, read_manifest, read_verified_files  # noqa: E402
from phaselens.metrics import METRIC_NAMES  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = PROJECT_ROOT / "src/phaselens/dashboard_app.py"
NEEDED = [
    PROJECT_ROOT / data.PILOT_FILE,
    PROJECT_ROOT / data.FINAL_MANIFEST,
    PROJECT_ROOT / "data/processed/analytics" / data.FINAL_COMMIT / "pilots" / Path(data.PILOT_FILE).stem
    / "build_metadata.json",
    PROJECT_ROOT / "manifests/statsbomb/open-data" / data.FINAL_COMMIT / f"match_{data.FINAL_MATCH_ID}.three_sixty.json",
]
SPAIN = 772
ALL = "all"  # the value of a filter's "All …" option in dashboard_app


def pilot_match_ids():
    return pilot.load_pilot(PROJECT_ROOT, PROJECT_ROOT / data.PILOT_FILE)["match_ids"]


@pytest.fixture
def app(monkeypatch):
    if not all(path.is_file() for path in NEEDED):
        pytest.skip("the prepared pilot and three-sixty data are not on disk")
    monkeypatch.chdir(PROJECT_ROOT)
    test = AppTest.from_file(str(APP), default_timeout=180)
    test.run()
    assert not test.exception, test.exception
    return test


def explorer(app):
    app.button_group(key="view").set_value("explorer").run()
    assert not app.exception
    return app


def texts(elements):
    return " ".join(element.value for element in elements)


def fingerprint():
    """Size and modification time of every prepared file: cheap, and enough to see a write."""
    roots = [PROJECT_ROOT / "data", PROJECT_ROOT / "manifests"]
    return sorted((str(p), p.stat().st_size, p.stat().st_mtime_ns) for r in roots for p in r.rglob("*") if p.is_file())


def test_overview_shows_the_match_header_comparison_and_player_rows(app):
    assert app.button_group(key="view").value == "overview" and app.selectbox(key="lang").value == "en"
    assert len(app.dataframe) == 2  # one player table per team; the comparison is a compact list
    match = app.selectbox(key="match")
    assert len(match.options) == len(pilot_match_ids())
    markdown = texts(app.markdown)
    assert "UEFA Euro 2024 · Final · 2024-07-14" in markdown and "2 – 1" in markdown
    assert "Pressure events" in markdown
    match.select_index(1).run()
    assert not app.exception
    captions = texts(app.caption)
    assert "not normalized" in captions and "not ratings" in captions and "StatsBomb Open Data" in captions


def test_every_pilot_match_shows_its_verified_totals_teams_score_and_rows(app):
    """Each pilot match, checked against sources the app does not use for this check.

    Team totals come straight from the verified pilot query; teams from the
    match manifest; the score from the verified match-list file that the
    manifest records, since the manifest itself holds no score.
    """
    pilot_file = PROJECT_ROOT / data.PILOT_FILE
    commit = pilot.load_pilot(PROJECT_ROOT, pilot_file)["source_commit"]
    columns, rows = pilot.run_pilot_query(PROJECT_ROOT, pilot_file, "team-totals")
    totals = {(row["match_id"], row["team_id"]): row for row in (dict(zip(columns, r)) for r in rows)}
    seen, shown_rows = [], 0
    for index in range(len(app.selectbox(key="match").options)):
        app.selectbox(key="match").select_index(index).run()
        assert not app.exception, app.exception
        match_id = app.selectbox(key="match").value
        seen.append(match_id)

        manifest = read_manifest(manifest_path(PROJECT_ROOT, commit, match_id))
        meta, selection = manifest["match_metadata"], manifest["selection"]
        home_id, away_id = meta["home_team"]["home_team_id"], meta["away_team"]["away_team_id"]
        list_path = statsbomb.matches_path(selection["competition_id"], selection["season_id"])
        listed = parse_json_array(read_verified_files(PROJECT_ROOT, manifest)[list_path], list_path)
        record = next(m for m in listed if m["match_id"] == match_id)
        markdown = texts(app.markdown)
        assert meta["home_team"]["home_team_name"] in markdown and meta["away_team"]["away_team_name"] in markdown
        assert f"{record['home_score']} – {record['away_score']}" in markdown

        shown_home = re.findall(r'<div class="v home">([^<]*)</div>', markdown)
        shown_away = re.findall(r'<div class="v away">([^<]*)</div>', markdown)
        assert shown_home == [str(totals[(match_id, home_id)][metric]) for metric in METRIC_NAMES]
        assert shown_away == [str(totals[(match_id, away_id)][metric]) for metric in METRIC_NAMES]

        assert len(app.dataframe) == 2
        tables = [table.value for table in app.dataframe]
        assert [int(table["team_id"].iloc[0]) for table in tables] == sorted([home_id, away_id])  # team-id order
        for table in tables:
            assert table["team_id"].nunique() == 1
            assert list(table["player_id"]) == sorted(table["player_id"])  # player-id order, not a ranking
        shown_rows += sum(len(table) for table in tables)
    assert seen == pilot_match_ids()  # every match, in the definition's order
    _, player_rows = pilot.run_pilot_query(PROJECT_ROOT, pilot_file, "player-rows")
    assert shown_rows == len(player_rows)  # the verified dataset's player-match rows


def companion_match_ids():
    """Pilot matches with a three-sixty companion manifest on disk, in pilot order."""
    commit = pilot.load_pilot(PROJECT_ROOT, PROJECT_ROOT / data.PILOT_FILE)["source_commit"]
    return [m for m in pilot_match_ids() if three_sixty.companion_path(PROJECT_ROOT, commit, m).is_file()]


def test_the_explorer_menu_lists_only_matches_with_verified_360_data(app):
    menu = explorer(app).selectbox(key="explorer_match")
    commit = pilot.load_pilot(PROJECT_ROOT, PROJECT_ROOT / data.PILOT_FILE)["source_commit"]
    expected = [data.match_summary(PROJECT_ROOT, manifest_path(PROJECT_ROOT, commit, m))["label"]
                for m in companion_match_ids()]
    assert menu.options == expected  # pilot order; a match without a companion manifest is not offered
    assert menu.value == companion_match_ids()[0]


def test_a_chosen_explorer_match_loads_and_is_kept_through_language_changes(app):
    target = companion_match_ids()[1]
    explorer(app).selectbox(key="explorer_match").select_index(1).run()
    assert not app.exception
    commit = pilot.load_pilot(PROJECT_ROOT, PROJECT_ROOT / data.PILOT_FILE)["source_commit"]
    meta = read_manifest(manifest_path(PROJECT_ROOT, commit, target))["match_metadata"]
    events = {e["id"] for e in data.load_explorer(PROJECT_ROOT, manifest_path(PROJECT_ROOT, commit, target))["events"]}
    for language in ("en", "tr", "de", "en"):
        app.selectbox(key="lang").set_value(language).run()
        assert not app.exception
        assert app.selectbox(key="explorer_match").value == target
        markdown = texts(app.markdown)
        assert meta["home_team"]["home_team_name"] in markdown and meta["away_team"]["away_team_name"] in markdown
        assert app.selectbox(key="event").value in events  # the actions are this match's
        assert f"{target}" in texts(app.caption)  # the footer names the match


def test_explorer_shows_an_action_without_a_snapshot_as_not_computed(app):
    explorer(app).selectbox(key="type").set_value("Starting XI").run()
    assert not app.exception
    infos = texts(app.info)
    assert "no 360° snapshot" in infos and "not computed" in infos


def test_explorer_draws_a_computed_action_and_explains_the_pitch(app):
    explorer(app).selectbox(key="type").set_value("Pressure").run()
    loaded = data.load_explorer(PROJECT_ROOT)
    computed = next(e["id"] for e in data.filter_events(loaded["events"], "Pressure")
                    if loaded["context_by_event"][e["id"]]["calculation_status"] == "computed")
    app.selectbox(key="event").set_value(computed).run()
    assert not app.exception
    captions = texts(app.caption)
    assert "Saved spatial_context.csv:" in captions and "not metres" in captions
    markdown = texts(app.markdown)
    assert "performed this action" in markdown and "attack from left to right" in markdown


def test_player_list_follows_the_team_and_runs_from_goalkeeper(app):
    explorer(app).selectbox(key="team").set_value(SPAIN).run()
    assert not app.exception
    squad = data.squad(data.load_explorer(PROJECT_ROOT)["events"])
    players = app.selectbox(key="player").options[1:]
    assert players and players[0].startswith("Unai Simón Mendibil · Goalkeeper")
    assert set(players) <= {data.player_label(info) for info in squad.values() if info["team_id"] == SPAIN}
    assert any("Morata" in option and "off 67:19" in option for option in players)


def test_filters_open_on_their_all_options_with_labels_in_each_language(app):
    explorer(app)
    for language, labels in (("en", ("All actions", "Both teams", "All players")),
                             ("tr", ("Tüm aksiyonlar", "İki takım", "Tüm oyuncular")),
                             ("de", ("Alle Aktionen", "Beide Teams", "Alle Spieler"))):
        app.selectbox(key="lang").set_value(language).run()
        for key, label in zip(("type", "team", "player"), labels):
            assert app.selectbox(key=key).value == ALL  # an option, never "no selection"
            assert shown_option(app, key) == label


def test_filters_that_match_nothing_say_so(app):
    explorer(app).selectbox(key="player").select_index(1).run()
    app.selectbox(key="type").set_value("Starting XI").run()
    assert not app.exception
    # The player is no longer a choice for that type, so the filter falls back to all players.
    assert app.selectbox(key="player").value == ALL and shown_option(app, "player") == "All players"


def test_reload_re_verifies_and_nothing_is_written(app):
    before = fingerprint()
    assert app.session_state["generation"] == 0
    app.button(key="reload").click().run()
    assert not app.exception
    assert app.session_state["generation"] == 1
    explorer(app)
    assert fingerprint() == before


def test_distance_rings_can_be_switched_off(app):
    explorer(app).selectbox(key="type").set_value("Pressure").run()
    rings = app.toggle(key="radii")
    assert rings.label.startswith("Distance rings") and rings.value is True
    rings.set_value(False).run()
    assert not app.exception and app.toggle(key="radii").value is False


def test_language_switch_translates_the_interface_and_keeps_the_selection(app):
    explorer(app).selectbox(key="type").set_value("Pressure").run()
    app.selectbox(key="event").select_index(3).run()
    chosen = app.selectbox(key="event").value
    for language, heading in (("tr", "Aksiyon bul"), ("de", "Aktion finden")):
        app.selectbox(key="lang").set_value(language).run()
        assert not app.exception
        assert any(heading in element.value for element in app.subheader)
        assert app.selectbox(key="type").value == "Pressure"  # the source name stays the value
        assert app.selectbox(key="event").value == chosen
    assert "Pressing" in app.selectbox(key="type").options
    app.selectbox(key="lang").set_value("en").run()
    assert app.toggle(key="radii").label.startswith("Distance rings")


# The action selector keeps the user's choice in its own session key (BC-05):
# in a browser, a language change could reset the selector to its default.
# AppTest does not run the browser's selector, so the reset is simulated by
# writing another value into the selector's state.


def shown_label(app):
    selector = app.selectbox(key="event")
    return selector.options[selector.index]


def test_a_chosen_action_survives_language_changes_and_is_labelled_in_each_language(app):
    explorer(app).selectbox(key="type").set_value("Pressure").run()
    app.selectbox(key="event").select_index(4).run()
    chosen = app.selectbox(key="event").value
    assert app.session_state["event_choice"] == chosen
    for language, type_name in (("tr", "Pres"), ("de", "Pressing"), ("en", "Pressure"), ("tr", "Pres")):
        app.selectbox(key="lang").set_value(language).run()
        assert not app.exception
        assert app.selectbox(key="event").value == chosen
        assert app.session_state["event_choice"] == chosen
        assert f" · {type_name} · " in shown_label(app)  # the label is in the active language


def test_a_lost_selector_value_is_restored_from_the_stored_choice(app):
    explorer(app).selectbox(key="type").set_value("Pressure").run()
    app.selectbox(key="event").select_index(4).run()
    chosen = app.selectbox(key="event").value
    other = data.filter_events(data.load_explorer(PROJECT_ROOT)["events"], "Pressure")[0]["id"]
    assert other != chosen
    app.session_state["event"] = other  # what a browser reset to the default looks like
    app.selectbox(key="lang").set_value("de").run()
    assert not app.exception
    assert app.selectbox(key="event").value == chosen


def test_a_choice_outside_the_filtered_list_falls_back_to_the_default(app):
    explorer(app).selectbox(key="type").set_value("Pressure").run()
    app.selectbox(key="event").select_index(4).run()
    chosen = app.selectbox(key="event").value
    loaded = data.load_explorer(PROJECT_ROOT)
    starting = data.filter_events(loaded["events"], "Starting XI")
    default = next((e["id"] for e in starting if loaded["context_by_event"][e["id"]]["frame_available"]),
                   starting[0]["id"])
    app.selectbox(key="type").set_value("Starting XI").run()
    assert not app.exception
    assert chosen not in {e["id"] for e in starting}
    assert app.selectbox(key="event").value == default  # the existing default: first with a snapshot, else first
    app.selectbox(key="lang").set_value("de").run()
    assert not app.exception
    assert app.selectbox(key="event").value == default  # and it stays through a language change
    app.selectbox(key="type").set_value("Pressure").run()
    assert app.selectbox(key="event").value == chosen  # available again, so the choice is restored


def test_actions_with_the_same_label_get_distinct_labels(app):
    explorer(app).selectbox(key="type").set_value("Starting XI").run()
    options = app.selectbox(key="event").options
    assert len(options) == len(set(options)) == 2
    assert options[0].endswith(" · Spain") and options[1].endswith(" · England")  # team names as recorded
    app.selectbox(key="event").select_index(1).run()
    england = app.selectbox(key="event").value
    app.selectbox(key="lang").set_value("tr").run()
    assert app.selectbox(key="event").value == england
    assert shown_label(app).endswith(" · England") and "İlk 11" in shown_label(app)


def test_previous_and_next_update_the_stored_choice(app):
    explorer(app).selectbox(key="type").set_value("Pressure").run()
    ids = [e["id"] for e in data.filter_events(data.load_explorer(PROJECT_ROOT)["events"], "Pressure")]
    start = ids.index(app.selectbox(key="event").value)
    app.button(key="event_next").click().run()
    assert app.selectbox(key="event").value == app.session_state["event_choice"] == ids[start + 1]
    app.button(key="event_prev").click().run()
    assert app.selectbox(key="event").value == app.session_state["event_choice"] == ids[start]
    app.selectbox(key="lang").set_value("tr").run()
    assert app.selectbox(key="event").value == ids[start]


def shown_option(app, key):
    selector = app.selectbox(key=key)
    return selector.options[selector.index]


def test_the_action_type_filter_keeps_its_value_and_is_labelled_in_each_language(app):
    explorer(app).selectbox(key="type").set_value("Pressure").run()
    assert app.session_state["type_choice"] == "Pressure"
    for language, label in (("tr", "Pres"), ("de", "Pressing"), ("en", "Pressure"), ("tr", "Pres")):
        app.selectbox(key="lang").set_value(language).run()
        assert not app.exception
        assert app.selectbox(key="type").value == "Pressure"  # the source name stays the value
        assert shown_option(app, "type") == label
    app.selectbox(key="type").set_value("Ball Recovery").run()  # chosen while the interface is Turkish
    assert shown_option(app, "type") == "Top kazanma"
    for language, label in (("en", "Ball Recovery"), ("de", "Ballgewinn")):
        app.selectbox(key="lang").set_value(language).run()
        assert app.selectbox(key="type").value == "Ball Recovery"
        assert shown_option(app, "type") == label


def test_the_action_type_filter_is_restored_or_falls_back_safely(app):
    explorer(app).selectbox(key="type").set_value("Pressure").run()
    app.session_state["type"] = ALL  # what a browser reset to the default looks like
    app.selectbox(key="lang").set_value("de").run()
    assert app.selectbox(key="type").value == "Pressure"
    # A kept value that is no longer an option is ignored, and so is a
    # selector left with no selection: the filter falls back to "All
    # actions". (AppTest cannot hold an invalid value in the selector.)
    app.session_state["type_choice"] = "No such type"
    app.session_state["type"] = None
    app.selectbox(key="lang").set_value("en").run()
    assert not app.exception
    assert app.selectbox(key="type").value == ALL and shown_option(app, "type") == "All actions"
    assert app.selectbox(key="event").value  # the action list still opens on its default


def test_the_player_filter_keeps_its_value_across_language_changes(app):
    explorer(app).selectbox(key="team").set_value(SPAIN).run()
    app.selectbox(key="player").select_index(1).run()
    goalkeeper = app.selectbox(key="player").value
    for language, position in (("tr", "Kaleci"), ("de", "Torwart"), ("en", "Goalkeeper")):
        app.selectbox(key="lang").set_value(language).run()
        assert app.selectbox(key="player").value == goalkeeper
        assert f" · {position} · " in shown_option(app, "player")  # recorded position, in the active language


def test_turkish_overview_uses_football_terms(app):
    app.selectbox(key="lang").set_value("tr").run()
    assert not app.exception
    assert "Pres aksiyonları" in texts(app.markdown)
    captions = texts(app.caption)
    assert "normalize edilmemiştir" in captions and "performans puanı değildir" in captions


def test_guide_opens_with_its_three_sections(app):
    app.button(key="guide").click().run()
    assert not app.exception
    markdown = texts(app.markdown)
    assert "Match overview" in markdown and "Gold star" in markdown and "Not computed" in markdown
