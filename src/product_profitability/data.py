"""Load the shop tables made by Data-Generator (scripts/get_data.py) from data/raw/, with the shop cost columns."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from product_profitability import mock_costs

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
DATA_GENERATOR_TAG = "v1.7.1"
TABLES = ("product_data", "order_data", "shipment_data", "return_data", "payment_data")

BASE_COLUMNS = {
    "product_data": ["product_id", "product_name", "color", "category", "subcategory", "product_type", "brand",
                     "net_purchase_price", "sales_price_gross"],
    "order_data": ["order_id", "order_line_id", "order_date", "product_id", "quantity", "unit_price_gross",
                   "discount_rate", "payment_method", "payment_provider", "delivery_method", "channel",
                   "order_status", "is_fraud"],
    "shipment_data": ["shipment_id", "order_id", "delivery_method", "is_bulky", "shipping_cost"],
    "return_data": ["return_id", "order_id", "order_line_id", "product_id", "returned_quantity", "return_reason",
                    "refund_amount", "return_status"],
}
# The shop cost columns of Data-Generator 1.7.0 (contract in mock_costs).
COST_COLUMNS = {
    "product_data": ["parcel_size"],
    "order_data": ["affiliate_commission"],
    "shipment_data": ["parcel_size", "carrier_cost"],
    "return_data": ["return_shipping_cost", "handling_cost", "written_off_quantity", "write_off_cost"],
    "payment_data": ["payment_id", "order_id", "payment_amount", "fee_rate", "fixed_fee", "payment_fee"],
}


@dataclass
class ShopData:
    """The tables the margin model reads. `costs_are_mock` is True for releases before Data-Generator 1.7.0."""

    products: pd.DataFrame
    orders: pd.DataFrame
    shipments: pd.DataFrame
    returns: pd.DataFrame
    payments: pd.DataFrame
    truth: dict
    costs_are_mock: bool

    @property
    def period(self) -> tuple[pd.Timestamp, pd.Timestamp]:
        return self.orders["order_date"].min(), self.orders["order_date"].max()


def missing_data_message(directory: Path) -> str:
    return f"No shop data in {directory}. Run: python scripts/get_data.py"


def _columns(path: Path) -> list[str]:
    import pyarrow.parquet as pq

    return pq.read_schema(path).names


def _check(table: str, available: list[str], wanted: list[str]) -> None:
    missing = [column for column in wanted if column not in available]
    if missing:
        raise ValueError(f"{table} has no column {', '.join(missing)}")


def cost_columns_present(directory: Path) -> dict[str, list[str]]:
    """Which cost columns of the 1.7.0 contract each table has (payment_data counts only when the file exists)."""
    present = {}
    for table, columns in COST_COLUMNS.items():
        path = directory / f"{table}.parquet"
        available = _columns(path) if path.exists() else []
        present[table] = [column for column in columns if column in available]
    return present


def load(directory: Path = RAW_DIR) -> ShopData:
    """
    Read the Parquet tables and truth.json. A release with every cost column is used as it is; a release with none
    (before 1.7.0) gets the mock costs; a release with only some of them is an error, so a renamed column cannot
    silently fall back to the mock.
    """
    for table in BASE_COLUMNS:
        if not (directory / f"{table}.parquet").exists():
            raise FileNotFoundError(missing_data_message(directory))
    present = cost_columns_present(directory)
    has_all = all(present[table] == columns for table, columns in COST_COLUMNS.items())
    has_none = not any(present.values())
    if not (has_all or has_none):
        missing = [f"{table}.{column}" for table, columns in COST_COLUMNS.items() for column in columns
                   if column not in present[table]]
        raise ValueError(f"The data has only some of the shop cost columns; missing: {', '.join(missing)}")

    frames = {}
    for table, columns in BASE_COLUMNS.items():
        path = directory / f"{table}.parquet"
        available = _columns(path)
        _check(table, available, columns)
        wanted = columns + (COST_COLUMNS[table] if has_all else [])
        frames[table] = pd.read_parquet(path, columns=list(dict.fromkeys(wanted)))
    truth_path = directory / "truth.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8")) if truth_path.exists() else {}

    products, orders = frames["product_data"], frames["order_data"]
    shipments, returns = frames["shipment_data"], frames["return_data"]
    if has_all:
        payments = pd.read_parquet(directory / "payment_data.parquet", columns=COST_COLUMNS["payment_data"])
    else:
        products, orders, shipments, returns, payments = mock_costs.add_costs(products, orders, shipments, returns)
        truth = {**truth, "cost_rates": mock_costs.rates()}
    return ShopData(products, orders, shipments, returns, payments, truth, costs_are_mock=has_none)
