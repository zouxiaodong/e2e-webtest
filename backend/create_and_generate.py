"""
Create login scenario and generate test via API
"""
import requests
import json

BASE_URL = "http://localhost:8000"

# Create new login scenario
scenario_data = {
    "name": "登录测试-新",
    "target_url": "https://xas.stelguard.com/login?redirect=/index",
    "user_query": "测试登录功能，使用用户名admin和密码PGzVdj8WnN登录，验证登录成功",
    "generation_strategy": "happy_path",
    "use_captcha": True,
    "auto_cookie_localstorage": True,
    "load_saved_storage": True
}

print("[STEP 1] Creating login scenario...")
resp = requests.post(f"{BASE_URL}/api/scenarios/", json=scenario_data, timeout=30)
print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    scenario = resp.json()
    scenario_id = scenario["id"]
    print(f"Created scenario ID: {scenario_id}")
    
    # Generate test cases
    print(f"\n[STEP 2] Generating test cases for scenario {scenario_id}...")
    resp = requests.post(f"{BASE_URL}/api/scenarios/{scenario_id}/generate", timeout=300)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text[:500]}")
else:
    print(f"Error: {resp.text}")
