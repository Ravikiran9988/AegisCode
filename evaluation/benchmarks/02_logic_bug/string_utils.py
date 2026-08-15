"""
Logic Bug Benchmark.
"""


def reverse_string(s: str) -> str:
    # BUG: returns lowercased text instead of reversed
    return s.lower()
