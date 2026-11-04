"""HTTP role policy for the video endpoints: interpolate, track-forward, timeline, upload (review I3, I1, I2)."""
import os
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-video-api-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.main import app
from app.models import Image, LabelClass, Project, User, Video, Workspace, WorkspaceFlag, new_id, set_annotations

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}"
PW = "demo1234"


def _login(client: TestClient, email: str) -> dict:
    r = client.post("/api/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _bbox(x: float, **extra) -> dict:
    return {"id": f"a{new_id()}", "classId": extra.pop("classId"), "source": extra.pop("source", "interpolated"),
            "shape": {"kind": "bbox", "x": x, "y": 0.1, "w": 0.2, "h": 0.2}, **extra}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def fx(client):
    with SessionLocal() as db:
        p = db.scalar(select(Project).where(Project.slug == PR))
        ws = db.get(Workspace, p.workspace_id)
        classes = db.scalars(select(LabelClass).where(LabelClass.project_id == p.id)).all()
        admin = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        reviewer = db.scalar(select(User).where(User.email == "reviewer@labeldesk.dev"))
        labeler = db.scalar(select(User).where(User.email == "labeler@labeldesk.dev"))
        v = Video(project_id=p.id, workspace_id=ws.id, name="role-clip.mp4", path="", status="ready")
        db.add(v)
        db.flush()
        frames = []
        for index, assignee in ((0, labeler.id), (1, None), (2, reviewer.id)):
            img = Image(project_id=p.id, video_id=v.id, frame_index=index, name=f"f{index}.jpg",
                        sha256=f"{index:064d}", width=640, height=360, path="", thumb="", split="train",
                        status="unassigned", assignee_id=assignee)
            db.add(img)
            db.flush()
            set_annotations(db, img, [] if index == 1 else
                            [_bbox(0.1 * index, classId=classes[0].id, trackId="t1", keyframe=True)])
            frames.append(img.id)
        db.commit()
        ids = {"video": v.id, "frames": frames, "class": classes[0].id, "other_class": classes[1].id,
               "admin": admin.id, "reviewer": reviewer.id, "labeler": labeler.id}
    return ids


def _set_frame_annotations(frame_id: str, anns: list[dict]) -> None:
    with SessionLocal() as db:
        img = db.get(Image, frame_id)
        for a in anns:
            a.setdefault("classId", "c1")
        set_annotations(db, img, anns)
        db.commit()


def _frame_annotations(frame_id: str) -> list[dict]:
    with SessionLocal() as db:
        return list(db.get(Image, frame_id).annotations or [])


def test_interpolate_requires_reviewer(client, fx):
    body = {"from_image_id": fx["frames"][0], "to_image_id": fx["frames"][2]}

    r = client.post(f"{BASE}/videos/{fx['video']}/interpolate", json=body, headers=_login(client, "labeler@labeldesk.dev"))
    assert r.status_code == 403, r.text

    r = client.post(f"{BASE}/videos/{fx['video']}/interpolate", json=body, headers=_login(client, "reviewer@labeldesk.dev"))
    assert r.status_code == 200, r.text
    assert r.json()["annotations"] == 1


def test_interpolate_pairs_independently_drawn_keyframes(client, fx):
    _set_frame_annotations(fx["frames"][0], [_bbox(0.1, classId=fx["class"])])
    _set_frame_annotations(fx["frames"][1], [])
    _set_frame_annotations(fx["frames"][2], [_bbox(0.4, classId=fx["class"])])

    r = client.post(f"{BASE}/videos/{fx['video']}/interpolate",
                    json={"from_image_id": fx["frames"][0], "to_image_id": fx["frames"][2]},
                    headers=_login(client, "reviewer@labeldesk.dev"))

    assert r.status_code == 200, r.text
    assert r.json()["annotations"] == 1
    start, end = _frame_annotations(fx["frames"][0])[0], _frame_annotations(fx["frames"][2])[0]
    assert start["trackId"] and start["trackId"] == end["trackId"]
    assert start["keyframe"] is True and end["keyframe"] is True
    middle = _frame_annotations(fx["frames"][1])[0]
    assert middle["trackId"] == start["trackId"]
    assert middle["shape"]["x"] == pytest.approx(0.25)


def test_interpolate_returns_409_without_a_shared_track(client, fx):
    _set_frame_annotations(fx["frames"][0], [_bbox(0.1, classId=fx["class"])])
    _set_frame_annotations(fx["frames"][2], [_bbox(0.4, classId=fx["other_class"])])

    r = client.post(f"{BASE}/videos/{fx['video']}/interpolate",
                    json={"from_image_id": fx["frames"][0], "to_image_id": fx["frames"][2]},
                    headers=_login(client, "reviewer@labeldesk.dev"))

    assert r.status_code == 409, r.text
    assert "track" in r.json()["detail"].lower()


def test_interpolate_keeps_a_human_edit_on_a_middle_frame(client, fx):
    _set_frame_annotations(fx["frames"][0], [_bbox(0.1, classId=fx["class"], trackId="t1", keyframe=True)])
    _set_frame_annotations(fx["frames"][2], [_bbox(0.4, classId=fx["class"], trackId="t1", keyframe=True)])
    human = _bbox(0.35, classId=fx["class"], trackId="t1", source="human", keyframe=False)
    _set_frame_annotations(fx["frames"][1], [human])

    r = client.post(f"{BASE}/videos/{fx['video']}/interpolate",
                    json={"from_image_id": fx["frames"][0], "to_image_id": fx["frames"][2]},
                    headers=_login(client, "reviewer@labeldesk.dev"))

    assert r.status_code == 200, r.text
    assert _frame_annotations(fx["frames"][1]) == [human]


def test_timeline_hides_unassigned_frames_from_annotators(client, fx):
    labeler = _login(client, "labeler@labeldesk.dev")
    reviewer = _login(client, "reviewer@labeldesk.dev")

    seen = client.get(f"{BASE}/videos/{fx['video']}/timeline", headers=labeler).json()
    assert seen["total"] == 1
    assert [f["frameIndex"] for f in seen["frames"]] == [0]

    all_frames = client.get(f"{BASE}/videos/{fx['video']}/timeline", headers=reviewer).json()
    assert all_frames["total"] == 3


def test_track_forward_requires_an_assigned_frame(client, fx):
    body = {"annotation_id": "missing", "frames": 1}
    labeler = _login(client, "labeler@labeldesk.dev")
    reviewer = _login(client, "reviewer@labeldesk.dev")

    # unassigned frame: the annotator is refused before the annotation lookup
    r = client.post(f"/api/images/{fx['frames'][1]}/track-forward", json=body, headers=labeler)
    assert r.status_code == 403, r.text

    r = client.post(f"/api/images/{fx['frames'][1]}/track-forward", json=body, headers=reviewer)
    assert r.status_code == 404, r.text      # assignment passes, annotation lookup fails

    seeded = _frame_annotations(fx["frames"][0])[0]["id"]
    r = client.post(f"/api/images/{fx['frames'][0]}/track-forward",
                    json={"annotation_id": seeded, "frames": 1}, headers=labeler)
    assert r.status_code == 200, r.text


def test_upload_video_requires_reviewer(client, fx):
    files = {"file": ("clip.mp4", b"not really a video", "video/mp4")}
    r = client.post(f"{BASE}/videos", files=files, headers=_login(client, "labeler@labeldesk.dev"))
    assert r.status_code == 403, r.text


def test_track_forward_is_hidden_when_the_video_flag_is_off(client, fx, monkeypatch):
    """I13: task_22 names track-forward, so its route must honour the flag too."""
    monkeypatch.delenv("LD_FLAGS_ON", raising=False)
    with SessionLocal() as db:
        db.execute(delete(WorkspaceFlag).where(WorkspaceFlag.key == "task_22"))
        db.commit()
    seeded = _frame_annotations(fx["frames"][0])[0]["id"]
    r = client.post(f"/api/images/{fx['frames'][0]}/track-forward",
                    json={"annotation_id": seeded, "frames": 1},
                    headers=_login(client, "labeler@labeldesk.dev"))
    assert r.status_code == 404, r.text
