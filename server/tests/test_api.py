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
async def test_user_isolation(client):
    """Test that regular users can only see their own clients"""
    # Register two users
    await client.post("/api/v1/auth/register", json={
        "username": "user_a",
        "email": "usera@example.com",
        "password": "testpassword123"
    })
    await client.post("/api/v1/auth/register", json={
        "username": "user_b",
        "email": "userb@example.com",
        "password": "testpassword123"
    })

    # Login as user_a
    resp_a = await client.post("/api/v1/auth/login", json={
        "username": "user_a", "password": "testpassword123"
    })
    token_a = resp_a.json()["access_token"]

    # Login as user_b
    resp_b = await client.post("/api/v1/auth/login", json={
        "username": "user_b", "password": "testpassword123"
    })
    token_b = resp_b.json()["access_token"]

    # user_a creates a client
    await client.post(
        "/api/v1/clients",
        json={"hostname": "host-a"},
        headers={"Authorization": f"Bearer {token_a}"}
    )

    # user_b creates a client
    await client.post(
        "/api/v1/clients",
        json={"hostname": "host-b"},
        headers={"Authorization": f"Bearer {token_b}"}
    )

    # user_a should only see their own client
    resp = await client.get("/api/v1/clients", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["clients"][0]["hostname"] == "host-a"

    # user_b should only see their own client
    resp = await client.get("/api/v1/clients", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["clients"][0]["hostname"] == "host-b"


@pytest.mark.asyncio
async def test_admin_sees_all_clients(client):
    """Test that admin user can see all clients"""
    from app.auth import get_password_hash, generate_api_token
    from app.models.user import User
    from sqlalchemy import select

    # Create admin user directly in the test DB
    async with test_session_maker() as db:
        admin = User(
            username="admin_test",
            email="admin_test@example.com",
            password_hash=get_password_hash("adminpass"),
            api_token=generate_api_token(),
            is_admin=True,
        )
        db.add(admin)
        await db.commit()

    # Register a regular user
    await client.post("/api/v1/auth/register", json={
        "username": "regular_user",
        "email": "regular@example.com",
        "password": "testpassword123"
    })
    resp_reg = await client.post("/api/v1/auth/login", json={
        "username": "regular_user", "password": "testpassword123"
    })
    token_reg = resp_reg.json()["access_token"]

    # Regular user creates a client
    await client.post(
        "/api/v1/clients",
        json={"hostname": "regular-host"},
        headers={"Authorization": f"Bearer {token_reg}"}
    )

    # Login as admin
    resp_admin = await client.post("/api/v1/auth/login", json={
        "username": "admin_test", "password": "adminpass"
    })
    token_admin = resp_admin.json()["access_token"]

    # Admin should see all clients
    resp = await client.get("/api/v1/clients", headers={"Authorization": f"Bearer {token_admin}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    hostnames = [c["hostname"] for c in data["clients"]]
    assert "regular-host" in hostnames

    # Admin should have owner_username in each client entry
    for c in data["clients"]:
        assert "owner_username" in c


@pytest.mark.asyncio
async def test_admin_access_other_user_client(client):
    """Test that admin can access another user's client"""
    from app.auth import get_password_hash, generate_api_token
    from app.models.user import User

    # Create admin user directly
    async with test_session_maker() as db:
        admin = User(
            username="admin2",
            email="admin2@example.com",
            password_hash=get_password_hash("adminpass2"),
            api_token=generate_api_token(),
            is_admin=True,
        )
        db.add(admin)
        await db.commit()

    # Register a regular user and create a client
    await client.post("/api/v1/auth/register", json={
        "username": "owner_user",
        "email": "owner@example.com",
        "password": "testpassword123"
    })
    resp_owner = await client.post("/api/v1/auth/login", json={
        "username": "owner_user", "password": "testpassword123"
    })
    token_owner = resp_owner.json()["access_token"]

    resp_client = await client.post(
        "/api/v1/clients",
        json={"hostname": "owned-host"},
        headers={"Authorization": f"Bearer {token_owner}"}
    )
    client_id = resp_client.json()["id"]

    # Login as admin
    resp_admin = await client.post("/api/v1/auth/login", json={
        "username": "admin2", "password": "adminpass2"
    })
    token_admin = resp_admin.json()["access_token"]

    # Admin should be able to access the client
    resp = await client.get(
        f"/api/v1/clients/{client_id}",
        headers={"Authorization": f"Bearer {token_admin}"}
    )
    assert resp.status_code == 200
    assert resp.json()["hostname"] == "owned-host"


@pytest.mark.asyncio
async def test_regular_user_cannot_access_other_client(client):
    """Test that a regular user cannot access another user's client"""
    # Register two users
    await client.post("/api/v1/auth/register", json={
        "username": "user_x",
        "email": "userx@example.com",
        "password": "testpassword123"
    })
    await client.post("/api/v1/auth/register", json={
        "username": "user_y",
        "email": "usery@example.com",
        "password": "testpassword123"
    })

    resp_x = await client.post("/api/v1/auth/login", json={
        "username": "user_x", "password": "testpassword123"
    })
    token_x = resp_x.json()["access_token"]

    resp_y = await client.post("/api/v1/auth/login", json={
        "username": "user_y", "password": "testpassword123"
    })
    token_y = resp_y.json()["access_token"]

    # user_x creates a client
    resp_client = await client.post(
        "/api/v1/clients",
        json={"hostname": "host-x"},
        headers={"Authorization": f"Bearer {token_x}"}
    )
    client_id = resp_client.json()["id"]

    # user_y should NOT be able to access user_x's client
    resp = await client.get(
        f"/api/v1/clients/{client_id}",
        headers={"Authorization": f"Bearer {token_y}"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_is_admin_field_in_user_response(client):
    """Test that is_admin field is present in user response"""
    await client.post("/api/v1/auth/register", json={
        "username": "check_admin",
        "email": "checkadmin@example.com",
        "password": "testpassword123"
    })
    resp = await client.post("/api/v1/auth/login", json={
        "username": "check_admin", "password": "testpassword123"
    })
    token = resp.json()["access_token"]

    resp_me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp_me.status_code == 200
    data = resp_me.json()
    assert "is_admin" in data
    assert data["is_admin"] is False

