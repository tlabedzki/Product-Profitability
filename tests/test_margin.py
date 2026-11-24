import pandas as pd
import pytest

from product_profitability import margin


def line(lines, line_id):
    return lines.set_index("order_line_id").loc[line_id]


def test_order_costs_are_spread_by_parcel_weight_and_value(tiny_shop):
    lines = margin.line_costs(tiny_shop)
    # Parcel weights from one-unit parcels: small 10, bulky 70, so line 11 (2 small) gets 20/90 of the carrier cost.
    assert line(lines, 11)["carrier_cost"] == pytest.approx(80 * 20 / 90)
    assert line(lines, 12)["carrier_cost"] == pytest.approx(80 * 70 / 90)
    # Payment fee by gross value after discount: 246 against 123.
    assert line(lines, 11)["payment_fee"] == pytest.approx(10 * 2 / 3)
    assert line(lines, 41)["delivery_fee"] == pytest.approx(10.0)


def test_cascade_of_each_line_by_hand(tiny_shop):
    steps = margin.add_steps(margin.line_costs(tiny_shop)).set_index("order_line_id")
    returned = steps.loc[11]
    assert returned["list_margin"] == pytest.approx(100.0)
    assert returned["returns"] == pytest.approx(100 - 50 + 50 + 8.5 + 8)
    assert returned["true_margin"] == pytest.approx(100 - 116.5 - 80 * 20 / 90 - 10 * 2 / 3 - 6)
    assert steps.loc[12, "true_margin"] == pytest.approx(200 - 100 - 100 - 80 * 70 / 90 - 10 / 3)
    failed = steps.loc[21]
    assert (failed["units"], failed["list_revenue"], failed["true_margin"]) == (0, 0, pytest.approx(-0.30))
    assert steps.loc[41, "shipping"] == pytest.approx(0.0)
    assert 31 not in steps.index  # fraud order left out


def test_product_margins_by_hand(tiny_shop):
    products = margin.product_margins(tiny_shop).set_index("product_id")
    assert products.loc[1, "true_margin"] == pytest.approx(150 - 116.5 - 80 * 20 / 90 - (10 * 2 / 3 + 0.3 + 1.5) - 6)
    assert products.loc[2, "true_margin"] == pytest.approx(200 - 100 - (80 * 70 / 90 + 70) - (10 / 3 + 3))
    assert products.loc[1, "units"] == 3 and products.loc[1, "units_refunded"] == 1
    assert products.loc[1, "return_rate"] == pytest.approx(1 / 3)


def test_steps_add_up_to_the_true_margin(tiny_shop):
    products = margin.product_margins(tiny_shop)
    rebuilt = products["list_margin"] - products[list(margin.STEPS)].sum(axis=1)
    assert rebuilt.to_numpy() == pytest.approx(products["true_margin"].to_numpy())
    cascade = margin.shop_cascade(products)
    assert cascade["True margin"] == pytest.approx(products["true_margin"].sum())


def test_every_cost_is_spread_to_the_grosz(tiny_shop):
    report = margin.reconcile(tiny_shop, margin.line_costs(tiny_shop)).set_index("cost")
    assert report["difference"].abs().max() < 0.005
    assert report.loc["carrier_cost", "fraud_left_out"] == pytest.approx(10.0)
    assert report.loc["payment_fee", "allocated"] == pytest.approx(10 + 0.3 + 1.5 + 3)


def test_reconciliation_catches_a_lost_line(tiny_shop):
    lines = margin.line_costs(tiny_shop)
    report = margin.reconcile(tiny_shop, lines[lines["order_line_id"] != 12]).set_index("cost")
    assert report.loc["carrier_cost", "difference"] == pytest.approx(80 * 70 / 90)


def test_a_doubled_shipment_is_an_error(tiny_shop):
    tiny_shop.shipments = pd.concat([tiny_shop.shipments, tiny_shop.shipments.head(1)], ignore_index=True)
    with pytest.raises(ValueError, match="shipments has more than one row"):
        margin.line_costs(tiny_shop)


def test_a_line_without_its_product_is_an_error(tiny_shop):
    tiny_shop.products = tiny_shop.products[tiny_shop.products["product_id"] != 2]
    with pytest.raises(ValueError, match="a product is missing"):
        margin.line_costs(tiny_shop)
