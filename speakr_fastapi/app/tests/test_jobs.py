import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from ..main import app
from .. import models
from ..database import get_db
import os
from unittest.mock import patch, MagicMock

# Use an in-memory SQLite database for testing
DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(DATABASE_URL, echo=True)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)

async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="module")
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture(scope="module", autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_create_job(client: AsyncClient):
    # Create a dummy user and organization
    async with TestingSessionLocal() as session:
        organization = models.Organization(name="Test Corp")
        session.add(organization)
        await session.commit()
        await session.refresh(organization)

        user = models.User(email="test@test.com", provider="test", organization_id=organization.id, role="user")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    # Mock the auth service to return the dummy user
    with patch("speakr_fastapi.app.auth.auth_service.authenticate_user") as mock_auth:
        mock_auth.return_value = user

        # Create a dummy file
        with open("test.wav", "wb") as f:
            f.write(b"test audio data")

        # Upload the file
        with open("test.wav", "rb") as f:
            response = await client.post(
                "/api/v1/jobs/upload",
                files={"file": ("test.wav", f, "audio/wav")},
                data={"language": "en"}
            )

        # Clean up the dummy file
        os.remove("test.wav")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["original_filename"] == "test.wav"

    # Verify that the job was created in the database
    async with TestingSessionLocal() as session:
        job = await session.get(models.Job, data["id"])
        assert job is not None
        assert job.user_id == user_id
        assert job.original_filename == "test.wav"
