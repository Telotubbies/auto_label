"""Experiment tracking — logs history every time batch segmentation is run.

Stores as SQLite + JSON artifacts (no MLflow server required)

Usage in batch_segment.py:
    from tracker import ExperimentTracker
    tracker = ExperimentTracker(cfg)
    exp_id = tracker.start_run(cfg, image_files)
    # ... run completed ...
    tracker.log_metrics(exp_id, {"annotations": 28})
    tracker.end_run(exp_id, status="completed")
"""

import hashlib
import json
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional


class ExperimentTracker:
    """Track experiments in SQLite + JSON artifacts."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.db_path = os.path.join(cfg.output_path, "experiments.db")
        self.artifacts_dir = os.path.join(cfg.output_path, "experiments")
        os.makedirs(self.artifacts_dir, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Create tables if not exist."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS experiments (
                    id TEXT PRIMARY KEY,
                    started_at TEXT,
                    ended_at TEXT,
                    status TEXT,
                    config_hash TEXT,
                    config_json TEXT,
                    num_images INTEGER,
                    num_annotations INTEGER,
                    total_time REAL,
                    avg_time_per_image REAL,
                    errors INTEGER,
                    git_commit TEXT,
                    model_version TEXT,
                    prompt_version TEXT
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    experiment_id TEXT,
                    key TEXT,
                    value REAL,
                    timestamp TEXT,
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS image_results (
                    experiment_id TEXT,
                    image_name TEXT,
                    num_annotations INTEGER,
                    time_seconds REAL,
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS ppe_counts (
                    experiment_id TEXT,
                    image_filename TEXT,
                    person_count INTEGER DEFAULT 0,
                    helmet_count_worn INTEGER DEFAULT 0,
                    harness_count_worn INTEGER DEFAULT 0,
                    closed_footwear_count_worn INTEGER DEFAULT 0,
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
                )
            """)
            conn.commit()

    def _config_hash(self, cfg) -> str:
        """Hash config for reproducibility."""
        config_dict = {
            "threshold": cfg.inference.confidence_threshold,
            "resolution": cfg.inference.resolution,
            "device": cfg.inference.device,
            "categories": [(c.id, c.name, c.prompt) for c in cfg.categories],
        }
        return hashlib.sha256(
            json.dumps(config_dict, sort_keys=True).encode()
        ).hexdigest()[:16]

    def _git_commit(self) -> str:
        """Get current git commit (best effort)."""
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=5,
                cwd=self.cfg.base_dir,
            )
            return result.stdout.strip() or "unknown"
        except Exception:
            return "unknown"

    def start_run(self, cfg, image_files: List[str]) -> str:
        """Start a new experiment run. Returns experiment ID."""
        import random
        import string
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
        exp_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._config_hash(cfg)}_{suffix}"
        config_json = json.dumps({
            "threshold": cfg.inference.confidence_threshold,
            "resolution": cfg.inference.resolution,
            "device": cfg.inference.device,
            "categories": [
                {"id": c.id, "name": c.name, "prompt": c.prompt}
                for c in cfg.categories
            ],
        }, ensure_ascii=False)

        # Provenance: model version from checkpoint filename, prompt version from config hash
        model_version = os.path.basename(cfg.ckpt_path) if hasattr(cfg, "ckpt_path") else "unknown"
        prompt_version = self._config_hash(cfg)

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "INSERT INTO experiments (id, started_at, status, config_hash, config_json, "
            "num_images, git_commit, model_version, prompt_version) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (exp_id, datetime.now().isoformat(), "running", self._config_hash(cfg),
             config_json, len(image_files), self._git_commit(),
             model_version, prompt_version),
        )
        conn.commit()
        conn.close()

        return exp_id

    def log_image_result(self, exp_id: str, image_name: str, num_annotations: int,
                         time_seconds: float):
        """Log result for one image."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "INSERT INTO image_results (experiment_id, image_name, num_annotations, time_seconds) VALUES (?, ?, ?, ?)",
            (
                exp_id,
                image_name,
                num_annotations,
                time_seconds,
            ),
        )
        conn.commit()
        conn.close()

    def log_ppe_counts(self, exp_id: str, image_filename: str,
                       person_count: int = 0,
                       helmet_count_worn: int = 0,
                       harness_count_worn: int = 0,
                       closed_footwear_count_worn: int = 0):
        """Log per-image PPE wear counts for compliance reporting.

        Counts how many detections of each PPE category were found in one
        image.  The *_worn suffix indicates the number of persons wearing
        that item (one detection == one wearer).
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "INSERT INTO ppe_counts "
            "(experiment_id, image_filename, person_count, "
            "helmet_count_worn, harness_count_worn, closed_footwear_count_worn) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                exp_id,
                image_filename,
                person_count,
                helmet_count_worn,
                harness_count_worn,
                closed_footwear_count_worn,
            ),
        )
        conn.commit()
        conn.close()

    def log_metrics(self, exp_id: str, metrics: Dict[str, float]):
        """Log summary metrics for a run."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        ts = datetime.now().isoformat()
        for key, value in metrics.items():
            c.execute(
                "INSERT INTO metrics (experiment_id, key, value, timestamp) VALUES (?, ?, ?, ?)",
                (exp_id, key, float(value), ts),
            )
        # Update experiment summary
        c.execute(
            """UPDATE experiments SET
                num_annotations = ?,
                total_time = ?, avg_time_per_image = ?, errors = ?
                WHERE id = ?""",
            (
                metrics.get("annotations", 0),
                metrics.get("total_time", 0),
                metrics.get("avg_time", 0),
                metrics.get("errors", 0),
                exp_id,
            ),
        )
        conn.commit()
        conn.close()

    def end_run(self, exp_id: str, status: str = "completed"):
        """End experiment run."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "UPDATE experiments SET ended_at = ?, status = ? WHERE id = ?",
            (datetime.now().isoformat(), status, exp_id),
        )
        conn.commit()
        conn.close()

    def list_experiments(self, limit: int = 20) -> List[dict]:
        """List recent experiments."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            "SELECT * FROM experiments ORDER BY started_at DESC LIMIT ?",
            (limit,),
        )
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows

    def get_experiment(self, exp_id: str) -> Optional[dict]:
        """Get one experiment with image results."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM experiments WHERE id = ?", (exp_id,))
        exp = c.fetchone()
        if not exp:
            conn.close()
            return None
        c.execute("SELECT * FROM image_results WHERE experiment_id = ?", (exp_id,))
        images = [dict(r) for r in c.fetchall()]
        c.execute("SELECT * FROM metrics WHERE experiment_id = ?", (exp_id,))
        metrics = {r["key"]: r["value"] for r in c.fetchall()}
        conn.close()
        return {"experiment": dict(exp), "images": images, "metrics": metrics}

    def get_stats(self) -> dict:
        """Get aggregate stats across all experiments."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM experiments")
        total_runs = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM experiments WHERE status = 'completed'")
        completed = c.fetchone()[0]
        c.execute("SELECT SUM(num_annotations) FROM experiments")
        total_anns = c.fetchone()[0] or 0
        c.execute("SELECT AVG(avg_time_per_image) FROM experiments WHERE avg_time_per_image > 0")
        avg_time = c.fetchone()[0] or 0
        conn.close()
        return {
            "total_runs": total_runs,
            "completed": completed,
            "total_annotations": total_anns,
            "avg_time_per_image": round(avg_time, 1),
        }
