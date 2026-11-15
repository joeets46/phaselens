"""Event-level spatial context around a frame's actor.

The contract is docs/metric_catalog.md, "Exploratory event-level
indicators". Events and frames are invented; distances are chosen so
that boundary cases fall exactly on a radius.
"""

import csv
import io
import json
import math

import pytest

from phaselens import cli, three_sixty
from phaselens.three_sixty import ThreeSixtyError, build_spatial_context
from synthetic import COMMIT, EVENTS_PATH, MATCH_ID, THREE_SIXTY_PATH, snapshot, source_url

RADII_LABELS = ("5u", "10u", "20u")


def event(event_id, location=(50.0, 40.0), **fields):
    record = {
        "id": event_id, "index": 1, "period": 1,
        "type": {"id": 17, "name": "Pressure"},
        "team": {"id": 1, "name": "Home"}, "player": {"id": 11, "name": "P"},
        **fields,
    }
    if location is not None:
        record["location"] = list(location)
    return record


def entry(location, teammate=True, actor=False, keeper=False):
    return {"location": location, "teammate": teammate, "actor": actor, "keeper": keeper}


ACTOR = entry([50.0, 40.0], actor=True)
CLOSED_AREA = [0, 0, 120, 0, 120, 80, 0, 80, 0, 0]
# The planned example: distances 5, 10, 6, 60 and 80 from the actor.
EXAMPLE_FRAME = {
    "event_uuid": "e1",
    "visible_area": CLOSED_AREA,
    "freeze_frame": [
        ACTOR,
        entry([53.0, 44.0]),                                  # teammate, 5.0
        entry([60.0, 40.0]),                                  # teammate, 10.0
        entry([50.0, 46.0], teammate=False),                  # opponent, 6.0
        entry([110.0, 40.0], teammate=False, keeper=True),    # opponent keeper, 60.0
        entry([130.0, 40.0], teammate=False),                 # opponent outside 0..120, 80.0
        entry([1.0]),                                         # malformed location
    ],
}


def frame(event_id, entries, **fields):
    return {"event_uuid": event_id, "visible_area": CLOSED_AREA, "freeze_frame": entries, **fields}


def build(frames, events, radii=three_sixty.CONTEXT_RADII):
    rows, columns, counts = build_spatial_context(frames, events, COMMIT, MATCH_ID, radii)
    return {row["event_id"]: row for row in rows}, columns, counts


def one(frames, events=None, event_id="e1", **kwargs):
    rows, _, _ = build(frames, events or [event(event_id)], **kwargs)
    return rows[event_id]


INDICATORS = [
    "visible_teammates", "visible_opponents", "nearest_visible_opponent_distance",
    *(f"visible_{side}_within_{label}" for label in RADII_LABELS for side in ("teammates", "opponents")),
    "entries_excluded_from_context", "context_has_excluded_entries",
]


# --- the planned example --------------------------------------------------


def test_planned_example():
    row = one([EXAMPLE_FRAME])
    assert row["calculation_status"] == "computed" and row["frame_available"] is True
    assert (row["actor_x"], row["actor_y"], row["actor_event_distance"]) == (50.0, 40.0, 0.0)
    assert row["visible_entries"] == 7
    assert (row["entries_location_invalid"], row["entries_teammate_flag_invalid"]) == (1, 0)
    assert (row["entries_excluded_from_context"], row["context_has_excluded_entries"]) == (1, True)
    assert row["entries_outside_frame_convention"] == 1
    assert row["visible_opponent_keeper_entries"] == 1
    assert (row["visible_teammates"], row["visible_opponents"]) == (2, 3)
    assert row["nearest_visible_opponent_distance"] == 6.0
    within = {label: (row[f"visible_teammates_within_{label}"], row[f"visible_opponents_within_{label}"])
              for label in RADII_LABELS}
    # 5.0 and 10.0 lie exactly on a radius and count: the boundary is inclusive.
    assert within == {"5u": (1, 0), "10u": (2, 1), "20u": (2, 1)}


def test_the_actor_is_not_counted_but_a_distinct_entry_at_its_location_is():
    row = one([frame("e1", [ACTOR, entry([50.0, 40.0]), entry([50.0, 40.0], teammate=False)])])
    assert (row["visible_teammates"], row["visible_opponents"]) == (1, 1)
    assert row["nearest_visible_opponent_distance"] == 0.0
    assert row["visible_teammates_within_5u"] == 1 and row["visible_opponents_within_5u"] == 1


def test_frame_with_only_the_actor_gives_zero_counts_and_no_nearest_opponent():
    row = one([frame("e1", [ACTOR])])
    assert row["calculation_status"] == "computed"
    assert (row["visible_teammates"], row["visible_opponents"]) == (0, 0)
    assert row["nearest_visible_opponent_distance"] is None
    assert all(row[f"visible_{side}_within_{label}"] == 0 for label in RADII_LABELS for side in ("teammates", "opponents"))
    assert row["context_has_excluded_entries"] is False


def test_event_without_a_frame_keeps_identity_and_leaves_indicators_null():
    rows, _, _ = build([EXAMPLE_FRAME], [event("e1"), event("e2", location=(30.0, 20.0))])
    row = rows["e2"]
    assert (row["frame_available"], row["calculation_status"]) == (False, "no_frame")
    assert (row["event_type_name"], row["team_id"], row["player_id"]) == ("Pressure", 1, 11)
    assert (row["event_x"], row["event_y"], row["event_location_status"]) == (30.0, 20.0, "valid")
    for column in INDICATORS + ["visible_entries", "visible_area_status", "actor_x", "actor_event_distance"]:
        assert row[column] is None, column


# --- statuses that prevent the calculation --------------------------------


@pytest.mark.parametrize(
    "frames, status",
    [
        ([frame("e1", [ACTOR]), frame("e1", [ACTOR])], "duplicate_frames"),
        ([frame("e1", "not a list")], "freeze_frame_malformed"),
        ([frame("e1", [ACTOR, {**entry([1.0, 1.0]), "actor": "true"}])], "actor_selection_ambiguous"),
        ([frame("e1", [ACTOR, {"location": [1.0, 1.0], "teammate": True}])], "actor_selection_ambiguous"),
        ([frame("e1", [ACTOR, {**entry([1.0, 1.0]), "actor": None}])], "actor_selection_ambiguous"),
        ([frame("e1", [ACTOR, "not an object"])], "actor_selection_ambiguous"),
        ([frame("e1", [entry([1.0, 1.0]), entry([2.0, 2.0])])], "no_actor"),
        ([frame("e1", [ACTOR, entry([1.0, 1.0], actor=True)])], "multiple_actors"),
    ],
    ids=["duplicate", "not a list", "actor as text", "actor missing", "actor null",
         "entry not an object", "no actor", "two actors"],
)
def test_frames_that_cannot_be_measured_get_a_status_and_null_indicators(frames, status):
    row = one(frames)
    assert row["calculation_status"] == status and row["frame_available"] is True
    assert all(row[column] is None for column in INDICATORS)


@pytest.mark.parametrize(
    "location",
    [[True, 40.0], ["50", 40.0], [math.nan, 40.0], [50.0, math.inf], [50.0], [50.0, 40.0, 0.0], None, "50,40"],
    ids=["boolean", "string", "nan", "infinity", "one value", "three values", "null", "text"],
)
def test_actor_location_must_be_two_finite_numbers(location):
    row = one([frame("e1", [{**ACTOR, "location": location}, entry([51.0, 40.0])])])
    assert row["calculation_status"] == "actor_location_invalid"
    assert row["actor_x"] is None and all(row[column] is None for column in INDICATORS)


def test_failed_rows_report_only_what_can_be_established():
    row = one([frame("e1", [entry([1.0, 1.0]), entry([2.0, 2.0])])])  # no actor
    assert (row["visible_entries"], row["visible_area_status"]) == (2, "closed_numeric")
    assert row["entries_location_invalid"] is None and row["entries_outside_frame_convention"] is None
    duplicate = one([frame("e1", [ACTOR]), frame("e1", [ACTOR])])
    assert duplicate["visible_entries"] is None and duplicate["visible_area_status"] is None


# --- excluded entries and overlapping diagnostics -------------------------


def test_excluded_entries_leave_a_computed_row_that_says_so():
    row = one([frame("e1", [
        ACTOR,
        entry([50.0, math.nan], teammate=False),          # non-finite: excluded
        entry([True, 40.0], teammate=False),              # boolean coordinate: excluded
        {**entry([52.0, 40.0]), "teammate": None},        # null teammate flag: excluded
        entry([55.0, 40.0], teammate=False),              # valid opponent at 5.0
    ])])
    assert row["calculation_status"] == "computed"
    assert row["entries_excluded_from_context"] == 3 and row["context_has_excluded_entries"] is True
    assert (row["entries_location_invalid"], row["entries_teammate_flag_invalid"]) == (2, 1)
    assert (row["visible_teammates"], row["visible_opponents"]) == (0, 1)
    assert row["nearest_visible_opponent_distance"] == 5.0


def test_one_entry_can_count_in_two_diagnostics_but_once_as_excluded():
    row = one([frame("e1", [ACTOR, {**entry([1.0]), "teammate": "yes"}])])
    assert (row["entries_location_invalid"], row["entries_teammate_flag_invalid"]) == (1, 1)
    assert row["entries_excluded_from_context"] == 1
    # Zero counts here mean no valid entry qualified, not an empty measured frame.
    assert (row["visible_teammates"], row["visible_opponents"], row["context_has_excluded_entries"]) == (0, 0, True)


def test_out_of_convention_coordinates_are_kept_and_flagged_never_corrected():
    row = one([frame("e1", [{**ACTOR, "location": [-2.0, 40.0]}, entry([-2.0, 86.0], teammate=False)])],
              events=[event("e1", location=(0.0, 40.0))])
    assert row["calculation_status"] == "computed"
    assert (row["actor_x"], row["actor_outside_frame_convention"]) == (-2.0, True)
    assert row["entries_outside_frame_convention"] == 1
    assert row["nearest_visible_opponent_distance"] == 46.0
    assert row["actor_event_distance"] == 2.0


@pytest.mark.parametrize(
    "location, status, distance",
    [(None, "missing", None), ((1.0, 2.0, 3.0), "invalid", None), ((50.0, 43.0), "valid", 3.0)],
    ids=["missing", "invalid", "valid"],
)
def test_event_location_only_affects_the_actor_event_distance(location, status, distance):
    row = one([frame("e1", [ACTOR])], events=[event("e1", location=location)])
    assert (row["event_location_status"], row["actor_event_distance"]) == (status, distance)
    assert row["calculation_status"] == "computed"


# --- inputs and parameters ------------------------------------------------


def test_duplicate_source_event_ids_are_rejected():
    with pytest.raises(ThreeSixtyError, match="occur more than once"):
        build([EXAMPLE_FRAME], [event("e1"), event("e1")])


def test_event_without_a_usable_id_is_rejected():
    with pytest.raises(ThreeSixtyError, match="no usable id"):
        build([EXAMPLE_FRAME], [{**event("x"), "id": None}])


@pytest.mark.parametrize(
    "radii",
    [[], [0], [-1.0], [True], ["5"], [math.inf], [math.nan], [5, 5.0], 5],
    ids=["empty", "zero", "negative", "boolean", "string", "infinity", "nan", "repeated", "not a sequence"],
)
def test_invalid_radii_are_rejected(radii):
    with pytest.raises(ThreeSixtyError):
        three_sixty.validate_radii(radii)


def test_radii_are_sorted_and_labelled():
    assert three_sixty.validate_radii([20, 2.5, 10]) == (2.5, 10.0, 20.0)
    _, columns, _ = build([EXAMPLE_FRAME], [event("e1")], radii=[2.5, 10])
    assert columns[-4:] == ["visible_teammates_within_2p5u", "visible_opponents_within_2p5u",
                            "visible_teammates_within_10u", "visible_opponents_within_10u"]


def test_radius_counts_never_decrease_and_never_exceed_the_group():
    frames = [EXAMPLE_FRAME, frame("e2", [ACTOR, *(entry([50.0 + d, 40.0], teammate=d % 2 == 0) for d in range(1, 30))])]
    rows, _, _ = build(frames, [event("e1"), event("e2")])
    for row in rows.values():
        for side, group in (("teammates", "visible_teammates"), ("opponents", "visible_opponents")):
            counts = [row[f"visible_{side}_within_{label}"] for label in RADII_LABELS]
            assert counts == sorted(counts) and counts[-1] <= row[group]


def test_frames_not_linked_to_any_event_are_counted_not_turned_into_rows():
    rows, _, counts = build([EXAMPLE_FRAME, frame("ghost", [ACTOR]), {"freeze_frame": []}], [event("e1")])
    assert list(rows) == ["e1"]
    assert counts == {"records": 3, "records_linked_to_an_event": 1,
                      "records_not_linked_to_an_event": 1, "records_with_unusable_key": 1}


# --- the command, on an ingested synthetic match ---------------------------

MANIFEST = f"manifests/statsbomb/open-data/{COMMIT}/match_{MATCH_ID}.json"
OUT = f"data/processed/three_sixty/{COMMIT}/{MATCH_ID}"
EVENTS = [event("e1"), event("e2", location=None, team={"id": 2, "name": "Away"}), event("e3")]
FRAMES = [EXAMPLE_FRAME, frame("e3", [ACTOR, entry([1.0, 1.0]), entry([1.0, 1.0], actor=True)])]


@pytest.fixture
def project(tmp_path, monkeypatch, source):
    source.responses[source_url(EVENTS_PATH)] = json.dumps(EVENTS).encode("utf-8")
    source.responses[source_url(THREE_SIXTY_PATH)] = json.dumps(FRAMES).encode("utf-8")
    (tmp_path / "pyproject.toml").write_text("")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "fetch_bytes", source.fetch)
    monkeypatch.setattr(cli, "url_exists", source.exists)
    assert cli.main(["ingest", "--commit", COMMIT, "--competition-id", "900",
                     "--season-id", "800", "--match-id", str(MATCH_ID)]) == 0
    assert cli.main(["three-sixty-ingest", "--manifest", MANIFEST]) == 0
    assert cli.main(["three-sixty-profile", "--manifest", MANIFEST]) == 0
    source.fetched.clear()
    source.checked.clear()
    return tmp_path


def test_command_writes_one_row_per_event_with_explicit_serialization(project, source):
    m7_report = {name: (project / OUT / name).read_bytes() for name in three_sixty.REPORT_FILES}
    before = snapshot(project)

    assert cli.main(["three-sixty-context", "--manifest", MANIFEST]) == 0

    assert source.fetched == [] and source.checked == []
    after = snapshot(project)
    assert {path: after[path] for path in before} == before
    assert sorted(set(after) - set(before)) == sorted(f"{OUT}/{name}" for name in three_sixty.CONTEXT_FILES)
    assert {name: (project / OUT / name).read_bytes() for name in three_sixty.REPORT_FILES} == m7_report

    text = (project / OUT / "spatial_context.csv").read_text(encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(text, newline="")))
    assert [row["event_id"] for row in rows] == ["e1", "e2", "e3"]
    assert [row["calculation_status"] for row in rows] == ["computed", "no_frame", "multiple_actors"]
    assert (rows[0]["context_has_excluded_entries"], rows[0]["nearest_visible_opponent_distance"]) == ("true", "6.0")
    assert (rows[1]["frame_available"], rows[1]["visible_opponents"], rows[1]["event_x"]) == ("false", "", "")
    assert rows[1]["event_location_status"] == "missing"


def test_summary_records_version_parameters_inputs_and_status_counts(project):
    assert cli.main(["three-sixty-context", "--manifest", MANIFEST]) == 0
    summary = json.loads((project / OUT / "spatial_context_summary.json").read_text(encoding="utf-8"))
    assert summary["context_definition_version"] == 1
    assert summary["parameters"]["radii"] == [5.0, 10.0, 20.0]
    assert summary["parameters"]["radius_boundary"].startswith("inclusive")
    assert summary["inputs"]["three_sixty_file"]["sha256"] and summary["inputs"]["events_file"]["sha256"]
    assert (summary["rows"], summary["rows_with_frame"]) == (3, 2)
    counts = summary["calculation_status_counts"]
    assert list(counts) == list(three_sixty.CONTEXT_STATUSES)
    assert (counts["computed"], counts["no_frame"], counts["multiple_actors"], counts["no_actor"]) == (1, 1, 1, 0)
    assert summary["diagnostics_over_computed_rows"]["entries_excluded_from_context"] == 1


def test_command_is_byte_identical_on_a_second_run(project):
    outputs = []
    for _ in range(2):
        assert cli.main(["three-sixty-context", "--manifest", MANIFEST]) == 0
        outputs.append({name: (project / OUT / name).read_bytes() for name in three_sixty.CONTEXT_FILES})
    assert outputs[0] == outputs[1]


def test_command_refuses_changed_frames_without_downloading(project, source, capsys):
    (project / f"data/raw/statsbomb/open-data/{COMMIT}/{THREE_SIXTY_PATH}").write_bytes(b"[]")
    assert cli.main(["three-sixty-context", "--manifest", MANIFEST]) == 1
    assert "conflicts with its manifest record" in capsys.readouterr().err
    assert source.fetched == []
    assert not (project / OUT / "spatial_context.csv").exists()
