"""Postgres persistence: idempotent upserts, run audit, and quarantine.

Idempotency contract: every raw table carries a natural-key UNIQUE constraint
(defined in database/init/02_raw_tables.sql); loads use ON CONFLICT DO UPDATE
so re-running any window is safe and late EIA revisions overwrite in place.
"""

import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg

logger = logging.getLogger("loaders")


def connect(database_url: str) -> psycopg.Connection:
    return psycopg.connect(database_url)


def upsert_records(
    conn: psycopg.Connection,
    table: str,
    records: list[dict[str, Any]],
    conflict_cols: list[str],
    run_id: UUID,
) -> int:
    if not records:
        return 0
    columns = [c for c in records[0].keys()] + ["_run_id"]
    update_cols = [c for c in columns if c not in conflict_cols]
    sql = (
        f"INSERT INTO {table} ({', '.join(columns)}) "
        f"VALUES ({', '.join(f'%({c})s' for c in columns)}) "
        f"ON CONFLICT ({', '.join(conflict_cols)}) DO UPDATE SET "
        + ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
        + ", _ingested_at = now()"
    )
    rows = [{**record, "_run_id": run_id} for record in records]
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    conn.commit()
    logger.info("table=%s upserted=%s run_id=%s", table, len(rows), run_id)
    return len(rows)


def quarantine(
    conn: psycopg.Connection,
    source: str,
    rejected: list[tuple[dict[str, Any], str]],
    run_id: UUID,
) -> int:
    if not rejected:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO ops.rejected_records (source, raw_payload, rejection_reason, _run_id) "
            "VALUES (%s, %s, %s, %s)",
            [(source, json.dumps(payload, default=str), reason, run_id) for payload, reason in rejected],
        )
    conn.commit()
    logger.warning("source=%s quarantined=%s run_id=%s", source, len(rejected), run_id)
    return len(rejected)


def record_run(
    conn: psycopg.Connection,
    run_id: UUID,
    asset_name: str,
    status: str,
    rows_processed: int,
    rows_rejected: int,
    window_start: datetime | None,
    window_end: datetime | None,
    started_at: datetime,
    error_message: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ops.pipeline_runs
                (run_id, asset_name, status, rows_processed, rows_rejected,
                 window_start, window_end, started_at, error_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (run_id, asset_name) DO UPDATE
                SET status = EXCLUDED.status,
                    rows_processed = EXCLUDED.rows_processed,
                    rows_rejected = EXCLUDED.rows_rejected,
                    finished_at = now(),
                    error_message = EXCLUDED.error_message
            """,
            (run_id, asset_name, status, rows_processed, rows_rejected,
             window_start, window_end, started_at, error_message),
        )
    conn.commit()


def get_max_period(conn: psycopg.Connection, table: str, column: str = "period_utc") -> datetime | None:
    """Watermark for incremental fetch windows."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT max({column}) FROM {table}")  # table names are code-owned, not user input
        return cur.fetchone()[0]
