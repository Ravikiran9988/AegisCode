"""
Tests for unfixable project fixture.
"""
from logic import compute_hash


def test_hash():
    assert compute_hash("test") == "EXPECTED_SHA256_HASH"
