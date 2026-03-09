import os

from dotenv import load_dotenv
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


async def create_tables() -> None:
    """Create all tables if they do not exist (used on startup)."""
    async with engine.begin() as conn:
        from . import models  # noqa: F401 — ensure models are registered
        await conn.run_sync(Base.metadata.create_all)
