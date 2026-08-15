"""
Buggy Calculator Module — Demo Project for AegisCode.

Contains intentional bugs:
1. subtract(a, b) performs addition instead of subtraction.
2. multiply(a, b) performs exponentiation instead of multiplication.
3. divide(a, b) fails to handle division by zero.
"""


def add(a: float, b: float) -> float:
    return a + b


def subtract(a: float, b: float) -> float:
    # BUG: addition instead of subtraction
    return a + b


def multiply(a: float, b: float) -> float:
    # BUG: exponentiation instead of multiplication
    return a**b


def divide(a: float, b: float) -> float:
    # BUG: missing zero check
    return a / b
