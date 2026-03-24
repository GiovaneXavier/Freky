import io
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from main import app
from models.database import Base, get_db
from core.rules import Decision, Detection


# Banco SQLite em memoria para testes
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine_test = create_async_engine(TEST_DATABASE_URL)
SessionTest = async_sessionmaker(engine_test, expire_on_commit=False)


async def override_get_db():
    async with SessionTest() as session:
        yield session


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def mock_detector():
    detector = MagicMock()
    detector.predict.return_value = (Decision.LIBERADO, [])
    return detector


@pytest.fixture
def client(mock_detector):
    app.dependency_overrides[get_db] = override_get_db
    app.state.detector = mock_detector
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_image_bytes() -> bytes:
    """Imagem JPEG minima valida para testes."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), color=(30, 30, 30)).save(buf, format="JPEG")
    return buf.getvalue()
