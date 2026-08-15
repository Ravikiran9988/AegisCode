"""
Arithmetic Bug Benchmark.
"""


def add(a: int, b: int) -> int:
    # BUG: returns subtraction instead of addition
    return a - b
