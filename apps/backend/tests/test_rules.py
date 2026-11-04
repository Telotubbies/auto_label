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
    ev = []
    for t in range(0, 5):
        ev += e.step(t, two)
    assert ev == []
    ev = e.step(5, two)
    assert ev[0]["kind"] == "count" and "track_id" not in ev[0]
    assert e.step(6, two) == []  # cooldown


def test_count_tolerates_short_gap_but_resets_after_ttl():
    rule = {"kind": "count", "class": "person", "op": ">=", "k": 2, "for_s": 5}
    two = [box("person", 1), box("person", 2)]
    e = Engine([rule], [])  # track_ttl_s = 2
    for t in range(0, 3):
        e.step(t, two)
    e.step(3, two[:1])  # one-frame dip
    assert e.step(4, two) == []
    assert len(e.step(5, two)) == 1  # timer kept: started at 0
    e = Engine([rule], [])
    for t in range(0, 3):
        e.step(t, two)
    e.step(3, two[:1])
    e.step(4, two[:1])
    e.step(5, two[:1])
    e.step(6, two[:1])  # absent for > ttl
    ev = []
    for t in range(7, 12):
        ev += e.step(t, two)
    assert ev == []  # restarted at 7, 4 s so far
    assert len(e.step(12, two)) == 1


def _dwell_run(e, times, tid=1):
    out = []
    for t in times:
        out += e.step(t, [box("person", tid, x=.25, y=.3)])
    return out


def test_dwell_per_track():
    e = Engine([{"kind": "dwell", "class": "person", "zone_id": "z1", "seconds": 10}], [SQUARE])
    ev = []
    for t in range(0, 20):
        preds = [box("person", 1, x=.25, y=.3)]
        if t >= 6:
            preds.append(box("person", 2, x=.25, y=.3))
        ev += [(t, x["track_id"]) for x in e.step(t, preds)]
    assert ev == [(11, 1), (17, 2)]  # each track timed on its own, strictly > seconds


def test_dwell_is_strictly_greater_and_gap_tolerant():
    rule = {"kind": "dwell", "class": "person", "zone_id": "z1", "seconds": 10}
    e = Engine([rule], [SQUARE])
    assert _dwell_run(e, range(0, 11)) == []  # exactly 10 s: not yet
    assert len(_dwell_run(e, [11])) == 1
    e = Engine([rule], [SQUARE])
    _dwell_run(e, range(0, 5))
    e.step(5, [])  # one missed frame keeps the timer
    assert len(_dwell_run(e, range(6, 12))) == 1
    e = Engine([rule], [SQUARE])
    _dwell_run(e, range(0, 5))
    for t in range(5, 9):
        e.step(t, [])  # gone longer than ttl
    assert _dwell_run(e, range(9, 19)) == []  # restarted at 9, 10 s not exceeded


def test_dwell_resets_when_leaving_zone():
    rule = {"kind": "dwell", "class": "person", "zone_id": "z1", "seconds": 10}
    e = Engine([rule], [SQUARE])
    _dwell_run(e, range(0, 8))
    for t in range(8, 12):
        e.step(t, [box("person", 1, x=.9, y=.9)])
    assert _dwell_run(e, range(12, 22)) == []


def at(ya, tid=1):
    return box("person", tid, x=.5, y=ya, h=0)


def run_line(e, ys):
    ev = []
    for t, y in enumerate(ys):
        ev += e.step(t, [] if y is None else [at(y)])
    return ev


def test_line_recross_within_cooldown_is_one_event():
    assert len(run_line(Engine([dict(LINE)], []), [.3, .7, .3, .7])) == 1


def test_line_recross_after_cooldown_is_two_events():
    e = Engine([dict(LINE)], [], cooldown_s=5)
    assert len(run_line(e, [.3, .7] + [.7] * 8 + [.3])) == 2


def test_line_sample_exactly_on_line_counts_crossing_with_right_direction():
    ev = run_line(Engine([{**LINE, "direction": "in"}], []), [.3, .5, .7])
    assert len(ev) == 1 and "in" in ev[0]["summary"]
    ev = run_line(Engine([dict(LINE)], []), [.7, .5, .3])
    assert len(ev) == 1 and "out" in ev[0]["summary"]
    assert run_line(Engine([dict(LINE)], []), [.3, .5, .3]) == []  # touch and return


def test_line_crossing_survives_short_gap_not_long_gap():
    assert len(run_line(Engine([dict(LINE)], []), [.3, None, .7])) == 1
    e = Engine([dict(LINE)], [])
    assert e.step(0, [at(.3)]) == []
    assert e.step(10, [at(.7)]) == []  # track forgotten after ttl


def test_state_stays_bounded_with_many_short_lived_tracks():
    e = Engine([{"kind": "zone", "class": "person", "zone_id": "z1"}, dict(LINE)], [SQUARE])
    for i in range(1000):
        e.step(i, [box("person", i, x=.25, y=.3)])
    assert len(e._last_fire) <= 31
    assert len(e._side) <= 3 and len(e._timer) <= 3


def test_vlm_rules_ignored_and_rule_index_kept():
    rules = [{"kind": "vlm", "question": "q", "every_s": 5},
             {"kind": "zone", "class": "person", "zone_id": "z1"}]
    e = Engine(rules, [SQUARE])
    ev = e.step(0, [box("person", x=.25, y=.3)])
    assert [x["rule"] for x in ev] == [1]
