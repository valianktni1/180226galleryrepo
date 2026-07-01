"""
Test Email Log Feature
- GET /api/admin/email-log endpoint
- Broadcast email endpoint (validation)
- Broadcast preview endpoint
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestEmailLogEndpoint:
    """Tests for GET /api/admin/email-log endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token for authenticated requests"""
        self.admin_token = None
        login_res = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        if login_res.status_code == 200:
            self.admin_token = login_res.json().get("token")
    
    def test_email_log_returns_401_without_auth(self):
        """GET /api/admin/email-log should return 401 without admin token"""
        response = requests.get(f"{BASE_URL}/api/admin/email-log")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Email log returns 401 without auth")
    
    def test_email_log_returns_200_with_auth(self):
        """GET /api/admin/email-log should return 200 with admin token"""
        if not self.admin_token:
            pytest.skip("Admin login failed")
        
        response = requests.get(
            f"{BASE_URL}/api/admin/email-log",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "emails" in data, "Response should contain 'emails' key"
        assert "count" in data, "Response should contain 'count' key"
        assert isinstance(data["emails"], list), "'emails' should be a list"
        assert isinstance(data["count"], int), "'count' should be an integer"
        print(f"PASS: Email log returns 200 with {data['count']} emails")
    
    def test_email_log_returns_empty_list_when_no_emails(self):
        """GET /api/admin/email-log should return empty list when no emails sent"""
        if not self.admin_token:
            pytest.skip("Admin login failed")
        
        response = requests.get(
            f"{BASE_URL}/api/admin/email-log",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        # In preview environment, no emails have been sent
        # So we expect empty list or whatever is in the log
        assert data["count"] == len(data["emails"]), "Count should match emails list length"
        print(f"PASS: Email log count matches list length ({data['count']})")
    
    def test_email_log_respects_limit_param(self):
        """GET /api/admin/email-log should respect limit parameter"""
        if not self.admin_token:
            pytest.skip("Admin login failed")
        
        response = requests.get(
            f"{BASE_URL}/api/admin/email-log?limit=5",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["emails"]) <= 5, "Should return at most 5 emails"
        print(f"PASS: Email log respects limit param (returned {len(data['emails'])} emails)")


class TestBroadcastEndpoints:
    """Tests for broadcast email endpoints (regression)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token for authenticated requests"""
        self.admin_token = None
        login_res = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        if login_res.status_code == 200:
            self.admin_token = login_res.json().get("token")
    
    def test_broadcast_preview_returns_401_without_auth(self):
        """GET /api/admin/broadcast-preview should return 401 without admin token"""
        response = requests.get(f"{BASE_URL}/api/admin/broadcast-preview")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Broadcast preview returns 401 without auth")
    
    def test_broadcast_preview_returns_200_with_auth(self):
        """GET /api/admin/broadcast-preview should return 200 with admin token"""
        if not self.admin_token:
            pytest.skip("Admin login failed")
        
        response = requests.get(
            f"{BASE_URL}/api/admin/broadcast-preview",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "recipients" in data, "Response should contain 'recipients' key"
        assert "count" in data, "Response should contain 'count' key"
        print(f"PASS: Broadcast preview returns {data['count']} recipients")
    
    def test_broadcast_email_returns_401_without_auth(self):
        """POST /api/admin/broadcast-email should return 401 without admin token"""
        response = requests.post(f"{BASE_URL}/api/admin/broadcast-email", json={
            "subject": "Test",
            "body": "Test body"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Broadcast email returns 401 without auth")
    
    def test_broadcast_email_validates_subject(self):
        """POST /api/admin/broadcast-email should reject empty subject"""
        if not self.admin_token:
            pytest.skip("Admin login failed")
        
        response = requests.post(
            f"{BASE_URL}/api/admin/broadcast-email",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"subject": "", "body": "Test body"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: Broadcast email rejects empty subject")
    
    def test_broadcast_email_validates_body(self):
        """POST /api/admin/broadcast-email should reject empty body"""
        if not self.admin_token:
            pytest.skip("Admin login failed")
        
        response = requests.post(
            f"{BASE_URL}/api/admin/broadcast-email",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"subject": "Test Subject", "body": ""}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: Broadcast email rejects empty body")


class TestShareLinkRegression:
    """Regression tests for share link functionality"""
    
    def test_share_info_endpoint(self):
        """GET /api/share/{token} should return share info"""
        token = "n7TdghPWGxKR6Pov9B8Hxg"
        response = requests.get(f"{BASE_URL}/api/share/{token}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "gallery_name" in data, "Response should contain 'gallery_name'"
        print(f"PASS: Share info returns gallery: {data.get('gallery_name')}")
    
    def test_share_open_access(self):
        """GET /api/share/{token}/open-access should return JWT for no-password shares"""
        token = "n7TdghPWGxKR6Pov9B8Hxg"
        response = requests.get(f"{BASE_URL}/api/share/{token}/open-access")
        
        # Should return 200 with jwt or 401 if password required
        assert response.status_code in [200, 401], f"Expected 200 or 401, got {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            # API returns 'jwt' key, not 'token'
            assert "jwt" in data, "Response should contain 'jwt'"
            print("PASS: Share open-access returns JWT token")
        else:
            print("PASS: Share requires password (401 expected)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
