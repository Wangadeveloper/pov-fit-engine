import pytest
import pytest_asyncio
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.core.database import Base, get_db
from app.models.user import User

# Use an in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession, expire_on_commit=False)

@pytest_asyncio.fixture(scope="function", autouse=True)
async def db_session():
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()
        
    # Drop tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        try:
            yield db_session
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_read_root(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "POV Fit Intelligence Platform API", "version": "1.0.0"}

@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_auth_register_and_login(client):
    # Test registration
    reg_payload = {
        "email": "testuser@example.com",
        "password": "strongpassword123"
    }
    response = await client.post("/api/v1/auth/register", json=reg_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["email"] == "testuser@example.com"
    
    # Test duplicate registration
    response = await client.post("/api/v1/auth/register", json=reg_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "EMAIL_ALREADY_EXISTS"

    # Test login JSON
    login_payload = {
        "email": "testuser@example.com",
        "password": "strongpassword123"
    }
    response = await client.post("/api/v1/auth/login-json", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "access_token" in data["data"]
    
    token = data["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test profile access
    response = await client.get("/api/v1/fit/profile", headers=headers)
    assert response.status_code == 200
    profile_data = response.json()
    assert profile_data["success"] is True
    assert profile_data["data"]["preferred_top_fit"] == "regular"

@pytest.mark.asyncio
async def test_onboarding(client):
    # Register and login
    reg_payload = {
        "email": "onboarding@example.com",
        "password": "password123"
    }
    await client.post("/api/v1/auth/register", json=reg_payload)
    
    login_res = await client.post("/api/v1/auth/login-json", json=reg_payload)
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Submit onboarding
    onboarding_payload = {
        "preferred_top_fit": "fitted",
        "preferred_bottom_fit": "slim",
        "preferred_jacket_fit": "fitted",
        "comfort_preferences": ["soft", "comfortable"],
        "height_cm": 180.0,
        "weight_kg": 75.0
    }
    response = await client.post("/api/v1/fit/onboarding", json=onboarding_payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["preferred_top_fit"] == "fitted"
    assert data["data"]["preferred_bottom_fit"] == "slim"
    assert data["data"]["height_cm"] == 180.0
    
    # Check confidence score endpoint
    response = await client.get("/api/v1/fit/confidence", headers=headers)
    assert response.status_code == 200
    conf_data = response.json()
    assert conf_data["success"] is True
    assert conf_data["data"]["signals"]["has_measurements"] is True
