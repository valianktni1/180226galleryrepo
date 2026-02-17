#!/usr/bin/env python3

import requests
import json
import sys
import os
import io
from datetime import datetime
from pathlib import Path

class WeddingGalleryTester:
    def __init__(self):
        # Use the public endpoint from frontend .env
        self.base_url = "https://couples-ceremony-hub.preview.emergentagent.com/api"
        self.admin_token = None
        self.client_token = None
        self.test_gallery_id = None
        self.test_gallery_slug = None
        self.test_photo_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def log_result(self, test_name, success, response=None, error=None):
        """Log test results"""
        self.tests_run += 1
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {test_name}")
        
        if success:
            self.tests_passed += 1
        else:
            self.failed_tests.append({
                "test": test_name,
                "error": error or "Unknown error",
                "response": response
            })
            if error:
                print(f"   Error: {error}")
            if response:
                print(f"   Response: {response}")
        print()

    def make_request(self, method, endpoint, data=None, files=None, headers=None):
        """Make HTTP request with error handling"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        request_headers = {'Content-Type': 'application/json'}
        if headers:
            request_headers.update(headers)
            
        if self.admin_token:
            request_headers['Authorization'] = f'Bearer {self.admin_token}'
        elif self.client_token:
            request_headers['Authorization'] = f'Bearer {self.client_token}'
            
        try:
            print(f"🌐 {method.upper()} {url}")
            if method.upper() == 'GET':
                response = requests.get(url, headers=request_headers, timeout=30)
            elif method.upper() == 'POST':
                if files:
                    # Remove Content-Type for multipart requests
                    request_headers.pop('Content-Type', None)
                    response = requests.post(url, files=files, headers=request_headers, timeout=60)
                else:
                    response = requests.post(url, json=data, headers=request_headers, timeout=30)
            elif method.upper() == 'PUT':
                response = requests.put(url, json=data, headers=request_headers, timeout=30)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=request_headers, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")
                
            print(f"   Status: {response.status_code}")
            if response.status_code >= 400:
                try:
                    error_detail = response.json()
                    print(f"   Error Response: {error_detail}")
                except:
                    print(f"   Error Text: {response.text}")
            
            return response
            
        except requests.exceptions.RequestException as e:
            print(f"   Request Exception: {str(e)}")
            return None, str(e)

    def test_admin_setup(self):
        """Test admin setup flow"""
        print("🔧 Testing Admin Setup Flow...")
        
        # Check if admin is already setup
        response = self.make_request('GET', '/admin/check-setup')
        if response and response.status_code == 200:
            setup_complete = response.json().get('setup_complete', False)
            self.log_result("Check Setup Status", True, f"Setup complete: {setup_complete}")
            
            if not setup_complete:
                # Setup admin
                setup_data = {
                    "username": "admin",
                    "password": "test1234",
                    "display_name": "Weddings By Mark"
                }
                response = self.make_request('POST', '/admin/setup', setup_data)
                
                if response and response.status_code == 200:
                    result = response.json()
                    self.admin_token = result.get('token')
                    self.log_result("Admin Setup", True, f"Admin created with token")
                else:
                    error_msg = response.json().get('detail') if response else "Setup failed"
                    self.log_result("Admin Setup", False, error=error_msg)
            else:
                # Admin already exists, try to login
                self.test_admin_login()
        else:
            error_msg = response.json().get('detail') if response else "Check setup failed"
            self.log_result("Check Setup Status", False, error=error_msg)

    def test_admin_login(self):
        """Test admin login"""
        print("🔑 Testing Admin Login...")
        
        login_data = {
            "username": "admin",
            "password": "test1234"
        }
        
        response = self.make_request('POST', '/admin/login', login_data)
        
        if response and response.status_code == 200:
            result = response.json()
            self.admin_token = result.get('token')
            print(f"   Token received: {self.admin_token[:20]}..." if self.admin_token else "   No token in response")
            self.log_result("Admin Login", True, f"Login successful")
        else:
            error_msg = response.json().get('detail') if response else "Login failed"
            self.log_result("Admin Login", False, error=error_msg)

    def test_admin_me(self):
        """Test admin profile retrieval"""
        if not self.admin_token:
            self.log_result("Admin Profile", False, error="No admin token")
            return
            
        response = self.make_request('GET', '/admin/me')
        
        if response and response.status_code == 200:
            result = response.json()
            self.log_result("Admin Profile", True, f"Profile retrieved: {result.get('username')}")
        else:
            error_msg = response.json().get('detail') if response else "Profile retrieval failed"
            self.log_result("Admin Profile", False, error=error_msg)

    def test_gallery_crud(self):
        """Test gallery CRUD operations"""
        print("📁 Testing Gallery CRUD Operations...")
        
        if not self.admin_token:
            self.log_result("Gallery CRUD", False, error="No admin token")
            return

        # Create gallery
        gallery_data = {
            "title": "Test Wedding Gallery",
            "couple_names": "John & Jane Doe",
            "wedding_date": "2024-06-15",
            "password": "wedding123",
            "description": "Beautiful wedding day",
            "is_active": True
        }
        
        response = self.make_request('POST', '/admin/galleries', gallery_data)
        
        if response and response.status_code == 200:
            result = response.json()
            self.test_gallery_id = result.get('id')
            self.test_gallery_slug = result.get('slug')
            self.log_result("Create Gallery", True, f"Gallery created: {self.test_gallery_id}")
        else:
            error_msg = response.json().get('detail') if response else "Gallery creation failed"
            self.log_result("Create Gallery", False, error=error_msg)
            return

        # List galleries
        response = self.make_request('GET', '/admin/galleries')
        
        if response and response.status_code == 200:
            galleries = response.json()
            self.log_result("List Galleries", True, f"Found {len(galleries)} galleries")
        else:
            error_msg = response.json().get('detail') if response else "List galleries failed"
            self.log_result("List Galleries", False, error=error_msg)

        # Get specific gallery
        if self.test_gallery_id:
            response = self.make_request('GET', f'/admin/galleries/{self.test_gallery_id}')
            
            if response and response.status_code == 200:
                gallery = response.json()
                self.log_result("Get Gallery", True, f"Gallery retrieved: {gallery.get('title')}")
            else:
                error_msg = response.json().get('detail') if response else "Get gallery failed"
                self.log_result("Get Gallery", False, error=error_msg)

        # Update gallery
        if self.test_gallery_id:
            update_data = {
                "description": "Updated description for testing"
            }
            response = self.make_request('PUT', f'/admin/galleries/{self.test_gallery_id}', update_data)
            
            if response and response.status_code == 200:
                updated = response.json()
                self.log_result("Update Gallery", True, f"Gallery updated")
            else:
                error_msg = response.json().get('detail') if response else "Update gallery failed"
                self.log_result("Update Gallery", False, error=error_msg)

    def test_photo_upload(self):
        """Test photo upload functionality"""
        print("📷 Testing Photo Upload...")
        
        if not self.admin_token or not self.test_gallery_id:
            self.log_result("Photo Upload", False, error="No admin token or gallery ID")
            return

        # Create a small test image (1x1 pixel PNG)
        test_image_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01\xdd\x8d\xb4\x1c\x00\x00\x00\x00IEND\xaeB`\x82'
        
        files = {
            'files': ('test.png', test_image_data, 'image/png')
        }
        
        response = self.make_request('POST', f'/admin/galleries/{self.test_gallery_id}/upload', files=files)
        
        if response and response.status_code == 200:
            result = response.json()
            uploaded_photos = result.get('uploaded', [])
            if uploaded_photos:
                self.test_photo_id = uploaded_photos[0].get('id')
                self.log_result("Photo Upload", True, f"Uploaded {len(uploaded_photos)} photo(s)")
            else:
                self.log_result("Photo Upload", False, error="No photos uploaded")
        else:
            error_msg = response.json().get('detail') if response else "Photo upload failed"
            self.log_result("Photo Upload", False, error=error_msg)

    def test_photo_delete(self):
        """Test photo deletion"""
        if not self.admin_token or not self.test_gallery_id or not self.test_photo_id:
            self.log_result("Photo Delete", False, error="Missing required IDs for photo delete")
            return

        response = self.make_request('DELETE', f'/admin/galleries/{self.test_gallery_id}/photos/{self.test_photo_id}')
        
        if response and response.status_code == 200:
            self.log_result("Photo Delete", True, "Photo deleted successfully")
        else:
            error_msg = response.json().get('detail') if response else "Photo delete failed"
            self.log_result("Photo Delete", False, error=error_msg)

    def test_media_serving(self):
        """Test media file serving"""
        if not self.test_gallery_id:
            self.log_result("Media Serving", False, error="No gallery ID for media test")
            return

        # Test with a non-existent file - should return 404
        response = self.make_request('GET', f'/media/{self.test_gallery_id}/thumbnails/nonexistent.jpg')
        
        if response and response.status_code == 404:
            self.log_result("Media Serving (404 Test)", True, "Correctly returns 404 for non-existent files")
        else:
            self.log_result("Media Serving (404 Test)", False, error=f"Expected 404, got {response.status_code if response else 'no response'}")

    def test_client_access(self):
        """Test client gallery access"""
        print("👥 Testing Client Access Flow...")
        
        if not self.test_gallery_slug:
            self.log_result("Client Access", False, error="No gallery slug for client access test")
            return

        # Get gallery info (public)
        response = self.make_request('GET', f'/galleries/{self.test_gallery_slug}')
        
        if response and response.status_code == 200:
            gallery_info = response.json()
            self.log_result("Get Gallery Info", True, f"Gallery info retrieved: {gallery_info.get('title')}")
        else:
            error_msg = response.json().get('detail') if response else "Get gallery info failed"
            self.log_result("Get Gallery Info", False, error=error_msg)

        # Access gallery with password
        access_data = {"password": "wedding123"}
        response = self.make_request('POST', f'/galleries/{self.test_gallery_slug}/access', access_data)
        
        if response and response.status_code == 200:
            result = response.json()
            self.client_token = result.get('token')
            self.log_result("Gallery Access", True, "Client access successful")
        else:
            error_msg = response.json().get('detail') if response else "Gallery access failed"
            self.log_result("Gallery Access", False, error=error_msg)

    def test_client_photos(self):
        """Test client photo retrieval"""
        if not self.client_token or not self.test_gallery_slug:
            self.log_result("Client Photos", False, error="No client token or gallery slug")
            return

        # Clear admin token to use client token
        temp_admin_token = self.admin_token
        self.admin_token = None
        
        response = self.make_request('GET', f'/galleries/{self.test_gallery_slug}/photos')
        
        if response and response.status_code == 200:
            result = response.json()
            photos = result.get('photos', [])
            self.log_result("Client Photo Retrieval", True, f"Retrieved {len(photos)} photos")
        else:
            error_msg = response.json().get('detail') if response else "Client photo retrieval failed"
            self.log_result("Client Photo Retrieval", False, error=error_msg)

        # Restore admin token
        self.admin_token = temp_admin_token

    def test_favourite_toggle(self):
        """Test photo favouriting"""
        if not self.client_token or not self.test_gallery_slug or not self.test_photo_id:
            self.log_result("Favourite Toggle", False, error="Missing tokens/IDs for favourite test")
            return

        # Clear admin token to use client token
        temp_admin_token = self.admin_token
        self.admin_token = None
        
        favourite_data = {"photo_id": self.test_photo_id}
        response = self.make_request('POST', f'/galleries/{self.test_gallery_slug}/favourite', favourite_data)
        
        if response and response.status_code == 200:
            result = response.json()
            favourited = result.get('favourited', False)
            self.log_result("Favourite Toggle", True, f"Favourite toggled: {favourited}")
        else:
            error_msg = response.json().get('detail') if response else "Favourite toggle failed"
            self.log_result("Favourite Toggle", False, error=error_msg)

        # Restore admin token
        self.admin_token = temp_admin_token

    def test_downloads(self):
        """Test download functionality"""
        if not self.client_token or not self.test_gallery_slug:
            self.log_result("Download Tests", False, error="Missing client token or gallery slug")
            return

        # Clear admin token to use client token
        temp_admin_token = self.admin_token
        self.admin_token = None

        # Test zip download (empty payload for all photos)
        response = self.make_request('POST', f'/galleries/{self.test_gallery_slug}/download-zip', [])
        
        if response and response.status_code == 200:
            self.log_result("Download Zip", True, "Zip download successful")
        else:
            error_msg = response.json().get('detail') if response else "Zip download failed"
            self.log_result("Download Zip", False, error=error_msg)

        # Test single photo download if we have a photo ID
        if self.test_photo_id:
            response = self.make_request('GET', f'/galleries/{self.test_gallery_slug}/download/{self.test_photo_id}')
            
            if response and response.status_code == 200:
                self.log_result("Single Photo Download", True, "Single photo download successful")
            else:
                error_msg = response.json().get('detail') if response else "Single photo download failed"
                self.log_result("Single Photo Download", False, error=error_msg)

        # Restore admin token
        self.admin_token = temp_admin_token

    def cleanup_test_data(self):
        """Clean up test gallery"""
        if self.admin_token and self.test_gallery_id:
            print("🧹 Cleaning up test data...")
            response = self.make_request('DELETE', f'/admin/galleries/{self.test_gallery_id}')
            
            if response and response.status_code == 200:
                self.log_result("Cleanup Test Gallery", True, "Test gallery deleted")
            else:
                self.log_result("Cleanup Test Gallery", False, error="Failed to delete test gallery")

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting Wedding Gallery API Tests...")
        print(f"🌐 Testing against: {self.base_url}")
        print("=" * 60)
        
        try:
            # Admin flow tests
            self.test_admin_setup()
            self.test_admin_me()
            
            # Gallery CRUD tests
            self.test_gallery_crud()
            
            # Photo management tests
            self.test_photo_upload()
            self.test_media_serving()
            
            # Client access tests
            self.test_client_access()
            self.test_client_photos()
            self.test_favourite_toggle()
            self.test_downloads()
            
            # Photo deletion (after other tests)
            self.test_photo_delete()
            
        finally:
            # Cleanup
            self.cleanup_test_data()
        
        # Print summary
        print("=" * 60)
        print(f"📊 TEST SUMMARY")
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {len(self.failed_tests)}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        
        if self.failed_tests:
            print("\n❌ FAILED TESTS:")
            for failure in self.failed_tests:
                print(f"  - {failure['test']}: {failure['error']}")
        
        return len(self.failed_tests) == 0

def main():
    """Main test runner"""
    tester = WeddingGalleryTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())