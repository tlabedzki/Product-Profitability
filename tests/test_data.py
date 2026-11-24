import pandas as pd
import pytest
from conftest import cost_tables, raw_tables, write_tables

from product_profitability import data


def test_a_release_without_costs_gets_the_mock(tmp_path):
    write_tables(tmp_path, raw_tables())
    shop = data.load(tmp_path)
    assert shop.costs_are_mock
    assert "cost_rates" in shop.truth
    assert set(shop.payments["order_id"]) == set(shop.orders["order_id"])
    assert {"carrier_cost", "parcel_size"} <= set(shop.shipments.columns)


def test_a_release_with_costs_is_read_as_it_is(tmp_path):
    write_tables(tmp_path, cost_tables())
    shop = data.load(tmp_path)
    assert not shop.costs_are_mock
    assert shop.shipments["carrier_cost"].tolist() == [80.0, 10.0, 10.0, 70.0]
    assert shop.payments["payment_fee"].sum() == pytest.approx(16.8)
    assert shop.period == (pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-06"))


def test_some_cost_columns_only_is_an_error(tmp_path):
    tables = cost_tables()
    tables["return_data"] = tables["return_data"].drop(columns="handling_cost")
    write_tables(tmp_path, tables)
    with pytest.raises(ValueError, match="return_data.handling_cost"):
        data.load(tmp_path)


def test_a_missing_payment_table_is_an_error_when_other_costs_exist(tmp_path):
    tables = cost_tables()
    del tables["payment_data"]
    write_tables(tmp_path, tables)
    with pytest.raises(ValueError, match="payment_data.payment_fee"):
        data.load(tmp_path)


def test_a_missing_base_column_is_named(tmp_path):
    tables = raw_tables()
    tables["order_data"] = tables["order_data"].drop(columns="discount_rate")
    write_tables(tmp_path, tables)
    with pytest.raises(ValueError, match="order_data has no column discount_rate"):
        data.load(tmp_path)


def test_missing_data_says_how_to_get_it(tmp_path):
    with pytest.raises(FileNotFoundError, match="get_data.py"):
        data.load(tmp_path)
