"""
Test suite for video streaming endpoint with async aiofiles implementation.
Tests the /api/share/{token}/stream/{file_id} endpoint for:
- Range request support (206 Partial Content)
- Proper Content-Type headers
- Cache-Control headers
- Accept-Ranges header
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from review request
SHARE_TOKEN = "n7TdghPWGxKR6Pov9B8Hxg"
VIDEO_FILE_ID = "8e6c9042-eb1a-4037-90b3-085a4341d9ce"
GALLERY_ID = "b4e09e25-dd5e-410a-bafd-8fc631064d40"


class TestVideoStreaming:
    """Video streaming endpoint tests for async aiofiles implementation."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get share JWT before each test."""
        response = requests.get(f"{BASE_URL}/api/share/{SHARE_TOKEN}/open-access")
        assert response.status_code == 200, f"Failed to get share JWT: {response.text}"
        self.jwt = response.json().get("jwt")
        assert self.jwt, "JWT not returned from open-access endpoint"
    
    def test_streaming_with_range_header_returns_206(self):
        """Test that streaming endpoint returns 206 with Range header."""
        response = requests.get(
            f"{BASE_URL}/api/share/{SHARE_TOKEN}/stream/{VIDEO_FILE_ID}",
            params={"t": self.jwt},
            headers={"Range": "bytes=0-1023"},
            stream=True
        )
        
        assert response.status_code == 206, f"Expected 206, got {response.status_code}"
        print(f"✓ Streaming with Range header returns 206 Partial Content")
    
    def test_streaming_returns_content_range_header(self):
        """Test that Content-Range header is present in 206 response."""
        response = requests.get(
            f"{BASE_URL}/api/share/{SHARE_TOKEN}/stream/{VIDEO_FILE_ID}",
            params={"t": self.jwt},
            headers={"Range": "bytes=0-1023"},
            stream=True
        )
        
        assert response.status_code == 206
        content_range = response.headers.get("Content-Range")
        assert content_range is not None, "Content-Range header missing"
        assert content_range.startswith("bytes 0-"), f"Invalid Content-Range: {content_range}"
        print(f"✓ Content-Range header present: {content_range}")
    
    def test_streaming_returns_correct_content_type(self):
        """Test that Content-Type is video/mp4 for MP4 files."""
        response = requests.get(
            f"{BASE_URL}/api/share/{SHARE_TOKEN}/stream/{VIDEO_FILE_ID}",
            params={"t": self.jwt},
            headers={"Range": "bytes=0-1023"},
            stream=True
        )
        
        content_type = response.headers.get("Content-Type")
        assert content_type == "video/mp4", f"Expected video/mp4, got {content_type}"
        print(f"✓ Content-Type is video/mp4")
    
    def test_streaming_returns_accept_ranges_header(self):
        """Test that Accept-Ranges: bytes header is present."""
        response = requests.get(
            f"{BASE_URL}/api/share/{SHARE_TOKEN}/stream/{VIDEO_FILE_ID}",
            params={"t": self.jwt},
            headers={"Range": "bytes=0-1023"},
            stream=True
        )
        
        accept_ranges = response.headers.get("Accept-Ranges")
        assert accept_ranges == "bytes", f"Expected 'bytes', got {accept_ranges}"
        print(f"✓ Accept-Ranges header is 'bytes'")
    
    def test_streaming_without_range_returns_200(self):
        """Test that streaming without Range header returns 200 OK."""
        response = requests.get(
            f"{BASE_URL}/api/share/{SHARE_TOKEN}/stream/{VIDEO_FILE_ID}",
            params={"t": self.jwt},
            stream=True
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ Streaming without Range header returns 200 OK")
    
    def test_streaming_without_range_has_accept_ranges(self):
        """Test that Accept-Ranges header is present even without Range request."""
        response = requests.get(
            f"{BASE_URL}/api/share/{SHARE_TOKEN}/stream/{VIDEO_FILE_ID}",
            params={"t": self.jwt},
            stream=True
        )
        
        accept_ranges = response.headers.get("Accept-Ranges")
        assert accept_ranges == "bytes", f"Expected 'bytes', got {accept_ranges}"
        print(f"✓ Accept-Ranges header present in non-range response")
    
    def test_streaming_requires_authentication(self):
        """Test that streaming endpoint requires JWT token."""
        response = requests.get(
            f"{BASE_URL}/api/share/{SHARE_TOKEN}/stream/{VIDEO_FILE_ID}",
            stream=True
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ Streaming endpoint requires authentication (401 without token)")
    
    def test_streaming_invalid_file_returns_404(self):
        """Test that invalid file ID returns 404."""
        response = requests.get(
            f"{BASE_URL}/api/share/{SHARE_TOKEN}/stream/invalid-file-id",
            params={"t": self.jwt},
            stream=True
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"✓ Invalid file ID returns 404")
    
    def test_streaming_partial_range_request(self):
        """Test partial range request (middle of file)."""
        response = requests.get(
            f"{BASE_URL}/api/share/{SHARE_TOKEN}/stream/{VIDEO_FILE_ID}",
            params={"t": self.jwt},
            headers={"Range": "bytes=1000-2000"},
            stream=True
        )
        
        assert response.status_code == 206, f"Expected 206, got {response.status_code}"
        content_range = response.headers.get("Content-Range")
        assert "1000-" in content_range, f"Content-Range should start at 1000: {content_range}"
        print(f"✓ Partial range request works: {content_range}")


class TestShareAccess:
    """Test share access endpoints (regression tests)."""
    
    def test_share_info_endpoint(self):
        """Test that share info endpoint works."""
        response = requests.get(f"{BASE_URL}/api/share/{SHARE_TOKEN}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "gallery_name" in data
        assert "has_password" in data
        print(f"✓ Share info endpoint works, gallery: {data.get('gallery_name')}")
    
    def test_open_access_returns_jwt(self):
        """Test that open-access endpoint returns JWT."""
        response = requests.get(f"{BASE_URL}/api/share/{SHARE_TOKEN}/open-access")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "jwt" in data, "JWT not in response"
        assert len(data["jwt"]) > 50, "JWT seems too short"
        print(f"✓ Open-access endpoint returns valid JWT")
    
    def test_share_files_endpoint(self):
        """Test that share files endpoint works with JWT."""
        # Get JWT first
        jwt_response = requests.get(f"{BASE_URL}/api/share/{SHARE_TOKEN}/open-access")
        jwt = jwt_response.json().get("jwt")
        
        response = requests.get(
            f"{BASE_URL}/api/share/{SHARE_TOKEN}/files",
            headers={"Authorization": f"Bearer {jwt}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "subfolders" in data
        assert "gallery_name" in data
        print(f"✓ Share files endpoint works, {len(data.get('subfolders', []))} subfolders")


class TestDownloadEndpoints:
    """Test download endpoints (regression tests)."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get share JWT before each test."""
        response = requests.get(f"{BASE_URL}/api/share/{SHARE_TOKEN}/open-access")
        self.jwt = response.json().get("jwt")
    
    def test_download_single_file(self):
        """Test single file download endpoint."""
        response = requests.get(
            f"{BASE_URL}/api/share/{SHARE_TOKEN}/download/{VIDEO_FILE_ID}",
            headers={"Authorization": f"Bearer {self.jwt}"},
            stream=True
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        content_type = response.headers.get("Content-Type")
        assert "octet-stream" in content_type or "video" in content_type
        print(f"✓ Single file download works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
