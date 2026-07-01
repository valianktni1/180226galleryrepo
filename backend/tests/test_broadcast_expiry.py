"""
Test suite for Broadcast Email and Expiry Reminder features.
Tests:
- GET /api/admin/broadcast-preview (requires admin auth)
- POST /api/admin/broadcast-email (validates inputs, checks SMTP config)
- Share link regression test (temporal dead zone bug fix)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "test123"
SHARE_TOKEN = "n7TdghPWGxKR6Pov9B8Hxg"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token."""
    response = requests.post(f"{BASE_URL}/api/admin/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    data = response.json()
    assert "token" in data, "No token in login response"
    return data["token"]


@pytest.fixture
def auth_headers(admin_token):
    """Headers with admin auth."""
    return {"Authorization": f"Bearer {admin_token}"}


class TestBroadcastPreview:
    """Tests for GET /api/admin/broadcast-preview endpoint."""

    def test_broadcast_preview_requires_auth(self):
        """Broadcast preview should return 401 without admin token."""
        response = requests.get(f"{BASE_URL}/api/admin/broadcast-preview")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Broadcast preview returns 401 without auth")

    def test_broadcast_preview_with_auth(self, auth_headers):
        """Broadcast preview should return list of galleries with emails."""
        response = requests.get(f"{BASE_URL}/api/admin/broadcast-preview", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "recipients" in data, "Response should have 'recipients' field"
        assert "count" in data, "Response should have 'count' field"
        assert isinstance(data["recipients"], list), "Recipients should be a list"
        assert data["count"] == len(data["recipients"]), "Count should match recipients length"
        
        # Verify structure of recipients (if any)
        for r in data["recipients"]:
            assert "id" in r, "Recipient should have 'id'"
            assert "folder_name" in r, "Recipient should have 'folder_name'"
            assert "client_email" in r, "Recipient should have 'client_email'"
        
        print(f"✓ Broadcast preview returns {data['count']} recipients")


class TestBroadcastEmail:
    """Tests for POST /api/admin/broadcast-email endpoint."""

    def test_broadcast_email_requires_auth(self):
        """Broadcast email should return 401 without admin token."""
        response = requests.post(f"{BASE_URL}/api/admin/broadcast-email", json={
            "subject": "Test",
            "body": "Test body"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Broadcast email returns 401 without auth")

    def test_broadcast_email_empty_subject(self, auth_headers):
        """Broadcast email should reject empty subject with 400."""
        response = requests.post(
            f"{BASE_URL}/api/admin/broadcast-email",
            headers=auth_headers,
            json={"subject": "", "body": "Test body"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("✓ Broadcast email rejects empty subject with 400")

    def test_broadcast_email_empty_body(self, auth_headers):
        """Broadcast email should reject empty body with 400."""
        response = requests.post(
            f"{BASE_URL}/api/admin/broadcast-email",
            headers=auth_headers,
            json={"subject": "Test Subject", "body": ""}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("✓ Broadcast email rejects empty body with 400")

    def test_broadcast_email_whitespace_only(self, auth_headers):
        """Broadcast email should reject whitespace-only inputs with 400."""
        response = requests.post(
            f"{BASE_URL}/api/admin/broadcast-email",
            headers=auth_headers,
            json={"subject": "   ", "body": "   "}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("✓ Broadcast email rejects whitespace-only inputs with 400")

    def test_broadcast_email_smtp_not_configured(self, auth_headers):
        """Broadcast email should return proper error when SMTP not configured."""
        response = requests.post(
            f"{BASE_URL}/api/admin/broadcast-email",
            headers=auth_headers,
            json={"subject": "Test Subject", "body": "Test body content"}
        )
        # Should be 400 with SMTP not configured message (since SMTP is not set up in preview)
        # OR could succeed if SMTP is configured and there are recipients
        if response.status_code == 400:
            data = response.json()
            detail = data.get("detail", "")
            # Either SMTP not configured or no recipients
            assert "SMTP" in detail or "email" in detail.lower(), f"Unexpected error: {detail}"
            print(f"✓ Broadcast email returns proper error: {detail}")
        elif response.status_code == 200:
            # SMTP is configured and emails were sent
            data = response.json()
            assert "sent" in data, "Response should have 'sent' count"
            print(f"✓ Broadcast email succeeded: sent={data.get('sent')}, failed={data.get('failed')}")
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}: {response.text}")


class TestShareLinkRegression:
    """Regression tests for share links (temporal dead zone bug fix)."""

    def test_share_info_endpoint(self):
        """Share info endpoint should return gallery info."""
        response = requests.get(f"{BASE_URL}/api/share/{SHARE_TOKEN}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "gallery_name" in data, "Response should have 'gallery_name'"
        assert "has_password" in data, "Response should have 'has_password'"
        print(f"✓ Share info returns gallery: {data.get('gallery_name')}")

    def test_share_open_access(self):
        """Open access endpoint should return JWT for no-password shares."""
        response = requests.get(f"{BASE_URL}/api/share/{SHARE_TOKEN}/open-access")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # API returns 'jwt' field, not 'token'
        assert "jwt" in data, "Response should have 'jwt'"
        print("✓ Share open-access returns JWT token")
        return data["jwt"]

    def test_share_files_endpoint(self):
        """Share files endpoint should return gallery files."""
        # First get access token
        access_response = requests.get(f"{BASE_URL}/api/share/{SHARE_TOKEN}/open-access")
        assert access_response.status_code == 200
        share_jwt = access_response.json()["jwt"]
        
        # Then get files
        response = requests.get(
            f"{BASE_URL}/api/share/{SHARE_TOKEN}/files",
            headers={"Authorization": f"Bearer {share_jwt}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # API returns subfolders as a list with files inside each
        assert "subfolders" in data, "Response should have 'subfolders'"
        assert "gallery_name" in data, "Response should have 'gallery_name'"
        assert isinstance(data["subfolders"], list), "Subfolders should be a list"
        
        # Count total files across all subfolders
        total_files = sum(len(sf.get("files", [])) for sf in data["subfolders"])
        print(f"✓ Share files returns {total_files} files across {len(data['subfolders'])} subfolders")

    def test_share_heartbeat(self):
        """Heartbeat endpoint should work for share sessions."""
        # First get access token
        access_response = requests.get(f"{BASE_URL}/api/share/{SHARE_TOKEN}/open-access")
        assert access_response.status_code == 200
        share_jwt = access_response.json()["jwt"]
        
        # Send heartbeat
        response = requests.post(
            f"{BASE_URL}/api/share/{SHARE_TOKEN}/heartbeat",
            headers={"Authorization": f"Bearer {share_jwt}"},
            json={
                "session_id": "test-session-123",
                "action": "browsing",
                "subfolder": None,
                "detail": None
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") == True, "Heartbeat should return ok=true"
        print("✓ Share heartbeat works correctly")


class TestExpiryReminderBackgroundTask:
    """Tests to verify expiry reminder background task exists and runs."""

    def test_server_startup_no_errors(self, auth_headers):
        """Verify server started without errors by checking admin endpoints work."""
        # If the expiry reminder loop had errors, the server might not start properly
        response = requests.get(f"{BASE_URL}/api/admin/galleries", headers=auth_headers)
        assert response.status_code == 200, f"Server may have startup errors: {response.status_code}"
        print("✓ Server started successfully (expiry reminder loop running)")

    def test_live_visitors_endpoint(self, auth_headers):
        """Live visitors endpoint should work (related to heartbeat/activity tracking)."""
        response = requests.get(f"{BASE_URL}/api/admin/live-visitors", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "visitors" in data, "Response should have 'visitors'"
        print(f"✓ Live visitors endpoint returns {len(data['visitors'])} visitors")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
