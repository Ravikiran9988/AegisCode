"""Tests for the syntax error project — will fail at collection."""
from bad_code import broken_function


def test_double():
    assert broken_function(5) == 10
