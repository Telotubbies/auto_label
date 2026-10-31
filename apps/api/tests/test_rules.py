from app.streams.rules import Engine


def box(cls, track_id=1, x=0.5, y=0.5, w=0.1, h=0.1):
    return {"class": cls, "track_id": track_id, "x": x, "y": y, "width": w, "height": h}


LINE = {"kind": "line", "class": "person", "line": [0, .5, 1, .5], "direction": "both"}
SQUARE = {"id": "z1", "points": [0, 0, .5, 0, .5, .5, 0, .5]}


def test_line_crossing_counts_once_per_track():
    e = Engine([dict(LINE)], [])
    ev = []
    for t, y in enumerate([.3, .4, .6, .7, .6]):
        ev += e.step(t, [box("person", track_id=1, y=y)])
    assert len(ev) == 1  # crossing back within cooldown is suppressed
    assert ev[0]["rule"] == 0 and ev[0]["kind"] == "line" and ev[0]["track_id"] == 1


def test_line_direction_in_out():
    # "in" = anchor moves downwards (+y) across a left-to-right line
    for direction, ys, n in [("in", [.3, .7], 1), ("in", [.7, .3], 0),
                             ("out", [.7, .3], 1), ("out", [.3, .7], 0)]:
        e = Engine([{**LINE, "direction": direction}], [])
        ev = []
        for t, y in enumerate(ys):
            ev += e.step(t, [box("person", y=y)])
        assert len(ev) == n, (direction, ys)


def test_zone_uses_bottom_centre():
    rules = [{"kind": "zone", "class": "person", "zone_id": "z1"}]
    # centre inside zone, feet outside -> no event
    e = Engine(rules, [SQUARE])
    assert e.step(0, [box("person", x=.25, y=.48, h=.2)]) == []
    # feet inside -> event
    e = Engine(rules, [SQUARE])
    ev = e.step(0, [box("person", x=.25, y=.3, h=.2)])
    assert len(ev) == 1 and ev[0]["kind"] == "zone"
    # wrong class ignored
    e = Engine(rules, [SQUARE])
    assert e.step(0, [box("car", x=.25, y=.3)]) == []


def test_count_for_seconds():
    e = Engine([{"kind": "count", "class": "person", "op": ">=", "k": 2, "for_s": 5}], [])
    two = [box("person", 1), box("person", 2)]
    assert e.step(0, two) == []
    assert e.step(4, two) == []
    assert e.step(4.5, two[:1]) == []  # drops below -> timer resets
    assert e.step(5, two) == []
    assert e.step(9, two) == []
    ev = e.step(10.5, two)
    assert len(ev) == 1 and ev[0]["kind"] == "count" and "track_id" not in ev[0]
    assert e.step(11, two) == []  # cooldown


def test_dwell_per_track():
    e = Engine([{"kind": "dwell", "class": "person", "zone_id": "z1", "seconds": 10}], [SQUARE])

    def inside(tid):
        return box("person", tid, x=.25, y=.3)

    assert e.step(0, [inside(1)]) == []
    assert e.step(6, [inside(1), inside(2)]) == []
    ev = e.step(10, [inside(1), inside(2)])
    assert [x["track_id"] for x in ev] == [1]
    ev = e.step(16, [inside(1), inside(2)])
    assert [x["track_id"] for x in ev] == [2]
    # leaving resets the dwell
    e.step(17, [])
    assert e.step(18, [inside(1)]) == []


def test_vlm_rules_ignored_and_rule_index_kept():
    rules = [{"kind": "vlm", "question": "q", "every_s": 5},
             {"kind": "zone", "class": "person", "zone_id": "z1"}]
    e = Engine(rules, [SQUARE])
    ev = e.step(0, [box("person", x=.25, y=.3)])
    assert [x["rule"] for x in ev] == [1]
