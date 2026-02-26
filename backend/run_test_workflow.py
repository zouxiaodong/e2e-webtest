"""
完整的测试流程脚本：启动服务器、生成测试用例、执行测试
"""
import asyncio
import sys
import os
import json
import requests
import time
import threading

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def start_server():
    """在后台启动服务器"""
    import subprocess
    subprocess.Popen(
        [r"D:\ProgramData\miniconda3\envs\e2e\python.exe", "-m", "app.main"],
        cwd=project_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    )


def wait_for_server(max_attempts=30):
    """等待服务器启动"""
    for i in range(max_attempts):
        try:
            resp = requests.get("http://localhost:8000/health", timeout=2)
            if resp.status_code == 200:
                print(f"[OK] Server started after {i+1} attempts")
                return True
        except:
            pass
        time.sleep(1)
    return False


def generate_test_cases(scenario_id):
    """生成测试用例"""
    print(f"\n[STEP 2] Generating test cases for scenario {scenario_id}...")
    url = f"http://localhost:8000/api/scenarios/{scenario_id}/generate"
    try:
        resp = requests.post(url, timeout=300)
        if resp.status_code == 200:
            data = resp.json()
            print(f"[OK] Generated {data.get('total_cases', 0)} test cases")
            return data
        else:
            print(f"[ERROR] Failed to generate: {resp.text}")
            return None
    except Exception as e:
        print(f"[ERROR] {e}")
        return None


def execute_test_cases(scenario_id):
    """执行测试用例"""
    print(f"\n[STEP 3] Executing test cases for scenario {scenario_id}...")
    url = f"http://localhost:8000/api/scenarios/{scenario_id}/execute"
    try:
        resp = requests.post(url, timeout=600)
        if resp.status_code == 200:
            data = resp.json()
            print(f"[OK] Execution complete!")
            print(f"  Total: {data.get('total', 0)}")
            print(f"  Passed: {data.get('passed', 0)}")
            print(f"  Failed: {data.get('failed', 0)}")
            return data
        else:
            print(f"[ERROR] Failed to execute: {resp.text}")
            return None
    except Exception as e:
        print(f"[ERROR] {e}")
        return None


def main():
    scenario_id = 1  # 之前创建的登录测试场景ID
    
    print("=" * 60)
    print("Starting E2E Test Workflow")
    print("=" * 60)
    
    # Step 1: 启动服务器
    print("\n[STEP 1] Starting backend server...")
    start_server()
    
    if not wait_for_server():
        print("[ERROR] Server failed to start")
        return
    
    # Step 2: 生成测试用例
    generate_result = generate_test_cases(scenario_id)
    if not generate_result:
        print("[ERROR] Failed to generate test cases")
        return
    
    # Step 3: 执行测试用例
    execute_result = execute_test_cases(scenario_id)
    
    print("\n" + "=" * 60)
    print("Workflow Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
