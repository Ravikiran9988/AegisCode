"""
Test Suite for Demo Calculator Project.
"""

import pytest
from calculator import add, divide, multiply, subtract


def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0


def test_subtract():
    assert subtract(5, 3) == 2
    assert subtract(10, 4) == 6


def test_multiply():
    assert multiply(3, 4) == 12
    assert multiply(2, 5) == 10


def test_divide():
    assert divide(10, 2) == 5.0
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        divide(5, 0)
