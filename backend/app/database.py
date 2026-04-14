import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is not set. "
        "Add it to your .env file, e.g.: "
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

engine = create_async_engine(DATABASE_URL, echo=False, future=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    pass


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
