"""An interactive pitch for one event's three-sixty frame, built with Altair.

The chart is a Vega-Lite specification drawn in the browser: pointing at a
player shows a tooltip, scrolling zooms, dragging pans, and a double-click
resets the view. Coordinates are drawn as recorded: origin top-left, y
downward, equal scaling on both axes. Nothing is clipped or flipped. Only
the actor is named: the 360 specification marks the player performing the
event as the actor, and that player is the event's `player`. Other entries
stay anonymous; their tooltip gives the team flag, the keeper flag, the
recorded position, and the straight-line distance to the actor in source
units, rounded for display only.
"""

import logging
import math
from functools import lru_cache

import altair as alt

from phaselens.dashboard_data import format_distance
from phaselens.dashboard_i18n import DEFAULT_LANGUAGE, t
from phaselens.three_sixty import FRAME_CONVENTION

BACKGROUND = "#131b34"  # the card colour of the dashboard
PITCH = "#1f7a47"
PITCH_STRIPE = "#23864e"  # decorative mowing stripes; carry no data
PITCH_LINES = "#d8efe0"
LIGHT = "#f4f6fb"
TEAMMATE = "#3b82f6"
OPPONENT = "#f97316"
UNKNOWN_TEAM = "#9ca3af"
ACTOR = "#facc15"
LABEL_BACKING = "#0b1020"  # behind the actor's name: 12.4:1 against ACTOR
# The name is drawn and measured in the same named font, so the backing
# fits it. A browser without this font substitutes another, and the
# measurement then falls back to Matplotlib's default font as well.
LABEL_FONT = "Arial"
LABEL_SIZE = 13
LABEL_PADDING = 6  # pixels on each side of the name
STAR = "M0,-1L0.24,-0.33L0.95,-0.31L0.39,0.12L0.59,0.81L0,0.4L-0.59,0.81L-0.39,0.12L-0.95,-0.31L-0.24,-0.33Z"
WIDTH = 760  # pixels; the height follows from equal scaling
_MARGIN = 4.0
_ARROW_GAP = 2.5  # source units between the pitch's bottom line and the direction arrow
# Box corners as labelled on the pitch figure of Events v4.0.0 (p. 23).
_MARKINGS = [((0, 18), 18, 44), ((0, 30), 6, 20), ((102, 18), 18, 44), ((114, 30), 6, 20)]


def _point(value):
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in value)
    )


@lru_cache(maxsize=512)
def label_width(text):
    """Pixel width of `text` in the bold label font, measured with Matplotlib's font metrics."""
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextToPath

    logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)  # a missing font falls back quietly
    font = FontProperties(family=LABEL_FONT, weight="bold", size=LABEL_SIZE)
    width, _, _ = TextToPath().get_text_width_height_descent(text, font, ismath=False)
    return math.ceil(width)  # at 72 dpi one point is one pixel, the unit of Vega's fontSize


def _circle(cx, cy, radius, group, steps=72):
    return [{"x": cx + radius * math.cos(2 * math.pi * i / steps), "y": cy + radius * math.sin(2 * math.pi * i / steps),
             "i": i, "group": group} for i in range(steps + 1)]


class _Axes:
    """Shared x and y encodings, so every layer uses the same fixed scales."""

    def __init__(self, x_domain, y_domain):
        self.x_scale = alt.Scale(domain=list(x_domain), nice=False, zero=False)
        self.y_scale = alt.Scale(domain=list(y_domain), nice=False, zero=False, reverse=True)

    def xy(self, x="x", y="y"):
        return {"x": alt.X(f"{x}:Q", scale=self.x_scale, axis=None),
                "y": alt.Y(f"{y}:Q", scale=self.y_scale, axis=None)}

    def box(self):
        return {**self.xy("x0", "y0"), "x2": alt.X2("x1:Q"), "y2": alt.Y2("y1:Q")}


def pitch_chart(event, frames, radii=(), show_visible_area=False, language=DEFAULT_LANGUAGE,
                colours=None, team_names=None):
    """A layered Altair chart for one event. `frames` is the list of frames linked to it.

    The frame is drawn only when exactly one frame is linked. Radius
    circles are centred on actor.location and are circles in source
    coordinate units, not asserted physical distances. `colours` may
    replace the teammate and opponent colours and `team_names` names the
    actor's team and the other team ({"teammate": ..., "opponent": ...});
    `language` sets the texts only.
    """
    colours = {"teammate": TEAMMATE, "opponent": OPPONENT, **(colours or {})}
    team_names = {"teammate": None, "opponent": None, **(team_names or {})}
    (x_low, x_high), (y_low, y_high) = FRAME_CONVENTION["x"], FRAME_CONVENTION["y"]
    xs, ys = [x_low, x_high], [y_low, y_high + _ARROW_GAP]  # the margin below holds the arrow's label
    player = event.get("player") if isinstance(event.get("player"), dict) else {}
    team = event.get("team") if isinstance(event.get("team"), dict) else {}
    actor_name = player.get("name")
    layers = []  # (rows, mark, encoding builder), drawn in order

    def add(rows, mark, options, encode):
        layers.append((rows, mark, options, encode))

    # Pitch: grass, decorative stripes, lines.
    stripe = (x_high - x_low) / 12
    add([{"x0": x_low, "x1": x_high, "y0": y_low, "y1": y_high}], "mark_rect", {"color": PITCH}, "box")
    add([{"x0": x_low + n * stripe, "x1": x_low + (n + 1) * stripe, "y0": y_low, "y1": y_high} for n in range(1, 12, 2)],
        "mark_rect", {"color": PITCH_STRIPE}, "box")
    boxes = [{"x0": x_low, "x1": x_high, "y0": y_low, "y1": y_high}] + [
        {"x0": cx, "x1": cx + w, "y0": cy, "y1": cy + h} for (cx, cy), w, h in _MARKINGS]
    add(boxes, "mark_rect", {"fillOpacity": 0, "stroke": PITCH_LINES, "strokeWidth": 1.2}, "box")
    # Decorative centre circle, like the stripes: not taken from the provider's figure.
    add([{"x": 60, "y": y_low, "i": 0, "group": "half"}, {"x": 60, "y": y_high, "i": 1, "group": "half"}]
        + _circle(60, 40, 10, "centre"), "mark_line", {"color": PITCH_LINES, "strokeWidth": 1}, "path")

    location = event.get("location")
    if _point(location):
        xs.append(location[0])
        ys.append(location[1])

    def add_spot():
        if _point(location):
            add([{"x": location[0], "y": location[1], "who": t("plot_event_location", language),
                  "position": f"{location[0]:.1f}, {location[1]:.1f}"}], "mark_point",
                {"shape": "diamond", "filled": False, "size": 260, "stroke": LIGHT, "strokeWidth": 2, "opacity": 1},
                "spot")

    frame = frames[0] if len(frames) == 1 else None
    if frame is None:
        message = t("plot_no_frame", language) if not frames else t("plot_duplicates", language, count=len(frames))
        add_spot()
        add([{"x0": 25, "x1": 95, "y0": 34, "y1": 46}], "mark_rect",
            {"color": BACKGROUND, "opacity": 0.9, "cornerRadius": 8}, "box")
        add([{"x": 60, "y": 40, "text": message}], "mark_text",
            {"color": LIGHT, "fontSize": 15, "align": "center", "baseline": "middle"}, "text")
    else:
        entries = [e for e in frame.get("freeze_frame", []) if isinstance(e, dict) and _point(e.get("location"))] \
            if isinstance(frame.get("freeze_frame"), list) else []
        actors = [e["location"] for e in entries if e.get("actor") is True]
        actor = actors[0] if len(actors) == 1 else None
        for entry in entries:
            xs.append(entry["location"][0])
            ys.append(entry["location"][1])

        area = frame.get("visible_area")
        if show_visible_area and isinstance(area, list) and len(area) >= 6 and len(area) % 2 == 0 \
                and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in area):
            points = list(zip(area[0::2], area[1::2]))
            add([{"x": x, "y": y, "i": i, "group": "area"} for i, (x, y) in enumerate(points)], "mark_line",
                {"filled": True, "fill": "white", "fillOpacity": 0.14, "stroke": LIGHT, "strokeDash": [2, 3],
                 "strokeWidth": 1}, "path")
            xs.extend(p[0] for p in points)
            ys.extend(p[1] for p in points)

        if actor is not None:
            for radius in radii:
                add(_circle(actor[0], actor[1], radius, f"r{radius:g}"), "mark_line",
                    {"color": LIGHT, "opacity": 0.75, "strokeDash": [5, 4], "strokeWidth": 1.1}, "path")
                xs.extend([actor[0] - radius, actor[0] + radius])
                ys.extend([actor[1] - radius, actor[1] + radius])

        rows = []
        for entry in entries:
            if entry.get("actor") is True:
                continue
            x, y = entry["location"]
            flag = entry.get("teammate")
            group = "teammate" if flag is True else "opponent" if flag is False else "unknown"
            who = t(f"tt_{group}", language, team=team_names[group] or "–") if group != "unknown" \
                else t("plot_unknown", language)
            if entry.get("keeper") is True:
                who += f" · {t('tt_keeper', language)}"
            rows.append({"x": x, "y": y, "group": group, "who": who, "keeper": entry.get("keeper") is True,
                         "position": f"{x:.1f}, {y:.1f}",
                         "distance": format_distance(math.hypot(x - actor[0], y - actor[1]), language)
                         if actor is not None else "–"})
        keepers = [r for r in rows if r["keeper"]]
        if keepers:
            add(keepers, "mark_point", {"shape": "circle", "filled": False, "size": 620, "stroke": LIGHT,
                                        "strokeWidth": 1.6}, "xy")
        if rows:
            add(rows, "mark_point", {"filled": True, "size": 190, "opacity": 1, "stroke": "white",
                                     "strokeWidth": 1.4, "cursor": "pointer"}, ("players", colours, actor_name))
        add_spot()  # under the star, so pointing at the star shows the actor
        if actor is not None:
            add([{"x": actor[0], "y": actor[1], "who": actor_name or t("plot_actor", language),
                  "position": f"{actor[0]:.1f}, {actor[1]:.1f}"}], "mark_point",
                {"shape": STAR, "filled": True, "size": 650, "color": ACTOR, "stroke": "#1f2937", "strokeWidth": 1,
                 "opacity": 1}, "actor")
            if actor_name:
                # A dark backing under the name keeps it readable over grass and
                # markers; its width is the measured width of the name.
                add([{"x": actor[0], "y": actor[1]}], "mark_rect",
                    {"color": LABEL_BACKING, "opacity": 0.85, "cornerRadius": 4, "height": LABEL_SIZE + 5,
                     "width": label_width(actor_name) + 2 * LABEL_PADDING, "yOffset": -22}, "xy")
                add([{"x": actor[0], "y": actor[1], "text": actor_name}], "mark_text",
                    {"color": ACTOR, "font": LABEL_FONT, "fontSize": LABEL_SIZE, "fontWeight": "bold", "dy": -22,
                     "align": "center", "baseline": "middle"}, "text")

        # The 360 specification orients every frame with the actor's team
        # attacking from 0 to 120 on the x axis (p. 2).
        arrow_y = y_high + _ARROW_GAP
        add([{"x": x_low + 40, "y": arrow_y, "i": 0, "group": "arrow"},
             {"x": x_high - 40, "y": arrow_y, "i": 1, "group": "arrow"}], "mark_line",
            {"color": LIGHT, "strokeWidth": 1.6}, "path")
        add([{"x": x_high - 40, "y": arrow_y}], "mark_point",
            {"shape": "triangle-right", "filled": True, "size": 120, "color": LIGHT, "opacity": 1}, "xy")
        direction = t("plot_attacking", language)
        add([{"x": 60, "y": arrow_y + 0.8, "text": f"{team.get('name')} · {direction}" if team.get("name") else direction}],
            "mark_text", {"color": LIGHT, "fontSize": 11, "align": "center", "baseline": "top"}, "text")

    x_domain = (min(xs) - _MARGIN, max(xs) + _MARGIN)
    y_domain = (min(ys) - _MARGIN, max(ys) + _MARGIN)
    axes = _Axes(x_domain, y_domain)
    tooltip_who = alt.Tooltip("who:N", title=t("tt_who", language))
    tooltip_position = alt.Tooltip("position:N", title=t("tt_position", language))
    charts = []
    for rows, mark, options, kind in layers:
        chart = getattr(alt.Chart(alt.Data(values=rows)), mark)(clip=True, **options)  # nothing spills when zoomed
        if kind == "box":
            chart = chart.encode(**axes.box())
        elif kind == "path":
            chart = chart.encode(**axes.xy(), order="i:Q", detail="group:N")
        elif kind == "text":
            chart = chart.encode(**axes.xy(), text="text:N")
        elif kind == "xy":
            chart = chart.encode(**axes.xy())
        elif kind in ("actor", "spot"):
            chart = chart.encode(**axes.xy(), tooltip=[tooltip_who, tooltip_position])
        else:  # the anonymous players
            _, colours_, name = kind
            chart = chart.encode(
                **axes.xy(),
                color=alt.Color("group:N", legend=None, scale=alt.Scale(
                    domain=["teammate", "opponent", "unknown"],
                    range=[colours_["teammate"], colours_["opponent"], UNKNOWN_TEAM])),
                shape=alt.Shape("group:N", legend=None, scale=alt.Scale(
                    domain=["teammate", "opponent", "unknown"], range=["circle", "circle", "triangle-up"])),
                tooltip=[tooltip_who,
                         alt.Tooltip("distance:N", title=t("tt_distance", language,
                                                           player=name or t("plot_actor", language))),
                         tooltip_position],
            )
        charts.append(chart)
    # Scroll to zoom and drag to pan; a double-click resets the view.
    charts[0] = charts[0].add_params(alt.selection_interval(bind="scales", name="zoom"))
    height = round(WIDTH * (y_domain[1] - y_domain[0]) / (x_domain[1] - x_domain[0]))
    # Explicit "pad" sizing: without it Streamlit applies "fit", which shrinks
    # the plot height to make room for padding and so breaks equal scaling.
    return alt.layer(*charts).properties(width=WIDTH, height=height, background="transparent", padding=0,
                                         autosize=alt.AutoSizeParams(type="pad", contains="content")) \
        .configure_view(strokeWidth=0)
