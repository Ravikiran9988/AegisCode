"""Tests for the passing calculator project."""
import pytest
from calculator import add, subtract, multiply, divide, factorial


def test_add_positive():
    assert add(2, 3) == 5


def test_add_negative():
    assert add(-1, -1) == -2


def test_add_zero():
    assert add(0, 5) == 5


def test_subtract():
    assert subtract(10, 4) == 6


def test_subtract_negative_result():
    assert subtract(3, 7) == -4


def test_multiply():
    assert multiply(3, 4) == 12


def test_multiply_by_zero():
    assert multiply(5, 0) == 0


def test_divide():
    assert divide(10.0, 2.0) == 5.0


def test_divide_by_zero():
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        divide(5.0, 0.0)


def test_factorial_zero():
    assert factorial(0) == 1


def test_factorial_positive():
    assert factorial(5) == 120


def test_factorial_negative():
    with pytest.raises(ValueError):
        factorial(-1)
