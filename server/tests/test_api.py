"""
Tests for the Agent Monitor Server
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
from app.database import get_db
from app.models.base import Base


# Test database URL (SQLite for testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


# Create test engine
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_maker = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def override_get_db():
    async with test_session_maker() as session:
        yield session


# Override the dependency
app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="function")
async def setup_database():
    """Set up test database"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(setup_database):
    """Create test client"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_root(client):
    """Test root endpoint"""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Agent Monitor Server"
    assert data["status"] == "running"


@pytest.mark.asyncio
async def test_health_check(client):
    """Test health check endpoint"""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_user_registration(client):
    """Test user registration"""
    user_data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpassword123"
    }
    response = await client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert "api_token" in data


@pytest.mark.asyncio
async def test_user_login(client):
    """Test user login"""
    # First register a user
    user_data = {
        "username": "loginuser",
        "email": "login@example.com",
        "password": "testpassword123"
    }
    await client.post("/api/v1/auth/register", json=user_data)
    
    # Then login
    login_data = {
        "username": "loginuser",
        "password": "testpassword123"
    }
    response = await client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_create_client(client):
    """Test client creation"""
    # Register and login
    user_data = {
        "username": "clientuser",
        "email": "client@example.com",
        "password": "testpassword123"
    }
    await client.post("/api/v1/auth/register", json=user_data)
    
    login_response = await client.post("/api/v1/auth/login", json={
        "username": "clientuser",
        "password": "testpassword123"
    })
    token = login_response.json()["access_token"]
    
    # Create a client
    client_data = {
        "hostname": "test-host",
        "os": "linux",
        "platform": "ubuntu",
        "arch": "amd64"
    }
    response = await client.post(
        "/api/v1/clients",
        json=client_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["hostname"] == "test-host"
    assert data["status"] == "offline"
    assert "client_token" in data


@pytest.mark.asyncio
async def test_list_clients(client):
    """Test listing clients"""
    # Register, login, and create a client
    await client.post("/api/v1/auth/register", json={
        "username": "listuser",
        "email": "list@example.com",
        "password": "testpassword123"
    })
    
    login_response = await client.post("/api/v1/auth/login", json={
        "username": "listuser",
        "password": "testpassword123"
    })
    token = login_response.json()["access_token"]
    
    # Create clients
    await client.post(
        "/api/v1/clients",
        json={"hostname": "host1"},
        headers={"Authorization": f"Bearer {token}"}
    )
    await client.post(
        "/api/v1/clients",
        json={"hostname": "host2"},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # List clients
    response = await client.get(
        "/api/v1/clients",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["clients"]) == 2
