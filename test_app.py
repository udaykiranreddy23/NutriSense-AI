"""
NutriSense AI — Basic Tests
"""
import json
import os
import sys
import pytest

# Set test DB path before importing app
os.environ["SECRET_KEY"] = "test-secret-key"

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import init_db, get_db, DB_PATH


@pytest.fixture
def client():
    """Create test client."""
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    # Use test DB
    with app.test_client() as client:
        with app.app_context():
            init_db()
        yield client

    # Cleanup test DB
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except OSError:
            pass


def test_home_page(client):
    """Home page should return 200."""
    rv = client.get("/")
    assert rv.status_code == 200
    assert b"NutriSense" in rv.data


def test_auth_page(client):
    """Auth page should render login/signup."""
    rv = client.get("/auth")
    assert rv.status_code == 200
    assert b"Sign In" in rv.data
    assert b"Create Account" in rv.data


def test_signup_flow(client):
    """Should be able to create account and get redirected."""
    rv = client.post("/signup", data={
        "name": "Test User",
        "email": "test@example.com",
        "password": "testpass123",
        "confirm_password": "testpass123"
    }, follow_redirects=True)
    assert rv.status_code == 200
    assert b"Welcome" in rv.data or b"Profile" in rv.data


def test_login_flow(client):
    """Should login with correct credentials."""
    # First signup
    client.post("/signup", data={
        "name": "Test User",
        "email": "test2@example.com",
        "password": "testpass123",
        "confirm_password": "testpass123"
    })
    # Logout
    client.get("/logout")
    # Login
    rv = client.post("/login", data={
        "email": "test2@example.com",
        "password": "testpass123"
    }, follow_redirects=True)
    assert rv.status_code == 200


def test_suggest_page(client):
    """Suggestions page should be accessible without login."""
    rv = client.get("/suggest")
    assert rv.status_code == 200


def test_api_foods(client):
    """Foods API should return JSON."""
    rv = client.get("/api/foods")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert "rice" in data
    assert "roti" in data


def test_protected_routes_redirect(client):
    """Protected routes should redirect to auth when not logged in."""
    routes = ["/profile", "/log", "/weight", "/summary"]
    for route in routes:
        rv = client.get(route)
        assert rv.status_code == 302, f"{route} should redirect"


def test_duplicate_signup(client):
    """Should not allow duplicate email signup."""
    data = {
        "name": "User One",
        "email": "dupe@example.com",
        "password": "pass123456",
        "confirm_password": "pass123456"
    }
    client.post("/signup", data=data)
    client.get("/logout")

    rv = client.post("/signup", data=data, follow_redirects=True)
    assert b"already exists" in rv.data


def test_wrong_password(client):
    """Should reject wrong password."""
    # Signup
    client.post("/signup", data={
        "name": "User",
        "email": "wrong@example.com",
        "password": "correct123",
        "confirm_password": "correct123"
    })
    client.get("/logout")

    # Login with wrong password
    rv = client.post("/login", data={
        "email": "wrong@example.com",
        "password": "wrongpassword"
    }, follow_redirects=True)
    assert b"Invalid" in rv.data
