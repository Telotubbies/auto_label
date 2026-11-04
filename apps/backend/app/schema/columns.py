"""Idempotent ``ALTER TABLE ... ADD COLUMN``, shared by every domain module."""
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError


def ensure_columns(eng, table: str, cols: dict[str, str]) -> None:
    """Idempotent ALTER TABLE ... ADD COLUMN; cols maps name -> DDL fragment (type + default)."""
    have = {c["name"] for c in inspect(eng).get_columns(table)}
    with eng.begin() as cn:
        for name, ddl in cols.items():
            if name in have:
                continue
            try:
                cn.exec_driver_sql(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}')
            except OperationalError as e:      # a concurrent process won the race after our inspect
                msg = str(e).lower()
                if "duplicate column" not in msg and "already exists" not in msg:
                    raise
