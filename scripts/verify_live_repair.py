"""
Live E2E Repair Verification Script for AegisCode on Render.com.
"""

import json
import time
from pathlib import Path
import requests

BASE_URL = "https://aegiscode-vrob.onrender.com"
ZIP_PATH = Path(__file__).parent.parent / "demo_projects" / "buggy_calculator.zip"


def main() -> None:
    print("=== AEGISCODE LIVE E2E REPAIR TEST ===")
    print(f"Backend URL: {BASE_URL}")

    # 1. Health Probe
    h_resp = requests.get(f"{BASE_URL}/health", timeout=15)
    print(f"1. Health Check Status: {h_resp.status_code}")
    print(f"   Health Body: {h_resp.text}")

    # 2. Upload Project
    print("\n2. Uploading demo_projects/buggy_calculator.zip...")
    zip_bytes = ZIP_PATH.read_bytes()
    files = {"file": ("buggy_calculator.zip", zip_bytes, "application/zip")}
    u_resp = requests.post(f"{BASE_URL}/api/projects/upload", files=files, timeout=30)
    print(f"   Upload Status: {u_resp.status_code}")
    u_data = u_resp.json()
    project_id = u_data["project_id"]
    print(f"   Project ID: {project_id}")

    # 3. Create Run
    print("\n3. Creating Run...")
    c_resp = requests.post(
        f"{BASE_URL}/api/runs",
        json={"project_id": project_id, "max_iterations": 3},
        timeout=30,
    )
    print(f"   Create Run Status: {c_resp.status_code}")
    c_data = c_resp.json()
    run_id = c_data["run_id"]
    print(f"   Run ID: {run_id}")

    # 4. Trigger Repair
    print(f"\n4. Launching Self-Healing Graph for Run {run_id}...")
    start_t = time.time()
    r_resp = requests.post(f"{BASE_URL}/api/runs/{run_id}/repair", timeout=180)
    print(f"   Repair Trigger Status: {r_resp.status_code}")
    print(f"   Repair Trigger Response: {r_resp.text}")

    # 5. Poll Status
    print("\n5. Polling Run Status...")
    while True:
        s_resp = requests.get(f"{BASE_URL}/api/runs/{run_id}/status", timeout=30)
        s_data = s_resp.json()
        status = s_data.get("status")
        cur_it = s_data.get("current_iteration")
        t_pass = s_data.get("tests_passed")
        r_appr = s_data.get("review_approved")

        elapsed = round(time.time() - start_t, 1)
        print(f"   [{elapsed}s] Status: {status} | Iter: {cur_it} | Tests Passed: {t_pass} | Review Approved: {r_appr}")

        if status in ("passed", "failed", "stalled", "error"):
            break
        time.sleep(3)

    duration = round(time.time() - start_t, 2)
    print(f"\n=== FINAL REPAIR RESULTS (Duration: {duration}s) ===")
    res_resp = requests.get(f"{BASE_URL}/api/runs/{run_id}/results", timeout=30)
    res_data = res_resp.json()
    print(json.dumps(res_data, indent=2))


if __name__ == "__main__":
    main()
