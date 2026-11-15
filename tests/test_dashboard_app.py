"""Exercise the Streamlit script with Streamlit's own AppTest, in-process.

This runs the app script and its widgets without a browser or a server;
it does not show that the browser interface renders correctly. Skipped
unless the dashboard group is installed and the real prepared data is on
disk. The app only reads, so the data is left unchanged.
"""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from phaselens import dashboard_data as data  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = PROJECT_ROOT / "src/phaselens/dashboard_app.py"
NEEDED = [
    PROJECT_ROOT / data.PILOT_FILE,
    PROJECT_ROOT / data.FINAL_MANIFEST,
    PROJECT_ROOT / "data/processed/analytics" / data.FINAL_COMMIT / "pilots/euro2024_knockout_pilot/build_metadata.json",
    PROJECT_ROOT / "manifests/statsbomb/open-data" / data.FINAL_COMMIT / f"match_{data.FINAL_MATCH_ID}.three_sixty.json",
]
SPAIN = 772


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
    assert len(match.options) == 5
    markdown = texts(app.markdown)
    assert "UEFA Euro 2024 · Final · 2024-07-14" in markdown and "2 – 1" in markdown
    assert "Pressure events" in markdown
    match.select_index(1).run()
    assert not app.exception
    captions = texts(app.caption)
    assert "not normalized" in captions and "not ratings" in captions and "StatsBomb Open Data" in captions


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


def test_filters_that_match_nothing_say_so(app):
    explorer(app).selectbox(key="player").select_index(1).run()
    app.selectbox(key="type").set_value("Starting XI").run()
    assert not app.exception
    # The player is no longer a choice for that type, so the filter falls back to all players.
    assert app.selectbox(key="player").value is None


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
