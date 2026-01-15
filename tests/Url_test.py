import os
# Set fake environment variables BEFORE importing app
# This prevents Settings validation error
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("HASHIDS_SALT", "test-salt-for-testing")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timezone, timedelta

from models.url import Base
from database import get_db
from main import app


# ============ TEST DATABASE SETUP ============
# This creates a fake SQLite database in memory (RAM)
# It's completely separate from your production Postgres

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},  # Needed for SQLite
    poolclass=StaticPool,  # Keeps the same connection for all tests
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """
    This replaces the real database with our test database.
    Every test gets a fresh database session.
    """
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Tell FastAPI to use our test database instead of production
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    """
    This runs before EACH test:
    1. Creates all tables
    2. Runs the test
    3. Drops all tables (clean slate for next test)
    """
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# Create test client
client = TestClient(app)


# ============ TESTS FOR POST /api/urls/shorten ============

class TestShortenEndpoint:
    """Tests for creating shortened URLs"""

    def test_shorten_url_basic(self):
        """Test creating a simple shortened URL"""
        response = client.post(
            "/api/urls/shorten",
            json={"long_url": "https://www.google.com"}
        )

        assert response.status_code == 201
        data = response.json()
        assert "short_code" in data
        assert "short_url" in data
        assert data["long_url"] == "https://www.google.com/"

    def test_shorten_url_with_custom_alias(self):
        """Test creating URL with custom alias"""
        response = client.post(
            "/api/urls/shorten",
            json={
                "long_url": "https://www.github.com",
                "custom_alias": "my-github"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert "my-github" in data["short_url"]

    def test_shorten_url_duplicate_alias_fails(self):
        """Test that duplicate custom alias returns error"""
        # Create first URL
        client.post(
            "/api/urls/shorten",
            json={"long_url": "https://www.google.com", "custom_alias": "test123"}
        )

        # Try to create second URL with same alias
        response = client.post(
            "/api/urls/shorten",
            json={"long_url": "https://www.github.com", "custom_alias": "test123"}
        )

        assert response.status_code == 400
        assert "already taken" in response.json()["detail"]

    def test_shorten_url_with_all_options(self):
        """Test creating URL with all optional fields"""
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

        response = client.post(
            "/api/urls/shorten",
            json={
                "long_url": "https://www.example.com",
                "custom_alias": "full-test",
                "title": "Example Site",
                "description": "A test URL",
                "expires_at": future_date,
                "max_clicks": 100,
                "password": "secret123"
            }
        )

        assert response.status_code == 201

    def test_shorten_url_invalid_url_fails(self):
        """Test that invalid URL returns validation error"""
        response = client.post(
            "/api/urls/shorten",
            json={"long_url": "not-a-valid-url"}
        )

        assert response.status_code == 422  # Validation error

    def test_shorten_url_invalid_alias_fails(self):
        """Test that invalid custom alias format returns error"""
        response = client.post(
            "/api/urls/shorten",
            json={
                "long_url": "https://www.google.com",
                "custom_alias": "has spaces!"  # Invalid characters
            }
        )

        assert response.status_code == 422


# ============ TESTS FOR GET ENDPOINTS ============

class TestGetEndpoints:
    """Tests for retrieving URL information"""

    def test_get_url_info(self):
        """Test getting URL info by code"""
        # First create a URL
        create_response = client.post(
            "/api/urls/shorten",
            json={"long_url": "https://www.google.com"}
        )
        short_code = create_response.json()["short_code"]

        # Then get its info
        response = client.get(f"/api/urls/{short_code}")

        assert response.status_code == 200
        data = response.json()
        assert data["short_code"] == short_code
        assert data["click_count"] == 0

    def test_get_url_info_not_found(self):
        """Test getting non-existent URL returns 404"""
        response = client.get("/api/urls/nonexistent123")

        assert response.status_code == 404

    def test_get_url_stats(self):
        """Test getting URL statistics"""
        # Create a URL
        create_response = client.post(
            "/api/urls/shorten",
            json={"long_url": "https://www.google.com"}
        )
        short_code = create_response.json()["short_code"]

        # Get stats
        response = client.get(f"/api/urls/{short_code}/stats")

        assert response.status_code == 200
        data = response.json()
        assert "click_count" in data
        assert "is_accessible" in data
        assert data["is_expired"] is False

    def test_list_urls(self):
        """Test listing all URLs"""
        # Create a few URLs
        client.post("/api/urls/shorten", json={"long_url": "https://www.google.com"})
        client.post("/api/urls/shorten", json={"long_url": "https://www.github.com"})

        # List them
        response = client.get("/api/urls/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_urls_pagination(self):
        """Test pagination works"""
        # Create 5 URLs
        for i in range(5):
            client.post("/api/urls/shorten", json={"long_url": f"https://www.example{i}.com"})

        # Get only 2
        response = client.get("/api/urls/?skip=0&limit=2")

        assert response.status_code == 200
        assert len(response.json()) == 2


# ============ TESTS FOR UPDATE/DELETE ============

class TestUpdateDelete:
    """Tests for updating and deleting URLs"""

    def test_update_url(self):
        """Test updating URL properties"""
        # Create URL
        create_response = client.post(
            "/api/urls/shorten",
            json={"long_url": "https://www.google.com"}
        )
        url_id = client.get(
            f"/api/urls/{create_response.json()['short_code']}"
        ).json()["id"]

        # Update it
        response = client.patch(
            f"/api/urls/{url_id}",
            json={"title": "New Title", "description": "New description"}
        )

        assert response.status_code == 200
        assert response.json()["title"] == "New Title"

    def test_update_url_not_found(self):
        """Test updating non-existent URL"""
        response = client.patch(
            "/api/urls/99999",
            json={"title": "New Title"}
        )

        assert response.status_code == 404

    def test_soft_delete_url(self):
        """Test soft deleting a URL (default)"""
        # Create URL
        create_response = client.post(
            "/api/urls/shorten",
            json={"long_url": "https://www.google.com"}
        )
        short_code = create_response.json()["short_code"]
        url_id = client.get(f"/api/urls/{short_code}").json()["id"]

        # Soft delete
        response = client.delete(f"/api/urls/{url_id}")
        assert response.status_code == 204

        # URL still exists but is inactive
        info = client.get(f"/api/urls/{short_code}")
        assert info.status_code == 200
        assert info.json()["is_active"] is False

    def test_hard_delete_url(self):
        """Test permanently deleting a URL"""
        # Create URL
        create_response = client.post(
            "/api/urls/shorten",
            json={"long_url": "https://www.google.com"}
        )
        short_code = create_response.json()["short_code"]
        url_id = client.get(f"/api/urls/{short_code}").json()["id"]

        # Hard delete
        response = client.delete(f"/api/urls/{url_id}?hard_delete=true")
        assert response.status_code == 204

        # URL is gone
        info = client.get(f"/api/urls/{short_code}")
        assert info.status_code == 404


# ============ TESTS FOR REDIRECT ============

class TestRedirect:
    """Tests for the redirect endpoint"""

    def test_redirect_works(self):
        """Test basic redirect"""
        # Create URL
        create_response = client.post(
            "/api/urls/shorten",
            json={"long_url": "https://www.google.com"}
        )
        short_code = create_response.json()["short_code"]

        # Follow redirect (allow_redirects=False to check the redirect response)
        response = client.get(f"/{short_code}", follow_redirects=False)

        assert response.status_code == 307
        assert "google.com" in response.headers["location"]

    def test_redirect_increments_click_count(self):
        """Test that redirect increments click count"""
        # Create URL
        create_response = client.post(
            "/api/urls/shorten",
            json={"long_url": "https://www.google.com"}
        )
        short_code = create_response.json()["short_code"]

        # Click it twice
        client.get(f"/{short_code}", follow_redirects=False)
        client.get(f"/{short_code}", follow_redirects=False)

        # Check count
        stats = client.get(f"/api/urls/{short_code}/stats").json()
        assert stats["click_count"] == 2

    def test_redirect_not_found(self):
        """Test redirect for non-existent code"""
        response = client.get("/nonexistent123", follow_redirects=False)
        assert response.status_code == 404

    def test_redirect_inactive_url_fails(self):
        """Test that inactive URLs return 410 Gone"""
        # Create and deactivate URL
        create_response = client.post(
            "/api/urls/shorten",
            json={"long_url": "https://www.google.com"}
        )
        short_code = create_response.json()["short_code"]
        url_id = client.get(f"/api/urls/{short_code}").json()["id"]

        # Deactivate
        client.patch(f"/api/urls/{url_id}", json={"is_active": False})

        # Try to redirect
        response = client.get(f"/{short_code}", follow_redirects=False)
        assert response.status_code == 410

    def test_redirect_with_custom_alias(self):
        """Test redirect works with custom alias"""
        create_response = client.post(
            "/api/urls/shorten",
            json={"long_url": "https://www.github.com", "custom_alias": "github"}  # min 3 chars
        )
        assert create_response.status_code == 201  # Verify URL was created

        response = client.get("/github", follow_redirects=False)
        assert response.status_code == 307
        assert "github.com" in response.headers["location"]

    def test_redirect_password_protected_without_password(self):
        """Test password protected URL requires password"""
        client.post(
            "/api/urls/shorten",
            json={
                "long_url": "https://www.secret.com",
                "custom_alias": "secret",
                "password": "mypassword"
            }
        )

        response = client.get("/secret", follow_redirects=False)
        assert response.status_code == 401

    def test_redirect_password_protected_with_correct_password(self):
        """Test password protected URL works with correct password"""
        client.post(
            "/api/urls/shorten",
            json={
                "long_url": "https://www.secret.com",
                "custom_alias": "secret2",
                "password": "mypassword"
            }
        )

        response = client.get("/secret2?password=mypassword", follow_redirects=False)
        assert response.status_code == 307

    def test_redirect_password_protected_with_wrong_password(self):
        """Test password protected URL rejects wrong password"""
        client.post(
            "/api/urls/shorten",
            json={
                "long_url": "https://www.secret.com",
                "custom_alias": "secret3",
                "password": "mypassword"
            }
        )

        response = client.get("/secret3?password=wrongpassword", follow_redirects=False)
        assert response.status_code == 401


# ============ TESTS FOR EDGE CASES ============

class TestEdgeCases:
    """Tests for edge cases and special scenarios"""

    def test_max_clicks_limit(self):
        """Test URL becomes inaccessible after max clicks"""
        # Create URL with max 2 clicks
        create_response = client.post(
            "/api/urls/shorten",
            json={"long_url": "https://www.google.com", "max_clicks": 2}
        )
        short_code = create_response.json()["short_code"]

        # Click twice (should work)
        client.get(f"/{short_code}", follow_redirects=False)
        client.get(f"/{short_code}", follow_redirects=False)

        # Third click should fail
        response = client.get(f"/{short_code}", follow_redirects=False)
        assert response.status_code == 410
        assert "maximum click limit" in response.json()["detail"]

    def test_health_check(self):
        """Test health endpoint still works"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
