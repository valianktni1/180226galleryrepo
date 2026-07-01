"""
Test suite for Awards Badge feature in branded emails.
Tests:
- Public email-assets endpoint (no auth required)
- SMTP settings with site_url field
- Gallery notification email endpoint
- Broadcast email endpoint
- Email templates CRUD (regression)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPublicEmailAssets:
    """Test public email assets endpoint - NO AUTH required"""
    
    def test_awards_badge_returns_200_with_image_png(self):
        """GET /api/public/email-assets/awards-badges.png returns 200 with image/png"""
        response = requests.get(f"{BASE_URL}/api/public/email-assets/awards-badges.png")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.headers.get('content-type') == 'image/png', f"Expected image/png, got {response.headers.get('content-type')}"
        assert len(response.content) > 1000, "Image should have substantial content"
    
    def test_nonexistent_asset_returns_404(self):
        """GET /api/public/email-assets/nonexistent.png returns 404"""
        response = requests.get(f"{BASE_URL}/api/public/email-assets/nonexistent.png")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"


class TestSMTPSettingsWithSiteUrl:
    """Test SMTP settings with new site_url field"""
    
    @pytest.fixture
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_get_smtp_settings_returns_site_url(self, auth_headers):
        """GET /api/admin/settings/smtp returns site_url field"""
        response = requests.get(f"{BASE_URL}/api/admin/settings/smtp", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        # site_url should be present in response (may be empty string)
        assert "site_url" in data, f"site_url field missing from response: {data}"
    
    def test_save_smtp_settings_with_site_url(self, auth_headers):
        """POST /api/admin/settings/smtp saves site_url correctly"""
        # First get current settings
        get_response = requests.get(f"{BASE_URL}/api/admin/settings/smtp", headers=auth_headers)
        current = get_response.json() if get_response.status_code == 200 else {}
        
        # Save with site_url
        test_site_url = "https://gallery.test-wedding.co.uk"
        save_data = {
            "smtp_server": current.get("smtp_server", "smtp.test.com"),
            "smtp_port": current.get("smtp_port", 465),
            "smtp_email": current.get("smtp_email", "test@test.com"),
            "smtp_password": "••••••••",  # Use masked placeholder
            "sender_name": current.get("sender_name", "Test Sender"),
            "site_url": test_site_url
        }
        
        response = requests.post(f"{BASE_URL}/api/admin/settings/smtp", json=save_data, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify it was saved
        verify_response = requests.get(f"{BASE_URL}/api/admin/settings/smtp", headers=auth_headers)
        assert verify_response.status_code == 200
        saved_data = verify_response.json()
        assert saved_data.get("site_url") == test_site_url, f"site_url not saved correctly: {saved_data}"
    
    def test_site_url_trailing_slash_stripped(self, auth_headers):
        """POST /api/admin/settings/smtp strips trailing slash from site_url"""
        get_response = requests.get(f"{BASE_URL}/api/admin/settings/smtp", headers=auth_headers)
        current = get_response.json() if get_response.status_code == 200 else {}
        
        # Save with trailing slash
        save_data = {
            "smtp_server": current.get("smtp_server", "smtp.test.com"),
            "smtp_port": current.get("smtp_port", 465),
            "smtp_email": current.get("smtp_email", "test@test.com"),
            "smtp_password": "••••••••",
            "sender_name": current.get("sender_name", "Test Sender"),
            "site_url": "https://gallery.test.com/"  # With trailing slash
        }
        
        response = requests.post(f"{BASE_URL}/api/admin/settings/smtp", json=save_data, headers=auth_headers)
        assert response.status_code == 200
        
        # Verify trailing slash was stripped
        verify_response = requests.get(f"{BASE_URL}/api/admin/settings/smtp", headers=auth_headers)
        saved_data = verify_response.json()
        assert saved_data.get("site_url") == "https://gallery.test.com", f"Trailing slash not stripped: {saved_data.get('site_url')}"


class TestGalleryNotifyEndpoint:
    """Test gallery notification email endpoint"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_notify_returns_400_for_gallery_without_email(self, auth_headers):
        """POST /api/admin/galleries/{id}/notify returns 400 if no client_email"""
        # First get a gallery
        galleries_response = requests.get(f"{BASE_URL}/api/admin/galleries", headers=auth_headers)
        if galleries_response.status_code != 200 or not galleries_response.json():
            pytest.skip("No galleries available for testing")
        
        galleries = galleries_response.json()
        # Find a gallery without email or create test scenario
        for gallery in galleries:
            if not gallery.get("client_email"):
                response = requests.post(
                    f"{BASE_URL}/api/admin/galleries/{gallery['id']}/notify",
                    headers=auth_headers
                )
                assert response.status_code == 400, f"Expected 400, got {response.status_code}"
                assert "email" in response.json().get("detail", "").lower()
                return
        
        # All galleries have emails - test passes by default
        pytest.skip("All galleries have client_email set")
    
    def test_notify_returns_404_for_nonexistent_gallery(self, auth_headers):
        """POST /api/admin/galleries/{id}/notify returns 404 for non-existent gallery"""
        response = requests.post(
            f"{BASE_URL}/api/admin/galleries/nonexistent-gallery-id/notify",
            headers=auth_headers
        )
        assert response.status_code == 404


class TestBroadcastEmailEndpoint:
    """Test broadcast email endpoint validation"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_broadcast_preview_works(self, auth_headers):
        """GET /api/admin/broadcast-preview returns recipients list"""
        response = requests.get(f"{BASE_URL}/api/admin/broadcast-preview", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "recipients" in data
        assert "count" in data
    
    def test_broadcast_requires_subject_and_body(self, auth_headers):
        """POST /api/admin/broadcast-email validates subject and body"""
        # Empty subject
        response = requests.post(
            f"{BASE_URL}/api/admin/broadcast-email",
            json={"subject": "", "body": "Test body"},
            headers=auth_headers
        )
        assert response.status_code == 400
        
        # Empty body
        response = requests.post(
            f"{BASE_URL}/api/admin/broadcast-email",
            json={"subject": "Test subject", "body": ""},
            headers=auth_headers
        )
        assert response.status_code == 400


class TestEmailTemplatesCRUD:
    """Regression tests for email templates CRUD"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_list_templates(self, auth_headers):
        """GET /api/admin/email-templates returns list"""
        response = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_create_and_delete_template(self, auth_headers):
        """POST and DELETE /api/admin/email-templates works"""
        # Create
        create_response = requests.post(
            f"{BASE_URL}/api/admin/email-templates",
            json={
                "name": "TEST_Awards_Badge_Test",
                "subject": "Test Subject",
                "body": "Test body content"
            },
            headers=auth_headers
        )
        assert create_response.status_code == 200
        template = create_response.json()
        assert "id" in template
        
        # Delete
        delete_response = requests.delete(
            f"{BASE_URL}/api/admin/email-templates/{template['id']}",
            headers=auth_headers
        )
        assert delete_response.status_code == 200


class TestShareLinksRegression:
    """Regression test for share links"""
    
    def test_share_link_works(self):
        """GET /api/share/{token} returns share info"""
        # Use the known share token from context
        response = requests.get(f"{BASE_URL}/api/share/n7TdghPWGxKR6Pov9B8Hxg")
        assert response.status_code == 200
        data = response.json()
        assert "gallery_name" in data


class TestAuthRequired:
    """Test that protected endpoints require auth"""
    
    def test_smtp_settings_requires_auth(self):
        """GET /api/admin/settings/smtp requires auth"""
        response = requests.get(f"{BASE_URL}/api/admin/settings/smtp")
        assert response.status_code == 401
    
    def test_save_smtp_requires_auth(self):
        """POST /api/admin/settings/smtp requires auth"""
        response = requests.post(f"{BASE_URL}/api/admin/settings/smtp", json={})
        assert response.status_code == 401
    
    def test_broadcast_preview_requires_auth(self):
        """GET /api/admin/broadcast-preview requires auth"""
        response = requests.get(f"{BASE_URL}/api/admin/broadcast-preview")
        assert response.status_code == 401
