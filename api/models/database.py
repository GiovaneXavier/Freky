from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from core.settings import settings


def _build_engine_url(url: str) -> str:
    """
    Normaliza a DATABASE_URL para o dialeto assíncrono correto.

    Formatos aceitos na variável de ambiente:
      - mssql://user:pass@host/db?driver=ODBC+Driver+18+for+SQL+Server
      - mssql+aioodbc://...   (já completo, retorna sem alteração)
      - postgresql://...      (legado — mantido para compatibilidade local/testes)
    """
    if url.startswith("mssql+aioodbc://"):
        return url
    if url.startswith("mssql://"):
        return url.replace("mssql://", "mssql+aioodbc://", 1)
    # fallback legado PostgreSQL (usado em testes locais / CI)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


engine = create_async_engine(
    _build_engine_url(settings.database_url),
    echo=settings.debug,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
