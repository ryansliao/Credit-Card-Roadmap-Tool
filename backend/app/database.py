import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapper
from sqlalchemy.schema import CreateColumn

load_dotenv()

_app_env = os.getenv("APP_ENV", "production")
_local_url = os.getenv("LOCAL_DATABASE_URL", "")
_prod_url = os.getenv("DATABASE_URL", "")

if _app_env == "development" and _local_url:
    DATABASE_URL = _local_url
    logger.info("Using local database (APP_ENV=development)")
elif _prod_url:
    DATABASE_URL = _prod_url
    logger.info("Using production database")
else:
    raise ValueError(
        "No database URL configured. Set DATABASE_URL in your .env file, e.g.: "
        "DATABASE_URL=mssql+aioodbc://sa:password@localhost:1433/creditcards"
        "?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
    )

# Normalise scheme — aioodbc requires mssql+aioodbc://
if DATABASE_URL.startswith("mssql://"):
    DATABASE_URL = DATABASE_URL.replace("mssql://", "mssql+aioodbc://", 1)
elif DATABASE_URL.startswith("sqlserver://"):
    DATABASE_URL = DATABASE_URL.replace("sqlserver://", "mssql+aioodbc://", 1)
elif DATABASE_URL.startswith("mssql+pyodbc://"):
    DATABASE_URL = DATABASE_URL.replace("mssql+pyodbc://", "mssql+aioodbc://", 1)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_size=10,
    max_overflow=5,
    pool_recycle=300,   # recycle connections idle >5 min (prevents MSSQL stale connections)
    pool_pre_ping=True, # test connection before reuse to avoid stale connection errors
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    pass


# Fetch server-generated values (server_default, server_onupdate, onupdate)
# back into the in-memory instance during flush via OUTPUT/RETURNING. Without
# this, accessing such columns (e.g. updated_at) after commit triggers a
# synchronous lazy-load that fails under AsyncSession (MissingGreenlet) when
# serialising via Pydantic.
@event.listens_for(Mapper, "mapper_configured")
def _enable_eager_defaults(mapper: Mapper, _class: type) -> None:
    mapper.eager_defaults = True


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


_MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


async def create_tables() -> None:
    """Create all tables and run pending migrations on startup."""
    async with engine.begin() as conn:
        from . import models  # noqa: F401 — ensure models are registered
        await conn.run_sync(Base.metadata.create_all)
    await _run_migrations()
    await _auto_add_missing_columns()


async def _auto_add_missing_columns() -> None:
    """Add columns defined on mapped models but missing from the live DB.

    Additive-only: never drops, renames, or retypes existing columns. Those
    still require an explicit backend/migrations/*.sql file. Covers the common
    case of adding a new nullable column to a user-data table without hand-
    rolling a migration. A NOT NULL column with no ``server_default`` will
    fail here if the table already has rows — that's by design; write a
    migration with an explicit backfill in that case.
    """
    from . import models  # noqa: F401 — ensure mappers are registered

    async with engine.begin() as conn:
        result = await conn.execute(text(
            """
            SELECT LOWER(o.name) AS table_name, LOWER(c.name) AS column_name
            FROM sys.columns c
            INNER JOIN sys.objects o ON c.object_id = o.object_id
            WHERE o.type = 'U'
            """
        ))
        live: dict[str, set[str]] = {}
        for row in result:
            live.setdefault(row.table_name, set()).add(row.column_name)

        for table in Base.metadata.sorted_tables:
            existing = live.get(table.name.lower())
            if existing is None:
                continue  # table didn't exist pre-create_all; nothing to patch
            for col in table.columns:
                if col.name.lower() in existing:
                    continue
                column_ddl = str(CreateColumn(col).compile(dialect=engine.dialect))
                logger.info("Auto-migrate: ALTER TABLE %s ADD %s", table.name, col.name)
                await conn.execute(text(f"ALTER TABLE {table.name} ADD {column_ddl}"))


async def _run_migrations() -> None:
    """Run any pending SQL migration files from backend/migrations/ in order.

    Each .sql file is T-SQL and may use GO on its own line as a batch separator.
    Applied migrations are recorded in the schema_migrations table so they are
    never re-executed on subsequent startups.
    """
    async with engine.begin() as conn:
        await conn.execute(text("""
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
        """))

    if not _MIGRATIONS_DIR.exists():
        return

    sql_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    for sql_file in sql_files:
        migration_id = sql_file.name
        async with engine.begin() as conn:
            row = await conn.execute(
                text("SELECT 1 FROM schema_migrations WHERE id = :id"),
                {"id": migration_id},
            )
            if row.scalar():
                continue

            logger.info("Applying migration: %s", migration_id)
            await _execute_migration_file(conn, sql_file.read_text())
            await conn.execute(
                text("INSERT INTO schema_migrations (id) VALUES (:id)"),
                {"id": migration_id},
            )
            logger.info("Applied migration: %s", migration_id)


async def _execute_migration_file(conn, sql_text: str) -> None:
    """Execute a T-SQL migration file, splitting on GO batch separators.

    GO must appear on its own line (case-insensitive).  Each resulting batch
    is submitted to SQL Server as a separate statement within the same
    transaction so the whole migration rolls back as a unit on failure.
    """
    batches = re.split(r"^\s*GO\s*$", sql_text, flags=re.MULTILINE | re.IGNORECASE)
    for batch in batches:
        batch = batch.strip()
        if batch:
            await conn.execute(text(batch))
