"""Projects, datasets, videos, annotations and dataset versions."""
from sqlalchemy import (JSON, Boolean, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base
from .common import new_id, now
from .identity import User


class Folder(Base):
    __tablename__ = "folders"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    created: Mapped[float] = mapped_column(Float, default=now)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("workspace_id", "slug"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    folder_id: Mapped[str | None] = mapped_column(ForeignKey("folders.id", ondelete="SET NULL"), nullable=True)
    slug: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(32), default="object-detection")
    multilabel: Mapped[bool] = mapped_column(Boolean, default=False)
    visibility: Mapped[str] = mapped_column(String(16), default="private")
    license: Mapped[str] = mapped_column(String(64), default="CC BY 4.0")
    annotation_group: Mapped[str] = mapped_column(String(120), default="objects")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)   # active learning, review mode …
    # PDPA: per-project retention in days (NULL/0 = keep) and face anonymisation before frames reach datasets.
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    face_blur: Mapped[bool] = mapped_column(Boolean, default=True)
    biometrics: Mapped[bool] = mapped_column(Boolean, default=False)      # face recognition — opt-in only
    legal_basis: Mapped[str] = mapped_column(Text, default="")            # documented PDPA s.26 basis
    created: Mapped[float] = mapped_column(Float, default=now)
    updated: Mapped[float] = mapped_column(Float, default=now)
    deleted_at: Mapped[float | None] = mapped_column(Float, nullable=True)


class LabelClass(Base):
    __tablename__ = "classes"
    __table_args__ = (UniqueConstraint("project_id", "name"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    color: Mapped[str] = mapped_column(String(16), default="#8b5cf6")
    # keypoint schema for this class: {"names": [...], "edges": [[i, j], ...], "flip_idx": [...]}
    skeleton: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created: Mapped[float] = mapped_column(Float, default=now)


class Video(Base):
    """An uploaded video whose sampled frames become images of one batch."""
    __tablename__ = "videos"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    name: Mapped[str] = mapped_column(String(512))
    path: Mapped[str] = mapped_column(String(1024))              # relative to DATA_DIR
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    fps: Mapped[float] = mapped_column(Float, default=0.0)
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    frame_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="queued")   # queued | extracting | ready | failed
    error: Mapped[str] = mapped_column(Text, default="")
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    created: Mapped[float] = mapped_column(Float, default=now)
    deleted_at: Mapped[float | None] = mapped_column(Float, nullable=True)


class Batch(Base):
    __tablename__ = "batches"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(32), default="upload")   # upload | import | api | active-learning
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created: Mapped[float] = mapped_column(Float, default=now)


class Image(Base):
    __tablename__ = "images"
    __table_args__ = (Index("ix_images_project_status", "project_id", "status"),
                      Index("ix_images_project_sha", "project_id", "sha256"),
                      Index("ix_images_project_created", "project_id", "deleted_at", "created"))
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("batches.id", ondelete="SET NULL"), nullable=True, index=True)
    video_id: Mapped[str | None] = mapped_column(ForeignKey("videos.id", ondelete="SET NULL"), nullable=True, index=True)
    frame_index: Mapped[int | None] = mapped_column(Integer, nullable=True)   # 0-based frame in the source video
    name: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    path: Mapped[str] = mapped_column(String(1024))       # relative to DATA_DIR
    thumb: Mapped[str] = mapped_column(String(1024))
    size: Mapped[int] = mapped_column(Integer, default=0)
    # data-quality signals measured once at ingest; NULL means unknown, never "good"
    sharpness: Mapped[float | None] = mapped_column(Float, nullable=True)   # 0-1 Laplacian-variance score
    luminance: Mapped[float | None] = mapped_column(Float, nullable=True)   # 0-1 mean grayscale
    split: Mapped[str] = mapped_column(String(8), default="train")
    status: Mapped[str] = mapped_column(String(16), default="unassigned")
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review: Mapped[str | None] = mapped_column(String(16), nullable=True)   # approved | rejected
    tags: Mapped[list] = mapped_column(JSON, default=list)
    annotations: Mapped[list] = mapped_column(JSON, default=list)
    n_annotations: Mapped[int] = mapped_column(Integer, default=0)
    created: Mapped[float] = mapped_column(Float, default=now)
    updated: Mapped[float] = mapped_column(Float, default=now)
    deleted_at: Mapped[float | None] = mapped_column(Float, nullable=True)


class ImageClass(Base):
    """Denormalised (image, class) -> count index of Image.annotations, kept in sync by
    set_annotations(). Lets class counts and class filters run in SQL instead of
    scanning every annotation JSON blob."""
    __tablename__ = "image_classes"
    __table_args__ = (Index("ix_image_classes_project_class", "project_id", "class_id"),)
    image_id: Mapped[str] = mapped_column(ForeignKey("images.id", ondelete="CASCADE"), primary_key=True)
    class_id: Mapped[str] = mapped_column(String(32), primary_key=True, index=True)
    project_id: Mapped[str] = mapped_column(String(32))
    n: Mapped[int] = mapped_column(Integer, default=1)


def set_annotations(db, img: "Image", anns: list[dict]):
    """The only way annotations should be written — keeps n_annotations and image_classes in sync."""
    from collections import Counter
    from sqlalchemy import delete
    img.annotations = anns
    img.n_annotations = len(anns)
    img.updated = now()
    if img.id is None:
        img.id = new_id()
    db.execute(delete(ImageClass).where(ImageClass.image_id == img.id))
    for cid, n in Counter(a.get("classId") for a in anns
                          if isinstance(a, dict) and a.get("classId")).items():
        db.add(ImageClass(image_id=img.id, class_id=cid, project_id=img.project_id, n=n))


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    image_id: Mapped[str] = mapped_column(ForeignKey("images.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text)
    created: Mapped[float] = mapped_column(Float, default=now)
    user: Mapped[User] = relationship(lazy="joined")


class Version(Base):
    __tablename__ = "versions"
    __table_args__ = (UniqueConstraint("project_id", "number"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(255), default="")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)   # preprocessing / augmentation / split
    status: Mapped[str] = mapped_column(String(16), default="queued")
    stats: Mapped[dict] = mapped_column(JSON, default=dict)      # counts per split / class
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created: Mapped[float] = mapped_column(Float, default=now)
