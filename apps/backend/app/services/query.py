"""The dataset query language: one text box over images, classes, tags, splits and counts.

Grammar, loosest binding last::

    query := or
    or    := and (OR and)*
    and   := unary ((AND)? unary)*        # adjacent terms are AND too
    unary := ("-" | NOT) unary | "(" or ")" | term
    term  := selector | free text         # a quoted phrase is one free-text term

A selector is ``tag split status class file batch assignee date width height annotations
metadata is`` (``filename`` and ``count`` are aliases), followed by ``:`` or one of the
comparison operators ``= >= <= > < !=``. Every term carries a 1-based ``position`` so the UI can
put a caret under the offending character, and ``parse`` never touches the database.

Per-selector rules:
- free text matches the file name (case-insensitive contains, ``%`` and ``_`` escaped).
- text selectors take ``:``/``=``/``!=``; ``width``/``height`` take a range only (pixels).
- ``annotations`` compares ``Image.n_annotations``.
- ``class:name`` means "at least one"; a count comparison follows the name (``class:x>=2``).
  ``class:x=0`` is "none" and compiles to NOT EXISTS. A count is 0-10000.
- ``date`` compares ``Image.created`` (the upload date, never ``updated``) at day granularity,
  from an ISO-8601 date or datetime in UTC.
- ``metadata`` parses but refuses to compile until T-082 registers its branch.

Input is capped at 2000 characters, 64 terms and 8 nesting levels so a pasted query can never
become a timeout.
"""
import json
import operator
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import ColumnElement, Text, and_, cast, exists, not_, or_, select

from ..models import Image, ImageClass, LabelClass

MAX_CHARS = 2000
MAX_TERMS = 64
MAX_DEPTH = 8
MAX_CLASS_COUNT = 10_000
DAY = 86_400.0

TEXT_SELECTORS = ("tag", "split", "status", "file", "batch", "assignee", "is")
NUMBER_SELECTORS = ("width", "height", "annotations")
SELECTORS = frozenset(TEXT_SELECTORS + NUMBER_SELECTORS + ("class", "date", "metadata"))
ALIASES = {"filename": "file", "count": "annotations"}
IS_VALUES = ("null", "annotated")
COMPARISONS = {"=": operator.eq, "!=": operator.ne, ">=": operator.ge, ">": operator.gt,
               "<=": operator.le, "<": operator.lt}
TEXT_COLUMNS = {"split": Image.split, "status": Image.status, "file": Image.name, "batch": Image.batch_id}
NUMBER_COLUMNS = {"width": Image.width, "height": Image.height, "annotations": Image.n_annotations}
# longest first, so ">=" is never read as ">"
_OPERATORS = (">=", "<=", "!=", "=", ">", "<", ":")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_DIGITS = re.compile(r"\d+")


class QueryError(ValueError):
    """A query the grid must not send: 1-based ``position`` for the caret and the ``token`` it names."""

    def __init__(self, message: str, position: int = 1, token: str = "") -> None:
        super().__init__(message)
        self.position = position
        self.token = token


@dataclass(frozen=True)
class Node:
    """One node of the parse tree: ``and``/``or``/``not`` hold children, ``term`` holds a filter."""

    kind: str
    children: tuple["Node", ...] = ()
    selector: str = ""      # tag, split, class, text (free text), …
    name: str = ""          # the name/tag/split value, or the free-text word
    op: str = ""            # comparison; "" is a bare "at least one" for class:
    value: int | float | None = None    # count/range operand, or the date's UTC midnight
    position: int = 1


def _fail(reason: str, position: int, token: str) -> QueryError:
    return QueryError(f"Check the query near `{token}`: {reason}", position, token)


class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.at = 0
        self.terms = 0

    def run(self) -> Node:
        self._skip()
        if self.at >= len(self.text):
            raise QueryError("Type a filter to narrow the images", 1, "")
        node = self._or(0)
        self._skip()
        if self.at < len(self.text):
            raise _fail("unexpected input", self.at + 1, self.text[self.at:self.at + 12])
        return node

    def _or(self, depth: int) -> Node:
        nodes = [self._and(depth)]
        while self._take_keyword("OR"):
            nodes.append(self._and(depth))
        return nodes[0] if len(nodes) == 1 else Node("or", tuple(nodes), position=nodes[0].position)

    def _and(self, depth: int) -> Node:
        nodes = [self._unary(depth)]
        while True:
            self._skip()
            if self.at >= len(self.text) or self.text[self.at] == ")" or self._peek_keyword("OR"):
                break
            self._take_keyword("AND")
            nodes.append(self._unary(depth))
        return nodes[0] if len(nodes) == 1 else Node("and", tuple(nodes), position=nodes[0].position)

    def _unary(self, depth: int) -> Node:
        self._skip()
        if self._peek_keyword("OR") or self._peek_keyword("AND"):
            raise _fail("a filter is missing before this word", self.at + 1, self._word(self.at))
        if self.at >= len(self.text):
            raise _fail("the query ends too early", len(self.text), "")
        char = self.text[self.at]
        if char == "(":
            return self._group(depth)
        if char == "-" or self._peek_keyword("NOT"):
            start = self.at
            self.at += 1 if char == "-" else len("NOT")
            return Node("not", (self._unary(depth),), position=start + 1)
        return self._term()

    def _group(self, depth: int) -> Node:
        start = self.at
        if depth + 1 > MAX_DEPTH:
            raise _fail(f"the query nests deeper than {MAX_DEPTH} levels", start + 1, "(")
        self.at += 1
        node = self._or(depth + 1)
        self._skip()
        if self.at >= len(self.text) or self.text[self.at] != ")":
            raise _fail("this bracket is never closed", start + 1, "(")
        self.at += 1
        return node

    def _term(self) -> Node:
        start = self.at
        if self.text[start] in "\"'":
            name, self.at = self._quoted(start)
            return self._leaf("text", name, "=", start)
        word = self._word(start)
        source = self._operator_at(start + len(word)) if word else ""
        if source:
            selector = ALIASES.get(word.lower(), word.lower())
            if selector not in SELECTORS:
                raise _fail("this is not a filter", start + 1, f"{word}{source}")
            return self._selector(selector, source, start + len(word) + len(source), start, start + len(word))
        end = self._end_of_word(start)
        if end == start:
            raise _fail("there is nothing to search for here", start + 1, self.text[start:start + 12])
        self.at = end
        return self._leaf("text", self.text[start:end], "=", start)

    def _selector(self, selector: str, source: str, value_at: int, start: int, op_at: int) -> Node:
        op = "=" if source == ":" else source
        if source == ":":
            trailing = self._operator_at(value_at)   # `annotations:>=2` reads like `annotations>=2`
            if trailing in COMPARISONS:
                op_at, op, value_at = value_at, trailing, value_at + len(trailing)
        self.at = value_at
        if self.text[value_at:value_at + 1] in ("\"", "'"):
            name, self.at = self._quoted(value_at)
        else:
            end = self._end_of_word(value_at, stop_comparison=selector == "class")
            name, self.at = self.text[value_at:end], end
        if not name:
            raise _fail(f"`{selector}:` needs a value", value_at + 1, f"{selector}:")
        if selector == "class":
            return self._class_term(name, start)
        if selector == "metadata":
            return self._leaf("metadata", name, op, start)
        if selector == "date":
            return self._leaf("date", name, op, start, value=self._day_start(name, value_at))
        if selector in TEXT_SELECTORS:
            if op not in ("=", "!="):
                raise _fail(f"`{selector}:` does not take {op}", op_at + 1, op)
            if selector == "is" and name not in IS_VALUES:
                raise _fail("`is:` takes null or annotated", value_at + 1, name)
            return self._leaf(selector, name, op, start)
        if selector in ("width", "height") and op not in (">=", "<=", ">", "<"):
            raise _fail(f"`{selector}:` takes a range, for example `{selector}:>=1024`", op_at + 1, op)
        try:
            number = int(name)
        except ValueError:
            raise _fail(f"`{selector}:` needs a whole number", value_at + 1, name) from None
        return self._leaf(selector, "", op, start, value=number)

    def _class_term(self, name: str, start: int) -> Node:
        source = self._operator_at(self.at)
        if source not in COMPARISONS:
            return self._leaf("class", name, "", start)
        number_at = self.at + len(source)
        match = _DIGITS.match(self.text, number_at)
        if not match:
            raise _fail(f"`class:` needs a whole number after {source}", number_at + 1,
                        f"class:{name}{source}")
        count = int(match.group(0))
        if count > MAX_CLASS_COUNT:
            raise _fail(f"a class count is 0-{MAX_CLASS_COUNT}", number_at + 1, match.group(0))
        self.at = match.end()
        return self._leaf("class", name, source, start, value=count)

    def _leaf(self, selector: str, name: str, op: str, start: int, value=None) -> Node:  # noqa: ANN001
        self.terms += 1
        if self.terms > MAX_TERMS:
            raise _fail(f"more than {MAX_TERMS} filters in one query", start + 1, self.text[start:start + 12])
        return Node("term", selector=selector, name=name, op=op, value=value, position=start + 1)

    def _day_start(self, text: str, position: int) -> float:
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            raise _fail("`date:` takes an ISO-8601 date, for example 2026-10-01",
                        position + 1, text) from None
        day = parsed.astimezone(timezone.utc).date() if parsed.tzinfo else parsed.date()
        return datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp()

    def _operator_at(self, index: int) -> str:
        for op in _OPERATORS:
            if self.text.startswith(op, index):
                return op
        return ""

    def _word(self, start: int) -> str:
        match = _IDENT.match(self.text, start)
        return match.group(0) if match else ""

    def _end_of_word(self, start: int, stop_comparison: bool = False) -> int:
        at = start
        while at < len(self.text):
            char = self.text[at]
            if char.isspace() or char in "()" or (stop_comparison and char in "><=!"):
                break
            at += 1
        return at

    def _quoted(self, start: int) -> tuple[str, int]:
        quote = self.text[start]
        at = start + 1
        while at < len(self.text) and self.text[at] != quote:
            at += 1
        if at >= len(self.text):
            raise _fail("this quote is never closed", start + 1, quote)
        return self.text[start + 1:at], at + 1

    def _skip(self) -> None:
        while self.at < len(self.text) and self.text[self.at].isspace():
            self.at += 1

    def _peek_keyword(self, word: str) -> bool:
        self._skip()
        end = self.at + len(word)
        if self.text[self.at:end].upper() != word:
            return False
        return end >= len(self.text) or not (self.text[end].isalnum() or self.text[end] == "_")

    def _take_keyword(self, word: str) -> bool:
        if not self._peek_keyword(word):
            return False
        self.at += len(word)
        return True


def parse(text: str) -> Node:
    """The parse tree for ``text``; raises :class:`QueryError` with a caret position."""
    if len(text) > MAX_CHARS:
        raise QueryError(f"Check the query near the end: keep it under {MAX_CHARS} characters",
                         MAX_CHARS + 1, text[MAX_CHARS:MAX_CHARS + 12])
    return _Parser(text).run()


def compile(node: Node, project_id: str) -> ColumnElement:  # noqa: A001 - the card names it compile
    """SQL for ``node``, always scoped to ``project_id`` so a condition cannot span projects."""
    return and_(Image.project_id == project_id, _where(node, project_id))


def _where(node: Node, project_id: str) -> ColumnElement:
    if node.kind == "and":
        return and_(*(_where(child, project_id) for child in node.children))
    if node.kind == "or":
        return or_(*(_where(child, project_id) for child in node.children))
    if node.kind == "not":
        return not_(_where(node.children[0], project_id))
    return _term(node, project_id)


def _term(node: Node, project_id: str) -> ColumnElement:
    selector, name, op, value = node.selector, node.name, node.op, node.value
    if selector == "text":
        return Image.name.ilike(f"%{_like(name)}%", escape="\\")
    if selector == "tag":
        found = cast(Image.tags, Text).like(f"%{_like(json.dumps(name))}%", escape="\\")
        return not_(found) if op == "!=" else found
    if selector == "is":
        empty = Image.n_annotations == 0
        if name == "null":
            return not_(empty) if op == "!=" else empty
        return empty if op == "!=" else not_(empty)
    if selector == "assignee":
        unassigned = Image.assignee_id.is_(None)
        if name == "none":
            return not_(unassigned) if op == "!=" else unassigned
        return Image.assignee_id != name if op == "!=" else Image.assignee_id == name
    if selector == "class":
        return _class(node, project_id)
    if selector == "date":
        return _date(op, float(value))
    if selector == "metadata":
        raise QueryError("metadata filters are not available yet", node.position, "metadata")
    if selector in TEXT_COLUMNS:
        column = TEXT_COLUMNS[selector]
        return column != name if op == "!=" else column == name
    return COMPARISONS[op](NUMBER_COLUMNS[selector], value)


def _class(node: Node, project_id: str) -> ColumnElement:
    """Exists/NOT EXISTS over the class index; upper bounds must also match images with no row."""
    ids = select(LabelClass.id).where(LabelClass.project_id == project_id, LabelClass.name == node.name)
    found = exists().where(ImageClass.image_id == Image.id, ImageClass.project_id == project_id,
                           ImageClass.class_id.in_(ids))
    op, count = node.op, node.value
    if op == "":
        return found
    if op == "=":
        return ~found if count == 0 else found.where(ImageClass.n == count)
    if op == "!=":
        return found if count == 0 else ~found.where(ImageClass.n == count)
    if op == ">=":
        return found.where(ImageClass.n >= count)
    if op == ">":
        return found.where(ImageClass.n > count)
    if op == "<=":
        return ~found.where(ImageClass.n > count)
    return ~found.where(ImageClass.n >= count)


def _date(op: str, start: float) -> ColumnElement:
    """Day-granularity windows: ``date:=`` is that whole day, ``date:>`` starts the next one."""
    end = start + DAY
    if op == "=":
        return and_(Image.created >= start, Image.created < end)
    if op == "!=":
        return or_(Image.created < start, Image.created >= end)
    if op == ">=":
        return Image.created >= start
    if op == ">":
        return Image.created >= end
    if op == "<=":
        return Image.created < end
    return Image.created < start


def _like(value: str) -> str:
    """Escape the LIKE wildcards so a file name or tag matches literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
