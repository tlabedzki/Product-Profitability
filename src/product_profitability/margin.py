"""
True margin of every product, step by step: from the margin in the price list to the margin after every selling cost.

    list margin   = list revenue - purchase cost            (what the price list promises)
    - discount      line discounts
    - returns       refunds - goods back in stock + write-offs + return labels + return handling
    - shipping      carrier cost - delivery fee paid by the customer
    - payment       payment operator fees (also on cancelled and failed orders)
    - commission    affiliate commission
    = true margin

All amounts in PLN without VAT. Orders labelled as fraud are left out (their revenue would be charged back) and shown
separately in the reconciliation.
"""
from __future__ import annotations

from importlib import resources

import duckdb
import pandas as pd

from product_profitability import i18n
from product_profitability.data import ShopData
from product_profitability.mock_costs import VAT_RATE

STEPS = ("discount", "returns", "shipping", "payment", "commission")
STEP_LABELS = i18n.STEP_LABELS["en"]
LINE_SUMS = ("units", "units_refunded", "units_written_off", "list_revenue", "discount", "purchase_cost", "refund",
             "restocked_cost", "write_off_cost", "return_shipping_cost", "return_handling_cost", "carrier_cost",
             "delivery_fee", "payment_fee", "commission", "shipped_lines", "free_delivery_lines")


def line_costs(shop: ShopData) -> pd.DataFrame:
    """Revenue and every selling cost of each order line (sql/line_costs.sql)."""
    query = resources.files("product_profitability").joinpath("sql/line_costs.sql").read_text(encoding="utf-8")
    vat = shop.truth.get("vat_rate", VAT_RATE)
    for name, key in (("products", "product_id"), ("shipments", "order_id"), ("payments", "order_id")):
        duplicated = getattr(shop, name)[key].duplicated()
        if duplicated.any():
            raise ValueError(f"{name} has more than one row for {key} {getattr(shop, name)[key][duplicated].iloc[0]}")
    with duckdb.connect() as con:
        for name in ("products", "orders", "shipments", "returns", "payments"):
            con.register(name, getattr(shop, name))
        lines = con.execute(query, {"vat": vat}).df()
    expected = shop.orders.loc[~shop.orders["order_id"].isin(fraud_orders(shop)), "order_line_id"]
    if len(lines) != len(expected) or set(lines["order_line_id"]) != set(expected):
        raise ValueError(f"{len(lines)} costed lines for {len(expected)} order lines: a product is missing")
    return lines


def fraud_orders(shop: ShopData) -> set:
    return set(shop.orders.loc[shop.orders["is_fraud"], "order_id"])


def add_steps(table: pd.DataFrame) -> pd.DataFrame:
    """Add the margin steps to a table of summed line amounts (per line, product, category or the whole shop)."""
    out = table.copy()
    out["list_margin"] = out["list_revenue"] - out["purchase_cost"]
    out["returns"] = (out["refund"] - out["restocked_cost"] + out["write_off_cost"] + out["return_shipping_cost"]
                      + out["return_handling_cost"])
    out["shipping"] = out["carrier_cost"] - out["delivery_fee"]
    out["payment"] = out["payment_fee"]
    out["true_margin"] = out["list_margin"] - out[list(STEPS)].sum(axis=1)
    out["net_revenue"] = out["list_revenue"] - out["discount"] - out["refund"]
    out["list_margin_rate"] = _ratio(out["list_margin"], out["list_revenue"])
    out["true_margin_rate"] = _ratio(out["true_margin"], out["net_revenue"])
    out["return_rate"] = _ratio(out["units_refunded"], out["units"])
    return out


def _ratio(top: pd.Series, bottom: pd.Series) -> pd.Series:
    return (top / bottom.where(bottom != 0)).astype(float)


def product_margins(shop: ShopData, lines: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per product that had at least one order line, sorted by units sold."""
    lines = line_costs(shop) if lines is None else lines
    summed = lines.groupby("product_id", as_index=False)[list(LINE_SUMS)].sum()
    info = shop.products[["product_id", "product_name", "color", "category", "product_type", "brand", "parcel_size",
                          "sales_price_gross", "net_purchase_price"]]
    out = add_steps(info.merge(summed, on="product_id", how="inner"))
    return out.sort_values(["units", "product_id"], ascending=[False, True], ignore_index=True)


def shop_cascade(products: pd.DataFrame) -> pd.Series:
    """The margin steps of the whole shop, in the order of the cascade."""
    total = products[["list_margin", *STEPS, "true_margin"]].sum()
    return total.rename(STEP_LABELS)


def reconcile(shop: ShopData, lines: pd.DataFrame) -> pd.DataFrame:
    """
    Every cost in the tables against the same cost spread over order lines. Costs of fraud orders are left out on
    purpose; any other difference means a lost or a doubled line.
    """
    fraud = fraud_orders(shop)
    vat = shop.truth.get("vat_rate", VAT_RATE)

    def split(frame: pd.DataFrame, column: str, scale: float = 1.0) -> tuple[float, float]:
        values = frame[column] * scale
        return float(values.sum()), float(values[frame["order_id"].isin(fraud)].sum())

    sources = {
        "carrier_cost": split(shop.shipments, "carrier_cost"),
        "delivery_fee": split(shop.shipments, "shipping_cost", 1 / (1 + vat)),
        "payment_fee": split(shop.payments, "payment_fee"),
        "commission": split(shop.orders, "affiliate_commission"),
        "refund": split(shop.returns[shop.returns["return_status"].eq("refunded")], "refund_amount", 1 / (1 + vat)),
        "write_off_cost": split(shop.returns, "write_off_cost"),
        "return_shipping_cost": split(shop.returns, "return_shipping_cost"),
        "return_handling_cost": split(shop.returns, "handling_cost"),
    }
    rows = []
    for source, (in_tables, fraud) in sources.items():
        allocated = float(lines[source].sum())
        rows.append({"cost": source, "in_tables": in_tables, "fraud_left_out": fraud, "allocated": allocated,
                     "difference": in_tables - fraud - allocated})
    return pd.DataFrame(rows)
