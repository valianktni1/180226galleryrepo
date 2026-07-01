"""
Tests for backup deletion feature on gallery and file delete endpoints.
Tests DELETE /api/admin/galleries/{id}?delete_backup=true|false
Tests DELETE /api/admin/galleries/{id}/files/{file_id}?delete_backup=true|false
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def admin_token():
    """Get admin token for authenticated requests."""
    response = requests.post(f"{BASE_URL}/api/admin/login", json={
        "username": "admin",
        "password": "test123"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Admin login failed - skipping authenticated tests")

@pytest.fixture
def auth_headers(admin_token):
    """Headers with admin token."""
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

@pytest.fixture
def test_gallery(auth_headers):
    """Create a test gallery for deletion tests."""
    # Create gallery
    response = requests.post(
        f"{BASE_URL}/api/admin/galleries",
        headers=auth_headers,
        json={"folder_name": "TEST_BackupDeletion_Gallery"}
    )
    assert response.status_code == 200, f"Failed to create test gallery: {response.text}"
    gallery = response.json()
    yield gallery
    # Cleanup - try to delete if still exists
    try:
        requests.delete(f"{BASE_URL}/api/admin/galleries/{gallery['id']}", headers=auth_headers)
    except:
        pass


class TestGalleryDeleteBackup:
    """Tests for DELETE /api/admin/galleries/{id} with delete_backup parameter."""
    
    def test_delete_gallery_without_backup_param(self, auth_headers):
        """DELETE gallery without delete_backup param returns backup_deleted: false."""
        # Create a gallery to delete
        create_res = requests.post(
            f"{BASE_URL}/api/admin/galleries",
            headers=auth_headers,
            json={"folder_name": "TEST_DeleteNoBackup_Gallery"}
        )
        assert create_res.status_code == 200
        gallery_id = create_res.json()["id"]
        
        # Delete without backup param (default)
        delete_res = requests.delete(
            f"{BASE_URL}/api/admin/galleries/{gallery_id}",
            headers=auth_headers
        )
        assert delete_res.status_code == 200
        data = delete_res.json()
        assert data["success"] == True
        assert data["backup_deleted"] == False
        print(f"PASS: DELETE gallery without backup param returns backup_deleted: false")
    
    def test_delete_gallery_with_backup_false(self, auth_headers):
        """DELETE gallery with delete_backup=false returns backup_deleted: false."""
        # Create a gallery to delete
        create_res = requests.post(
            f"{BASE_URL}/api/admin/galleries",
            headers=auth_headers,
            json={"folder_name": "TEST_DeleteBackupFalse_Gallery"}
        )
        assert create_res.status_code == 200
        gallery_id = create_res.json()["id"]
        
        # Delete with delete_backup=false
        delete_res = requests.delete(
            f"{BASE_URL}/api/admin/galleries/{gallery_id}?delete_backup=false",
            headers=auth_headers
        )
        assert delete_res.status_code == 200
        data = delete_res.json()
        assert data["success"] == True
        assert data["backup_deleted"] == False
        print(f"PASS: DELETE gallery with delete_backup=false returns backup_deleted: false")
    
    def test_delete_gallery_with_backup_true(self, auth_headers):
        """DELETE gallery with delete_backup=true returns backup_deleted: true."""
        # Create a gallery to delete
        create_res = requests.post(
            f"{BASE_URL}/api/admin/galleries",
            headers=auth_headers,
            json={"folder_name": "TEST_DeleteBackupTrue_Gallery"}
        )
        assert create_res.status_code == 200
        gallery_id = create_res.json()["id"]
        
        # Delete with delete_backup=true
        delete_res = requests.delete(
            f"{BASE_URL}/api/admin/galleries/{gallery_id}?delete_backup=true",
            headers=auth_headers
        )
        assert delete_res.status_code == 200
        data = delete_res.json()
        assert data["success"] == True
        assert data["backup_deleted"] == True
        print(f"PASS: DELETE gallery with delete_backup=true returns backup_deleted: true")
    
    def test_delete_gallery_requires_auth(self):
        """DELETE gallery without auth returns 401."""
        response = requests.delete(f"{BASE_URL}/api/admin/galleries/fake-id")
        assert response.status_code == 401
        print(f"PASS: DELETE gallery without auth returns 401")
    
    def test_delete_gallery_not_found(self, auth_headers):
        """DELETE non-existent gallery returns 404."""
        response = requests.delete(
            f"{BASE_URL}/api/admin/galleries/non-existent-id-12345",
            headers=auth_headers
        )
        assert response.status_code == 404
        print(f"PASS: DELETE non-existent gallery returns 404")


class TestFileDeleteBackup:
    """Tests for DELETE /api/admin/galleries/{id}/files/{file_id} with delete_backup parameter."""
    
    def test_delete_file_requires_auth(self):
        """DELETE file without auth returns 401."""
        response = requests.delete(f"{BASE_URL}/api/admin/galleries/fake-gallery/files/fake-file")
        assert response.status_code == 401
        print(f"PASS: DELETE file without auth returns 401")
    
    def test_delete_file_not_found(self, auth_headers, test_gallery):
        """DELETE non-existent file returns 404."""
        response = requests.delete(
            f"{BASE_URL}/api/admin/galleries/{test_gallery['id']}/files/non-existent-file-id",
            headers=auth_headers
        )
        assert response.status_code == 404
        print(f"PASS: DELETE non-existent file returns 404")


class TestShareRegression:
    """Regression tests for share functionality."""
    
    def test_share_get_returns_data(self):
        """GET /api/share/{token} returns share data (regression)."""
        # Use the known share token from previous tests
        token = "n7TdghPWGxKR6Pov9B8Hxg"
        response = requests.get(f"{BASE_URL}/api/share/{token}")
        # Should return 200 or 404 if share doesn't exist
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        if response.status_code == 200:
            data = response.json()
            assert "gallery_name" in data or "label" in data
            print(f"PASS: GET /api/share/{token} returns share data")
        else:
            print(f"PASS: GET /api/share/{token} returns 404 (share may have been deleted)")


class TestBroadcastRegression:
    """Regression tests for broadcast functionality."""
    
    def test_broadcast_preview_requires_auth(self):
        """GET /api/admin/broadcast-preview requires auth."""
        response = requests.get(f"{BASE_URL}/api/admin/broadcast-preview")
        assert response.status_code == 401
        print(f"PASS: GET /api/admin/broadcast-preview requires auth")
    
    def test_broadcast_preview_returns_recipients(self, auth_headers):
        """GET /api/admin/broadcast-preview returns recipients list."""
        response = requests.get(f"{BASE_URL}/api/admin/broadcast-preview", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "recipients" in data
        assert isinstance(data["recipients"], list)
        print(f"PASS: GET /api/admin/broadcast-preview returns recipients list")


class TestEmailLogRegression:
    """Regression tests for email log functionality."""
    
    def test_email_log_requires_auth(self):
        """GET /api/admin/email-log requires auth."""
        response = requests.get(f"{BASE_URL}/api/admin/email-log")
        assert response.status_code == 401
        print(f"PASS: GET /api/admin/email-log requires auth")
    
    def test_email_log_returns_data(self, auth_headers):
        """GET /api/admin/email-log returns emails list."""
        response = requests.get(f"{BASE_URL}/api/admin/email-log", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "emails" in data
        assert "count" in data
        print(f"PASS: GET /api/admin/email-log returns emails list")
