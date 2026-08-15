"""
Passing project fixture — calculator with correct implementations.
All tests should pass when pytest runs against this project.
"""


def add(a: int | float, b: int | float) -> int | float:
    return a + b


def subtract(a: int | float, b: int | float) -> int | float:
    return a - b


def multiply(a: int | float, b: int | float) -> int | float:
    return a * b


def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


def factorial(n: int) -> int:
    if n < 0:
        raise ValueError("Factorial of negative number")
    if n == 0:
        return 1
    return n * factorial(n - 1)
