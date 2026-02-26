"""
Debug script to generate test cases and capture error
"""
import requests
import sys
import logging

# Enable more verbose logging
logging.basicConfig(level=logging.DEBUG)

BASE_URL = "http://localhost:8000"
SCENARIO_ID = 16

print(f"[DEBUG] Generating test cases for scenario {SCENARIO_ID}...")

try:
    resp = requests.post(
        f"{BASE_URL}/api/scenarios/{SCENARIO_ID}/generate",
        timeout=300,
        stream=True
    )
    print(f"[DEBUG] Status: {resp.status_code}")
    print(f"[DEBUG] Response: {resp.text}")
except Exception as e:
    print(f"[ERROR] {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
