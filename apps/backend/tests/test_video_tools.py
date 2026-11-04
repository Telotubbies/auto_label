"""Video tools: frame planning, scene detection, timeline interpolation, SAM track-forward, extraction."""
import math
import os
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-video-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import cv2
import numpy as np
import pytest
from PIL import Image as PImage

from app import bootstrap, worker
from app.config import DATA_DIR
from app.db import SessionLocal
from app.models import Image, Job, Project, User, Video, Workspace, new_id, set_annotations
from app.services import track
from app.services.video import (DEFAULT_SCENE_THRESHOLD, MAX_INTERPOLATION_SPAN, EXTRACT_MODES, interpolate_shape,
                                interpolate_tracks, is_scene_change, merge_interpolated, pair_tracks, plan_frames)


# --- plan_frames ---------------------------------------------------------------------------

def test_plan_frames_fps_mode():
    assert plan_frames(300, 30.0, "fps", target_fps=1.0) == list(range(0, 300, 30))
    assert len(plan_frames(300, 30.0, "fps", target_fps=1.0)) == 10


def test_plan_frames_every_mode():
    idx = plan_frames(300, 30.0, "every", every_s=2.0)
    assert idx == list(range(0, 300, 60))
    assert len(idx) == 5


def test_plan_frames_every_frame():
    assert plan_frames(300, 30.0, "fps", target_fps=30.0) == list(range(300))


def test_plan_frames_scene_falls_back_to_target_fps():
    assert plan_frames(300, 30.0, "scene", target_fps=1.0) == plan_frames(300, 30.0, "fps", target_fps=1.0)


def test_plan_frames_max_frames_thins_evenly_and_keeps_first():
    idx = plan_frames(300, 30.0, "fps", target_fps=30.0, max_frames=10)
    assert len(idx) == 10
    assert idx[0] == 0
    assert idx == sorted(set(idx))
    assert all(0 <= i < 300 for i in idx)


def test_plan_frames_invalid_arguments():
    for kwargs in ({"mode": "bogus"}, {"mode": "fps", "target_fps": 0}, {"mode": "every", "every_s": 0},
                   {"mode": "fps", "frame_count": -1}):
        args = {"frame_count": 100, "fps": 25.0, "mode": "fps"}
        args.update(kwargs)
        with pytest.raises(ValueError):
            plan_frames(**args)


def test_extract_modes_constant():
    assert EXTRACT_MODES == ("fps", "every", "scene")


# --- scene change --------------------------------------------------------------------------

def _hist(peak: int) -> np.ndarray:
    h = np.zeros((64, 1), np.float32)
    h[peak] = 1.0
    return h


def test_is_scene_change_identical_histograms():
    h = _hist(10)
    assert is_scene_change(h, h) is False


def test_is_scene_change_disjoint_histograms():
    assert is_scene_change(_hist(0), _hist(63)) is True


def test_is_scene_change_first_frame():
    assert is_scene_change(None, _hist(3)) is True


# --- interpolate_shape ---------------------------------------------------------------------

def test_interpolate_bbox_midpoint():
    a = {"kind": "bbox", "x": 0.0, "y": 0.0, "w": 1.0, "h": 0.5}
    b = {"kind": "bbox", "x": 0.5, "y": 0.2, "w": 0.4, "h": 0.9}
    mid = interpolate_shape(a, b, 0.5)
    assert mid["kind"] == "bbox"
    assert mid["x"] == pytest.approx(0.25)
    assert mid["y"] == pytest.approx(0.1)
    assert mid["w"] == pytest.approx(0.7)
    assert mid["h"] == pytest.approx(0.7)


def test_interpolate_obb_angle_takes_short_way():
    a = {"kind": "obb", "cx": 0.5, "cy": 0.5, "w": 0.2, "h": 0.1, "angle": math.radians(350)}
    b = {"kind": "obb", "cx": 0.5, "cy": 0.5, "w": 0.2, "h": 0.1, "angle": math.radians(10)}
    mid = interpolate_shape(a, b, 0.5)
    # 350° -> 10° is +20° the short way; the midpoint is 0°/360°
    assert math.atan2(math.sin(mid["angle"]), math.cos(mid["angle"])) == pytest.approx(0.0, abs=1e-6)
    end = interpolate_shape(a, b, 1.0)
    assert end["angle"] == pytest.approx(math.radians(10))


def test_interpolate_keypoints_visibility_rules():
    a = {"kind": "keypoints", "points": [0.1, 0.1, 2, 0.5, 0.5, 2, 0.9, 0.9, 0]}
    b = {"kind": "keypoints", "points": [0.3, 0.3, 2, 0.7, 0.7, 0, 0.9, 0.9, 1]}
    mid = interpolate_shape(a, b, 0.5)
    pts = mid["points"]
    assert pts[0:3] == pytest.approx([0.2, 0.2, 2])
    assert pts[3:6] == pytest.approx([0.5, 0.5, 1])      # not visible in both: keep a's coords
    assert pts[6:9] == pytest.approx([0.9, 0.9, 1])      # one side visible -> occluded


def test_interpolate_polygon_midpoint():
    a = {"kind": "polygon", "points": [0.0, 0.0, 1.0, 0.0, 1.0, 1.0]}
    b = {"kind": "polygon", "points": [0.2, 0.2, 0.8, 0.2, 0.8, 0.8]}
    mid = interpolate_shape(a, b, 0.5)
    assert mid["points"] == pytest.approx([0.1, 0.1, 0.9, 0.1, 0.9, 0.9])


def test_interpolate_shape_does_not_mutate_and_copies_mismatch():
    a = {"kind": "bbox", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}
    b = {"kind": "polygon", "points": [0, 0, 1, 0, 1, 1]}
    before = {k: dict(v) if isinstance(v, dict) else v for k, v in a.items()}
    out = interpolate_shape(a, b, 0.5)
    assert out == a
    assert out is not a
    assert a == before


# --- interpolate_tracks --------------------------------------------------------------------

def _ann(ann_id: str, track_id: str, x: float, cls: str = "c1") -> dict:
    return {"id": ann_id, "classId": cls, "trackId": track_id,
            "shape": {"kind": "bbox", "x": x, "y": 0.1, "w": 0.2, "h": 0.2}}


def test_interpolate_tracks_writes_intermediate_frames():
    frames = [(0, [_ann("a1", "t1", 0.0)]), (1, []), (2, [_ann("a2", "t1", 0.4)])]
    out = interpolate_tracks(frames, 0, 2)
    assert set(out) == {1}
    assert out[1][0]["trackId"] == "t1"
    assert out[1][0]["shape"]["x"] == pytest.approx(0.2)
    assert out[1][0]["keyframe"] is False


def test_interpolate_tracks_requires_both_endpoints_and_same_class():
    frames = [(0, [_ann("a1", "t1", 0.0), _ann("a3", "only-start", 0.0)]),
              (2, [_ann("a2", "t1", 0.4, cls="other")])]
    assert interpolate_tracks(frames, 0, 2) == {}


def test_pair_tracks_assigns_one_id_per_drawn_keyframe_pair():
    a = {"id": "a1", "classId": "c1", "shape": {"kind": "bbox", "x": 0.0, "y": 0.0, "w": 0.2, "h": 0.2}}
    b = {"id": "a2", "classId": "c1", "shape": {"kind": "bbox", "x": 0.4, "y": 0.0, "w": 0.2, "h": 0.2}}

    pairs = pair_tracks([a], [b])

    assert len(pairs) == 1
    assert pairs[0][0] is a and pairs[0][1] is b
    assert pairs[0][2]


def test_pair_tracks_refuses_ambiguous_groups():
    a = [{"id": "a1", "classId": "c1", "shape": {"kind": "bbox", "x": 0.0, "y": 0.0, "w": 0.1, "h": 0.1}},
         {"id": "a2", "classId": "c1", "shape": {"kind": "bbox", "x": 0.4, "y": 0.0, "w": 0.1, "h": 0.1}}]
    b = [{"id": "b1", "classId": "c1", "shape": {"kind": "bbox", "x": 0.0, "y": 0.4, "w": 0.1, "h": 0.1}}]

    assert pair_tracks(a, b) == []


def test_merge_interpolated_treats_a_human_edit_as_a_barrier():
    human = {"id": "a1", "classId": "c1", "trackId": "t1", "keyframe": False, "source": "human",
             "shape": {"kind": "bbox", "x": 0.5, "y": 0.1, "w": 0.2, "h": 0.2}}
    new = {"id": "a9", "classId": "c1", "trackId": "t1", "keyframe": False, "source": "interpolated",
           "shape": {"kind": "bbox", "x": 0.2, "y": 0.1, "w": 0.2, "h": 0.2}}

    anns, written = merge_interpolated([human], [new])

    assert written == 0
    assert anns == [human]


def test_merge_interpolated_replaces_stale_ai_rows():
    stale = {"id": "a1", "classId": "c1", "trackId": "t1", "keyframe": False, "source": "sam3",
             "shape": {"kind": "bbox", "x": 0.5, "y": 0.1, "w": 0.2, "h": 0.2}}
    new = {"id": "a9", "classId": "c1", "trackId": "t1", "keyframe": False, "source": "interpolated",
           "shape": {"kind": "bbox", "x": 0.2, "y": 0.1, "w": 0.2, "h": 0.2}}

    anns, written = merge_interpolated([stale], [new])

    assert written == 1
    assert anns == [new]


def test_video_constants():
    assert DEFAULT_SCENE_THRESHOLD == 0.35
    assert MAX_INTERPOLATION_SPAN == 240


# --- track_forward -------------------------------------------------------------------------

def _frames(n: int = 3, size=(100, 100)) -> list[PImage.Image]:
    return [PImage.new("RGB", size) for _ in range(n)]


def test_box_of_shape_variants():
    assert track.box_of_shape({"kind": "bbox", "x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}) == (0.1, 0.2, 0.3, 0.4)
    assert track.box_of_shape({"kind": "polygon", "points": [0.2, 0.3, 0.5, 0.3, 0.5, 0.6]}) == (0.2, 0.3, 0.3, 0.3)
    box = track.box_of_shape({"kind": "keypoints", "points": [0.1, 0.1, 0, 0.2, 0.3, 2]})
    assert box == (0.2, 0.3, 0.0, 0.0)
    assert track.box_of_shape({"kind": "class"}) is None


def test_track_forward_moves_boxes_from_sam_polygon():
    calls = {"n": 0}

    def fake_sam(_im, _box):
        calls["n"] += 1
        dx = 0.1 * calls["n"]
        return [0.1 + dx, 0.1, 0.3 + dx, 0.1, 0.3 + dx, 0.3, 0.1 + dx, 0.3], 0.9

    seed = {"kind": "bbox", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}
    shapes = track.track_forward(_frames(), seed, sam_box=fake_sam, project_type="object-detection")
    assert [s["kind"] for s in shapes] == ["bbox", "bbox", "bbox"]
    assert shapes[0]["x"] == pytest.approx(0.2)
    assert shapes[1]["x"] > shapes[0]["x"]
    assert shapes[2]["x"] > shapes[1]["x"]


def test_track_forward_keeps_box_when_sam_returns_none():
    seed = {"kind": "bbox", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}
    shapes = track.track_forward(_frames(1), seed, sam_box=lambda _im, _box: (None, 0.0))
    assert shapes[0] == {"kind": "bbox", "x": pytest.approx(0.1), "y": pytest.approx(0.1),
                         "w": pytest.approx(0.2), "h": pytest.approx(0.2)}


def test_track_forward_survives_one_failing_frame():
    calls = {"n": 0}

    def flaky(_im, _box):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("SAM hiccup")
        return [0.2, 0.2, 0.4, 0.2, 0.4, 0.4, 0.2, 0.4], 0.8

    seed = {"kind": "bbox", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}
    shapes = track.track_forward(_frames(3), seed, sam_box=flaky)
    assert len(shapes) == 3


def test_track_forward_segmentation_returns_polygons():
    def fake_sam(_im, _box):
        return [0.1, 0.1, 0.3, 0.1, 0.3, 0.3], 0.9

    seed = {"kind": "bbox", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}
    shapes = track.track_forward(_frames(2), seed, sam_box=fake_sam, project_type="instance-segmentation")
    assert all(s["kind"] == "polygon" for s in shapes)
    assert len(shapes[0]["points"]) == 6


# --- extraction worker ---------------------------------------------------------------------

@pytest.fixture(scope="module")
def db_ready():
    # init_db(), not create_all(): the shared session DB must run the demo seed before this module
    # inserts users, or later login-based modules find no demo@labeldesk.dev (review I6).
    bootstrap.init_db()
    yield


def _write_video(path, frames: int = 20, fps: float = 10.0, size=(40, 30)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, size)
    if not w.isOpened():
        pytest.skip("cv2.VideoWriter cannot open an encoder on this machine")
    for i in range(frames):
        frame = np.full((size[1], size[0], 3), (i * 10 % 255, 50, 200), np.uint8)
        w.write(frame)
    w.release()


def test_run_extract_frames_creates_images(db_ready):
    clip = DATA_DIR / "videos" / f"{new_id()}.avi"
    _write_video(clip, frames=20, fps=10.0)

    with SessionLocal() as db:
        u = User(id=new_id(), email=f"{new_id()}@video.test", name="Video Tester")
        db.add(u)
        db.flush()
        ws = Workspace(id=new_id(), slug=f"v{new_id()}", name="Video WS", owner_id=u.id)
        db.add(ws)
        db.flush()
        p = Project(id=new_id(), workspace_id=ws.id, slug=f"v{new_id()}", name="Video Project")
        db.add(p)
        db.flush()
        v = Video(project_id=p.id, workspace_id=ws.id, name="clip.avi",
                  path=clip.relative_to(DATA_DIR).as_posix(), status="queued")
        db.add(v)
        db.flush()
        j = Job(workspace_id=ws.id, project_id=p.id, kind="extract_frames",
                params={"video_id": v.id, "mode": "fps", "target_fps": 1.0, "every_s": 1.0,
                        "scene_threshold": 0.35, "created_by": u.id})
        db.add(j)
        db.commit()
        jid, vid = j.id, v.id

    with SessionLocal() as db:
        job = db.get(Job, jid)
        db.expunge(job)
    result = worker.run_extract_frames(job)

    assert result["video_id"] == vid
    assert result["frames"] == 2
    with SessionLocal() as db:
        v = db.get(Video, vid)
        assert v.status == "ready"
        assert v.frame_count == 20
        assert v.fps == pytest.approx(10.0)
        assert v.batch_id == result["batch_id"]
        rows = db.query(Image).filter(Image.video_id == vid).order_by(Image.frame_index).all()
        assert [i.frame_index for i in rows] == [0, 10]
        assert all(i.batch_id == result["batch_id"] and i.project_id == v.project_id for i in rows)
        assert all(i.assignee_id == u.id for i in rows)      # extracted frames belong to the uploader


def test_demo_login_still_works_after_this_module_inserted_users(db_ready):
    from fastapi.testclient import TestClient

    from app.main import app as api_app

    with TestClient(api_app) as client:
        r = client.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "demo1234"})
        assert r.status_code == 200, r.text
        assert r.json()["token"]


def test_run_track_forward_stamps_the_seed_and_tracks_the_next_frame(db_ready):
    d = DATA_DIR / "projects" / f"track-{new_id()}"
    d.mkdir(parents=True, exist_ok=True)
    for name in ("f0.jpg", "f1.jpg"):
        PImage.new("RGB", (80, 60), (10, 20, 30)).save(d / name, "JPEG")
    rel = d.relative_to(DATA_DIR).as_posix()

    with SessionLocal() as db:
        u = User(id=new_id(), email=f"{new_id()}@track.test", name="Track Tester")
        db.add(u)
        db.flush()
        ws = Workspace(id=new_id(), slug=f"t{new_id()}", name="Track WS", owner_id=u.id)
        db.add(ws)
        db.flush()
        p = Project(id=new_id(), workspace_id=ws.id, slug=f"t{new_id()}", name="Track Project")
        db.add(p)
        db.flush()
        v = Video(project_id=p.id, workspace_id=ws.id, name="clip.avi", path="", status="ready")
        db.add(v)
        db.flush()
        seed = Image(project_id=p.id, video_id=v.id, frame_index=0, name="f0.jpg", sha256="0" * 64, width=80,
                     height=60, path=f"{rel}/f0.jpg", thumb=f"{rel}/f0.jpg", split="train", status="unassigned")
        nxt = Image(project_id=p.id, video_id=v.id, frame_index=1, name="f1.jpg", sha256="1" * 64, width=80,
                    height=60, path=f"{rel}/f1.jpg", thumb=f"{rel}/f1.jpg", split="train", status="unassigned")
        db.add_all([seed, nxt])
        db.flush()
        set_annotations(db, seed, [{"id": "seed", "classId": "c1", "source": "human",
                                    "shape": {"kind": "bbox", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}}])
        set_annotations(db, nxt, [])
        j = Job(workspace_id=ws.id, project_id=p.id, kind="track_forward",
                params={"image_id": seed.id, "annotation_id": "seed", "frames": 1, "created_by": u.id})
        db.add(j)
        db.commit()
        jid, seed_id, nxt_id = j.id, seed.id, nxt.id

    with SessionLocal() as db:
        job = db.get(Job, jid)
        db.expunge(job)
    result = worker.run_track_forward(job)

    assert result["tracked"] == 1
    with SessionLocal() as db:
        seed = db.get(Image, seed_id)
        assert seed.annotations[0]["trackId"] == result["track_id"]     # the seed joins its own track
        assert seed.annotations[0]["keyframe"] is True
        target = db.get(Image, nxt_id)
        assert [a["trackId"] for a in target.annotations] == [result["track_id"]]


# --- tracked-annotation merge -------------------------------------------------------------

def test_merge_track_replaces_interpolated_but_never_a_keyframe():
    interpolated = {"id": "a1", "trackId": "t1", "keyframe": False, "source": "interpolated"}
    other = {"id": "a2", "trackId": "t2", "keyframe": False, "source": "sam3"}
    anns, written = track.merge_track([interpolated, other], {"id": "a3", "trackId": "t1"}, "t1")

    assert written is True
    assert [a["id"] for a in anns] == ["a2", "a3"]          # stale interpolation replaced, other tracked kept

    keyframe = {"id": "a4", "trackId": "t1", "keyframe": True, "source": "sam3"}
    anns, written = track.merge_track([keyframe], {"id": "a5", "trackId": "t1"}, "t1")
    assert written is False and anns == [keyframe]           # a human keyframe is never overwritten


def test_merge_track_never_overwrites_a_human_edit_on_a_tracked_frame():
    human = {"id": "a1", "trackId": "t1", "keyframe": False, "source": "human"}
    anns, written = track.merge_track([human], {"id": "a2", "trackId": "t1"}, "t1")

    assert written is False
    assert anns == [human]
