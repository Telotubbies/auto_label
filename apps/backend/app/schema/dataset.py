"""Column upgrades for projects, datasets and their annotations."""

PROJECTS = {"retention_days": "INTEGER", "face_blur": "BOOLEAN DEFAULT TRUE",
            "biometrics": "BOOLEAN DEFAULT FALSE", "legal_basis": "TEXT DEFAULT ''"}
CLASSES = {"skeleton": "JSON"}
IMAGES = {"video_id": "VARCHAR(32)", "frame_index": "INTEGER",
          "sharpness": "FLOAT", "luminance": "FLOAT"}
LABEL_EVENTS = {"ai_ids": "JSON"}
CONSENSUS_JOBS = {"image_metrics": "JSON"}
