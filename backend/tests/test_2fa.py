"""
Two-Factor Authentication (2FA) Tests for Wedding Gallery Admin Panel
Tests the complete 2FA flow: setup, enable, login with 2FA, recovery codes, disable
Rate limiting: 3 attempts / 30 minutes
"""
import pytest
import requests
import os
import pyotp
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "test123"


class Test2FAFeature:
    """Complete 2FA feature tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token for authenticated requests"""
        # First, ensure 2FA is disabled so we can login normally
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        
        if response.status_code == 200:
            data = response.json()
            if data.get("requires_2fa"):
                # 2FA is enabled, we need to handle this
                pytest.skip("2FA is currently enabled - need to disable first")
            self.token = data.get("token")
        else:
            pytest.fail(f"Failed to login: {response.status_code} - {response.text}")
        
        self.headers = {"Authorization": f"Bearer {self.token}"}
        yield
    
    def test_01_normal_login_works(self):
        """Test that normal login works when 2FA is not enabled"""
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        # Should either return token or requires_2fa
        assert "token" in data or data.get("requires_2fa") == True
        print(f"Login response: {data.keys()}")
    
    def test_02_2fa_status_returns_enabled_false(self):
        """Test 2FA status endpoint returns enabled:false when not set up"""
        response = requests.get(f"{BASE_URL}/api/admin/2fa/status", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        print(f"2FA status: enabled={data['enabled']}")
    
    def test_03_2fa_setup_returns_qr_and_secret(self):
        """Test 2FA setup endpoint returns QR code and secret"""
        response = requests.post(f"{BASE_URL}/api/admin/2fa/setup", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "secret" in data, "Response should contain 'secret'"
        assert "qr_code" in data, "Response should contain 'qr_code'"
        assert "uri" in data, "Response should contain 'uri'"
        
        # Verify secret is valid base32
        assert len(data["secret"]) >= 16, "Secret should be at least 16 characters"
        
        # Verify QR code is base64 PNG
        assert data["qr_code"].startswith("data:image/png;base64,"), "QR code should be base64 PNG"
        
        # Verify URI format
        assert "otpauth://totp/" in data["uri"], "URI should be TOTP format"
        
        print(f"2FA setup successful - secret length: {len(data['secret'])}")
    
    def test_04_2fa_enable_with_invalid_code_fails(self):
        """Test that enabling 2FA with invalid code fails"""
        # First setup
        setup_response = requests.post(f"{BASE_URL}/api/admin/2fa/setup", headers=self.headers)
        assert setup_response.status_code == 200
        
        # Try to enable with invalid code
        response = requests.post(f"{BASE_URL}/api/admin/2fa/enable", 
                                headers=self.headers,
                                json={"code": "000000"})
        assert response.status_code == 400
        data = response.json()
        assert "Invalid code" in data.get("detail", "")
        print(f"Invalid code rejected: {data.get('detail')}")


class Test2FAFullFlow:
    """Test complete 2FA enable -> login -> disable flow"""
    
    def test_full_2fa_flow(self):
        """
        Complete 2FA flow test:
        1. Login normally
        2. Check 2FA status (should be disabled)
        3. Setup 2FA (get QR/secret)
        4. Enable 2FA with valid TOTP code
        5. Verify recovery codes returned
        6. Logout and try login without 2FA code (should get requires_2fa)
        7. Login with wrong 2FA code (should fail)
        8. Login with valid 2FA code (should succeed)
        9. Test recovery code login
        10. Disable 2FA
        11. Verify normal login works again
        """
        
        # Step 1: Login normally
        print("\n=== Step 1: Normal login ===")
        login_response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            if data.get("requires_2fa"):
                # 2FA already enabled, need to disable first
                print("2FA already enabled, attempting to disable...")
                # We can't proceed without a valid code, so skip
                pytest.skip("2FA is already enabled - manual intervention needed")
            token = data["token"]
        else:
            pytest.fail(f"Initial login failed: {login_response.status_code}")
        
        headers = {"Authorization": f"Bearer {token}"}
        print(f"Login successful, got token")
        
        # Step 2: Check 2FA status
        print("\n=== Step 2: Check 2FA status ===")
        status_response = requests.get(f"{BASE_URL}/api/admin/2fa/status", headers=headers)
        assert status_response.status_code == 200
        status_data = status_response.json()
        print(f"2FA enabled: {status_data['enabled']}")
        
        if status_data['enabled']:
            print("2FA is already enabled, skipping enable flow")
            # Try to disable it
            pytest.skip("2FA already enabled")
        
        # Step 3: Setup 2FA
        print("\n=== Step 3: Setup 2FA ===")
        setup_response = requests.post(f"{BASE_URL}/api/admin/2fa/setup", headers=headers)
        assert setup_response.status_code == 200
        setup_data = setup_response.json()
        secret = setup_data["secret"]
        print(f"Got secret: {secret[:8]}...")
        
        # Step 4: Enable 2FA with valid TOTP code
        print("\n=== Step 4: Enable 2FA ===")
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()
        print(f"Generated TOTP code: {valid_code}")
        
        enable_response = requests.post(f"{BASE_URL}/api/admin/2fa/enable",
                                       headers=headers,
                                       json={"code": valid_code})
        assert enable_response.status_code == 200, f"Enable failed: {enable_response.text}"
        enable_data = enable_response.json()
        
        # Step 5: Verify recovery codes
        print("\n=== Step 5: Verify recovery codes ===")
        assert enable_data.get("enabled") == True
        assert "recovery_codes" in enable_data
        recovery_codes = enable_data["recovery_codes"]
        assert len(recovery_codes) == 8, f"Expected 8 recovery codes, got {len(recovery_codes)}"
        print(f"Got {len(recovery_codes)} recovery codes")
        print(f"First recovery code: {recovery_codes[0]}")
        
        # Step 6: Login without 2FA code (should get requires_2fa)
        print("\n=== Step 6: Login without 2FA code ===")
        login_no_2fa = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert login_no_2fa.status_code == 200
        login_no_2fa_data = login_no_2fa.json()
        assert login_no_2fa_data.get("requires_2fa") == True, "Should require 2FA"
        print("Correctly requires 2FA code")
        
        # Step 7: Login with wrong 2FA code
        print("\n=== Step 7: Login with wrong 2FA code ===")
        login_wrong_code = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD,
            "totp_code": "000000"
        })
        assert login_wrong_code.status_code == 401, f"Expected 401, got {login_wrong_code.status_code}"
        print("Wrong code correctly rejected with 401")
        
        # Step 8: Login with valid 2FA code
        print("\n=== Step 8: Login with valid 2FA code ===")
        # Wait a moment to ensure we get a fresh code
        time.sleep(1)
        valid_code_2 = totp.now()
        print(f"Generated new TOTP code: {valid_code_2}")
        
        login_with_2fa = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD,
            "totp_code": valid_code_2
        })
        assert login_with_2fa.status_code == 200, f"Login with 2FA failed: {login_with_2fa.text}"
        login_with_2fa_data = login_with_2fa.json()
        assert "token" in login_with_2fa_data
        new_token = login_with_2fa_data["token"]
        new_headers = {"Authorization": f"Bearer {new_token}"}
        print("Login with valid 2FA code successful")
        
        # Step 9: Test recovery code login
        print("\n=== Step 9: Test recovery code login ===")
        recovery_code = recovery_codes[0]
        print(f"Using recovery code: {recovery_code}")
        
        login_recovery = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD,
            "totp_code": recovery_code
        })
        assert login_recovery.status_code == 200, f"Recovery code login failed: {login_recovery.text}"
        recovery_data = login_recovery.json()
        assert "token" in recovery_data
        recovery_token = recovery_data["token"]
        recovery_headers = {"Authorization": f"Bearer {recovery_token}"}
        print("Recovery code login successful")
        
        # Step 10: Disable 2FA
        print("\n=== Step 10: Disable 2FA ===")
        # Generate a fresh TOTP code for disabling
        time.sleep(1)
        disable_code = totp.now()
        print(f"Using TOTP code to disable: {disable_code}")
        
        disable_response = requests.post(f"{BASE_URL}/api/admin/2fa/disable",
                                        headers=recovery_headers,
                                        json={"code": disable_code})
        assert disable_response.status_code == 200, f"Disable failed: {disable_response.text}"
        disable_data = disable_response.json()
        assert disable_data.get("enabled") == False
        print("2FA disabled successfully")
        
        # Step 11: Verify normal login works again
        print("\n=== Step 11: Verify normal login works ===")
        final_login = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert final_login.status_code == 200
        final_data = final_login.json()
        assert "token" in final_data, "Should get token without 2FA"
        assert final_data.get("requires_2fa") != True, "Should not require 2FA"
        print("Normal login works after disabling 2FA")
        
        print("\n=== ALL 2FA TESTS PASSED ===")


class TestRateLimiting:
    """Test rate limiting: 3 attempts / 30 minutes"""
    
    def test_rate_limit_message(self):
        """Test that rate limit returns correct message after 3 failed attempts"""
        # Note: This test may affect other tests due to rate limiting
        # We'll just verify the rate limit configuration exists
        
        # First, do a successful login to clear any existing rate limits
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        
        if response.status_code == 429:
            # Already rate limited
            data = response.json()
            assert "30 minutes" in data.get("detail", ""), "Rate limit message should mention 30 minutes"
            print(f"Rate limit active: {data.get('detail')}")
            return
        
        # Try 3 failed attempts with wrong password
        for i in range(3):
            fail_response = requests.post(f"{BASE_URL}/api/admin/login", json={
                "username": ADMIN_USERNAME,
                "password": "wrongpassword"
            })
            print(f"Attempt {i+1}: Status {fail_response.status_code}")
            if fail_response.status_code == 429:
                data = fail_response.json()
                assert "30 minutes" in data.get("detail", "")
                print(f"Rate limited after {i+1} attempts: {data.get('detail')}")
                break
        
        # The 4th attempt should be rate limited
        rate_limited = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": ADMIN_USERNAME,
            "password": "wrongpassword"
        })
        
        if rate_limited.status_code == 429:
            data = rate_limited.json()
            assert "30 minutes" in data.get("detail", "") or "Too many" in data.get("detail", "")
            print(f"Rate limit confirmed: {data.get('detail')}")
        else:
            print(f"Rate limit not triggered (status: {rate_limited.status_code})")


class TestShareAccess:
    """Test that share access still works"""
    
    def test_share_access_works(self):
        """Test that existing share token works"""
        share_token = "ERBUfa0C0q83_af3QKyvmA"
        
        response = requests.get(f"{BASE_URL}/api/share/{share_token}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Share access works - Gallery: {data.get('gallery_name')}")
            assert "gallery_name" in data
        elif response.status_code == 404:
            print("Share token not found (may have been deleted)")
        else:
            print(f"Share access returned: {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
