#!/usr/bin/env python3

import requests
import json
import sys
import os
import io
import tempfile
from datetime import datetime
from pathlib import Path

class WeddingPhotographyGalleryTester:
    def __init__(self):
        # Use the public endpoint from frontend .env
        self.base_url = "https://wedding-photo-hub-2.preview.emergentagent.com/api"
        self.admin_token = None
        self.share_token = None
        self.test_template_id = None
        self.test_gallery_id = None
        self.test_file_id = None
        self.test_share_id = None
        self.test_share_token = None
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

    def make_request(self, method, endpoint, data=None, files=None, headers=None, use_share_token=False):
        """Make HTTP request with error handling"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        request_headers = {}
        if headers:
            request_headers.update(headers)
            
        # Set auth token
        token = self.share_token if use_share_token else self.admin_token
        if token:
            request_headers['Authorization'] = f'Bearer {token}'

        # Set content type for non-file requests
        if not files and method.upper() in ['POST', 'PUT']:
            request_headers['Content-Type'] = 'application/json'
            
        try:
            print(f"🌐 {method.upper()} {url}")
            if method.upper() == 'GET':
                response = requests.get(url, headers=request_headers, timeout=30)
            elif method.upper() == 'POST':
                if files:
                    # Remove Content-Type for multipart requests
                    request_headers.pop('Content-Type', None)
                    response = requests.post(url, files=files, data=data, headers=request_headers, timeout=60)
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
            return None

    def test_admin_setup_flow(self):
        """Test admin setup and login flow"""
        print("🔧 Testing Admin Setup Flow...")
        
        # Check setup status
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
                    self.log_result("Admin Setup", True, "Admin account created")
                else:
                    error_msg = response.json().get('detail') if response else "Setup failed"
                    self.log_result("Admin Setup", False, error=error_msg)
                    return False
            else:
                # Login with existing admin
                return self.test_admin_login()
        else:
            error_msg = response.json().get('detail') if response else "Check setup failed"
            self.log_result("Check Setup Status", False, error=error_msg)
            return False
        
        return True

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
            self.log_result("Admin Login", True, "Login successful")
            return True
        else:
            error_msg = response.json().get('detail') if response else "Login failed"
            self.log_result("Admin Login", False, error=error_msg)
            return False

    def test_templates(self):
        """Test template management"""
        print("📋 Testing Template Management...")
        
        if not self.admin_token:
            self.log_result("Template Tests", False, error="No admin token")
            return False

        # List templates (should have default)
        response = self.make_request('GET', '/admin/templates')
        if response and response.status_code == 200:
            templates = response.json()
            default_template = next((t for t in templates if t.get('is_default')), None)
            self.log_result("List Templates", True, f"Found {len(templates)} templates, default exists: {bool(default_template)}")
        else:
            error_msg = response.json().get('detail') if response else "List templates failed"
            self.log_result("List Templates", False, error=error_msg)

        # Create custom template
        template_data = {
            "name": "Custom Wedding Template",
            "subfolders": ["Ceremony", "Reception", "Portraits", "Guest Photos"]
        }
        response = self.make_request('POST', '/admin/templates', template_data)
        if response and response.status_code == 200:
            result = response.json()
            self.test_template_id = result.get('id')
            self.log_result("Create Template", True, f"Template created: {self.test_template_id}")
        else:
            error_msg = response.json().get('detail') if response else "Create template failed"
            self.log_result("Create Template", False, error=error_msg)

        return True

    def test_gallery_creation(self):
        """Test gallery creation (couple folder)"""
        print("📁 Testing Gallery Creation...")
        
        if not self.admin_token:
            self.log_result("Gallery Creation", False, error="No admin token")
            return False

        gallery_data = {
            "folder_name": "Gina & Mark 30.11.22",
            "template_id": self.test_template_id  # Use custom template if available
        }
        
        response = self.make_request('POST', '/admin/galleries', gallery_data)
        if response and response.status_code == 200:
            result = response.json()
            self.test_gallery_id = result.get('id')
            folder_name = result.get('folder_name')
            subfolders = result.get('subfolders', [])
            self.log_result("Create Gallery", True, f"Gallery created: {folder_name}, {len(subfolders)} subfolders")
        else:
            error_msg = response.json().get('detail') if response else "Create gallery failed"
            self.log_result("Create Gallery", False, error=error_msg)
            return False

        # List galleries
        response = self.make_request('GET', '/admin/galleries')
        if response and response.status_code == 200:
            galleries = response.json()
            self.log_result("List Galleries", True, f"Found {len(galleries)} galleries")
        else:
            error_msg = response.json().get('detail') if response else "List galleries failed"
            self.log_result("List Galleries", False, error=error_msg)

        # Get gallery detail
        if self.test_gallery_id:
            response = self.make_request('GET', f'/admin/galleries/{self.test_gallery_id}')
            if response and response.status_code == 200:
                gallery = response.json()
                files = gallery.get('files', [])
                shares = gallery.get('shares', [])
                self.log_result("Get Gallery Detail", True, f"Gallery has {len(files)} files, {len(shares)} shares")
            else:
                error_msg = response.json().get('detail') if response else "Get gallery failed"
                self.log_result("Get Gallery Detail", False, error=error_msg)

        return True

    def test_file_upload(self):
        """Test file upload with original filename preservation"""
        print("📷 Testing File Upload...")
        
        if not self.admin_token or not self.test_gallery_id:
            self.log_result("File Upload", False, error="No admin token or gallery ID")
            return False

        # First get the gallery to see what subfolders are available
        response = self.make_request('GET', f'/admin/galleries/{self.test_gallery_id}')
        if not response or response.status_code != 200:
            self.log_result("File Upload", False, error="Could not get gallery details for upload")
            return False
            
        gallery = response.json()
        subfolders = gallery.get('subfolders', [])
        if not subfolders:
            self.log_result("File Upload", False, error="No subfolders available for upload")
            return False
            
        # Use the first available subfolder
        target_subfolder = subfolders[0]

        # Create a small test image (1x1 pixel PNG)
        test_image_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01\xdd\x8d\xb4\x1c\x00\x00\x00\x00IEND\xaeB`\x82'
        
        files = {'files': ('test-wedding-photo.png', test_image_data, 'image/png')}
        data = {'subfolder': target_subfolder}
        
        response = self.make_request('POST', f'/admin/galleries/{self.test_gallery_id}/upload', 
                                   data=data, files=files)
        
        if response and response.status_code == 200:
            result = response.json()
            uploaded_files = result.get('uploaded', [])
            if uploaded_files:
                self.test_file_id = uploaded_files[0].get('id')
                original_filename = uploaded_files[0].get('original_filename')
                preserved_filename = uploaded_files[0].get('filename')
                self.log_result("File Upload", True, 
                              f"Uploaded to '{target_subfolder}': {len(uploaded_files)} file(s), original: {original_filename}, preserved: {preserved_filename}")
            else:
                self.log_result("File Upload", False, error="No files uploaded")
        else:
            error_msg = response.json().get('detail') if response else "File upload failed"
            self.log_result("File Upload", False, error=error_msg)
            return False

        return True

    def test_share_creation(self):
        """Test share creation with different configurations"""
        print("🔗 Testing Share Creation...")
        
        if not self.admin_token or not self.test_gallery_id:
            self.log_result("Share Creation", False, error="No admin token or gallery ID")
            return False

        # Get gallery details to find available subfolders
        response = self.make_request('GET', f'/admin/galleries/{self.test_gallery_id}')
        if not response or response.status_code != 200:
            self.log_result("Share Creation", False, error="Could not get gallery details")
            return False
            
        gallery = response.json()
        subfolders = gallery.get('subfolders', [])

        # Create password-protected share for whole gallery
        share_data = {
            "gallery_id": self.test_gallery_id,
            "subfolder": None,  # Whole gallery
            "password": "wedding123",
            "allow_uploads": False,
            "label": "Gina & Mark's Gallery"
        }
        
        response = self.make_request('POST', f'/admin/galleries/{self.test_gallery_id}/shares', share_data)
        if response and response.status_code == 200:
            result = response.json()
            self.test_share_id = result.get('id')
            self.test_share_token = result.get('token')
            has_password = result.get('has_password')
            self.log_result("Create Password Share", True, 
                          f"Share created: {self.test_share_token[:10]}..., password protected: {has_password}")
        else:
            error_msg = response.json().get('detail') if response else "Create share failed"
            self.log_result("Create Password Share", False, error=error_msg)
            return False

        # Create open share for guest uploads - use the last subfolder or create a generic one
        guest_subfolder = subfolders[-1] if subfolders else None  # Use last subfolder
        guest_share_data = {
            "gallery_id": self.test_gallery_id,
            "subfolder": guest_subfolder,
            "password": None,  # No password
            "allow_uploads": True,
            "label": "Upload Your Photos"
        }
        
        response = self.make_request('POST', f'/admin/galleries/{self.test_gallery_id}/shares', guest_share_data)
        if response and response.status_code == 200:
            result = response.json()
            self.log_result("Create Guest Upload Share", True, f"Guest upload share created for '{guest_subfolder}'")
        else:
            error_msg = response.json().get('detail') if response else "Create guest share failed"
            self.log_result("Create Guest Upload Share", False, error=error_msg)

        return True

    def test_qr_code_generation(self):
        """Test QR code generation"""
        if not self.admin_token or not self.test_share_id:
            self.log_result("QR Code Generation", False, error="No admin token or share ID")
            return False

        base_url = "https://wedding-photo-hub-2.preview.emergentagent.com"
        response = self.make_request('GET', f'/admin/shares/{self.test_share_id}/qr?base_url={base_url}')
        
        if response and response.status_code == 200:
            # Check if response is PNG image
            content_type = response.headers.get('content-type', '')
            if 'image/png' in content_type:
                self.log_result("QR Code Generation", True, "QR code PNG generated successfully")
            else:
                self.log_result("QR Code Generation", False, error=f"Expected PNG, got {content_type}")
        else:
            error_msg = response.json().get('detail') if response else "QR generation failed"
            self.log_result("QR Code Generation", False, error=error_msg)

        return True

    def test_share_toggle(self):
        """Test share active status toggle"""
        if not self.admin_token or not self.test_share_id:
            self.log_result("Share Toggle", False, error="No admin token or share ID")
            return False

        # Toggle to inactive first
        response = self.make_request('PUT', f'/admin/shares/{self.test_share_id}/toggle')
        if response and response.status_code == 200:
            result = response.json()
            is_active = result.get('is_active')
            self.log_result("Share Toggle (Deactivate)", True, f"Share deactivated, active: {is_active}")
            
            # Toggle back to active for subsequent tests
            response2 = self.make_request('PUT', f'/admin/shares/{self.test_share_id}/toggle')
            if response2 and response2.status_code == 200:
                result2 = response2.json()
                is_active2 = result2.get('is_active')
                self.log_result("Share Toggle (Reactivate)", True, f"Share reactivated, active: {is_active2}")
            else:
                self.log_result("Share Toggle (Reactivate)", False, error="Could not reactivate share")
        else:
            error_msg = response.json().get('detail') if response else "Share toggle failed"
            self.log_result("Share Toggle", False, error=error_msg)

        return True

    def test_public_share_access(self):
        """Test public share access flow"""
        print("👥 Testing Public Share Access...")
        
        if not self.test_share_token:
            self.log_result("Public Share Access", False, error="No share token")
            return False

        # Get share info
        response = self.make_request('GET', f'/share/{self.test_share_token}')
        if response and response.status_code == 200:
            share_info = response.json()
            gallery_name = share_info.get('gallery_name')
            has_password = share_info.get('has_password')
            file_count = share_info.get('file_count')
            self.log_result("Get Share Info", True, 
                          f"Gallery: {gallery_name}, password: {has_password}, files: {file_count}")
        else:
            error_msg = response.json().get('detail') if response else "Get share info failed"
            self.log_result("Get Share Info", False, error=error_msg)
            return False

        # Access share with password
        access_data = {"password": "wedding123"}
        response = self.make_request('POST', f'/share/{self.test_share_token}/access', access_data)
        if response and response.status_code == 200:
            result = response.json()
            self.share_token = result.get('jwt')
            gallery_name = result.get('gallery_name')
            self.log_result("Share Access", True, f"Access granted for {gallery_name}")
        else:
            error_msg = response.json().get('detail') if response else "Share access failed"
            self.log_result("Share Access", False, error=error_msg)
            return False

        return True

    def test_share_files_retrieval(self):
        """Test retrieving files through share"""
        if not self.share_token or not self.test_share_token:
            self.log_result("Share Files Retrieval", False, error="No share token")
            return False

        response = self.make_request('GET', f'/share/{self.test_share_token}/files', use_share_token=True)
        if response and response.status_code == 200:
            result = response.json()
            subfolders = result.get('subfolders', [])
            total_files = sum(len(sf.get('files', [])) for sf in subfolders)
            self.log_result("Share Files Retrieval", True, 
                          f"Retrieved {len(subfolders)} subfolders with {total_files} total files")
        else:
            error_msg = response.json().get('detail') if response else "Share files retrieval failed"
            self.log_result("Share Files Retrieval", False, error=error_msg)

        return True

    def test_favourite_toggle(self):
        """Test favourite toggle functionality"""
        if not self.share_token or not self.test_share_token or not self.test_file_id:
            self.log_result("Favourite Toggle", False, error="Missing tokens or file ID")
            return False

        favourite_data = {"file_id": self.test_file_id}
        response = self.make_request('POST', f'/share/{self.test_share_token}/favourite', 
                                   favourite_data, use_share_token=True)
        
        if response and response.status_code == 200:
            result = response.json()
            favourited = result.get('favourited')
            self.log_result("Favourite Toggle", True, f"File favourited: {favourited}")
        else:
            error_msg = response.json().get('detail') if response else "Favourite toggle failed"
            self.log_result("Favourite Toggle", False, error=error_msg)

        return True

    def test_guest_upload(self):
        """Test guest upload functionality"""
        print("📤 Testing Guest Upload...")
        
        # First create a guest upload share with an available subfolder
        if not self.admin_token or not self.test_gallery_id:
            self.log_result("Guest Upload Setup", False, error="No admin token or gallery")
            return False

        # Get available subfolders
        response = self.make_request('GET', f'/admin/galleries/{self.test_gallery_id}')
        if not response or response.status_code != 200:
            self.log_result("Guest Upload Setup", False, error="Could not get gallery details")
            return False
            
        gallery = response.json()
        subfolders = gallery.get('subfolders', [])
        if not subfolders:
            self.log_result("Guest Upload Setup", False, error="No subfolders available")
            return False
            
        # Use the first available subfolder for guest uploads
        guest_subfolder = subfolders[0]
        
        guest_share_data = {
            "gallery_id": self.test_gallery_id,
            "subfolder": guest_subfolder,
            "password": None,
            "allow_uploads": True,
            "label": "Test Guest Upload"
        }
        
        response = self.make_request('POST', f'/admin/galleries/{self.test_gallery_id}/shares', guest_share_data)
        if response and response.status_code == 200:
            guest_share = response.json()
            guest_token = guest_share.get('token')
            
            # Get access to guest share (no password)
            access_response = self.make_request('GET', f'/share/{guest_token}/open-access')
            if access_response and access_response.status_code == 200:
                access_result = access_response.json()
                guest_jwt = access_result.get('jwt')
                
                # Test guest upload
                test_image_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01\xdd\x8d\xb4\x1c\x00\x00\x00\x00IEND\xaeB`\x82'
                files = {'files': ('guest-photo.png', test_image_data, 'image/png')}
                
                # Temporarily use guest JWT
                temp_share_token = self.share_token
                self.share_token = guest_jwt
                
                upload_response = self.make_request('POST', f'/share/{guest_token}/upload', 
                                                  files=files, use_share_token=True)
                
                if upload_response and upload_response.status_code == 200:
                    upload_result = upload_response.json()
                    uploaded_count = len(upload_result.get('uploaded', []))
                    self.log_result("Guest Upload", True, f"Guest uploaded {uploaded_count} file(s) to '{guest_subfolder}'")
                else:
                    error_msg = upload_response.json().get('detail') if upload_response else "Guest upload failed"
                    self.log_result("Guest Upload", False, error=error_msg)
                
                # Restore original share token
                self.share_token = temp_share_token
            else:
                self.log_result("Guest Upload Access", False, error="Could not access guest share")
        else:
            error_msg = response.json().get('detail') if response else "Could not create guest upload share"
            self.log_result("Guest Upload Setup", False, error=error_msg)

        return True

    def test_downloads(self):
        """Test download functionality"""
        if not self.share_token or not self.test_share_token:
            self.log_result("Downloads", False, error="No share token")
            return False

        # Test single file download
        if self.test_file_id:
            response = self.make_request('GET', f'/share/{self.test_share_token}/download/{self.test_file_id}', 
                                       use_share_token=True)
            if response and response.status_code == 200:
                self.log_result("Single File Download", True, "File downloaded successfully")
            else:
                error_msg = response.json().get('detail') if response else "Single download failed"
                self.log_result("Single File Download", False, error=error_msg)

        # Test ZIP download
        response = self.make_request('POST', f'/share/{self.test_share_token}/download-zip', 
                                   [], use_share_token=True)
        if response and response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if 'zip' in content_type.lower():
                self.log_result("ZIP Download", True, "ZIP download successful")
            else:
                self.log_result("ZIP Download", False, error=f"Expected ZIP, got {content_type}")
        else:
            error_msg = response.json().get('detail') if response else "ZIP download failed"
            self.log_result("ZIP Download", False, error=error_msg)

        return True

    def test_file_deletion(self):
        """Test file deletion"""
        if not self.admin_token or not self.test_gallery_id or not self.test_file_id:
            self.log_result("File Deletion", False, error="Missing required IDs")
            return False

        response = self.make_request('DELETE', f'/admin/galleries/{self.test_gallery_id}/files/{self.test_file_id}')
        if response and response.status_code == 200:
            self.log_result("File Deletion", True, "File deleted successfully")
        else:
            error_msg = response.json().get('detail') if response else "File deletion failed"
            self.log_result("File Deletion", False, error=error_msg)

        return True

    def cleanup_test_data(self):
        """Clean up test data"""
        if self.admin_token:
            print("🧹 Cleaning up test data...")
            
            # Delete test gallery (cascades to files and shares)
            if self.test_gallery_id:
                response = self.make_request('DELETE', f'/admin/galleries/{self.test_gallery_id}')
                if response and response.status_code == 200:
                    self.log_result("Cleanup Gallery", True, "Test gallery deleted")
                else:
                    self.log_result("Cleanup Gallery", False, error="Failed to delete test gallery")
            
            # Delete test template
            if self.test_template_id:
                response = self.make_request('DELETE', f'/admin/templates/{self.test_template_id}')
                if response and response.status_code == 200:
                    self.log_result("Cleanup Template", True, "Test template deleted")
                else:
                    self.log_result("Cleanup Template", False, error="Failed to delete test template")

    def run_all_tests(self):
        """Run comprehensive test suite"""
        print("🚀 Starting Wedding Photography Gallery System Tests...")
        print(f"🌐 Testing against: {self.base_url}")
        print("=" * 70)
        
        try:
            # Core admin flow
            if not self.test_admin_setup_flow():
                print("❌ Admin setup failed - stopping tests")
                return False
            
            # Template management
            self.test_templates()
            
            # Gallery management
            self.test_gallery_creation()
            
            # File operations
            self.test_file_upload()
            
            # Share management
            self.test_share_creation()
            self.test_qr_code_generation()
            self.test_share_toggle()
            
            # Public share access
            self.test_public_share_access()
            self.test_share_files_retrieval()
            self.test_favourite_toggle()
            
            # Guest features
            self.test_guest_upload()
            
            # Downloads
            self.test_downloads()
            
            # Cleanup operations
            self.test_file_deletion()
            
        finally:
            # Always cleanup
            self.cleanup_test_data()
        
        # Print summary
        print("=" * 70)
        print(f"📊 TEST SUMMARY")
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {len(self.failed_tests)}")
        
        if self.tests_run > 0:
            success_rate = (self.tests_passed / self.tests_run * 100)
            print(f"Success Rate: {success_rate:.1f}%")
        
        if self.failed_tests:
            print("\n❌ FAILED TESTS:")
            for failure in self.failed_tests:
                print(f"  - {failure['test']}: {failure['error']}")
        
        print("\n🎯 BACKEND API TESTING COMPLETE")
        return len(self.failed_tests) == 0

def main():
    """Main test runner"""
    tester = WeddingPhotographyGalleryTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())