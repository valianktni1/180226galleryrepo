"""
Test Download Functionality - P0 Bug Testing
Tests for:
- Admin login
- Gallery creation
- File upload
- Share link creation
- Client share access
- Single file download
- Disk-backed ZIP download job
- Retirement of the former in-memory ZIP routes
- Diagnose gallery endpoint
"""

import pytest
import requests
import os
import io
import zipfile
import base64
import time
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "test123"

# Test data prefix for cleanup
TEST_PREFIX = "TEST_DOWNLOAD_"


def complete_download_job(token, jwt_token, start_response):
    """Poll a prepared ZIP job and return its streamed response."""
    assert start_response.status_code == 200, start_response.text
    job = start_response.json()
    deadline = time.time() + 20
    headers = {"Authorization": f"Bearer {jwt_token}"}
    while time.time() < deadline:
        status_response = requests.get(
            f"{BASE_URL}/api/share/{token}/download-jobs/{job['id']}",
            headers=headers,
        )
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        if status["status"] == "ready":
            return requests.get(
                f"{BASE_URL}/api/download-jobs/{job['id']}/file",
                params={"ticket": job["ticket"]},
            )
        assert status["status"] not in {"failed"}, status
        time.sleep(0.1)
    raise AssertionError("Download job did not become ready")


class TestAdminLogin:
    """Test admin authentication"""
    
    def test_admin_login_success(self):
        """Admin can login with correct credentials"""
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        assert data.get("username") == ADMIN_USERNAME
        print(f"Admin login successful, token received")
        return data["token"]
    
    def test_admin_login_invalid_credentials(self):
        """Admin login fails with wrong credentials"""
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "wrong",
            "password": "wrong"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestDownloadWorkflow:
    """Full workflow test: create gallery, upload files, create share, test downloads"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token for authenticated requests"""
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def admin_headers(self, admin_token):
        """Headers with admin auth"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    @pytest.fixture(scope="class")
    def test_gallery(self, admin_headers):
        """Create a test gallery and return its ID"""
        gallery_name = f"{TEST_PREFIX}Gallery_{datetime.now().strftime('%H%M%S')}"
        response = requests.post(
            f"{BASE_URL}/api/admin/galleries",
            headers=admin_headers,
            json={"folder_name": gallery_name}
        )
        assert response.status_code in [200, 201], f"Gallery creation failed: {response.text}"
        data = response.json()
        assert "id" in data, "No gallery ID in response"
        print(f"Created test gallery: {gallery_name} (ID: {data['id']})")
        yield data
        
        # Cleanup: delete gallery after tests
        try:
            requests.delete(f"{BASE_URL}/api/admin/galleries/{data['id']}", headers=admin_headers)
            print(f"Cleaned up test gallery: {data['id']}")
        except Exception as e:
            print(f"Cleanup failed: {e}")
    
    @pytest.fixture(scope="class")
    def uploaded_files(self, admin_headers, test_gallery):
        """Upload test files to the gallery"""
        gallery_id = test_gallery["id"]
        subfolder = "Wedding Images"
        
        # Create small test JPEG files (valid JPEG header)
        # Minimal valid JPEG: FFD8 FFE0 ... FFD9
        jpeg_header = bytes([
            0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
            0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
            0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
            0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
            0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
            0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
            0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
            0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
            0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
            0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
            0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
            0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
            0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
            0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
            0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
            0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
            0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
            0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
            0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
            0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
            0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
            0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
            0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
            0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
            0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
            0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01,
            0x00, 0x00, 0x3F, 0x00, 0xFB, 0xD5, 0xDB, 0x20, 0xA8, 0xBA, 0xAE, 0xEB,
            0xBA, 0xEE, 0xBB, 0xAE, 0xEB, 0xBA, 0xEE, 0xBB, 0xAE, 0xEB, 0xBA, 0xEE,
            0xBB, 0xAE, 0xEB, 0xBA, 0xEE, 0xBB, 0xAE, 0xEB, 0xBA, 0xEE, 0xBB, 0xAE,
            0xEB, 0xBA, 0xEE, 0xBB, 0xAE, 0xEB, 0xBA, 0xEE, 0xBB, 0xAE, 0xEB, 0xBA,
            0xFF, 0xD9
        ])
        
        # Upload 3 test files
        uploaded = []
        for i in range(1, 4):
            filename = f"test_image_{i}.jpg"
            files = {
                'files': (filename, io.BytesIO(jpeg_header), 'image/jpeg')
            }
            response = requests.post(
                f"{BASE_URL}/api/admin/galleries/{gallery_id}/upload",
                headers=admin_headers,
                data={"subfolder": subfolder},
                files=files
            )
            assert response.status_code in [200, 201], f"Upload failed for {filename}: {response.text}"
            data = response.json()
            # Handle various response formats
            if isinstance(data, dict):
                if "uploaded" in data:
                    uploaded.extend(data["uploaded"])
                elif "files" in data:
                    uploaded.extend(data["files"])
                elif "id" in data:
                    uploaded.append(data)
            elif isinstance(data, list) and len(data) > 0:
                uploaded.extend(data)
            print(f"Uploaded: {filename}")
        
        assert len(uploaded) >= 1, f"No files were uploaded. Last response: {data}"
        print(f"Total files uploaded: {len(uploaded)}")
        return uploaded
    
    @pytest.fixture(scope="class")
    def share_link(self, admin_headers, test_gallery):
        """Create a share link for the gallery"""
        gallery_id = test_gallery["id"]
        response = requests.post(
            f"{BASE_URL}/api/admin/galleries/{gallery_id}/shares",
            headers=admin_headers,
            json={
                "gallery_id": gallery_id,
                "access_level": "download",
                "label": f"{TEST_PREFIX}Share"
            }
        )
        assert response.status_code in [200, 201], f"Share creation failed: {response.text}"
        data = response.json()
        assert "token" in data, "No share token in response"
        print(f"Created share link with token: {data['token']}")
        return data
    
    @pytest.fixture(scope="class")
    def share_jwt(self, share_link):
        """Access the share and get JWT token"""
        token = share_link["token"]
        response = requests.post(f"{BASE_URL}/api/share/{token}/access")
        assert response.status_code == 200, f"Share access failed: {response.text}"
        data = response.json()
        assert "jwt" in data, f"No JWT in response: {data}"
        print(f"Got share JWT token")
        return data["jwt"]
    
    def test_01_gallery_created(self, test_gallery):
        """Verify gallery was created"""
        assert "id" in test_gallery
        assert "folder_name" in test_gallery
        print(f"Gallery created: {test_gallery['folder_name']}")
    
    def test_02_files_uploaded(self, uploaded_files):
        """Verify files were uploaded"""
        assert len(uploaded_files) >= 1, "No files uploaded"
        for f in uploaded_files:
            assert "id" in f, f"File missing ID: {f}"
            assert "filename" in f, f"File missing filename: {f}"
        print(f"Files uploaded: {[f.get('filename') for f in uploaded_files]}")
    
    def test_03_share_created(self, share_link):
        """Verify share link was created"""
        assert "token" in share_link
        print(f"Share token: {share_link['token']}")
    
    def test_04_share_access(self, share_jwt):
        """Verify share access returns JWT"""
        assert share_jwt is not None
        assert len(share_jwt) > 10
        print("Share JWT obtained successfully")
    
    def test_05_list_share_files(self, share_link, share_jwt):
        """Client can list files via share"""
        token = share_link["token"]
        headers = {"Authorization": f"Bearer {share_jwt}"}
        response = requests.get(f"{BASE_URL}/api/share/{token}/files", headers=headers)
        assert response.status_code == 200, f"List files failed: {response.text}"
        data = response.json()
        
        # Response has subfolders structure with files inside
        files = []
        if isinstance(data, dict):
            if "subfolders" in data:
                for sf in data["subfolders"]:
                    files.extend(sf.get("files", []))
            elif "files" in data:
                files = data["files"]
        elif isinstance(data, list):
            files = data
        
        assert len(files) > 0, f"No files found in share response"
        print(f"Listed {len(files)} files via share")
        return files
    
    def test_06_download_single_file(self, share_link, share_jwt, uploaded_files):
        """Client can download a single file - P0 BUG TEST"""
        token = share_link["token"]
        headers = {"Authorization": f"Bearer {share_jwt}"}
        
        # Get file ID from uploaded files
        file_id = uploaded_files[0].get("id")
        assert file_id, "No file ID available"
        
        response = requests.get(
            f"{BASE_URL}/api/share/{token}/download/{file_id}",
            headers=headers
        )
        
        assert response.status_code == 200, f"Single file download failed: {response.status_code} - {response.text}"
        
        # Verify we got actual file content
        content = response.content
        assert len(content) > 0, "Downloaded file is empty"
        
        # Check it's a valid JPEG (starts with FFD8)
        assert content[:2] == b'\xff\xd8', f"Downloaded content is not a valid JPEG: {content[:10]}"
        
        print(f"Single file download successful: {len(content)} bytes")
    
    def test_07_download_zip_job(self, share_link, share_jwt, uploaded_files):
        """Client can prepare and stream a disk-backed folder ZIP."""
        token = share_link["token"]
        headers = {
            "Authorization": f"Bearer {share_jwt}",
            "Content-Type": "application/json"
        }
        
        start_response = requests.post(
            f"{BASE_URL}/api/share/{token}/download-jobs",
            headers=headers,
            json={"subfolder": "Wedding Images"}
        )
        response = complete_download_job(token, share_jwt, start_response)
        
        assert response.status_code == 200, f"ZIP download failed: {response.status_code} - {response.text}"
        
        content = response.content
        assert len(content) > 0, "ZIP file is empty"
        
        # Verify it's a valid ZIP (starts with PK)
        assert content[:2] == b'PK', f"Downloaded content is not a valid ZIP: {content[:10]}"
        
        # Verify ZIP contains files
        zip_buffer = io.BytesIO(content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            file_list = zf.namelist()
            assert len(file_list) > 0, "ZIP is empty (no files inside)"
            print(f"ZIP contains {len(file_list)} files: {file_list}")
            
            # Verify each file in ZIP has content
            for name in file_list:
                file_content = zf.read(name)
                assert len(file_content) > 0, f"File {name} in ZIP is empty"
        
        print(f"ZIP download successful: {len(content)} bytes, {len(file_list)} files")
    
    def test_08_legacy_memory_zip_routes_are_retired(self, share_link, share_jwt):
        """Old whole-gallery in-memory ZIP routes no longer exist."""
        token = share_link["token"]
        headers = {"Authorization": f"Bearer {share_jwt}"}
        for method, path in (
            (requests.post, "download-zip"),
            (requests.get, "download-album"),
            (requests.get, "download-favourites"),
        ):
            response = method(f"{BASE_URL}/api/share/{token}/{path}", headers=headers)
            assert response.status_code in {404, 405}
    
    def test_09_diagnose_gallery(self, admin_headers, test_gallery):
        """Admin diagnostic endpoint shows correct file count"""
        gallery_id = test_gallery["id"]
        
        response = requests.get(
            f"{BASE_URL}/api/admin/diagnose-gallery/{gallery_id}",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"Diagnose failed: {response.status_code} - {response.text}"
        
        data = response.json()
        print(f"Diagnose result: {data}")
        
        # Verify structure
        assert "gallery_name" in data
        assert "db_file_count" in data
        assert "files_found" in data
        assert "files_missing" in data
        assert "gallery_path_exists" in data
        
        # Verify no missing files
        assert data["files_missing"] == 0, f"Missing files detected: {data.get('missing_samples', [])}"
        assert data["files_found"] == data["db_file_count"], "File count mismatch between DB and disk"
        
        print(f"Diagnose: {data['files_found']}/{data['db_file_count']} files found, 0 missing")


class TestDownloadPermissions:
    """Test download permission enforcement"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    def test_download_without_auth_fails(self):
        """Download without auth header should fail"""
        # Use a fake token
        response = requests.get(f"{BASE_URL}/api/share/fake_token/download/fake_file_id")
        assert response.status_code in [401, 403], f"Expected auth error, got {response.status_code}"
    
    def test_download_zip_without_auth_fails(self):
        """ZIP download without auth should fail"""
        response = requests.post(
            f"{BASE_URL}/api/share/fake_token/download-jobs",
            json={"subfolder": "Wedding Images"}
        )
        assert response.status_code in [401, 403], f"Expected auth error, got {response.status_code}"


class TestExistingShareDownload:
    """Test downloads using existing share from previous iteration"""
    
    def test_existing_share_if_available(self):
        """Test with existing share token from iteration_18"""
        # From iteration_18: Share token n7TdghPWGxKR6Pov9B8Hxg works for Test Couple gallery
        existing_token = "n7TdghPWGxKR6Pov9B8Hxg"
        
        # Try to access the share
        response = requests.post(f"{BASE_URL}/api/share/{existing_token}/access")
        
        if response.status_code != 200:
            pytest.skip(f"Existing share not available: {response.status_code}")
        
        data = response.json()
        jwt = data.get("jwt")
        assert jwt, "No JWT in response"
        
        # List files
        headers = {"Authorization": f"Bearer {jwt}"}
        files_response = requests.get(f"{BASE_URL}/api/share/{existing_token}/files", headers=headers)
        
        if files_response.status_code != 200:
            pytest.skip("Could not list files from existing share")
        
        files_data = files_response.json()
        files = files_data.get("files", []) if isinstance(files_data, dict) else files_data
        
        if not files:
            pytest.skip("No files in existing share")
        
        # Test single file download
        file_id = files[0].get("id")
        if file_id:
            dl_response = requests.get(
                f"{BASE_URL}/api/share/{existing_token}/download/{file_id}",
                headers=headers
            )
            print(f"Existing share single download: {dl_response.status_code}")
            if dl_response.status_code == 200:
                assert len(dl_response.content) > 0, "Downloaded file is empty"
        
        # Folder ZIP behaviour is exercised by TestDownloadWorkflow above.


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
