"""Live E2E Repair Verification Script for AegisCode."""

import json
import os
import time
from pathlib import Path

import requests

BASE_URL = os.environ.get("BACKEND_URL", "").strip().rstrip("/")
ZIP_PATH = Path(__file__).parent.parent / "demo_projects" / "buggy_calculator.zip"


def main() -> None:
    if not BASE_URL:
        raise RuntimeError("BACKEND_URL must be set to the deployed FastAPI base URL.")

    print("=== AEGISCODE LIVE E2E REPAIR TEST ===")
    print(f"Backend URL: {BASE_URL}")

    h_resp = requests.get(f"{BASE_URL}/health", timeout=15)
    h_resp.raise_for_status()
    print(f"1. Health Check Status: {h_resp.status_code}")
    print(f"   Health Body: {h_resp.text}")

    print("\n2. Uploading demo_projects/buggy_calculator.zip...")
    zip_bytes = ZIP_PATH.read_bytes()
    files = {"file": ("buggy_calculator.zip", zip_bytes, "application/zip")}
    u_resp = requests.post(f"{BASE_URL}/api/projects/upload", files=files, timeout=60)
    u_resp.raise_for_status()
    u_data = u_resp.json()
    project_id = u_data["project_id"]
    print(f"   Project ID: {project_id}")

    print("\n3. Creating Run...")
    c_resp = requests.post(
        f"{BASE_URL}/api/runs",
        json={"project_id": project_id, "max_iterations": 3},
        timeout=90,
    )
    c_resp.raise_for_status()
    c_data = c_resp.json()
    run_id = c_data["run_id"]
    print(f"   Run ID: {run_id}")

    print(f"\n4. Launching Self-Healing Graph for Run {run_id}...")
    start_t = time.time()
    r_resp = requests.post(f"{BASE_URL}/api/runs/{run_id}/repair", timeout=30)
    r_resp.raise_for_status()
    print(f"   Repair Trigger Status: {r_resp.status_code}")
    print(f"   Repair Trigger Response: {r_resp.text}")

    print("\n5. Polling Run Status...")
    while True:
        s_resp = requests.get(f"{BASE_URL}/api/runs/{run_id}/status", timeout=30)
        s_resp.raise_for_status()
        s_data = s_resp.json()
        status = s_data.get("status")
        cur_it = s_data.get("current_iteration")
        t_pass = s_data.get("tests_passed")
        r_appr = s_data.get("review_approved")

        elapsed = round(time.time() - start_t, 1)
        print(
            f"   [{elapsed}s] Status: {status} | Iter: {cur_it} | "
            f"Tests Passed: {t_pass} | Review Approved: {r_appr}"
        )

        if status in ("passed", "failed", "stalled", "error"):
            break
        time.sleep(3)

    duration = round(time.time() - start_t, 2)
    print(f"\n=== FINAL REPAIR RESULTS (Duration: {duration}s) ===")
    res_resp = requests.get(f"{BASE_URL}/api/runs/{run_id}/results", timeout=30)
    res_resp.raise_for_status()
    print(json.dumps(res_resp.json(), indent=2))


if __name__ == "__main__":
    main()
