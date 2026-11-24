import numpy as np
import pandas as pd
import pytest
from conftest import raw_tables

from product_profitability import mock_costs


def mock():
    tables = raw_tables()
    return mock_costs.add_costs(tables["product_data"], tables["order_data"], tables["shipment_data"],
                                tables["return_data"])


def test_parcel_size_bulky_types_first():
    products = pd.DataFrame({"category": ["Furniture", "Electronics", "Electronics", "Clothing"],
                             "product_type": ["Sofa", "Laptop", "Phone", "Dress"]})
    assert mock_costs.parcel_size(products).tolist() == ["bulky", "medium", "small", "small"]


def test_free_delivery_still_costs_the_shop():
    _, _, shipments, _, _ = mock()
    free = shipments[shipments["shipping_cost"] == 0]
    assert (free["carrier_cost"] > 0).all()
    # Order 1 has a bulky sofa: its parcel is bulky and costs the bulky courier rate.
    assert shipments.loc[0, "parcel_size"] == "bulky"
    assert shipments.loc[0, "carrier_cost"] == mock_costs.CARRIER_RATES["InPost courier"]["bulky"]


def test_payments_one_row_per_order_and_failed_pays_only_the_fixed_fee():
    _, _, _, _, payments = mock()
    assert payments["order_id"].is_unique and len(payments) == 5
    failed = payments.set_index("order_id").loc[2]
    assert failed["payment_amount"] == 0 and failed["payment_fee"] == pytest.approx(0.30)
    first = payments.set_index("order_id").loc[1]
    assert first["payment_fee"] == pytest.approx(round(369.0 * 0.012 + 0.25, 2))


def test_commission_only_on_affiliate_lines_and_kept_units():
    _, orders, _, _, _ = mock()
    commission = orders.set_index("order_line_id")["affiliate_commission"]
    assert commission[[21, 31, 41, 51]].eq(0).all()
    # Line 11: 2 units, 1 refunded, Home & Garden 6% of 100 net per unit.
    assert commission[11] == pytest.approx(0.06 * 100)


def test_returns_write_off_no_more_than_returned_and_nothing_when_rejected():
    tables = raw_tables()
    returns = pd.concat([tables["return_data"]] * 50, ignore_index=True)
    returns["returned_quantity"] = 3
    returns.loc[::2, "return_status"] = "rejected"
    _, _, _, out, _ = mock_costs.add_costs(tables["product_data"], tables["order_data"], tables["shipment_data"],
                                           returns)
    assert (out["written_off_quantity"] <= out["returned_quantity"]).all()
    assert out.loc[out["return_status"] == "rejected", "written_off_quantity"].eq(0).all()
    assert out["write_off_cost"].to_numpy() == pytest.approx(out["written_off_quantity"].to_numpy() * 50.0)
    assert (out["handling_cost"] > 0).all()


def test_mock_is_the_same_on_every_run():
    first, second = mock(), mock()
    for a, b in zip(first, second, strict=True):
        pd.testing.assert_frame_equal(a, b)
    assert np.isfinite(first[2]["carrier_cost"]).all()
