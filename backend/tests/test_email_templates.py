"""
Test Email Templates CRUD and Send Template Email functionality
Tests:
- GET /api/admin/email-templates (list templates, auth required)
- POST /api/admin/email-templates (create template)
- PUT /api/admin/email-templates/{id} (update template)
- DELETE /api/admin/email-templates/{id} (delete template)
- POST /api/admin/galleries/{gallery_id}/send-template-email (send email with template)
- All endpoints return 401 without admin token
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestEmailTemplatesAuth:
    """Test that all email template endpoints require authentication"""
    
    def test_list_templates_requires_auth(self):
        """GET /api/admin/email-templates returns 401 without token"""
        response = requests.get(f"{BASE_URL}/api/admin/email-templates")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/admin/email-templates returns 401 without auth")
    
    def test_create_template_requires_auth(self):
        """POST /api/admin/email-templates returns 401 without token"""
        response = requests.post(f"{BASE_URL}/api/admin/email-templates", json={
            "name": "Test", "subject": "Test", "body": "Test"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: POST /api/admin/email-templates returns 401 without auth")
    
    def test_update_template_requires_auth(self):
        """PUT /api/admin/email-templates/{id} returns 401 without token"""
        response = requests.put(f"{BASE_URL}/api/admin/email-templates/fake-id", json={
            "name": "Test", "subject": "Test", "body": "Test"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: PUT /api/admin/email-templates/{id} returns 401 without auth")
    
    def test_delete_template_requires_auth(self):
        """DELETE /api/admin/email-templates/{id} returns 401 without token"""
        response = requests.delete(f"{BASE_URL}/api/admin/email-templates/fake-id")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: DELETE /api/admin/email-templates/{id} returns 401 without auth")
    
    def test_send_template_email_requires_auth(self):
        """POST /api/admin/galleries/{id}/send-template-email returns 401 without token"""
        response = requests.post(f"{BASE_URL}/api/admin/galleries/fake-id/send-template-email", json={
            "template_id": "fake-template-id"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: POST /api/admin/galleries/{id}/send-template-email returns 401 without auth")


class TestEmailTemplatesCRUD:
    """Test email template CRUD operations with authentication"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get admin token"""
        login_response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.created_template_ids = []
        yield
        # Cleanup: delete any templates created during tests
        for tid in self.created_template_ids:
            try:
                requests.delete(f"{BASE_URL}/api/admin/email-templates/{tid}", headers=self.headers)
            except:
                pass
    
    def test_list_templates_returns_list(self):
        """GET /api/admin/email-templates returns list of templates"""
        response = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"PASS: GET /api/admin/email-templates returns list ({len(data)} templates)")
    
    def test_create_template_success(self):
        """POST /api/admin/email-templates creates a new template"""
        unique_name = f"TEST_Template_{uuid.uuid4().hex[:8]}"
        payload = {
            "name": unique_name,
            "subject": "Test Subject for {couple_name}",
            "body": "Hello {couple_name},\n\nYour gallery is ready: {gallery_link}\n\nBest regards"
        }
        response = requests.post(f"{BASE_URL}/api/admin/email-templates", json=payload, headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Response should contain 'id'"
        assert data["name"] == unique_name, f"Name mismatch: {data['name']} != {unique_name}"
        assert data["subject"] == payload["subject"], "Subject mismatch"
        assert data["body"] == payload["body"], "Body mismatch"
        
        self.created_template_ids.append(data["id"])
        print(f"PASS: POST /api/admin/email-templates creates template with id={data['id']}")
        
        # Verify template appears in list
        list_response = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=self.headers)
        templates = list_response.json()
        found = any(t["id"] == data["id"] for t in templates)
        assert found, "Created template should appear in list"
        print("PASS: Created template appears in GET list")
    
    def test_create_template_validation(self):
        """POST /api/admin/email-templates validates required fields"""
        # Empty name
        response = requests.post(f"{BASE_URL}/api/admin/email-templates", json={
            "name": "", "subject": "Test", "body": "Test"
        }, headers=self.headers)
        assert response.status_code == 400, f"Expected 400 for empty name, got {response.status_code}"
        
        # Empty subject
        response = requests.post(f"{BASE_URL}/api/admin/email-templates", json={
            "name": "Test", "subject": "", "body": "Test"
        }, headers=self.headers)
        assert response.status_code == 400, f"Expected 400 for empty subject, got {response.status_code}"
        
        # Empty body
        response = requests.post(f"{BASE_URL}/api/admin/email-templates", json={
            "name": "Test", "subject": "Test", "body": ""
        }, headers=self.headers)
        assert response.status_code == 400, f"Expected 400 for empty body, got {response.status_code}"
        
        print("PASS: POST /api/admin/email-templates validates required fields")
    
    def test_update_template_success(self):
        """PUT /api/admin/email-templates/{id} updates an existing template"""
        # First create a template
        unique_name = f"TEST_Update_{uuid.uuid4().hex[:8]}"
        create_response = requests.post(f"{BASE_URL}/api/admin/email-templates", json={
            "name": unique_name,
            "subject": "Original Subject",
            "body": "Original Body"
        }, headers=self.headers)
        assert create_response.status_code == 200
        template_id = create_response.json()["id"]
        self.created_template_ids.append(template_id)
        
        # Update the template
        updated_name = f"TEST_Updated_{uuid.uuid4().hex[:8]}"
        update_response = requests.put(f"{BASE_URL}/api/admin/email-templates/{template_id}", json={
            "name": updated_name,
            "subject": "Updated Subject for {couple_name}",
            "body": "Updated Body with {gallery_link}"
        }, headers=self.headers)
        assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}: {update_response.text}"
        
        # Verify update by fetching list
        list_response = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=self.headers)
        templates = list_response.json()
        updated_template = next((t for t in templates if t["id"] == template_id), None)
        assert updated_template is not None, "Updated template should exist"
        assert updated_template["name"] == updated_name, f"Name not updated: {updated_template['name']}"
        assert updated_template["subject"] == "Updated Subject for {couple_name}", "Subject not updated"
        
        print(f"PASS: PUT /api/admin/email-templates/{template_id} updates template")
    
    def test_update_nonexistent_template(self):
        """PUT /api/admin/email-templates/{id} returns 404 for non-existent template"""
        response = requests.put(f"{BASE_URL}/api/admin/email-templates/nonexistent-id-12345", json={
            "name": "Test", "subject": "Test", "body": "Test"
        }, headers=self.headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: PUT /api/admin/email-templates returns 404 for non-existent template")
    
    def test_delete_template_success(self):
        """DELETE /api/admin/email-templates/{id} deletes a template"""
        # First create a template
        unique_name = f"TEST_Delete_{uuid.uuid4().hex[:8]}"
        create_response = requests.post(f"{BASE_URL}/api/admin/email-templates", json={
            "name": unique_name,
            "subject": "To Delete",
            "body": "Will be deleted"
        }, headers=self.headers)
        assert create_response.status_code == 200
        template_id = create_response.json()["id"]
        
        # Delete the template
        delete_response = requests.delete(f"{BASE_URL}/api/admin/email-templates/{template_id}", headers=self.headers)
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}"
        
        # Verify deletion
        list_response = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=self.headers)
        templates = list_response.json()
        found = any(t["id"] == template_id for t in templates)
        assert not found, "Deleted template should not appear in list"
        
        print(f"PASS: DELETE /api/admin/email-templates/{template_id} deletes template")
    
    def test_delete_nonexistent_template(self):
        """DELETE /api/admin/email-templates/{id} returns 404 for non-existent template"""
        response = requests.delete(f"{BASE_URL}/api/admin/email-templates/nonexistent-id-12345", headers=self.headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: DELETE /api/admin/email-templates returns 404 for non-existent template")


class TestSendTemplateEmail:
    """Test send-template-email endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get admin token"""
        login_response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.created_template_ids = []
        yield
        # Cleanup
        for tid in self.created_template_ids:
            try:
                requests.delete(f"{BASE_URL}/api/admin/email-templates/{tid}", headers=self.headers)
            except:
                pass
    
    def test_send_template_email_no_client_email(self):
        """POST /api/admin/galleries/{id}/send-template-email returns error if no client_email set"""
        # Get list of galleries
        galleries_response = requests.get(f"{BASE_URL}/api/admin/galleries", headers=self.headers)
        assert galleries_response.status_code == 200
        galleries = galleries_response.json()
        
        if not galleries:
            pytest.skip("No galleries available for testing")
        
        # Find a gallery without client_email or create test scenario
        # First, create a template
        unique_name = f"TEST_SendEmail_{uuid.uuid4().hex[:8]}"
        create_response = requests.post(f"{BASE_URL}/api/admin/email-templates", json={
            "name": unique_name,
            "subject": "Test Subject",
            "body": "Test Body"
        }, headers=self.headers)
        assert create_response.status_code == 200
        template_id = create_response.json()["id"]
        self.created_template_ids.append(template_id)
        
        # Try to find a gallery without client_email
        gallery_without_email = None
        for g in galleries:
            if not g.get("client_email"):
                gallery_without_email = g
                break
        
        if gallery_without_email:
            response = requests.post(
                f"{BASE_URL}/api/admin/galleries/{gallery_without_email['id']}/send-template-email",
                json={"template_id": template_id},
                headers=self.headers
            )
            assert response.status_code == 400, f"Expected 400, got {response.status_code}"
            assert "email" in response.json().get("detail", "").lower(), "Error should mention email"
            print("PASS: send-template-email returns 400 when no client_email set")
        else:
            print("SKIP: All galleries have client_email set, cannot test no-email scenario")
    
    def test_send_template_email_nonexistent_gallery(self):
        """POST /api/admin/galleries/{id}/send-template-email returns 404 for non-existent gallery"""
        response = requests.post(
            f"{BASE_URL}/api/admin/galleries/nonexistent-gallery-id/send-template-email",
            json={"template_id": "some-template-id"},
            headers=self.headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: send-template-email returns 404 for non-existent gallery")
    
    def test_send_template_email_nonexistent_template(self):
        """POST /api/admin/galleries/{id}/send-template-email returns 404 for non-existent template"""
        # Get a gallery
        galleries_response = requests.get(f"{BASE_URL}/api/admin/galleries", headers=self.headers)
        galleries = galleries_response.json()
        
        if not galleries:
            pytest.skip("No galleries available for testing")
        
        # Find a gallery with client_email
        gallery_with_email = None
        for g in galleries:
            if g.get("client_email"):
                gallery_with_email = g
                break
        
        if gallery_with_email:
            response = requests.post(
                f"{BASE_URL}/api/admin/galleries/{gallery_with_email['id']}/send-template-email",
                json={"template_id": "nonexistent-template-id"},
                headers=self.headers
            )
            assert response.status_code == 404, f"Expected 404, got {response.status_code}"
            print("PASS: send-template-email returns 404 for non-existent template")
        else:
            print("SKIP: No gallery with client_email found")


class TestRegressionShareLinks:
    """Regression tests for share links"""
    
    def test_share_link_works(self):
        """GET /api/share/{token} returns share data"""
        # Use the known share token from context
        share_token = "n7TdghPWGxKR6Pov9B8Hxg"
        response = requests.get(f"{BASE_URL}/api/share/{share_token}")
        # Should return 200 or require password (which is still a valid response)
        assert response.status_code in [200, 401], f"Expected 200 or 401, got {response.status_code}"
        print(f"PASS: Share link /api/share/{share_token} responds correctly (status={response.status_code})")


class TestRegressionBroadcast:
    """Regression tests for broadcast functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get admin token"""
        login_response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        assert login_response.status_code == 200
        self.token = login_response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_broadcast_preview_requires_auth(self):
        """GET /api/admin/broadcast-preview requires auth"""
        response = requests.get(f"{BASE_URL}/api/admin/broadcast-preview")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/admin/broadcast-preview requires auth")
    
    def test_broadcast_preview_works(self):
        """GET /api/admin/broadcast-preview returns recipients list"""
        response = requests.get(f"{BASE_URL}/api/admin/broadcast-preview", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "recipients" in data, "Response should contain 'recipients'"
        print(f"PASS: GET /api/admin/broadcast-preview returns {len(data.get('recipients', []))} recipients")


class TestRegressionLiveVisitors:
    """Regression tests for live visitors panel"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get admin token"""
        login_response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "admin",
            "password": "test123"
        })
        assert login_response.status_code == 200
        self.token = login_response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_live_visitors_endpoint(self):
        """GET /api/admin/live-visitors returns visitor data"""
        response = requests.get(f"{BASE_URL}/api/admin/live-visitors", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "visitors" in data, "Response should contain 'visitors'"
        print(f"PASS: GET /api/admin/live-visitors returns {len(data.get('visitors', []))} visitors")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
