"""
Test suite for Dashboard Stats Redesign
Tests the new GET /api/admin/dashboard-stats endpoint and related functionality
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDashboardStats:
    """Tests for the new dashboard stats endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token for authenticated requests"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.token = token
        else:
            pytest.skip("Admin login failed - skipping authenticated tests")
    
    # ─── Dashboard Stats Endpoint Tests ───
    
    def test_dashboard_stats_returns_200(self):
        """GET /api/admin/dashboard-stats returns 200 with auth"""
        response = self.session.get(f"{BASE_URL}/api/admin/dashboard-stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: Dashboard stats endpoint returns 200")
    
    def test_dashboard_stats_returns_correct_structure(self):
        """GET /api/admin/dashboard-stats returns all 5 expected fields"""
        response = self.session.get(f"{BASE_URL}/api/admin/dashboard-stats")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check all 5 fields exist
        required_fields = ["active_galleries", "expiring_soon", "downloads_this_week", "pending_albums", "storage_used_bytes"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"PASS: Dashboard stats contains all 5 fields: {list(data.keys())}")
    
    def test_dashboard_stats_field_types(self):
        """GET /api/admin/dashboard-stats returns correct data types"""
        response = self.session.get(f"{BASE_URL}/api/admin/dashboard-stats")
        assert response.status_code == 200
        
        data = response.json()
        
        # All fields should be integers
        assert isinstance(data["active_galleries"], int), f"active_galleries should be int, got {type(data['active_galleries'])}"
        assert isinstance(data["expiring_soon"], int), f"expiring_soon should be int, got {type(data['expiring_soon'])}"
        assert isinstance(data["downloads_this_week"], int), f"downloads_this_week should be int, got {type(data['downloads_this_week'])}"
        assert isinstance(data["pending_albums"], int), f"pending_albums should be int, got {type(data['pending_albums'])}"
        assert isinstance(data["storage_used_bytes"], (int, float)), f"storage_used_bytes should be numeric, got {type(data['storage_used_bytes'])}"
        
        print(f"PASS: All fields have correct types - active_galleries={data['active_galleries']}, expiring_soon={data['expiring_soon']}, downloads_this_week={data['downloads_this_week']}, pending_albums={data['pending_albums']}, storage_used_bytes={data['storage_used_bytes']}")
    
    def test_dashboard_stats_values_non_negative(self):
        """GET /api/admin/dashboard-stats returns non-negative values"""
        response = self.session.get(f"{BASE_URL}/api/admin/dashboard-stats")
        assert response.status_code == 200
        
        data = response.json()
        
        assert data["active_galleries"] >= 0, "active_galleries should be non-negative"
        assert data["expiring_soon"] >= 0, "expiring_soon should be non-negative"
        assert data["downloads_this_week"] >= 0, "downloads_this_week should be non-negative"
        assert data["pending_albums"] >= 0, "pending_albums should be non-negative"
        assert data["storage_used_bytes"] >= 0, "storage_used_bytes should be non-negative"
        
        print("PASS: All dashboard stats values are non-negative")
    
    def test_dashboard_stats_requires_auth(self):
        """GET /api/admin/dashboard-stats returns 401 without token"""
        # Create a new session without auth
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        response = no_auth_session.get(f"{BASE_URL}/api/admin/dashboard-stats")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        
        print("PASS: Dashboard stats requires authentication (401 without token)")
    
    # ─── Existing Endpoints Regression Tests ───
    
    def test_galleries_endpoint_still_works(self):
        """GET /api/admin/galleries still works (regression)"""
        response = self.session.get(f"{BASE_URL}/api/admin/galleries")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Galleries should return a list"
        
        print(f"PASS: GET /api/admin/galleries returns {len(data)} galleries")
    
    def test_live_visitors_endpoint_still_works(self):
        """GET /api/admin/live-visitors still works (regression)"""
        response = self.session.get(f"{BASE_URL}/api/admin/live-visitors")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "visitors" in data, "Response should contain 'visitors' field"
        
        print(f"PASS: GET /api/admin/live-visitors returns {len(data.get('visitors', []))} visitors")
    
    def test_email_log_endpoint_still_works(self):
        """GET /api/admin/email-log still works (regression)"""
        response = self.session.get(f"{BASE_URL}/api/admin/email-log")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Email log returns {count: int, emails: list}
        assert "emails" in data, "Email log should contain 'emails' field"
        assert isinstance(data["emails"], list), "emails should be a list"
        
        print(f"PASS: GET /api/admin/email-log returns {len(data['emails'])} entries")
    
    # ─── Share Link Regression Test ───
    
    def test_share_link_still_works(self):
        """Share link /api/share/{token} still works (regression)"""
        share_token = "n7TdghPWGxKR6Pov9B8Hxg"
        
        # Use a clean session without admin auth
        share_session = requests.Session()
        share_session.headers.update({"Content-Type": "application/json"})
        
        response = share_session.get(f"{BASE_URL}/api/share/{share_token}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "gallery_name" in data or "label" in data, "Share info should contain gallery info"
        
        print(f"PASS: Share link works - gallery: {data.get('gallery_name', data.get('label', 'unknown'))}")
    
    # ─── Email Templates Tab Regression Test ───
    
    def test_email_templates_endpoint_still_works(self):
        """GET /api/admin/email-templates still works (regression)"""
        response = self.session.get(f"{BASE_URL}/api/admin/email-templates")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Email templates should return a list"
        
        print(f"PASS: GET /api/admin/email-templates returns {len(data)} templates")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
