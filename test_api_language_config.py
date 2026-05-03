"""Test API endpoints for language configuration.

Run this after restarting the server to test the new endpoints.
"""

import requests
import json


def test_get_language_config():
    """Test GET /api/language-config endpoint."""
    print("\n" + "=" * 70)
    print("Testing GET /api/language-config")
    print("=" * 70)
    
    try:
        response = requests.get("http://127.0.0.1:8000/api/language-config")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\nVersion: {data.get('version')}")
            print(f"Config Path: {data.get('config_path')}")
            print(f"Enabled Extensions: {data.get('total_enabled')}")
            print(f"Disabled Extensions: {data.get('total_disabled')}")
            
            print("\nFirst 3 enabled extensions:")
            for ext in data.get('enabled_extensions', [])[:3]:
                print(f"  {ext['extension']} -> {ext['language']}")
            
            print("\n✅ GET endpoint works!")
            return True
        else:
            print(f"\n❌ Unexpected status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("\n❌ Could not connect to server. Is it running?")
        print("Start server with: python -m uvicorn app.main:app --reload")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def test_reload_language_config():
    """Test POST /api/language-config/reload endpoint."""
    print("\n" + "=" * 70)
    print("Testing POST /api/language-config/reload")
    print("=" * 70)
    
    # This endpoint requires API key
    print("Note: This endpoint requires API key authentication")
    print("Set DRIFTGUARD_API_KEY in .env file to test")
    
    try:
        # Try without API key (should fail with 401)
        response = requests.post("http://127.0.0.1:8000/api/language-config/reload")
        print(f"Status Code (no auth): {response.status_code}")
        
        if response.status_code == 401:
            print("✅ Correctly requires authentication")
            return True
        else:
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("\n❌ Could not connect to server. Is it running?")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("API LANGUAGE CONFIGURATION ENDPOINT TESTS")
    print("=" * 70)
    print("\nMake sure the server is running:")
    print("  python -m uvicorn app.main:app --reload")
    print("\nThen run this test script.")
    
    success1 = test_get_language_config()
    success2 = test_reload_language_config()
    
    print("\n" + "=" * 70)
    if success1 and success2:
        print("✅ ALL API TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED")
        if not success1:
            print("  - GET /api/language-config failed")
        if not success2:
            print("  - POST /api/language-config/reload failed")
    print("=" * 70)

# Made with Bob
