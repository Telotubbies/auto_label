"""Pure stream rule engine (count, zone, line, dwell).

``Engine.step(ts, preds)`` expects predictions in the unified schema with
*normalized* (0-1) centre-based boxes: ``x, y`` is the box centre, ``width`` /
``height`` its size, plus ``class`` and ``track_id``. The anchor point used for
all geometry is the bottom-centre ``(x, y + height / 2)``.

Zones: ``{"id": str, "points": [x1, y1, x2, y2, ...]}``. ``vlm`` rules are
ignored here (the manager evaluates them). Events are
``{"rule": index, "kind", "summary", "track_id"?}``, de-duplicated by
``cooldown_s`` per (rule, track), or per rule for ``count``.

Line direction: "in" = the anchor moves to the right-hand side of the vector
p1->p2 as drawn on screen (image y points down); swapping p1/p2 flips in/out.
Per-track state (line side, dwell timer, count timer) survives gaps of up to
``track_ttl_s`` seconds without the track (or, for dwell, outside the zone);
dwell fires once the time inside is strictly greater than ``seconds``.
"""
import operator

_OPS = {">=": operator.ge, ">": operator.gt, "<=": operator.le,
        "<": operator.lt, "==": operator.eq}


def _anchor(p: dict) -> tuple[float, float]:
    return p["x"], p["y"] + p["height"] / 2


def _in_polygon(pt, pts) -> bool:
    x, y = pt
    poly = list(zip(pts[0::2], pts[1::2]))
    inside = False
    for i, (x1, y1) in enumerate(poly):
        x2, y2 = poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _cross(ax, ay, bx, by) -> float:
    return ax * by - ay * bx


def _side(pt, line) -> int:
    x1, y1, x2, y2 = line
    v = _cross(x2 - x1, y2 - y1, pt[0] - x1, pt[1] - y1)
    return (v > 0) - (v < 0)


def _hits_segment(prev, cur, line) -> bool:
    """Does the move prev->cur cross the finite segment of the line?"""
    x1, y1, x2, y2 = line
    dx, dy = x2 - x1, y2 - y1
    mx, my = cur[0] - prev[0], cur[1] - prev[1]
    den = _cross(mx, my, dx, dy)
    if den == 0:
        return False
    u = _cross(x1 - prev[0], y1 - prev[1], mx, my) / den
    return 0 <= u <= 1


class Engine:
    def __init__(self, rules: list[dict], zones: list[dict], cooldown_s: float = 30,
                 track_ttl_s: float = 2.0):
        self.rules = rules
        self.zones = {z["id"]: z["points"] for z in zones}
        self.cooldown_s = cooldown_s
        self.track_ttl_s = track_ttl_s
        self._last_fire: dict[tuple, float] = {}
        # (rule, track) -> (last non-zero side, anchor at that time, last_seen)
        self._side: dict[tuple, tuple] = {}
        # (rule, track|None) -> (start, last_active) for dwell and count timers
        self._timer: dict[tuple, tuple[float, float]] = {}

    def _fire(self, ts, key) -> bool:
        last = self._last_fire.get(key)
        if last is not None and ts - last < self.cooldown_s:
            return False
        self._last_fire[key] = ts
        return True

    def _expire(self, ts, i, seen):
        for d, idx in ((self._side, 2), (self._timer, 1)):
            for k in [k for k, v in d.items()
                      if k[0] == i and k not in seen and ts - v[idx] > self.track_ttl_s]:
                del d[k]

    def step(self, ts: float, preds: list[dict]) -> list[dict]:
        self._last_fire = {k: t for k, t in self._last_fire.items()
                           if ts - t < self.cooldown_s}
        events: list[dict] = []
        for i, r in enumerate(self.rules):
            kind = r.get("kind")
            hits = [p for p in preds if p.get("class") == r.get("class")]
            if kind == "count":
                self._count(i, r, ts, hits, events)
            elif kind == "zone":
                pts = self.zones.get(r.get("zone_id"))
                for p in hits:
                    if pts and _in_polygon(_anchor(p), pts) and self._fire(ts, (i, p.get("track_id"))):
                        events.append(self._ev(i, kind, f"{r['class']} in zone {r['zone_id']}", p))
            elif kind == "line":
                self._line(i, r, ts, hits, events)
            elif kind == "dwell":
                self._dwell(i, r, ts, hits, events)
        return events

    @staticmethod
    def _ev(i, kind, summary, p=None) -> dict:
        ev = {"rule": i, "kind": kind, "summary": summary}
        if p is not None and p.get("track_id") is not None:
            ev["track_id"] = p["track_id"]
        return ev

    def _count(self, i, r, ts, hits, events):
        key = (i, None)
        if _OPS[r.get("op", ">=")](len(hits), r["k"]):
            start, last = self._timer.get(key, (ts, ts))
            if ts - last > self.track_ttl_s:
                start = ts
            self._timer[key] = (start, ts)
            if ts - start >= r.get("for_s", 0) and self._fire(ts, key):
                events.append(self._ev(i, "count", f"{len(hits)} {r['class']} {r.get('op', '>=')} {r['k']}"))
        else:
            self._expire(ts, i, set())

    def _line(self, i, r, ts, hits, events):
        want = {"in": 1, "out": -1}.get(r.get("direction", "both"))
        seen = set()
        for p in hits:
            tid = p.get("track_id")
            if tid is None:
                continue
            key = (i, tid)
            seen.add(key)
            cur = _anchor(p)
            side = _side(cur, r["line"])
            st = self._side.get(key)
            if st is not None and ts - st[2] > self.track_ttl_s:
                st = None
            if side == 0:  # on the line: keep the last real side
                if st is not None:
                    self._side[key] = (st[0], st[1], ts)
                continue
            if st is not None and st[0] != side and _hits_segment(st[1], cur, r["line"]):
                if (want is None or side == want) and self._fire(ts, key):
                    events.append(self._ev(i, "line", f"{r['class']} crossed line ({'in' if side > 0 else 'out'})", p))
            self._side[key] = (side, cur, ts)
        self._expire(ts, i, seen)

    def _dwell(self, i, r, ts, hits, events):
        pts = self.zones.get(r.get("zone_id"))
        seen = set()
        for p in hits:
            tid = p.get("track_id")
            if tid is None or not pts or not _in_polygon(_anchor(p), pts):
                continue
            key = (i, tid)
            seen.add(key)
            start, last = self._timer.get(key, (ts, ts))
            if ts - last > self.track_ttl_s:
                start = ts
            self._timer[key] = (start, ts)
            if ts - start > r["seconds"] and self._fire(ts, key):
                events.append(self._ev(i, "dwell", f"{r['class']} #{tid} dwelled {ts - start:.0f}s in zone {r['zone_id']}", p))
        self._expire(ts, i, seen)
