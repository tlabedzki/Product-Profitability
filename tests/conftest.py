"""
A tiny shop in the Data-Generator layout, small enough to compute every number by hand (tests run without data files).

    product 1: small parcel, purchase cost 50      product 2: bulky, purchase cost 100
    order 1  delivered, free delivery, carrier 80, payment fee 10, affiliate
             line 11: product 1, 2 x 123.00 gross        line 12: product 2, 1 x 246.00 gross, 50% discount
             line 11 has a refunded return of 1 unit (written off), label 8.50, handling 8.00
    order 2  payment_failed, product 1, failed card payment fee 0.30
    order 3  fraud, delivered, product 1 (left out of the margins)
    order 4  delivered, product 1 alone (one unit), carrier 10, delivery fee 12.30 gross, payment fee 1.50
    order 5  delivered, product 2 alone (one unit), carrier 70, payment fee 3.00
"""
from __future__ import annotations

import pandas as pd
import pytest

from product_profitability.data import ShopData


def raw_tables() -> dict[str, pd.DataFrame]:
    """The tiny shop without the 1.7.0 cost columns (like Data-Generator 1.6.0)."""
    products = pd.DataFrame({
        "product_id": [1, 2], "product_name": ["Mug Small", "Sofa Big"], "color": ["white", "gray"],
        "category": ["Home & Garden", "Furniture"], "subcategory": ["Kitchen", "Living Room"],
        "product_type": ["Mug", "Sofa"], "brand": ["Brand", "Brand"], "net_purchase_price": [50.0, 100.0],
        "sales_price_gross": [123.0, 246.0],
    })
    orders = pd.DataFrame({
        "order_id": [1, 1, 2, 3, 4, 5],
        "order_line_id": [11, 12, 21, 31, 41, 51],
        "order_date": pd.to_datetime(["2024-01-02"] * 2 + ["2024-01-03", "2024-01-04", "2024-01-05", "2024-01-06"]),
        "product_id": [1, 2, 1, 1, 1, 2],
        "quantity": [2, 1, 1, 1, 1, 1],
        "unit_price_gross": [123.0, 246.0, 123.0, 123.0, 123.0, 246.0],
        "discount_rate": [0.0, 0.5, 0.0, 0.0, 0.0, 0.0],
        "payment_method": ["BLIK", "BLIK", "Card", "Card", "BLIK", "BLIK"],
        "payment_provider": ["PayU"] * 6,
        "delivery_method": ["InPost courier"] * 6,
        "channel": ["affiliate", "affiliate", "direct", "direct", "direct", "direct"],
        "order_status": ["delivered", "delivered", "payment_failed", "delivered", "delivered", "delivered"],
        "is_fraud": [False, False, False, True, False, False],
    })
    shipments = pd.DataFrame({
        "shipment_id": [1, 2, 3, 4], "order_id": [1, 3, 4, 5], "delivery_method": ["InPost courier"] * 4,
        "is_bulky": [True, False, False, True], "shipping_cost": [0.0, 12.3, 12.3, 0.0],
    })
    returns = pd.DataFrame({
        "return_id": [1], "order_id": [1], "order_line_id": [11], "product_id": [1], "returned_quantity": [1],
        "return_reason": ["defective"], "refund_amount": [123.0], "return_status": ["refunded"],
    })
    return {"product_data": products, "order_data": orders, "shipment_data": shipments, "return_data": returns}


def cost_tables() -> dict[str, pd.DataFrame]:
    """The tiny shop with hand-set 1.7.0 cost columns (like Data-Generator 1.7.0)."""
    tables = {name: frame.copy() for name, frame in raw_tables().items()}
    tables["product_data"]["parcel_size"] = ["small", "bulky"]
    tables["order_data"]["affiliate_commission"] = [6.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    tables["shipment_data"]["parcel_size"] = ["bulky", "small", "small", "bulky"]
    tables["shipment_data"]["carrier_cost"] = [80.0, 10.0, 10.0, 70.0]
    tables["return_data"]["return_shipping_cost"] = [8.5]
    tables["return_data"]["handling_cost"] = [8.0]
    tables["return_data"]["written_off_quantity"] = [1]
    tables["return_data"]["write_off_cost"] = [50.0]
    tables["payment_data"] = pd.DataFrame({
        "payment_id": [1, 2, 3, 4, 5], "order_id": [1, 2, 3, 4, 5],
        "payment_amount": [369.0, 0.0, 135.3, 135.3, 246.0], "fee_rate": [0.012, 0.0, 0.016, 0.012, 0.012],
        "fixed_fee": [0.25, 0.30, 0.25, 0.25, 0.25], "payment_fee": [10.0, 0.30, 2.0, 1.5, 3.0],
    })
    return tables


def write_tables(directory, tables: dict[str, pd.DataFrame]) -> None:
    for name, frame in tables.items():
        frame.to_parquet(directory / f"{name}.parquet")


@pytest.fixture
def tiny_shop() -> ShopData:
    tables = cost_tables()
    return ShopData(tables["product_data"], tables["order_data"], tables["shipment_data"], tables["return_data"],
                    tables["payment_data"], truth={"vat_rate": 0.23}, costs_are_mock=False)
