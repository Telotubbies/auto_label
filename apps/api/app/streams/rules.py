"""Pure stream rule engine (count, zone, line, dwell).

``Engine.step(ts, preds)`` expects predictions in the unified schema with
*normalized* (0-1) centre-based boxes: ``x, y`` is the box centre, ``width`` /
``height`` its size, plus ``class`` and ``track_id``. The anchor point used for
all geometry is the bottom-centre ``(x, y + height / 2)``.

Zones: ``{"id": str, "points": [x1, y1, x2, y2, ...]}``. ``vlm`` rules are
ignored here (the manager evaluates them). Events are
``{"rule": index, "kind", "summary", "track_id"?}``, de-duplicated by
``cooldown_s`` per (rule, track), or per rule for ``count``.
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


def _crossing(prev, cur, line) -> int:
    """0 if the move prev->cur does not cross the line segment, else the
    sign of the movement relative to the line direction (+1 = "in")."""
    x1, y1, x2, y2 = line
    dx, dy = x2 - x1, y2 - y1
    s_prev = _cross(dx, dy, prev[0] - x1, prev[1] - y1)
    s_cur = _cross(dx, dy, cur[0] - x1, cur[1] - y1)
    if s_prev == s_cur or (s_prev > 0) == (s_cur > 0) and s_prev != 0 and s_cur != 0:
        return 0
    if s_prev == 0:  # started exactly on the line: not a crossing yet
        return 0
    # segment prev->cur must also hit the finite line segment
    mx, my = cur[0] - prev[0], cur[1] - prev[1]
    t_b = _cross(mx, my, dx, dy)
    if t_b == 0:
        return 0
    u = _cross(x1 - prev[0], y1 - prev[1], mx, my) / t_b
    if not 0 <= u <= 1:
        return 0
    return 1 if s_cur > 0 else -1


class Engine:
    def __init__(self, rules: list[dict], zones: list[dict], cooldown_s: float = 30):
        self.rules = rules
        self.zones = {z["id"]: z["points"] for z in zones}
        self.cooldown_s = cooldown_s
        self._last_fire: dict[tuple, float] = {}
        self._prev: dict[tuple, tuple] = {}      # (rule, track) -> last anchor
        self._since: dict[tuple, float] = {}     # dwell / count start times

    def _fire(self, ts, key) -> bool:
        last = self._last_fire.get(key)
        if last is not None and ts - last < self.cooldown_s:
            return False
        self._last_fire[key] = ts
        return True

    def step(self, ts: float, preds: list[dict]) -> list[dict]:
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
            start = self._since.setdefault(key, ts)
            if ts - start >= r.get("for_s", 0) and self._fire(ts, key):
                events.append(self._ev(i, "count", f"{len(hits)} {r['class']} {r.get('op', '>=')} {r['k']}"))
        else:
            self._since.pop(key, None)

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
            prev = self._prev.get(key)
            self._prev[key] = cur
            if prev is None:
                continue
            c = _crossing(prev, cur, r["line"])
            if c and (want is None or c == want) and self._fire(ts, key):
                events.append(self._ev(i, "line", f"{r['class']} crossed line ({'in' if c > 0 else 'out'})", p))
        for key in [k for k in self._prev if k[0] == i and k not in seen]:
            del self._prev[key]

    def _dwell(self, i, r, ts, hits, events):
        pts = self.zones.get(r.get("zone_id"))
        seen = set()
        for p in hits:
            tid = p.get("track_id")
            if tid is None or not pts or not _in_polygon(_anchor(p), pts):
                continue
            key = (i, tid)
            seen.add(key)
            start = self._since.setdefault(key, ts)
            if ts - start >= r["seconds"] and self._fire(ts, key):
                events.append(self._ev(i, "dwell", f"{r['class']} #{tid} dwelled {ts - start:.0f}s in zone {r['zone_id']}", p))
        for key in [k for k in self._since if k[0] == i and k not in seen]:
            del self._since[key]
