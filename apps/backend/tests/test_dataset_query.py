"""Dataset query language: selectors, boolean grammar, limits and the SQL it compiles to."""
import pytest
from sqlalchemy import exists, select
from sqlalchemy.dialects import sqlite

from app.db import SessionLocal
from app.models import Image, ImageClass, LabelClass, Project, Workspace, set_annotations
from app.services.query import QueryError, compile, parse

WORKSPACE = "labeldesk-demo"


def sql(cond) -> str:
    """The statement text a caller would run, with its bound values inlined for inspection."""
    return str(cond.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))


def _project(db, slug: str, classes=("helmet", "car")) -> Project:
    ws = db.scalar(select(Workspace).where(Workspace.slug == WORKSPACE))
    project = Project(workspace_id=ws.id, slug=slug, name=slug)
    db.add(project)
    db.flush()
    for name in classes:
        db.add(LabelClass(project_id=project.id, name=name))
    db.flush()
    return project


def _class_ids(db, project) -> dict[str, str]:
    return {c.name: c.id for c in db.scalars(select(LabelClass).where(LabelClass.project_id == project.id))}


def _image(db, project, name: str, **kw) -> Image:
    row = Image(project_id=project.id, name=name, sha256=name, path=name, thumb=name,
                width=kw.pop("width", 640), height=kw.pop("height", 480), **kw)
    db.add(row)
    db.flush()
    return row


def test_parses_selectors_and_ranges():
    node = parse("class:helmet>=3 tag:night split:test")

    assert node.kind == "and"
    assert [leaf.kind for leaf in node.children] == ["term", "term", "term"]
    helmet, night, test = node.children
    assert (helmet.selector, helmet.name, helmet.op, helmet.value) == ("class", "helmet", ">=", 3)
    assert (night.selector, night.name, night.op) == ("tag", "night", "=")
    assert (test.selector, test.name, test.op) == ("split", "test", "=")


def test_boolean_precedence_and_negation():
    node = parse("a OR b AND -c")

    assert node.kind == "or"
    left, right = node.children
    assert (left.kind, left.name) == ("term", "a")
    assert right.kind == "and"
    b, negated = right.children
    assert (b.kind, b.name) == ("term", "b")
    assert negated.kind == "not"
    assert (negated.children[0].kind, negated.children[0].name) == ("term", "c")


def test_free_text_is_filename_contains():
    both = sql(compile(parse("forklift night"), "p1"))
    assert both.count("LIKE") == 2
    assert "images.name" in both
    assert "%forklift%" in both and "%night%" in both

    escaped = sql(compile(parse("50%_off"), "p1"))
    assert r"%50\%\_off%" in escaped
    assert "ESCAPE" in escaped


def test_rejects_bad_syntax_with_position():
    with pytest.raises(QueryError) as bad:
        parse("class:(")

    assert bad.value.position == 7
    assert "class:" in str(bad.value)


def test_limits_reject_overflow():
    for text in (" ".join(["a"] * 65), "(" * 9 + "a" + ")" * 9, "a" * 2001):
        with pytest.raises(QueryError):
            parse(text)


def test_metadata_selector_is_gated():
    with pytest.raises(QueryError) as gated:
        compile(parse('metadata:cam="1"'), "p1")

    assert "metadata filters are not available yet" in str(gated.value)


def test_compiled_condition_stays_inside_the_project():
    with SessionLocal() as db:
        mine = _project(db, "query-scope-a")
        theirs = _project(db, "query-scope-b")
        in_mine = _image(db, mine, "forklift.jpg", tags=["night"])
        _image(db, theirs, "forklift.jpg", tags=["night"])
        db.flush()   # never commit: this suite must not spend the demo workspace's project cap

        got = set(db.scalars(select(Image.id).where(compile(parse("tag:night forklift"), mine.id))))

    assert got == {in_mine.id}


def test_mixed_query_matches_the_legacy_split_and_class_filters():
    with SessionLocal() as db:
        project = _project(db, "query-parity")
        ids = _class_ids(db, project)
        train_helmet = _image(db, project, "helmet-train.jpg", split="train")
        test_helmet = _image(db, project, "helmet-test.jpg", split="test")
        train_car = _image(db, project, "car-train.jpg", split="train")
        for row, name in ((train_helmet, "helmet"), (test_helmet, "helmet"), (train_car, "car")):
            set_annotations(db, row, [{"id": row.name, "classId": ids[name], "shape": {}}])
        db.flush()   # never commit: this suite must not spend the demo workspace's project cap

        got = set(db.scalars(select(Image.id).where(compile(parse("split:train class:helmet"), project.id))))
        # the legacy parameters the grid already serves: split=train plus class_id=helmet
        legacy = set(db.scalars(select(Image.id).where(
            Image.split == "train",
            exists().where(ImageClass.image_id == Image.id, ImageClass.class_id == ids["helmet"]))))

    assert got == legacy == {train_helmet.id}


def test_mixed_query_with_parens_or_and_negation_returns_exact_rows():
    with SessionLocal() as db:
        project = _project(db, "query-mixed")
        ids = _class_ids(db, project)
        rows = {}
        for name, split, tags, cls in (
            ("night-train-helmet.jpg", "train", ["night"], "helmet"),
            ("day-test-car.jpg", "test", ["day"], "car"),
            ("night-test-car.jpg", "test", ["night"], "car"),
            ("night-test-helmet.jpg", "test", ["night"], "helmet"),
        ):
            rows[name] = _image(db, project, name, split=split, tags=tags)
            set_annotations(db, rows[name], [{"id": name, "classId": ids[cls], "shape": {}}])
        db.flush()   # never commit: this suite must not spend the demo workspace's project cap

        got = set(db.scalars(select(Image.id).where(
            compile(parse("split:test (tag:night OR class:helmet) -class:car"), project.id))))

    assert got == {rows["night-test-helmet.jpg"].id}
