"""
Test video thumbnail generation feature for wedding gallery system.
Tests:
- Video file has has_thumb=True after upload
- Thumbnail endpoint returns valid image
- Admin gallery view includes video with thumbnail
- Share view includes video with thumbnail
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestVideoThumbnails:
    """Video thumbnail feature tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login as admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        response = self.session.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        token = response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.token = token
    
    def test_video_file_has_thumb_true(self):
        """Test that video file in database has has_thumb=True"""
        # Get gallery detail for test gallery
        gallery_id = "b4e09e25-dd5e-410a-bafd-8fc631064d40"
        response = self.session.get(f"{BASE_URL}/api/admin/galleries/{gallery_id}")
        assert response.status_code == 200, f"Failed to get gallery: {response.text}"
        
        gallery = response.json()
        files = gallery.get("files", [])
        
        # Find video file
        video_files = [f for f in files if f.get("file_type") == "video"]
        assert len(video_files) > 0, "No video files found in test gallery"
        
        video = video_files[0]
        assert video.get("has_thumb") == True, f"Video file does not have has_thumb=True: {video}"
        assert video.get("has_preview") == True, f"Video file does not have has_preview=True: {video}"
        print(f"SUCCESS: Video file {video['filename']} has has_thumb=True and has_preview=True")
    
    def test_video_thumbnail_endpoint_returns_image(self):
        """Test that thumbnail endpoint returns valid JPEG image"""
        gallery_id = "b4e09e25-dd5e-410a-bafd-8fc631064d40"
        
        # Get the thumbnail
        thumb_url = f"{BASE_URL}/api/media/thumb/{gallery_id}/video/test_wedding_video.thumb.jpg"
        response = requests.get(thumb_url)
        
        assert response.status_code == 200, f"Thumbnail endpoint failed: {response.status_code}"
        assert response.headers.get("content-type") == "image/jpeg", f"Wrong content type: {response.headers.get('content-type')}"
        assert len(response.content) > 1000, "Thumbnail too small, might be invalid"
        print(f"SUCCESS: Thumbnail endpoint returns valid JPEG ({len(response.content)} bytes)")
    
    def test_video_preview_endpoint_returns_image(self):
        """Test that preview endpoint returns valid JPEG image"""
        gallery_id = "b4e09e25-dd5e-410a-bafd-8fc631064d40"
        
        # Get the preview
        preview_url = f"{BASE_URL}/api/media/preview/{gallery_id}/video/test_wedding_video.preview.jpg"
        response = requests.get(preview_url)
        
        assert response.status_code == 200, f"Preview endpoint failed: {response.status_code}"
        assert response.headers.get("content-type") == "image/jpeg", f"Wrong content type: {response.headers.get('content-type')}"
        assert len(response.content) > 1000, "Preview too small, might be invalid"
        print(f"SUCCESS: Preview endpoint returns valid JPEG ({len(response.content)} bytes)")
    
    def test_admin_gallery_includes_video_with_thumb(self):
        """Test that admin gallery detail includes video file with thumbnail info"""
        gallery_id = "b4e09e25-dd5e-410a-bafd-8fc631064d40"
        response = self.session.get(f"{BASE_URL}/api/admin/galleries/{gallery_id}")
        assert response.status_code == 200
        
        gallery = response.json()
        
        # Check Video subfolder exists
        assert "Video" in gallery.get("subfolders", []), "Video subfolder not found"
        
        # Check video file is in files list
        video_files = [f for f in gallery.get("files", []) if f.get("subfolder") == "Video"]
        assert len(video_files) > 0, "No files in Video subfolder"
        
        video = video_files[0]
        assert video.get("file_type") == "video", f"File is not video type: {video.get('file_type')}"
        assert video.get("has_thumb") == True, "Video missing has_thumb flag"
        print(f"SUCCESS: Admin gallery includes video with thumbnail: {video['filename']}")
    
    def test_share_files_includes_video_with_thumb(self):
        """Test that share files endpoint includes video with thumbnail info"""
        # Use a share token that has access to the whole gallery
        share_token = "0Yxy_MfAzwJ8qRqz08tOWw"
        
        # Get open access JWT
        response = requests.get(f"{BASE_URL}/api/share/{share_token}/open-access")
        assert response.status_code == 200, f"Failed to get share access: {response.text}"
        
        jwt_token = response.json().get("jwt")
        
        # Get share files
        headers = {"Authorization": f"Bearer {jwt_token}"}
        response = requests.get(f"{BASE_URL}/api/share/{share_token}/files", headers=headers)
        assert response.status_code == 200, f"Failed to get share files: {response.text}"
        
        data = response.json()
        subfolders = data.get("subfolders", [])
        
        # Find Video subfolder
        video_subfolder = next((sf for sf in subfolders if sf.get("name") == "Video"), None)
        assert video_subfolder is not None, "Video subfolder not found in share"
        
        video_files = video_subfolder.get("files", [])
        assert len(video_files) > 0, "No video files in Video subfolder"
        
        video = video_files[0]
        assert video.get("has_thumb") == True, f"Video missing has_thumb in share: {video}"
        print(f"SUCCESS: Share files includes video with thumbnail: {video['filename']}")


class TestNumpyRemoved:
    """Test that numpy is removed from the codebase"""
    
    def test_numpy_not_in_requirements(self):
        """Test that numpy is not in requirements.txt"""
        with open("/app/backend/requirements.txt", "r") as f:
            content = f.read()
        
        assert "numpy" not in content.lower(), "numpy found in requirements.txt"
        print("SUCCESS: numpy not in requirements.txt")
    
    def test_numpy_not_imported_in_server(self):
        """Test that numpy is not imported in server.py"""
        with open("/app/backend/server.py", "r") as f:
            content = f.read()
        
        assert "import numpy" not in content, "numpy import found in server.py"
        assert "from numpy" not in content, "numpy import found in server.py"
        print("SUCCESS: numpy not imported in server.py")
    
    def test_backend_starts_without_numpy_error(self):
        """Test that backend health check works (no numpy import error)"""
        response = requests.get(f"{BASE_URL}/api/admin/check-setup")
        assert response.status_code == 200, f"Backend health check failed: {response.text}"
        print("SUCCESS: Backend starts without numpy import error")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
