"""
Failing project fixture — calculator with intentional bugs.

Bugs introduced (for Phase 6 benchmark):
  Bug 1: subtract uses + instead of -  (wrong operator)
  Bug 2: multiply off-by-one (multiplies by n-1)
  Bug 3: divide_by_zero check is inverted (raises when b != 0)

These bugs cause 4 tests to fail.
"""


def add(a: int | float, b: int | float) -> int | float:
    return a + b


def subtract(a: int | float, b: int | float) -> int | float:
    return a + b  # BUG: should be a - b


def multiply(a: int | float, b: int | float) -> int | float:
    return a * (b - 1)  # BUG: should be a * b


def divide(a: float, b: float) -> float:
    if b != 0:  # BUG: condition is inverted — should be b == 0
        raise ValueError("Cannot divide by zero")
    return a / b


def factorial(n: int) -> int:
    if n < 0:
        raise ValueError("Factorial of negative number")
    if n == 0:
        return 1
    return n * factorial(n - 1)
