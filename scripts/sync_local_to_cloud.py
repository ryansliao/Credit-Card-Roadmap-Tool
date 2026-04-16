#!/usr/bin/env python3
"""
Sync local SQL Server → cloud Azure SQL.

Applies any pending schema migrations to the cloud DB (including user-table
schema changes), then MERGEs all reference-data tables from local → cloud.
User / wallet tables are left untouched — their schema stays current via
migrations, but their row data stays cloud-only.

Usage
-----
    python3 scripts/sync_local_to_cloud.py [--dry-run] [--no-delete]

    --dry-run     Print what would change; write nothing.
    --no-delete   Upsert only — do not delete cloud rows absent from local.
                  Default behaviour deletes orphan rows (rolls back per-table
                  if a FK violation is hit and warns you instead).

Requirements
------------
    - pyodbc installed (pip install pyodbc)
    - ODBC Driver 18 for SQL Server on the host (brew install msodbcsql18)
    - .env at the repo root with LOCAL_DATABASE_URL and DATABASE_URL
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent

try:
    import pyodbc
except ImportError:
    sys.exit("pyodbc not found. Run: pip install pyodbc")

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass  # env vars may already be set externally

MIGRATIONS_DIR = REPO_ROOT / "backend" / "migrations"

# ── Sync manifest ────────────────────────────────────────────────────────────
# Reference tables in topological / dependency order (parents before children).
# Only these tables have their *data* synced to the cloud.
REFERENCE_TABLES: list[str] = [
    "issuers",
    "co_brands",
    "networks",
    "network_tiers",
    "currencies",               # self-ref: converts_to_currency_id
    "spend_categories",         # self-ref: parent_id
    "travel_portals",
    "cards",
    "card_multiplier_groups",
    "card_category_multipliers",
    "rotating_categories",
    "credits",
    "card_credits",             # composite PK, no IDENTITY
    "travel_portal_cards",      # composite PK, no IDENTITY
    "issuer_application_rules",
]

# Tables whose data must NOT be synced (schema kept current via migrations).
USER_TABLES: frozenset[str] = frozenset({
    "users",
    "wallets",
    "wallet_cards",
    "wallet_currency_balances",
    "wallet_card_credits",
    "wallet_card_group_selections",
    "wallet_card_category_priorities",
    "wallet_portal_shares",
    "wallet_currency_cpp",
    "wallet_card_multipliers",
    "wallet_spend_items",
    # Legacy tables kept for schema compatibility only
    "wallet_spend_categories",
    "wallet_spend_category_mappings",
    # Each DB tracks its own applied migrations
    "schema_migrations",
})

# Self-referential FK tables: NOCHECK constraints during MERGE so insert order
# within the set doesn't matter (re-checked after).
SELF_REF_FK_TABLES: frozenset[str] = frozenset({"currencies", "spend_categories"})

BATCH_SIZE = 500


# ── Connection helpers ───────────────────────────────────────────────────────

def _url_to_pyodbc(url: str) -> str:
    """Convert a mssql+aioodbc:// SQLAlchemy URL to a pyodbc connection string."""
    url = re.sub(r"^mssql\+(?:aioodbc|pyodbc)://", "x://", url)
    p = urlparse(url)
    userinfo, _, hostinfo = p.netloc.rpartition("@")
    host, _, port = hostinfo.partition(":")
    port = port or "1433"
    uid, _, pwd = userinfo.partition(":")
    database = p.path.lstrip("/")

    qs = parse_qs(p.query)
    driver = qs.get("driver", ["ODBC Driver 18 for SQL Server"])[0].replace("+", " ")
    encrypt = (qs.get("Encrypt") or [None])[0]
    trust = (qs.get("TrustServerCertificate") or [None])[0]

    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={host},{port}",
        f"DATABASE={database}",
        f"UID={unquote(uid)}",
        f"PWD={{{unquote(pwd)}}}",
    ]
    if encrypt:
        parts.append(f"Encrypt={encrypt}")
    if trust:
        parts.append(f"TrustServerCertificate={trust}")
    return ";".join(parts)


def _connect(url: str, label: str) -> pyodbc.Connection:
    cs = _url_to_pyodbc(url)
    try:
        conn = pyodbc.connect(cs, autocommit=False)
        print(f"  connected to {label}")
        return conn
    except pyodbc.Error as exc:
        sys.exit(f"Cannot connect to {label}: {exc}")


# ── Schema introspection ─────────────────────────────────────────────────────

def _columns(cur: pyodbc.Cursor, table: str) -> list[str]:
    cur.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = ? ORDER BY ORDINAL_POSITION
    """, table)
    return [r[0] for r in cur.fetchall()]


def _pk_columns(cur: pyodbc.Cursor, table: str) -> list[str]:
    cur.execute("""
        SELECT ccu.COLUMN_NAME
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
        JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
            ON ccu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
            AND ccu.TABLE_NAME = tc.TABLE_NAME
        WHERE tc.TABLE_NAME = ? AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
    """, table)
    return [r[0] for r in cur.fetchall()]


def _has_identity(cur: pyodbc.Cursor, table: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) FROM sys.columns WHERE object_id = OBJECT_ID(?) AND is_identity = 1",
        table,
    )
    return bool(cur.fetchone()[0])


def _all_tables(cur: pyodbc.Cursor) -> set[str]:
    cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
    return {r[0] for r in cur.fetchall()}


# ── Migration runner ─────────────────────────────────────────────────────────

def run_migrations(conn: pyodbc.Connection, *, dry_run: bool) -> None:
    print("\n── Schema migrations ──────────────────────────────────────────")
    cur = conn.cursor()

    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM sys.objects
            WHERE object_id = OBJECT_ID(N'schema_migrations') AND type = 'U'
        )
        BEGIN
            CREATE TABLE schema_migrations (
                id         NVARCHAR(255)     PRIMARY KEY,
                applied_at DATETIMEOFFSET(7) NOT NULL DEFAULT GETUTCDATE()
            )
        END
    """)
    conn.commit()

    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not sql_files:
        print("  (no migration files found)")
        return

    for f in sql_files:
        mid = f.name
        cur.execute("SELECT 1 FROM schema_migrations WHERE id = ?", mid)
        if cur.fetchone():
            print(f"  skip  {mid}")
            continue

        suffix = "  (dry-run, not applied)" if dry_run else ""
        print(f"  apply {mid}{suffix}")
        if dry_run:
            continue

        sql = f.read_text()
        for batch in re.split(r"^\s*GO\s*$", sql, flags=re.MULTILINE | re.IGNORECASE):
            batch = batch.strip()
            if batch:
                cur.execute(batch)
        cur.execute("INSERT INTO schema_migrations (id) VALUES (?)", mid)
        conn.commit()


# ── Table sync ───────────────────────────────────────────────────────────────

def _sync_table(
    src: pyodbc.Connection,
    dst: pyodbc.Connection,
    table: str,
    *,
    delete_orphans: bool,
    dry_run: bool,
) -> None:
    src_cur = src.cursor()
    dst_cur = dst.cursor()

    cols = _columns(src_cur, table)
    pk_cols = _pk_columns(src_cur, table)
    identity = _has_identity(src_cur, table)
    non_pk_cols = [c for c in cols if c not in pk_cols]

    q_cols = ", ".join(f"[{c}]" for c in cols)
    src_cur.execute(f"SELECT {q_cols} FROM [{table}]")
    rows = src_cur.fetchall()

    print(f"  {table:<42} {len(rows):>5} rows", end="", flush=True)

    if dry_run:
        print("  (dry-run)")
        return

    temp = f"#sync_{table}"

    # Mirror the destination table structure into a session-scoped temp table.
    dst_cur.execute(f"SELECT TOP 0 {q_cols} INTO [{temp}] FROM [{table}]")

    try:
        # ── Load source rows into the temp table ──────────────────────────
        if identity:
            dst_cur.execute(f"SET IDENTITY_INSERT [{temp}] ON")

        insert_sql = (
            f"INSERT INTO [{temp}] ({q_cols}) "
            f"VALUES ({', '.join('?' * len(cols))})"
        )
        for i in range(0, len(rows), BATCH_SIZE):
            dst_cur.executemany(insert_sql, [tuple(r) for r in rows[i : i + BATCH_SIZE]])

        if identity:
            dst_cur.execute(f"SET IDENTITY_INSERT [{temp}] OFF")

        # ── Build and run MERGE ───────────────────────────────────────────
        on_clause = " AND ".join(f"t.[{c}] = s.[{c}]" for c in pk_cols)
        matched_clause = (
            "WHEN MATCHED THEN UPDATE SET "
            + ", ".join(f"t.[{c}] = s.[{c}]" for c in non_pk_cols)
        ) if non_pk_cols else ""
        not_matched_clause = (
            f"WHEN NOT MATCHED BY TARGET THEN "
            f"INSERT ({q_cols}) VALUES ({', '.join(f's.[{c}]' for c in cols)})"
        )
        delete_clause = "WHEN NOT MATCHED BY SOURCE THEN DELETE" if delete_orphans else ""

        merge_sql = "\n".join(filter(None, [
            f"MERGE INTO [{table}] AS t",
            f"USING [{temp}] AS s ON {on_clause}",
            matched_clause,
            not_matched_clause,
            delete_clause + ";",
        ]))

        if table in SELF_REF_FK_TABLES:
            dst_cur.execute(f"ALTER TABLE [{table}] NOCHECK CONSTRAINT ALL")
        if identity:
            dst_cur.execute(f"SET IDENTITY_INSERT [{table}] ON")

        dst_cur.execute(merge_sql)
        affected = dst_cur.rowcount

        if identity:
            dst_cur.execute(f"SET IDENTITY_INSERT [{table}] OFF")
        if table in SELF_REF_FK_TABLES:
            dst_cur.execute(f"ALTER TABLE [{table}] WITH CHECK CHECK CONSTRAINT ALL")

        dst.commit()
        print(f"  → {affected} affected")

    except pyodbc.Error as exc:
        dst.rollback()
        # Error 547 = FK constraint violation — usually means a cloud row that
        # no longer exists locally is still referenced by user/wallet data.
        # Retry without the delete and warn so the user knows.
        if delete_orphans and "547" in str(exc):
            print(f"\n    WARNING: FK violation prevented delete on [{table}].")
            print(f"    Cloud has rows not in local that are still referenced by user data.")
            print(f"    Retrying as upsert-only for this table...")
            _sync_table(src, dst, table, delete_orphans=False, dry_run=dry_run)
            return
        print(f"\n    ERROR syncing [{table}]: {exc}")
        raise

    finally:
        # Always clean up the temp table, even on error
        cleanup_cur = dst.cursor()
        cleanup_cur.execute(
            f"IF OBJECT_ID('tempdb..[{temp}]') IS NOT NULL DROP TABLE [{temp}]"
        )
        dst.commit()


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="Show planned changes without writing")
    ap.add_argument("--no-delete", action="store_true", help="Upsert only; skip delete of cloud-only rows")
    args = ap.parse_args()

    local_url = os.environ.get("LOCAL_DATABASE_URL", "")
    cloud_url = os.environ.get("DATABASE_URL", "")
    if not local_url:
        sys.exit("LOCAL_DATABASE_URL not set in .env")
    if not cloud_url:
        sys.exit("DATABASE_URL not set in .env")

    print("Connecting...")
    src = _connect(local_url, "local")
    dst = _connect(cloud_url, "cloud")

    if args.dry_run:
        print("\n[DRY RUN — no changes will be written]")

    run_migrations(dst, dry_run=args.dry_run)

    print("\n── Reference data ─────────────────────────────────────────────")
    dst_tables = _all_tables(dst.cursor())

    for table in REFERENCE_TABLES:
        if table not in dst_tables:
            print(f"  {table}: not in cloud yet — run migrations first, then re-sync")
            continue
        _sync_table(src, dst, table, delete_orphans=not args.no_delete, dry_run=args.dry_run)

    src.close()
    dst.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
