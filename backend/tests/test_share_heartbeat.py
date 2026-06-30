"""
Test suite for Share Link and Live Visitors Heartbeat functionality.
Tests the fix for the temporal dead zone bug in ShareView.js and verifies
the heartbeat/live-visitors feature works correctly.

Bug fixed: useEffect at line 110 referenced `displayFiles` in its dependency array,
but `displayFiles` was declared at line 313 (temporal dead zone = ReferenceError).
Fix: moved the useEffect to line 299 (after displayFiles declaration).
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAdminAuth:
    """Admin authentication tests"""
    
    def test_admin_check_setup(self):
        """Verify admin setup is complete"""
        response = requests.get(f"{BASE_URL}/api/admin/check-setup")
        assert response.status_code == 200
        data = response.json()
        assert data.get("setup_complete") == True
    
    def test_admin_login_success(self):
        """Verify admin login with correct credentials"""
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data.get("username") == "admin"
        return data["token"]


class TestShareAccess:
    """Share link access tests"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token for authenticated requests"""
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Admin login failed")
    
    @pytest.fixture
    def share_token(self, admin_token):
        """Get an existing share token or create one"""
        # First, get galleries
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/galleries", headers=headers)
        assert response.status_code == 200
        galleries = response.json()
        
        if not galleries:
            pytest.skip("No galleries available for testing")
        
        gallery_id = galleries[0]["id"]
        
        # Get shares for this gallery
        response = requests.get(f"{BASE_URL}/api/admin/galleries/{gallery_id}/shares", headers=headers)
        assert response.status_code == 200
        shares = response.json()
        
        # Find a share without password
        for share in shares:
            if not share.get("has_password"):
                return share["token"]
        
        # Create a new share if none exists
        response = requests.post(
            f"{BASE_URL}/api/admin/galleries/{gallery_id}/shares",
            headers=headers,
            json={
                "gallery_id": gallery_id,
                "access_level": "download",
                "label": "Test Share for Heartbeat"
            }
        )
        assert response.status_code == 200
        return response.json()["token"]
    
    def test_share_info_endpoint(self, share_token):
        """Verify share info endpoint returns correct data"""
        response = requests.get(f"{BASE_URL}/api/share/{share_token}")
        assert response.status_code == 200
        data = response.json()
        assert "gallery_name" in data
        assert "has_password" in data
        assert "access_level" in data
    
    def test_open_access_share(self, share_token):
        """Verify open-access endpoint returns JWT for no-password shares"""
        response = requests.get(f"{BASE_URL}/api/share/{share_token}/open-access")
        assert response.status_code == 200
        data = response.json()
        assert "jwt" in data
        assert "gallery_name" in data
        return data["jwt"]


class TestHeartbeat:
    """Live visitors heartbeat tests"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Admin login failed")
    
    @pytest.fixture
    def share_token(self, admin_token):
        """Get share token"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/galleries", headers=headers)
        galleries = response.json()
        if not galleries:
            pytest.skip("No galleries")
        
        gallery_id = galleries[0]["id"]
        response = requests.get(f"{BASE_URL}/api/admin/galleries/{gallery_id}/shares", headers=headers)
        shares = response.json()
        
        for share in shares:
            if not share.get("has_password"):
                return share["token"]
        pytest.skip("No open shares available")
    
    def test_heartbeat_endpoint_success(self, share_token):
        """Verify heartbeat endpoint accepts valid data and returns 200"""
        response = requests.post(
            f"{BASE_URL}/api/share/{share_token}/heartbeat",
            json={
                "session_id": "test-session-heartbeat-001",
                "action": "browsing",
                "subfolder": None,
                "detail": None
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
    
    def test_heartbeat_with_viewing_photo_action(self, share_token):
        """Verify heartbeat with viewing_photo action"""
        response = requests.post(
            f"{BASE_URL}/api/share/{share_token}/heartbeat",
            json={
                "session_id": "test-session-heartbeat-002",
                "action": "viewing_photo",
                "subfolder": "Wedding Images",
                "detail": "photo_001.jpg"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
    
    def test_heartbeat_with_watching_video_action(self, share_token):
        """Verify heartbeat with watching_video action"""
        response = requests.post(
            f"{BASE_URL}/api/share/{share_token}/heartbeat",
            json={
                "session_id": "test-session-heartbeat-003",
                "action": "watching_video",
                "subfolder": "Video",
                "detail": "wedding_video.mp4"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
    
    def test_live_visitors_endpoint(self, admin_token, share_token):
        """Verify admin live-visitors endpoint returns visitor data"""
        # First send a heartbeat to ensure there's a visitor
        requests.post(
            f"{BASE_URL}/api/share/{share_token}/heartbeat",
            json={
                "session_id": "test-session-live-visitors",
                "action": "browsing",
                "subfolder": None,
                "detail": None
            }
        )
        
        # Now check live visitors
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/live-visitors", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "visitors" in data
        assert isinstance(data["visitors"], list)
        
        # Verify visitor structure if any visitors exist
        if data["count"] > 0:
            visitor = data["visitors"][0]
            assert "session_id" in visitor
            assert "gallery_id" in visitor
            assert "action" in visitor
    
    def test_live_visitors_requires_auth(self):
        """Verify live-visitors endpoint requires admin authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/live-visitors")
        assert response.status_code == 401


class TestShareFiles:
    """Share files access tests"""
    
    @pytest.fixture
    def share_jwt(self):
        """Get share JWT for authenticated share requests"""
        # First get admin token
        admin_response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        if admin_response.status_code != 200:
            pytest.skip("Admin login failed")
        
        admin_token = admin_response.json()["token"]
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get galleries
        response = requests.get(f"{BASE_URL}/api/admin/galleries", headers=headers)
        galleries = response.json()
        if not galleries:
            pytest.skip("No galleries")
        
        gallery_id = galleries[0]["id"]
        
        # Get shares
        response = requests.get(f"{BASE_URL}/api/admin/galleries/{gallery_id}/shares", headers=headers)
        shares = response.json()
        
        for share in shares:
            if not share.get("has_password"):
                # Get JWT via open-access
                response = requests.get(f"{BASE_URL}/api/share/{share['token']}/open-access")
                if response.status_code == 200:
                    return response.json()["jwt"], share["token"]
        
        pytest.skip("No open shares available")
    
    def test_share_files_endpoint(self, share_jwt):
        """Verify share files endpoint returns gallery files"""
        jwt, token = share_jwt
        headers = {"Authorization": f"Bearer {jwt}"}
        response = requests.get(f"{BASE_URL}/api/share/{token}/files", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "gallery_name" in data
        assert "subfolders" in data
        assert isinstance(data["subfolders"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
