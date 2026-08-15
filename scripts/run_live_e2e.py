"""
Standalone live E2E repair verification script for Render deployment.
"""

import json
import time
import requests

BASE = "https://aegiscode-vrob.onrender.com"
ZIP_PATH = "demo_projects/buggy_calculator.zip"


def run_e2e():
    print(f"=== Starting Live E2E Repair Test on {BASE} ===")

    # 1. Health Check
    h = requests.get(f"{BASE}/health").json()
    print(f"1. Health Check: status={h.get('status')}, llm={h.get('llm_provider')}, db={h.get('database')}")

    # 2. Upload Project
    with open(ZIP_PATH, "rb") as f:
        r = requests.post(f"{BASE}/api/projects/upload", files={"file": ("buggy_calculator.zip", f, "application/zip")})
    upload_res = r.json()
    project_id = upload_res["project_id"]
    print(f"2. Project Uploaded: project_id={project_id} ({upload_res.get('file_count')} files)")

    # 3. Create Run
    r = requests.post(f"{BASE}/api/runs", json={"project_id": project_id, "max_iterations": 3})
    run_res = r.json()
    run_id = run_res["run_id"]
    print(f"3. Run Created: run_id={run_id}")

    # 4. Trigger Repair
    r = requests.post(f"{BASE}/api/runs/{run_id}/repair")
    print(f"4. Repair Loop Triggered: HTTP {r.status_code} ({r.json().get('message')})")

    # 5. Poll Status
    start = time.time()
    while True:
        st = requests.get(f"{BASE}/api/runs/{run_id}/status").json()
        status = st.get("status")
        cur_it = st.get("current_iteration")
        t_pass = st.get("tests_passed")
        r_appr = st.get("review_approved")
        elapsed = round(time.time() - start, 1)

        print(f"   [{elapsed}s] status={status} | iter={cur_it} | tests_passed={t_pass} | review_approved={r_appr}")
        if status in ("passed", "failed", "stalled", "error"):
            break
        time.sleep(3)

    duration = round(time.time() - start, 2)
    print(f"\n=== FINAL REPAIR RESULT (Duration: {duration}s) ===")
    res = requests.get(f"{BASE}/api/runs/{run_id}/results").json()
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    run_e2e()
