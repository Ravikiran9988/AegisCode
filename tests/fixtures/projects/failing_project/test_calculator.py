"""Tests for the failing calculator project — same tests, buggy implementation."""
import pytest
from calculator import add, subtract, multiply, divide, factorial


def test_add_positive():
    assert add(2, 3) == 5  # PASSES


def test_add_zero():
    assert add(0, 5) == 5  # PASSES


def test_subtract():
    assert subtract(10, 4) == 6  # FAILS — bug returns 14


def test_subtract_negative_result():
    assert subtract(3, 7) == -4  # FAILS — bug returns 10


def test_multiply():
    assert multiply(3, 4) == 12  # FAILS — bug returns 9


def test_multiply_by_zero():
    assert multiply(5, 0) == 0  # PASSES (5 * (0-1) = -5 … actually FAILS)


def test_divide():
    assert divide(10.0, 2.0) == 5.0  # FAILS — bug raises ValueError


def test_divide_by_zero():
    with pytest.raises(ValueError):
        divide(5.0, 0.0)  # FAILS — bug does NOT raise (division by zero OSError)


def test_factorial_zero():
    assert factorial(0) == 1  # PASSES


def test_factorial_positive():
    assert factorial(5) == 120  # PASSES
