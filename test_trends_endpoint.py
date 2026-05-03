"""Test the trends endpoint directly without the running server."""
import sys
sys.path.insert(0, '.')

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Test the trends endpoint
response = client.get("/api/trends?file=app/main.py")
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

# Made with Bob
