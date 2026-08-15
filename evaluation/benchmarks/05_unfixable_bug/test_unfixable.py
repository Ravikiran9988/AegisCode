from unfixable import compute_constant


def test_unfixable():
    # Impossible contract assert
    assert compute_constant() == 999999
