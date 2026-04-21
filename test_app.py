"""
Test suite for NutriSense AI application.
Run with: python -m pytest test_app.py -v
"""

import json
import pytest
from app import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    with app.test_client() as client:
        yield client


class TestRoutes:
    """Test all application routes return correct status codes."""

    def test_home_page(self, client):
        """Test home page loads successfully."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"NutriSense" in response.data

    def test_profile_page_get(self, client):
        """Test profile page loads on GET request."""
        response = client.get("/profile")
        assert response.status_code == 200
        assert b"Health Profile" in response.data

    def test_profile_page_post(self, client):
        """Test profile calculation with valid data."""
        response = client.post("/profile", data={
            "name": "Test User",
            "age": "25",
            "weight": "70",
            "height": "175",
            "goal": "maintain",
            "activity": "moderate",
        })
        assert response.status_code == 200
        assert b"BMI" in response.data

    def test_profile_bmi_calculation(self, client):
        """Test BMI calculation accuracy."""
        response = client.post("/profile", data={
            "name": "Test",
            "age": "25",
            "weight": "70",
            "height": "175",
            "goal": "maintain",
            "activity": "moderate",
        })
        assert response.status_code == 200
        # BMI = 70 / (1.75)^2 = 22.9
        assert b"22.9" in response.data

    def test_log_page_get(self, client):
        """Test food log page loads with food database."""
        response = client.get("/log")
        assert response.status_code == 200
        assert b"Food Logger" in response.data

    def test_log_food_post(self, client):
        """Test logging a food item."""
        response = client.post("/log", data={
            "food": "rice",
            "qty": "100",
        })
        assert response.status_code == 200
        assert b"Rice" in response.data or b"rice" in response.data

    def test_log_invalid_food(self, client):
        """Test logging an invalid food item."""
        response = client.post("/log", data={
            "food": "nonexistent_food",
            "qty": "100",
        })
        assert response.status_code == 200

    def test_suggest_page(self, client):
        """Test meal suggestions page loads."""
        response = client.get("/suggest")
        assert response.status_code == 200

    def test_summary_page(self, client):
        """Test dashboard/summary page loads."""
        response = client.get("/summary")
        assert response.status_code == 200
        assert b"Health Score" in response.data

    def test_clear_log(self, client):
        """Test clearing the food log."""
        response = client.get("/clear-log")
        assert response.status_code == 200

    def test_api_foods(self, client):
        """Test the foods API endpoint returns JSON."""
        response = client.get("/api/foods")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, dict)
        assert "rice" in data

    def test_update_water(self, client):
        """Test water intake update endpoint."""
        response = client.post(
            "/update-water",
            data=json.dumps({"count": 5}),
            content_type="application/json",
        )
        assert response.status_code == 200


class TestSecurity:
    """Test security measures."""

    def test_xss_prevention_in_food_name(self, client):
        """Test that script tags in food names are not rendered."""
        response = client.post("/log", data={
            "food": "<script>alert('xss')</script>",
            "qty": "100",
        })
        assert b"<script>alert" not in response.data

    def test_invalid_quantity_handled(self, client):
        """Test that invalid quantity values are handled gracefully."""
        response = client.post("/log", data={
            "food": "rice",
            "qty": "abc",
        })
        # Should not crash
        assert response.status_code in [200, 400]


class TestAccessibility:
    """Test basic accessibility features."""

    def test_html_lang_attribute(self, client):
        """Test that HTML has lang attribute for screen readers."""
        response = client.get("/")
        assert b'lang="en"' in response.data

    def test_viewport_meta(self, client):
        """Test that viewport meta tag exists for mobile."""
        response = client.get("/")
        assert b"viewport" in response.data

    def test_aria_labels_on_nav(self, client):
        """Test that navigation has aria labels."""
        response = client.get("/")
        assert b"aria-label" in response.data
