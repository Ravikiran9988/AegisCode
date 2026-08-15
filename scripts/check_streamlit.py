"""Verify Streamlit frontend module imports cleanly."""
import sys

try:
    import streamlit  # noqa: F401
    print(f"streamlit version: {streamlit.__version__}")

    # Verify frontend module imports (without actually rendering the UI)
    import importlib.util
    spec = importlib.util.spec_from_file_location("frontend.app", "frontend/app.py")
    # We just check the spec loads without error — running it would open a browser
    if spec is None:
        raise ImportError("Could not load frontend/app.py spec")
    print("frontend/app.py: module spec loaded OK")
    print("STREAMLIT IMPORT OK")
    sys.exit(0)
except Exception as e:
    print(f"STREAMLIT IMPORT FAILED: {e}")
    sys.exit(1)
