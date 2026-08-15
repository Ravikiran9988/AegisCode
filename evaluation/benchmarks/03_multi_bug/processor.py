"""
Multi-Bug Benchmark.
"""


def double_val(x: int) -> int:
    # BUG: returns x + 2 instead of x * 2
    return x + 2


def square_val(x: int) -> int:
    # BUG: returns x * 2 instead of x ** 2
    return x * 2
