import sqlite3, os, json

db = "/mnt/e/02_Projects/auto_label/yolo26_ppe/artifacts/mlflow/backend/mlflow.db"
if not os.path.exists(db):
    print("MLflow DB not found:", db)
    exit(1)

conn = sqlite3.connect(db)
c = conn.cursor()

# List experiments
print("=== Experiments ===")
for row in c.execute("SELECT experiment_id, name, lifecycle_stage FROM experiments"):
    print(f"  ID={row[0]}  name={row[1]}  stage={row[2]}")

# List runs
print("\n=== Runs ===")
for row in c.execute("""
    SELECT r.run_uuid, r.name, r.experiment_id, r.status, r.start_time
    FROM runs r ORDER BY r.start_time DESC LIMIT 20
"""):
    print(f"  run={row[0][:12]}...  name={row[1]}  exp={row[2]}  status={row[3]}  start={row[4]}")

# Get params for latest run
print("\n=== Latest Run Params ===")
latest = c.execute("SELECT run_uuid FROM runs ORDER BY start_time DESC LIMIT 1").fetchone()
if latest:
    run_id = latest[0]
    for row in c.execute("SELECT key, value FROM params WHERE run_uuid=? ORDER BY key", (run_id,)):
        print(f"  {row[0]}: {row[1]}")

    print("\n=== Latest Run Metrics ===")
    for row in c.execute("SELECT key, value FROM metrics WHERE run_uuid=? ORDER BY key", (run_id,)):
        print(f"  {row[0]}: {row[1]}")

conn.close()
