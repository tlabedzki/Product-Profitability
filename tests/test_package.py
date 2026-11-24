import product_profitability


def test_version_is_set():
    assert product_profitability.__version__.count(".") == 2
