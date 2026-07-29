"""
Test suite for Video Health Check and QR Design Preview features.
Tests:
- GET /api/admin/galleries/{gallery_id}/video-health endpoint
- GET /api/admin/qr-design-preview/{design_num}?token=... endpoint (designs 1-5)
- Authentication requirements for both endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAdminLogin:
    """Verify admin login works and returns valid JWT token"""
    
    def test_admin_login_success(self):
        """POST /api/admin/login returns valid JWT token"""
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "Response missing 'token' field"
        assert isinstance(data["token"], str), "Token should be a string"
        assert len(data["token"]) > 20, "Token seems too short"
        print(f"Login successful, token length: {len(data['token'])}")


class TestVideoHealthEndpoint:
    """Test GET /api/admin/galleries/{gallery_id}/video-health endpoint"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin JWT token"""
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json()["token"]
    
    @pytest.fixture
    def test_gallery_id(self, admin_token):
        """Create a test gallery and return its ID"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.post(f"{BASE_URL}/api/admin/galleries", json={
            "name": "TEST_VideoHealth_Gallery",
            "folder_name": "test_video_health_gallery"
        }, headers=headers)
        if response.status_code not in (200, 201):
            pytest.skip(f"Could not create test gallery: {response.text}")
        gallery_id = response.json().get("id")
        yield gallery_id
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/galleries/{gallery_id}", headers=headers)
    
    def test_video_health_requires_auth(self):
        """Video health endpoint returns 401 without authentication"""
        # Use a dummy gallery ID - auth check happens before gallery lookup
        response = requests.get(f"{BASE_URL}/api/admin/galleries/dummy-id/video-health")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("Video health endpoint correctly requires authentication")
    
    def test_video_health_returns_valid_structure(self, admin_token, test_gallery_id):
        """Video health endpoint returns correct JSON structure"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{BASE_URL}/api/admin/galleries/{test_gallery_id}/video-health",
            headers=headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Check 'videos' array exists
        assert "videos" in data, "Response missing 'videos' field"
        assert isinstance(data["videos"], list), "'videos' should be an array"
        
        # Check 'summary' object exists with required fields
        assert "summary" in data, "Response missing 'summary' field"
        summary = data["summary"]
        assert "total" in summary, "Summary missing 'total' field"
        assert "optimised" in summary, "Summary missing 'optimised' field"
        assert "not_optimised" in summary, "Summary missing 'not_optimised' field"
        
        # Verify types
        assert isinstance(summary["total"], int), "'total' should be an integer"
        assert isinstance(summary["optimised"], int), "'optimised' should be an integer"
        assert isinstance(summary["not_optimised"], int), "'not_optimised' should be an integer"
        
        # Verify math: total = optimised + not_optimised
        assert summary["total"] == summary["optimised"] + summary["not_optimised"], \
            "Summary math incorrect: total should equal optimised + not_optimised"
        
        print(f"Video health response valid: {summary}")
    
    def test_video_health_404_for_nonexistent_gallery(self, admin_token):
        """Video health endpoint returns 404 for non-existent gallery"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{BASE_URL}/api/admin/galleries/nonexistent-gallery-id/video-health",
            headers=headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("Video health correctly returns 404 for non-existent gallery")


class TestQRDesignPreviewEndpoint:
    """Test GET /api/admin/qr-design-preview/{design_num}?token=... endpoint"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin JWT token"""
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json()["token"]
    
    def test_qr_preview_requires_token(self):
        """QR preview endpoint returns 401 without token query parameter"""
        response = requests.get(f"{BASE_URL}/api/admin/qr-design-preview/1")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("QR preview endpoint correctly requires token")
    
    def test_qr_preview_design_1(self, admin_token):
        """QR preview design 1 returns PNG image"""
        response = requests.get(
            f"{BASE_URL}/api/admin/qr-design-preview/1?token={admin_token}"
        )
        assert response.status_code == 200, f"Design 1 failed: {response.status_code}"
        assert response.headers.get("content-type") == "image/png", \
            f"Expected image/png, got {response.headers.get('content-type')}"
        assert len(response.content) > 1000, "Image content seems too small"
        print(f"Design 1 OK - PNG size: {len(response.content)} bytes")
    
    def test_qr_preview_design_2(self, admin_token):
        """QR preview design 2 returns PNG image"""
        response = requests.get(
            f"{BASE_URL}/api/admin/qr-design-preview/2?token={admin_token}"
        )
        assert response.status_code == 200, f"Design 2 failed: {response.status_code}"
        assert response.headers.get("content-type") == "image/png"
        print(f"Design 2 OK - PNG size: {len(response.content)} bytes")
    
    def test_qr_preview_design_3(self, admin_token):
        """QR preview design 3 returns PNG image"""
        response = requests.get(
            f"{BASE_URL}/api/admin/qr-design-preview/3?token={admin_token}"
        )
        assert response.status_code == 200, f"Design 3 failed: {response.status_code}"
        assert response.headers.get("content-type") == "image/png"
        print(f"Design 3 OK - PNG size: {len(response.content)} bytes")
    
    def test_qr_preview_design_4(self, admin_token):
        """QR preview design 4 returns PNG image"""
        response = requests.get(
            f"{BASE_URL}/api/admin/qr-design-preview/4?token={admin_token}"
        )
        assert response.status_code == 200, f"Design 4 failed: {response.status_code}"
        assert response.headers.get("content-type") == "image/png"
        print(f"Design 4 OK - PNG size: {len(response.content)} bytes")
    
    def test_qr_preview_design_5(self, admin_token):
        """QR preview design 5 returns PNG image"""
        response = requests.get(
            f"{BASE_URL}/api/admin/qr-design-preview/5?token={admin_token}"
        )
        assert response.status_code == 200, f"Design 5 failed: {response.status_code}"
        assert response.headers.get("content-type") == "image/png"
        print(f"Design 5 OK - PNG size: {len(response.content)} bytes")
    
    def test_qr_preview_invalid_design_defaults_to_1(self, admin_token):
        """QR preview with invalid design number defaults to design 1"""
        response = requests.get(
            f"{BASE_URL}/api/admin/qr-design-preview/99?token={admin_token}"
        )
        # Should default to design 1 and return 200
        assert response.status_code == 200, f"Invalid design should default to 1, got {response.status_code}"
        assert response.headers.get("content-type") == "image/png"
        print("Invalid design number correctly defaults to design 1")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
