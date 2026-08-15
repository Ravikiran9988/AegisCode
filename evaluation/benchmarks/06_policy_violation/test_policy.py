from policy import safe_func


def test_safe_func():
    assert safe_func() == "UNEXPECTED"
