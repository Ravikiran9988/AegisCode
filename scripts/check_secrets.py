"""Scan source files for hardcoded secrets / API keys."""
import pathlib
import re
import sys

SECRET_PATTERNS = [
    (r"sk-[A-Za-z0-9]{20,}", "OpenAI API key"),
    (r"AKIA[0-9A-Z]{16}", "AWS access key"),
    (r"ghp_[A-Za-z0-9]{36}", "GitHub PAT"),
    (r"xoxb-[0-9A-Za-z\-]{50,}", "Slack bot token"),
    (r"password\s*=\s*[\"'][A-Za-z0-9!@#$%^&*]{8,}[\"']", "Hardcoded password"),
]

SCAN_DIRS = ["backend", "frontend", "tests"]
SKIP_FILES = {".env.example"}  # Template file — allowed to have placeholders

findings = []

for d in SCAN_DIRS:
    for f in pathlib.Path(d).rglob("*.py"):
        if f.name in SKIP_FILES:
            continue
        content = f.read_text(encoding="utf-8", errors="ignore")
        for pattern, label in SECRET_PATTERNS:
            matches = re.findall(pattern, content)
            if matches:
                findings.append((str(f), label, matches))

if findings:
    for fname, label, matches in findings:
        print(f"FOUND {label} in {fname}: {matches}")
    sys.exit(1)
else:
    print("NO HARDCODED SECRETS FOUND")
    sys.exit(0)
