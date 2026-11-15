"""The interactive pitch for one event's frame. Skipped unless the dashboard group is installed.

The chart is checked through its Vega-Lite specification; nothing is
rendered and no browser is opened.
"""

import math

import pytest

pytest.importorskip("altair")

from phaselens.dashboard_pitch import pitch_chart  # noqa: E402


def entry(location, teammate=True, actor=False, keeper=False):
    return {"location": location, "teammate": teammate, "actor": actor, "keeper": keeper}


EVENT = {"id": "e1", "location": [50.0, 40.0], "player": {"id": 7, "name": "Player Seven"},
         "team": {"id": 1, "name": "Team One"}}
FRAME = {
    "event_uuid": "e1",
    "visible_area": [0, 0, 120, 0, 120, 80, 0, 0],
    "freeze_frame": [
        entry([50.5, 40.0], actor=True),
        entry([53.0, 44.0]),
        entry([60.0, 40.0], teammate=False),
        entry([130.0, -6.0], teammate=False, keeper=True),  # outside the pitch frame
        entry([1.0]),                                       # malformed: not drawn
    ],
}
NAMES = {"teammate": "Team One", "opponent": "Team Two"}


def spec(*args, **kwargs):
    return pitch_chart(*args, team_names=NAMES, **kwargs).to_dict()


def layers(chart):
    return chart["layer"]


def rows(layer):
    return layer["data"]["values"]


def groups(chart, prefix):
    """Path layers whose group name starts with `prefix`, as {group: points}."""
    found = {}
    for layer in layers(chart):
        for row in rows(layer):
            if str(row.get("group", "")).startswith(prefix):
                found.setdefault(row["group"], []).append((row["x"], row["y"]))
    return found


def texts(chart):
    return [row["text"] for layer in layers(chart) if layer["mark"]["type"] == "text" for row in rows(layer)]


def players(chart):
    layer = next((layer for layer in layers(chart) if "color" in layer.get("encoding", {})), None)
    return (rows(layer), layer) if layer else ([], None)


def test_scales_are_shared_fixed_and_y_points_down():
    chart = spec(EVENT, [FRAME])
    y = layers(chart)[0]["encoding"]["y"]["scale"]
    x = layers(chart)[0]["encoding"]["x"]["scale"]
    assert y["reverse"] is True  # origin at the top-left, y downward
    x_span, y_span = x["domain"][1] - x["domain"][0], y["domain"][1] - y["domain"][0]
    assert chart["height"] == round(chart["width"] * y_span / x_span)  # equal scaling
    assert all(layer["encoding"]["x"]["scale"] == x for layer in layers(chart))


def test_out_of_convention_points_stay_inside_the_domain():
    chart = spec(EVENT, [FRAME])
    (x_low, x_high), (y_low, y_high) = (layers(chart)[0]["encoding"][axis]["scale"]["domain"] for axis in "xy")
    assert x_low < 0 and x_high > 130.0
    assert y_low < -6.0 and y_high > 80.0


def test_radius_circles_are_centred_on_the_actor():
    rings = groups(spec(EVENT, [FRAME], radii=(5.0, 10.0, 20.0)), "r")
    assert sorted(rings) == ["r10", "r20", "r5"]
    for name, points in rings.items():
        radius = float(name[1:])
        assert all(math.isclose(math.hypot(x - 50.5, y - 40.0), radius) for x, y in points)
    assert not any("5" in text for text in texts(spec(EVENT, [FRAME], radii=(5.0,)))
                   if text != "Player Seven")  # no radius text on the pitch


def test_radius_circles_switched_off_leave_no_circle():
    assert groups(spec(EVENT, [FRAME], radii=()), "r") == {}


def test_only_the_actor_is_named_and_neighbours_carry_team_and_distance():
    chart = spec(EVENT, [FRAME])
    assert texts(chart) == ["Player Seven", "Team One · attacking direction"]
    shown, layer = players(chart)
    assert {row["who"] for row in shown} == {"Team One · teammate", "Team Two · opponent",
                                             "Team Two · opponent · goalkeeper"}
    assert not any("Player" in row["who"] for row in shown)
    assert next(row for row in shown if row["x"] == 53.0)["distance"] == "4.717"
    assert [tip["title"] for tip in layer["encoding"]["tooltip"]] == [
        "Player", "Distance to Player Seven", "Position (x, y)"]


def test_team_colours_can_be_set():
    _, layer = players(pitch_chart(EVENT, [FRAME], colours={"teammate": "#123456", "opponent": "#654321"}).to_dict())
    assert layer["encoding"]["color"]["scale"]["range"][:2] == ["#123456", "#654321"]


def test_visible_area_is_drawn_only_on_request():
    assert groups(spec(EVENT, [FRAME]), "area") == {}
    area = groups(spec(EVENT, [FRAME], show_visible_area=True), "area")["area"]
    assert area == [(0, 0), (120, 0), (120, 80), (0, 0)]


def test_event_without_a_frame_shows_a_message_and_no_players_or_arrow():
    chart = spec(EVENT, [])
    assert texts(chart) == ["No 360° snapshot for this action"]
    assert players(chart) == ([], None)
    assert groups(chart, "arrow") == {}


def test_duplicate_frames_are_not_drawn():
    chart = spec(EVENT, [FRAME, FRAME])
    assert texts(chart) == ["2 snapshots linked to this action; none is drawn"]
    assert players(chart) == ([], None)


def test_texts_follow_the_language():
    chart = spec(EVENT, [FRAME], language="tr")
    shown, layer = players(chart)
    assert "Team One · takım arkadaşı" in {row["who"] for row in shown}
    assert layer["encoding"]["tooltip"][1]["title"] == "Player Seven ile mesafe"
    assert texts(spec(EVENT, [], language="de")) == ["Keine 360°-Aufnahme für diese Aktion"]


def test_scroll_zoom_is_bound_to_the_scales():
    params = spec(EVENT, [FRAME])["params"]  # Altair lifts a layer's param to the top level
    assert params[0]["name"] == "zoom" and params[0]["bind"] == "scales"
