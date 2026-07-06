"""
Test Gallery Themes and Network Stats Features
- Gallery theme creation and update
- Network & Storage Monitor endpoint
- Dashboard stats endpoint
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAdminAuth:
    """Admin authentication tests"""
    
    def test_admin_login_success(self):
        """Test admin login with correct credentials"""
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["username"] == "admin"
        assert "display_name" in data
        print(f"PASS: Admin login successful, got token")
        return data["token"]


class TestDashboardStats:
    """Dashboard stats endpoint tests"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        return response.json()["token"]
    
    def test_dashboard_stats_returns_5_fields(self, auth_token):
        """GET /api/admin/dashboard-stats returns all 5 required fields"""
        response = requests.get(
            f"{BASE_URL}/api/admin/dashboard-stats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify all 5 required fields exist
        required_fields = ["active_galleries", "expiring_soon", "downloads_this_week", "pending_albums", "storage_used_bytes"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
            assert isinstance(data[field], int), f"Field {field} should be int, got {type(data[field])}"
        
        print(f"PASS: Dashboard stats has all 5 fields: {list(data.keys())}")
        print(f"  - active_galleries: {data['active_galleries']}")
        print(f"  - expiring_soon: {data['expiring_soon']}")
        print(f"  - downloads_this_week: {data['downloads_this_week']}")
        print(f"  - pending_albums: {data['pending_albums']}")
        print(f"  - storage_used_bytes: {data['storage_used_bytes']}")


class TestNetworkStats:
    """Network stats endpoint tests"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        return response.json()["token"]
    
    def test_network_stats_returns_all_sections(self, auth_token):
        """GET /api/admin/network-stats returns daily, weekly, video, downloads, current sections"""
        response = requests.get(
            f"{BASE_URL}/api/admin/network-stats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required sections exist
        required_sections = ["daily", "weekly", "video", "downloads", "current"]
        for section in required_sections:
            assert section in data, f"Missing section: {section}"
        
        # Verify daily section structure
        assert "sent_bytes" in data["daily"]
        assert "recv_bytes" in data["daily"]
        assert "total_bytes" in data["daily"]
        
        # Verify weekly section structure
        assert "sent_bytes" in data["weekly"]
        assert "recv_bytes" in data["weekly"]
        assert "total_bytes" in data["weekly"]
        
        # Verify video section structure
        assert "daily_bytes" in data["video"]
        assert "weekly_bytes" in data["video"]
        
        # Verify downloads section structure
        assert "daily_bytes" in data["downloads"]
        assert "weekly_bytes" in data["downloads"]
        
        # Verify current section structure
        assert "bytes_sent" in data["current"]
        assert "bytes_recv" in data["current"]
        assert "timestamp" in data["current"]
        
        print(f"PASS: Network stats has all 5 sections: {list(data.keys())}")
        print(f"  - daily total: {data['daily']['total_bytes']} bytes")
        print(f"  - weekly total: {data['weekly']['total_bytes']} bytes")
        print(f"  - video daily: {data['video']['daily_bytes']} bytes")
        print(f"  - downloads daily: {data['downloads']['daily_bytes']} bytes")


class TestGalleryThemes:
    """Gallery theme feature tests"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        return response.json()["token"]
    
    def test_create_gallery_with_default_theme(self, auth_token):
        """Creating gallery without theme uses classic_gold default"""
        response = requests.post(
            f"{BASE_URL}/api/admin/galleries",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"folder_name": "TEST Default Theme 07.06.26"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "theme" in data
        assert data["theme"] == "classic_gold", f"Expected classic_gold, got {data['theme']}"
        
        # Cleanup
        gallery_id = data["id"]
        requests.delete(
            f"{BASE_URL}/api/admin/galleries/{gallery_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        print(f"PASS: Gallery created with default theme 'classic_gold'")
    
    def test_create_gallery_with_custom_theme(self, auth_token):
        """Creating gallery with specific theme works"""
        themes_to_test = ["modern_minimal", "dark_elegance", "soft_romantic", "earthy_botanical"]
        
        for theme in themes_to_test:
            response = requests.post(
                f"{BASE_URL}/api/admin/galleries",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={"folder_name": f"TEST {theme} Gallery", "theme": theme}
            )
            assert response.status_code == 200
            data = response.json()
            
            assert data["theme"] == theme, f"Expected {theme}, got {data['theme']}"
            
            # Cleanup
            requests.delete(
                f"{BASE_URL}/api/admin/galleries/{data['id']}",
                headers={"Authorization": f"Bearer {auth_token}"}
            )
        
        print(f"PASS: Gallery creation works with all 4 custom themes: {themes_to_test}")
    
    def test_update_gallery_theme(self, auth_token):
        """Updating gallery theme via PUT works"""
        # Create gallery
        response = requests.post(
            f"{BASE_URL}/api/admin/galleries",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"folder_name": "TEST Theme Update 07.06.26", "theme": "classic_gold"}
        )
        assert response.status_code == 200
        gallery_id = response.json()["id"]
        
        # Update theme
        response = requests.put(
            f"{BASE_URL}/api/admin/galleries/{gallery_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"theme": "dark_elegance"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["theme"] == "dark_elegance", f"Expected dark_elegance, got {data['theme']}"
        
        # Verify via GET
        response = requests.get(
            f"{BASE_URL}/api/admin/galleries/{gallery_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["theme"] == "dark_elegance"
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/admin/galleries/{gallery_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        print(f"PASS: Gallery theme update works (classic_gold -> dark_elegance)")


class TestExistingFunctionality:
    """Regression tests for existing dashboard functionality"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        return response.json()["token"]
    
    def test_list_galleries(self, auth_token):
        """GET /api/admin/galleries returns list of galleries"""
        response = requests.get(
            f"{BASE_URL}/api/admin/galleries",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List galleries returns {len(data)} galleries")
    
    def test_live_visitors(self, auth_token):
        """GET /api/admin/live-visitors returns visitor data"""
        response = requests.get(
            f"{BASE_URL}/api/admin/live-visitors",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "visitors" in data
        print(f"PASS: Live visitors endpoint works, {len(data['visitors'])} visitors")
    
    def test_templates(self, auth_token):
        """GET /api/admin/templates returns templates"""
        response = requests.get(
            f"{BASE_URL}/api/admin/templates",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Templates endpoint works, {len(data)} templates")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
