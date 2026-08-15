"""
Syntax error project fixture.

This file has a deliberate syntax error that prevents collection.
Pytest will report an ERROR (exit code 2 or 4) rather than a test failure.
"""


def broken_function(x)  # SyntaxError: missing colon
    return x * 2
