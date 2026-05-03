"""Test script for remediation API endpoint."""

import requests
import json

# Test without API key (should fail with 500 since no key is configured)
print("Testing remediation API endpoint...")
print("-" * 60)

url = "http://127.0.0.1:8000/api/remediation/app_alert_manager_py"

print(f"\nGET {url}")
print("(without API key - expecting error since API key not configured)")

try:
    response = requests.get(url)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "-" * 60)
print("Note: To use the API endpoint, set DRIFTGUARD_API_KEY environment variable")
print("and include X-DriftGuard-Key header in requests.")

# Made with Bob
