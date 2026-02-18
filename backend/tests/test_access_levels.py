"""
Test suite for granular share access levels feature.
Tests 4 access levels: view, download, upload, full
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test share tokens (created via API)
SHARE_TOKENS = {
    "view": "KdOJNvdV2WBa04qFviUaHg",
    "download": "0Yxy_MfAzwJ8qRqz08tOWw",
    "upload": "QO7Iir0tEfhDXDX2iKXY2w",
    "full": "XZkN1c0kGeJyjJjZo6u29g"
}

GALLERY_ID = "b4e09e25-dd5e-410a-bafd-8fc631064d40"


class TestShareInfo:
    """Test that share info returns correct access_level and allow_uploads flags"""
    
    def test_view_only_share_info(self):
        """View-only share should have access_level=view, allow_uploads=false"""
        response = requests.get(f"{BASE_URL}/api/share/{SHARE_TOKENS['view']}")
        assert response.status_code == 200
        data = response.json()
        assert data["access_level"] == "view"
        assert data["allow_uploads"] == False
        print(f"✓ View-only share info correct: access_level={data['access_level']}, allow_uploads={data['allow_uploads']}")
    
    def test_download_share_info(self):
        """Download share should have access_level=download, allow_uploads=false"""
        response = requests.get(f"{BASE_URL}/api/share/{SHARE_TOKENS['download']}")
        assert response.status_code == 200
        data = response.json()
        assert data["access_level"] == "download"
        assert data["allow_uploads"] == False
        print(f"✓ Download share info correct: access_level={data['access_level']}, allow_uploads={data['allow_uploads']}")
    
    def test_upload_share_info(self):
        """Upload share should have access_level=upload, allow_uploads=true"""
        response = requests.get(f"{BASE_URL}/api/share/{SHARE_TOKENS['upload']}")
        assert response.status_code == 200
        data = response.json()
        assert data["access_level"] == "upload"
        assert data["allow_uploads"] == True
        print(f"✓ Upload share info correct: access_level={data['access_level']}, allow_uploads={data['allow_uploads']}")
    
    def test_full_access_share_info(self):
        """Full access share should have access_level=full, allow_uploads=true"""
        response = requests.get(f"{BASE_URL}/api/share/{SHARE_TOKENS['full']}")
        assert response.status_code == 200
        data = response.json()
        assert data["access_level"] == "full"
        assert data["allow_uploads"] == True
        print(f"✓ Full access share info correct: access_level={data['access_level']}, allow_uploads={data['allow_uploads']}")


class TestJWTPermissions:
    """Test that JWT tokens contain correct permission flags"""
    
    def get_jwt_for_share(self, token):
        """Get JWT for a share via open-access endpoint"""
        response = requests.get(f"{BASE_URL}/api/share/{token}/open-access")
        assert response.status_code == 200
        return response.json()["jwt"]
    
    def get_files_with_permissions(self, share_token, jwt):
        """Get files endpoint which returns permission flags"""
        response = requests.get(
            f"{BASE_URL}/api/share/{share_token}/files",
            headers={"Authorization": f"Bearer {jwt}"}
        )
        assert response.status_code == 200
        return response.json()
    
    def test_view_only_jwt_permissions(self):
        """View-only JWT should have allow_downloads=false, allow_uploads=false, allow_delete=false"""
        jwt = self.get_jwt_for_share(SHARE_TOKENS["view"])
        data = self.get_files_with_permissions(SHARE_TOKENS["view"], jwt)
        
        assert data["access_level"] == "view"
        assert data["allow_downloads"] == False
        assert data["allow_uploads"] == False
        assert data["allow_delete"] == False
        print(f"✓ View-only JWT permissions: downloads={data['allow_downloads']}, uploads={data['allow_uploads']}, delete={data['allow_delete']}")
    
    def test_download_jwt_permissions(self):
        """Download JWT should have allow_downloads=true, allow_uploads=false, allow_delete=false"""
        jwt = self.get_jwt_for_share(SHARE_TOKENS["download"])
        data = self.get_files_with_permissions(SHARE_TOKENS["download"], jwt)
        
        assert data["access_level"] == "download"
        assert data["allow_downloads"] == True
        assert data["allow_uploads"] == False
        assert data["allow_delete"] == False
        print(f"✓ Download JWT permissions: downloads={data['allow_downloads']}, uploads={data['allow_uploads']}, delete={data['allow_delete']}")
    
    def test_upload_jwt_permissions(self):
        """Upload JWT should have allow_downloads=true, allow_uploads=true, allow_delete=false"""
        jwt = self.get_jwt_for_share(SHARE_TOKENS["upload"])
        data = self.get_files_with_permissions(SHARE_TOKENS["upload"], jwt)
        
        assert data["access_level"] == "upload"
        assert data["allow_downloads"] == True
        assert data["allow_uploads"] == True
        assert data["allow_delete"] == False
        print(f"✓ Upload JWT permissions: downloads={data['allow_downloads']}, uploads={data['allow_uploads']}, delete={data['allow_delete']}")
    
    def test_full_access_jwt_permissions(self):
        """Full access JWT should have allow_downloads=true, allow_uploads=true, allow_delete=true"""
        jwt = self.get_jwt_for_share(SHARE_TOKENS["full"])
        data = self.get_files_with_permissions(SHARE_TOKENS["full"], jwt)
        
        assert data["access_level"] == "full"
        assert data["allow_downloads"] == True
        assert data["allow_uploads"] == True
        assert data["allow_delete"] == True
        print(f"✓ Full access JWT permissions: downloads={data['allow_downloads']}, uploads={data['allow_uploads']}, delete={data['allow_delete']}")


class TestDownloadPermissionEnforcement:
    """Test that download endpoints enforce download permission"""
    
    def get_jwt_for_share(self, token):
        response = requests.get(f"{BASE_URL}/api/share/{token}/open-access")
        assert response.status_code == 200
        return response.json()["jwt"]
    
    def test_view_only_cannot_download_file(self):
        """View-only share should get 403 when trying to download a file"""
        jwt = self.get_jwt_for_share(SHARE_TOKENS["view"])
        # Try to download a non-existent file - should get 403 for permission, not 404 for file
        response = requests.get(
            f"{BASE_URL}/api/share/{SHARE_TOKENS['view']}/download/fake-file-id",
            headers={"Authorization": f"Bearer {jwt}"}
        )
        # Should be 403 (forbidden) because downloads not allowed
        assert response.status_code == 403
        assert "Downloads not allowed" in response.json().get("detail", "")
        print(f"✓ View-only share correctly blocked from downloading: {response.json()['detail']}")
    
    def test_view_only_cannot_download_zip(self):
        """View-only share should get 403 when trying to download zip"""
        jwt = self.get_jwt_for_share(SHARE_TOKENS["view"])
        response = requests.post(
            f"{BASE_URL}/api/share/{SHARE_TOKENS['view']}/download-zip",
            headers={"Authorization": f"Bearer {jwt}"},
            json=[]
        )
        assert response.status_code == 403
        assert "Downloads not allowed" in response.json().get("detail", "")
        print(f"✓ View-only share correctly blocked from zip download: {response.json()['detail']}")
    
    def test_download_share_can_download(self):
        """Download share should be able to download (will get 404 for non-existent file)"""
        jwt = self.get_jwt_for_share(SHARE_TOKENS["download"])
        response = requests.get(
            f"{BASE_URL}/api/share/{SHARE_TOKENS['download']}/download/fake-file-id",
            headers={"Authorization": f"Bearer {jwt}"}
        )
        # Should be 404 (file not found) not 403 (forbidden)
        assert response.status_code == 404
        print(f"✓ Download share allowed to attempt download (got 404 for non-existent file)")
    
    def test_upload_share_can_download(self):
        """Upload share should be able to download"""
        jwt = self.get_jwt_for_share(SHARE_TOKENS["upload"])
        response = requests.get(
            f"{BASE_URL}/api/share/{SHARE_TOKENS['upload']}/download/fake-file-id",
            headers={"Authorization": f"Bearer {jwt}"}
        )
        # Should be 404 (file not found) not 403 (forbidden)
        assert response.status_code == 404
        print(f"✓ Upload share allowed to attempt download (got 404 for non-existent file)")
    
    def test_full_access_can_download(self):
        """Full access share should be able to download"""
        jwt = self.get_jwt_for_share(SHARE_TOKENS["full"])
        response = requests.get(
            f"{BASE_URL}/api/share/{SHARE_TOKENS['full']}/download/fake-file-id",
            headers={"Authorization": f"Bearer {jwt}"}
        )
        # Should be 404 (file not found) not 403 (forbidden)
        assert response.status_code == 404
        print(f"✓ Full access share allowed to attempt download (got 404 for non-existent file)")


class TestUploadPermissionEnforcement:
    """Test that upload endpoint enforces upload permission"""
    
    def get_jwt_for_share(self, token):
        response = requests.get(f"{BASE_URL}/api/share/{token}/open-access")
        assert response.status_code == 200
        return response.json()["jwt"]
    
    def test_view_only_cannot_upload(self):
        """View-only share should get 403 when trying to upload"""
        jwt = self.get_jwt_for_share(SHARE_TOKENS["view"])
        # Create a simple test file
        files = {"files": ("test.txt", b"test content", "text/plain")}
        response = requests.post(
            f"{BASE_URL}/api/share/{SHARE_TOKENS['view']}/upload",
            headers={"Authorization": f"Bearer {jwt}"},
            files=files
        )
        assert response.status_code == 403
        assert "Uploads not allowed" in response.json().get("detail", "")
        print(f"✓ View-only share correctly blocked from uploading: {response.json()['detail']}")
    
    def test_download_share_cannot_upload(self):
        """Download share should get 403 when trying to upload"""
        jwt = self.get_jwt_for_share(SHARE_TOKENS["download"])
        files = {"files": ("test.txt", b"test content", "text/plain")}
        response = requests.post(
            f"{BASE_URL}/api/share/{SHARE_TOKENS['download']}/upload",
            headers={"Authorization": f"Bearer {jwt}"},
            files=files
        )
        assert response.status_code == 403
        assert "Uploads not allowed" in response.json().get("detail", "")
        print(f"✓ Download share correctly blocked from uploading: {response.json()['detail']}")
    
    def test_upload_share_can_upload(self):
        """Upload share should be able to upload"""
        jwt = self.get_jwt_for_share(SHARE_TOKENS["upload"])
        # Create a simple test image
        files = {"files": ("test_upload.jpg", b"\xff\xd8\xff\xe0test image content", "image/jpeg")}
        response = requests.post(
            f"{BASE_URL}/api/share/{SHARE_TOKENS['upload']}/upload",
            headers={"Authorization": f"Bearer {jwt}"},
            files=files
        )
        # Should succeed (200) or at least not be 403
        assert response.status_code != 403
        print(f"✓ Upload share allowed to upload: status={response.status_code}")
    
    def test_full_access_can_upload(self):
        """Full access share should be able to upload"""
        jwt = self.get_jwt_for_share(SHARE_TOKENS["full"])
        files = {"files": ("test_full.jpg", b"\xff\xd8\xff\xe0test image content", "image/jpeg")}
        response = requests.post(
            f"{BASE_URL}/api/share/{SHARE_TOKENS['full']}/upload",
            headers={"Authorization": f"Bearer {jwt}"},
            files=files
        )
        # Should succeed (200) or at least not be 403
        assert response.status_code != 403
        print(f"✓ Full access share allowed to upload: status={response.status_code}")


class TestDeletePermissionEnforcement:
    """Test that delete endpoint enforces delete permission"""
    
    def get_jwt_for_share(self, token):
        response = requests.get(f"{BASE_URL}/api/share/{token}/open-access")
        assert response.status_code == 200
        return response.json()["jwt"]
    
    def test_view_only_cannot_delete(self):
        """View-only share should get 403 when trying to delete"""
        jwt = self.get_jwt_for_share(SHARE_TOKENS["view"])
        response = requests.post(
            f"{BASE_URL}/api/share/{SHARE_TOKENS['view']}/delete",
            headers={"Authorization": f"Bearer {jwt}"},
            json={"file_ids": ["fake-file-id"]}
        )
        assert response.status_code == 403
        assert "Deleting not allowed" in response.json().get("detail", "")
        print(f"✓ View-only share correctly blocked from deleting: {response.json()['detail']}")
    
    def test_download_share_cannot_delete(self):
        """Download share should get 403 when trying to delete"""
        jwt = self.get_jwt_for_share(SHARE_TOKENS["download"])
        response = requests.post(
            f"{BASE_URL}/api/share/{SHARE_TOKENS['download']}/delete",
            headers={"Authorization": f"Bearer {jwt}"},
            json={"file_ids": ["fake-file-id"]}
        )
        assert response.status_code == 403
        assert "Deleting not allowed" in response.json().get("detail", "")
        print(f"✓ Download share correctly blocked from deleting: {response.json()['detail']}")
    
    def test_upload_share_cannot_delete(self):
        """Upload share should get 403 when trying to delete"""
        jwt = self.get_jwt_for_share(SHARE_TOKENS["upload"])
        response = requests.post(
            f"{BASE_URL}/api/share/{SHARE_TOKENS['upload']}/delete",
            headers={"Authorization": f"Bearer {jwt}"},
            json={"file_ids": ["fake-file-id"]}
        )
        assert response.status_code == 403
        assert "Deleting not allowed" in response.json().get("detail", "")
        print(f"✓ Upload share correctly blocked from deleting: {response.json()['detail']}")
    
    def test_full_access_can_delete(self):
        """Full access share should be able to delete (will delete 0 files for non-existent IDs)"""
        jwt = self.get_jwt_for_share(SHARE_TOKENS["full"])
        response = requests.post(
            f"{BASE_URL}/api/share/{SHARE_TOKENS['full']}/delete",
            headers={"Authorization": f"Bearer {jwt}"},
            json={"file_ids": ["fake-file-id"]}
        )
        # Should succeed (200) with deleted=0, not 403
        assert response.status_code == 200
        data = response.json()
        assert "deleted" in data
        print(f"✓ Full access share allowed to delete: deleted={data['deleted']}")


class TestAdminShareCreation:
    """Test admin can create shares with all 4 access levels"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(
            f"{BASE_URL}/api/admin/login",
            json={"username": "admin", "password": "test123"}
        )
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json()["token"]
    
    def test_create_view_only_share(self, admin_token):
        """Admin can create a view-only share"""
        response = requests.post(
            f"{BASE_URL}/api/admin/galleries/{GALLERY_ID}/shares",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "gallery_id": GALLERY_ID,
                "access_level": "view",
                "label": "Test View Only"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["access_level"] == "view"
        assert data["allow_uploads"] == False
        print(f"✓ Created view-only share: token={data['token']}")
    
    def test_create_download_share(self, admin_token):
        """Admin can create a download share"""
        response = requests.post(
            f"{BASE_URL}/api/admin/galleries/{GALLERY_ID}/shares",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "gallery_id": GALLERY_ID,
                "access_level": "download",
                "label": "Test Download"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["access_level"] == "download"
        assert data["allow_uploads"] == False
        print(f"✓ Created download share: token={data['token']}")
    
    def test_create_upload_share(self, admin_token):
        """Admin can create an upload share"""
        response = requests.post(
            f"{BASE_URL}/api/admin/galleries/{GALLERY_ID}/shares",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "gallery_id": GALLERY_ID,
                "access_level": "upload",
                "label": "Test Upload"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["access_level"] == "upload"
        assert data["allow_uploads"] == True
        print(f"✓ Created upload share: token={data['token']}")
    
    def test_create_full_access_share(self, admin_token):
        """Admin can create a full access share"""
        response = requests.post(
            f"{BASE_URL}/api/admin/galleries/{GALLERY_ID}/shares",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "gallery_id": GALLERY_ID,
                "access_level": "full",
                "label": "Test Full Access"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["access_level"] == "full"
        assert data["allow_uploads"] == True
        print(f"✓ Created full access share: token={data['token']}")
    
    def test_invalid_access_level_rejected(self, admin_token):
        """Invalid access level should be rejected"""
        response = requests.post(
            f"{BASE_URL}/api/admin/galleries/{GALLERY_ID}/shares",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "gallery_id": GALLERY_ID,
                "access_level": "invalid_level",
                "label": "Test Invalid"
            }
        )
        assert response.status_code == 400
        assert "Invalid access level" in response.json().get("detail", "")
        print(f"✓ Invalid access level correctly rejected")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
