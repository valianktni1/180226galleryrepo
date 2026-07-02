"""
Test for responsive CSS fix on share page instruction cards
Bug: 3 instruction cards were showing in 3-column grid on mobile, making text unreadable
Fix: Changed grid-cols-3 to grid-cols-1 sm:grid-cols-3 so they stack vertically on mobile
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestShareEndpoint:
    """Test share endpoint still works after CSS fix"""
    
    def test_share_endpoint_returns_200(self):
        """Share endpoint should return 200 for valid token"""
        response = requests.get(f"{BASE_URL}/api/share/n7TdghPWGxKR6Pov9B8Hxg")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Share endpoint returns 200")
    
    def test_share_endpoint_returns_gallery_data(self):
        """Share endpoint should return gallery name and data"""
        response = requests.get(f"{BASE_URL}/api/share/n7TdghPWGxKR6Pov9B8Hxg")
        assert response.status_code == 200
        data = response.json()
        
        assert "gallery_name" in data, "Missing gallery_name in response"
        assert data["gallery_name"] == "Test Couple 01.06.25", f"Unexpected gallery name: {data['gallery_name']}"
        print(f"PASS: Gallery name is '{data['gallery_name']}'")
    
    def test_share_endpoint_returns_access_level(self):
        """Share endpoint should return access_level"""
        response = requests.get(f"{BASE_URL}/api/share/n7TdghPWGxKR6Pov9B8Hxg")
        assert response.status_code == 200
        data = response.json()
        
        assert "access_level" in data, "Missing access_level in response"
        print(f"PASS: Access level is '{data['access_level']}'")


class TestDashboardRegression:
    """Regression tests for admin dashboard"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "test123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_dashboard_stats_endpoint(self, auth_token):
        """Dashboard stats endpoint should work"""
        response = requests.get(
            f"{BASE_URL}/api/admin/dashboard-stats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        expected_fields = ["active_galleries", "expiring_soon", "downloads_this_week", "pending_albums", "storage_used_gb"]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"PASS: Dashboard stats has all 5 fields")
    
    def test_galleries_endpoint(self, auth_token):
        """Galleries endpoint should work"""
        response = requests.get(
            f"{BASE_URL}/api/admin/galleries",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Galleries endpoint returns 200")
    
    def test_live_visitors_endpoint(self, auth_token):
        """Live visitors endpoint should work"""
        response = requests.get(
            f"{BASE_URL}/api/admin/live-visitors",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Live visitors endpoint returns 200")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
