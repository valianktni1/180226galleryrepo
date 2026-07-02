"""
Test suite for Share Page CSS Fix - Bug fix verification
Tests that share endpoint and dashboard stats still work after CSS changes
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestShareEndpoint:
    """Test share endpoint still works"""
    
    def test_share_endpoint_returns_200(self):
        """GET /api/share/{token} returns 200"""
        response = requests.get(f"{BASE_URL}/api/share/n7TdghPWGxKR6Pov9B8Hxg")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Share endpoint returns 200")
    
    def test_share_endpoint_returns_gallery_data(self):
        """GET /api/share/{token} returns gallery name"""
        response = requests.get(f"{BASE_URL}/api/share/n7TdghPWGxKR6Pov9B8Hxg")
        data = response.json()
        assert "gallery_name" in data, "Missing gallery_name in response"
        assert "Test Couple" in data["gallery_name"], f"Expected 'Test Couple' in name, got {data['gallery_name']}"
        print(f"PASS: Share endpoint returns gallery_name: {data['gallery_name']}")


class TestDashboardStats:
    """Test dashboard stats endpoint still works"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        if response.status_code == 200:
            return response.json().get("token")  # Fixed: 'token' not 'access_token'
        pytest.skip(f"Auth failed: {response.status_code} - {response.text}")
    
    def test_dashboard_stats_returns_200(self, auth_token):
        """GET /api/admin/dashboard-stats returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/admin/dashboard-stats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Dashboard stats returns 200")
    
    def test_dashboard_stats_returns_5_fields(self, auth_token):
        """GET /api/admin/dashboard-stats returns 5 stat fields"""
        response = requests.get(
            f"{BASE_URL}/api/admin/dashboard-stats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        data = response.json()
        expected_fields = ["active_galleries", "expiring_soon", "downloads_this_week", "pending_albums", "storage_used_bytes"]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        print(f"PASS: Dashboard stats returns all 5 fields: {list(data.keys())}")


class TestAdminRegression:
    """Regression tests for admin endpoints"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        if response.status_code == 200:
            return response.json().get("token")  # Fixed: 'token' not 'access_token'
        pytest.skip(f"Auth failed: {response.status_code} - {response.text}")
    
    def test_galleries_endpoint(self, auth_token):
        """GET /api/admin/galleries returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/admin/galleries",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        print("PASS: Galleries endpoint returns 200")
    
    def test_live_visitors_endpoint(self, auth_token):
        """GET /api/admin/live-visitors returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/admin/live-visitors",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        print("PASS: Live visitors endpoint returns 200")
    
    def test_email_templates_endpoint(self, auth_token):
        """GET /api/admin/email-templates returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/admin/email-templates",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        print("PASS: Email templates endpoint returns 200")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
