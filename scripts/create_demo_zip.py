"""
Create demo ZIP for the live E2E deployment test.

Run: python scripts/create_demo_zip.py
Produces: demo_projects/buggy_calculator.zip
"""

import zipfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
DEMO_DIR = ROOT / "demo_projects" / "buggy_calculator"
OUTPUT = ROOT / "demo_projects" / "buggy_calculator.zip"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(DEMO_DIR.rglob("*"))
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            if f.is_file():
                arcname = f.relative_to(DEMO_DIR)
                zf.write(f, arcname)
    print(f"Created {OUTPUT}  ({OUTPUT.stat().st_size} bytes)")
    print("Files included:")
    with zipfile.ZipFile(OUTPUT) as zf:
        for name in zf.namelist():
            print(f"  {name}")


if __name__ == "__main__":
    main()
