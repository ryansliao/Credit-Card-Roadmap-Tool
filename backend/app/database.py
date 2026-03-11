import os

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Normalise scheme — asyncpg requires postgresql+asyncpg://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

_is_azure = "azure.com" in DATABASE_URL
_connect_args: dict = {}

if _is_azure:
    _connect_args["ssl"] = "require"

    # If no password is in the URL, use Azure Managed Identity to fetch a token.
    # This allows the App Service to connect to Azure PostgreSQL without storing
    # a password — the platform identity is used instead.
    _no_password = ":@" in DATABASE_URL or DATABASE_URL.endswith("@")
    if _no_password or not os.getenv("PGPASSWORD"):
        try:
            from azure.identity import DefaultAzureCredential

            _credential = DefaultAzureCredential()
            _token = _credential.get_token("https://ossrdbms-aad.database.windows.net/.default")
            _connect_args["password"] = _token.token
        except Exception:
            pass  # Fall back to password-based auth if identity unavailable

engine = create_async_engine(DATABASE_URL, echo=False, future=True, connect_args=_connect_args)

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


def _drop_currency_comparison_factor(sync_conn):
    """Remove comparison_factor from currencies (we only use cpp)."""
    if sync_conn.dialect.name != "postgresql":
        return
    sync_conn.execute(
        text("""
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'currencies' AND column_name = 'comparison_factor'
          ) THEN
            ALTER TABLE currencies DROP COLUMN comparison_factor;
          END IF;
        END $$;
        """)
    )


def _currency_issuer_nullable(sync_conn):
    """Allow currencies.issuer_id to be NULL (e.g. for Cash)."""
    if sync_conn.dialect.name != "postgresql":
        return
    sync_conn.execute(
        text("""
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'currencies' AND column_name = 'issuer_id'
          ) AND (
            SELECT is_nullable = 'NO' FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'currencies' AND column_name = 'issuer_id'
          ) THEN
            ALTER TABLE currencies ALTER COLUMN issuer_id DROP NOT NULL;
          END IF;
        END $$;
        """)
    )


def _add_issuer_columns_if_missing(sync_conn):
    """Add co_brand_partner and network to issuers if they don't exist (PostgreSQL)."""
    if sync_conn.dialect.name != "postgresql":
        return
    sync_conn.execute(
        text("""
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'issuers' AND column_name = 'co_brand_partner'
          ) THEN
            ALTER TABLE issuers ADD COLUMN co_brand_partner VARCHAR(80);
          END IF;
          IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'issuers' AND column_name = 'network'
          ) THEN
            ALTER TABLE issuers ADD COLUMN network VARCHAR(40);
          END IF;
        END $$;
        """)
    )


def _migrate_boost_to_cashback_conversion(sync_conn):
    """Replace ecosystem boost with currency converts_to_points + card anchors_cashback_conversion (PostgreSQL)."""
    if sync_conn.dialect.name != "postgresql":
        return
    sync_conn.execute(
        text("""
        DO $$
        BEGIN
          -- Currencies: add converts_to_points and converts_to_currency_id
          IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'currencies' AND column_name = 'converts_to_points'
          ) THEN
            ALTER TABLE currencies ADD COLUMN converts_to_points BOOLEAN DEFAULT FALSE NOT NULL;
          END IF;
          IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'currencies' AND column_name = 'converts_to_currency_id'
          ) THEN
            ALTER TABLE currencies ADD COLUMN converts_to_currency_id INTEGER REFERENCES currencies(id);
          END IF;
          -- Cards: add anchors_cashback_conversion and secondary_points_currency_id if migrating from old boost
          IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'cards' AND column_name = 'anchors_cashback_conversion'
          ) THEN
            ALTER TABLE cards ADD COLUMN anchors_cashback_conversion BOOLEAN DEFAULT FALSE NOT NULL;
          END IF;
          IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'cards' AND column_name = 'secondary_points_currency_id'
          ) THEN
            ALTER TABLE cards ADD COLUMN secondary_points_currency_id INTEGER REFERENCES currencies(id);
          END IF;
          -- Cards: drop ecosystem_boost_id
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'cards' AND column_name = 'ecosystem_boost_id'
          ) THEN
            ALTER TABLE cards DROP CONSTRAINT IF EXISTS cards_ecosystem_boost_id_fkey;
            ALTER TABLE cards DROP COLUMN ecosystem_boost_id;
          END IF;
          -- Drop old boost tables (order matters for FKs)
          DROP TABLE IF EXISTS ecosystem_boost_anchors;
          DROP TABLE IF EXISTS ecosystem_boosts;
        END $$;
        """)
    )


def _migrate_to_ecosystems(sync_conn):
    """
    Migrate from card.anchors_cashback_conversion + secondary_points_currency_id
    to Ecosystem + CardEcosystem. Creates ecosystems from existing data, then drops old columns.
    """
    if sync_conn.dialect.name != "postgresql":
        return
    # Check if cards still has the old columns
    r = sync_conn.execute(
        text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'cards' AND column_name = 'anchors_cashback_conversion'
        """)
    )
    if r.scalar() is None:
        return  # already migrated

    # 1) Backfill ecosystems from distinct points currencies (from cards.secondary or currencies.converts_to)
    sync_conn.execute(
        text("""
        INSERT INTO ecosystems (name, points_currency_id, cashback_currency_id)
        SELECT DISTINCT ON (cur.id)
          cur.name,
          cur.id,
          COALESCE(
            (SELECT c.currency_id FROM cards c WHERE c.secondary_points_currency_id = cur.id LIMIT 1),
            (SELECT cu.id FROM currencies cu WHERE cu.converts_to_currency_id = cur.id AND cu.id != cur.id LIMIT 1)
          )
        FROM currencies cur
        WHERE cur.id IN (SELECT secondary_points_currency_id FROM cards WHERE secondary_points_currency_id IS NOT NULL)
           OR cur.id IN (SELECT converts_to_currency_id FROM currencies WHERE converts_to_currency_id IS NOT NULL)
        ON CONFLICT (name) DO NOTHING
        """)
    )
    # 2) Key cards: anchors_cashback_conversion = true -> ecosystem where points_currency_id = card.currency_id
    sync_conn.execute(
        text("""
        INSERT INTO card_ecosystems (card_id, ecosystem_id, key_card)
        SELECT c.id, e.id, true
        FROM cards c
        JOIN ecosystems e ON e.points_currency_id = c.currency_id
        WHERE c.anchors_cashback_conversion = true
        ON CONFLICT (card_id, ecosystem_id) DO UPDATE SET key_card = true
        """)
    )
    # 3) Beneficiaries: secondary_points_currency_id set -> ecosystem with that points currency
    sync_conn.execute(
        text("""
        INSERT INTO card_ecosystems (card_id, ecosystem_id, key_card)
        SELECT c.id, e.id, false
        FROM cards c
        JOIN ecosystems e ON e.points_currency_id = c.secondary_points_currency_id
        WHERE c.secondary_points_currency_id IS NOT NULL
        ON CONFLICT (card_id, ecosystem_id) DO NOTHING
        """)
    )
    # 4) Drop old columns
    sync_conn.execute(
        text("""
        DO $$
        BEGIN
          ALTER TABLE cards DROP COLUMN IF EXISTS anchors_cashback_conversion;
          ALTER TABLE cards DROP COLUMN IF EXISTS secondary_points_currency_id;
        END $$;
        """)
    )


def _restore_cashback_and_additional_currencies(sync_conn):
    """Add cashback_currency_id back if it was dropped; backfill from first ecosystem_currency, leave rest as additional."""
    if sync_conn.dialect.name != "postgresql":
        return
    r = sync_conn.execute(
        text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'ecosystems' AND column_name = 'cashback_currency_id'
        """)
    )
    if r.scalar() is not None:
        return  # column already exists (e.g. fresh DB or never migrated)
    sync_conn.execute(
        text("ALTER TABLE ecosystems ADD COLUMN cashback_currency_id INTEGER REFERENCES currencies(id) ON DELETE SET NULL")
    )
    sync_conn.execute(
        text("""
        UPDATE ecosystems e SET cashback_currency_id = (
            SELECT ec.currency_id FROM ecosystem_currencies ec WHERE ec.ecosystem_id = e.id ORDER BY ec.id LIMIT 1
        ) WHERE EXISTS (SELECT 1 FROM ecosystem_currencies ec WHERE ec.ecosystem_id = e.id)
        """)
    )
    sync_conn.execute(
        text("""
        DELETE FROM ecosystem_currencies ec
        USING ecosystems e
        WHERE e.id = ec.ecosystem_id AND e.cashback_currency_id = ec.currency_id
        """)
    )


async def create_tables() -> None:
    """Create all tables if they do not exist (used on startup)."""
    async with engine.begin() as conn:
        from . import models  # noqa: F401 — ensure models are registered
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_issuer_columns_if_missing)
        await conn.run_sync(_currency_issuer_nullable)
        await conn.run_sync(_drop_currency_comparison_factor)
        await conn.run_sync(_migrate_boost_to_cashback_conversion)
        await conn.run_sync(_restore_cashback_and_additional_currencies)  # before _migrate_to_ecosystems so column exists
        await conn.run_sync(_migrate_to_ecosystems)
