"""Quick health check script — run after uvicorn is up."""
import json
import sys
import time
import urllib.request

PORT = 8001  # configurable
time.sleep(2)

try:
    resp = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=10)
    data = json.loads(resp.read())
    print(json.dumps(data, indent=2))
    assert data["status"] == "ok", f"Expected ok, got {data['status']}"
    assert data["database"] == "connected", f"Expected connected, got {data['database']}"
    print("\nHEALTH CHECK PASSED")
    sys.exit(0)
except Exception as e:
    print(f"\nHEALTH CHECK FAILED: {e}")
    sys.exit(1)
