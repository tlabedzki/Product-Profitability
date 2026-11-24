"""
Stand-in for the shop cost columns of Data-Generator 1.7.0, for older releases that do not have them yet.

The contract (agreed with Data-Generator 1.7.0): all costs in PLN without VAT, rounded to the grosz.

- product_data.parcel_size: small, medium, large or bulky.
- shipment_data.parcel_size and carrier_cost: what the carrier charges the shop for the parcel (plus the collection
  fee for cash on delivery).
- return_data.return_shipping_cost, handling_cost, written_off_quantity and write_off_cost.
- payment_data: one row per order with payment_amount, fee_rate, fixed_fee and payment_fee.
- order_data.affiliate_commission: commission paid to the affiliate network on the units the customer kept.

The rates below copy the Data-Generator 1.7.0 settings (Shop costs). Only the written-off units are drawn at random,
from their own stream, so the mock is the same on every run.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

VAT_RATE = 0.23
SEED = 18
PARCEL_SIZES = ("small", "medium", "large", "bulky")
REALISED = ("delivered", "returned")

BULKY_PRODUCT_TYPES = ["Sofa", "Wardrobe", "Mattress", "Office Desk", "Dining Chair", "Office Chair", "Mountain Bike",
                       "Baby Stroller", "Car Tire"]
DEFAULT_PARCEL_SIZE = "medium"
CATEGORY_PARCEL_SIZE = {
    "Electronics": "small", "Clothing": "small", "Home & Garden": "medium", "Sports": "medium", "Beauty": "small",
    "Toys": "medium", "Automotive": "medium", "Books & Media": "small", "Health": "small", "Pet Supplies": "large",
    "Baby & Kids": "medium", "Office": "small", "Jewelry & Accessories": "small", "Furniture": "large",
    "DIY Tools": "medium",
}
PRODUCT_TYPE_PARCEL_SIZE = {
    "Laptop": "medium", "Printer": "large", "Sneakers": "medium", "Jacket": "medium", "Vacuum Cleaner": "large",
    "Coffee Machine": "large", "Garden Tool": "large", "Car Battery": "large", "Brake Pads": "small",
    "Pet Toy": "small", "Diapers": "large", "Car Seat": "large", "Baby Bottle": "small", "Monitor": "large",
    "Paper Shredder": "large", "Handbag": "medium", "Tool Box": "large",
}
STEP_UP_UNITS = 4

CARRIER_RATES = {
    "InPost parcel locker": {"small": 9.20, "medium": 10.10, "large": 11.40, "bulky": 11.40},
    "InPost courier":       {"small": 11.50, "medium": 12.90, "large": 15.40, "bulky": 69.00},
    "DPD":                  {"small": 12.40, "medium": 14.20, "large": 17.10, "bulky": 75.00},
    "DHL":                  {"small": 12.90, "medium": 14.60, "large": 17.90, "bulky": 79.00},
    "Allegro One":          {"small": 8.40, "medium": 9.20, "large": 10.60, "bulky": 10.60},
    "Orlen Paczka":         {"small": 7.90, "medium": 8.70, "large": 10.20, "bulky": 10.20},
    "Poczta Polska":        {"small": 9.60, "medium": 11.30, "large": 14.10, "bulky": 14.10},
    "UPS":                  {"small": 14.90, "medium": 17.20, "large": 21.40, "bulky": 89.00},
    "FedEx":                {"small": 16.50, "medium": 19.40, "large": 24.10, "bulky": 95.00},
    "Store pickup":         {"small": 3.00, "medium": 3.00, "large": 4.50, "bulky": 25.00},
}
DEFAULT_CARRIER_RATES = {"small": 13.00, "medium": 15.00, "large": 18.00, "bulky": 80.00}
COD_COLLECTION_FEE = {"rate": 0.01, "fixed": 2.00}

RETURN_LABEL_RATES = {"small": 8.50, "medium": 9.50, "large": 12.50, "bulky": 79.00}
SHOP_PAID_RETURN_REASONS = ["defective", "damaged", "wrong_item", "not_as_described", "wrong_size"]
RETURN_HANDLING_COST = {"per_return": 6.00, "per_unit": 2.00, "bulky_extra": 25.00}
WRITE_OFF_SHARE = {"defective": 0.85, "damaged": 0.75, "not_as_described": 0.15, "wrong_item": 0.05,
                   "changed_mind": 0.05, "wrong_size": 0.03}
DEFAULT_WRITE_OFF_SHARE = 0.10

PAYMENT_FEE_RATE = {"BLIK": 0.012, "Card": 0.016, "Fast transfer": 0.011, "Deferred payment": 0.035, "COD": 0.0,
                    "Wallet": 0.018, "Bank transfer": 0.005}
DEFAULT_PAYMENT_FEE_RATE = 0.015
PAYMENT_FIXED_FEE = {"PayU": 0.25, "Przelewy24": 0.30, "Tpay": 0.25, "Autopay": 0.20, "Stripe": 1.00, "PayPal": 1.35,
                     "PayPo": 0.00, "Other": 0.30}
DEFAULT_PAYMENT_FIXED_FEE = 0.30
FAILED_PAYMENT_FEE = {"Card": 0.30}
METHODS_WITHOUT_OPERATOR = ["COD"]

AFFILIATE_COMMISSION_RATE = {"Electronics": 0.03, "Clothing": 0.10, "Beauty": 0.09, "Jewelry & Accessories": 0.10,
                             "Health": 0.07, "Sports": 0.07, "Toys": 0.07, "Home & Garden": 0.06, "Furniture": 0.05,
                             "Books & Media": 0.05}
DEFAULT_AFFILIATE_COMMISSION_RATE = 0.06


def rates() -> dict:
    """The mock rates, saved to truth.json next to the data so that reports can name them."""
    return {
        "carrier_rates": CARRIER_RATES, "default_carrier_rates": DEFAULT_CARRIER_RATES,
        "cod_collection_fee": COD_COLLECTION_FEE, "return_label_rates": RETURN_LABEL_RATES,
        "shop_paid_return_reasons": SHOP_PAID_RETURN_REASONS, "return_handling_cost": RETURN_HANDLING_COST,
        "write_off_share": WRITE_OFF_SHARE, "default_write_off_share": DEFAULT_WRITE_OFF_SHARE,
        "payment_fee_rate": PAYMENT_FEE_RATE, "default_payment_fee_rate": DEFAULT_PAYMENT_FEE_RATE,
        "payment_fixed_fee": PAYMENT_FIXED_FEE, "default_payment_fixed_fee": DEFAULT_PAYMENT_FIXED_FEE,
        "failed_payment_fee": FAILED_PAYMENT_FEE, "affiliate_commission_rate": AFFILIATE_COMMISSION_RATE,
        "default_affiliate_commission_rate": DEFAULT_AFFILIATE_COMMISSION_RATE,
    }


def parcel_size(products: pd.DataFrame) -> pd.Series:
    """Parcel size of every product: bulky types, then the product type exception, then the category."""
    size = products["category"].map(CATEGORY_PARCEL_SIZE).fillna(DEFAULT_PARCEL_SIZE)
    by_type = products["product_type"].map(PRODUCT_TYPE_PARCEL_SIZE)
    size = by_type.fillna(size)
    size[products["product_type"].isin(BULKY_PRODUCT_TYPES)] = "bulky"
    return size.astype(str)


def _net(gross: pd.Series | np.ndarray) -> np.ndarray:
    return np.asarray(gross, dtype=float) / (1 + VAT_RATE)


def _line_value_gross(orders: pd.DataFrame) -> pd.Series:
    return orders["quantity"] * orders["unit_price_gross"] * (1 - orders["discount_rate"])


def _shipments(shipments, orders, products) -> pd.DataFrame:
    size_rank = {size: rank for rank, size in enumerate(PARCEL_SIZES)}
    lines = orders[["order_id", "product_id", "quantity", "payment_method"]].merge(
        products[["product_id", "parcel_size"]], on="product_id", how="left")
    lines["rank"] = lines["parcel_size"].map(size_rank).fillna(size_rank[DEFAULT_PARCEL_SIZE])
    per_order = lines.groupby("order_id").agg(rank=("rank", "max"), units=("quantity", "sum"),
                                              payment_method=("payment_method", "first"))
    step_up = (per_order["units"] >= STEP_UP_UNITS) & (per_order["rank"] < size_rank["large"])
    per_order.loc[step_up, "rank"] += 1
    per_order["parcel_size"] = per_order["rank"].astype(int).map(dict(enumerate(PARCEL_SIZES)))

    out = shipments.copy()
    size = out["order_id"].map(per_order["parcel_size"])
    out["parcel_size"] = size.to_numpy()
    base = [CARRIER_RATES.get(method, DEFAULT_CARRIER_RATES)[s] for method, s in zip(out["delivery_method"], size,
                                                                                    strict=True)]
    collected = out["order_id"].map(_line_value_gross(orders).groupby(orders["order_id"]).sum()) + out["shipping_cost"]
    cod = out["order_id"].map(per_order["payment_method"]).eq("COD")
    fee = np.where(cod, collected * COD_COLLECTION_FEE["rate"] + COD_COLLECTION_FEE["fixed"], 0.0)
    out["carrier_cost"] = np.round(np.asarray(base) + fee, 2)
    return out


def _returns(returns, products, generator) -> pd.DataFrame:
    out = returns.copy()
    info = products.set_index("product_id")
    size = out["product_id"].map(info["parcel_size"]).fillna(DEFAULT_PARCEL_SIZE)
    shop_pays = out["return_reason"].isin(SHOP_PAID_RETURN_REASONS)
    out["return_shipping_cost"] = np.where(shop_pays, size.map(RETURN_LABEL_RATES), 0.0).round(2)
    handling = (RETURN_HANDLING_COST["per_return"] + RETURN_HANDLING_COST["per_unit"] * out["returned_quantity"]
                + np.where(size.eq("bulky"), RETURN_HANDLING_COST["bulky_extra"], 0.0))
    out["handling_cost"] = np.round(handling.to_numpy(dtype=float), 2)
    share = out["return_reason"].map(WRITE_OFF_SHARE).fillna(DEFAULT_WRITE_OFF_SHARE).to_numpy()
    drawn = generator.binomial(out["returned_quantity"].to_numpy(), share)
    out["written_off_quantity"] = np.where(out["return_status"].eq("refunded"), drawn, 0).astype("int64")
    cost = out["product_id"].map(info["net_purchase_price"]).to_numpy(dtype=float)
    out["write_off_cost"] = np.round(out["written_off_quantity"] * cost, 2)
    return out


def _payments(orders, shipments) -> pd.DataFrame:
    first = orders.drop_duplicates("order_id").set_index("order_id")
    goods = _line_value_gross(orders).groupby(orders["order_id"]).sum()
    delivery = shipments.set_index("order_id")["shipping_cost"].reindex(first.index).fillna(0.0)
    status, method = first["order_status"], first["payment_method"]
    unpaid = (status.eq("cancelled") & method.isin(METHODS_WITHOUT_OPERATOR)) | status.eq("payment_failed")
    amount = np.where(unpaid, 0.0, goods.reindex(first.index).to_numpy() + delivery.to_numpy())
    rate = method.map(PAYMENT_FEE_RATE).fillna(DEFAULT_PAYMENT_FEE_RATE).to_numpy()
    fixed = first["payment_provider"].map(PAYMENT_FIXED_FEE).fillna(DEFAULT_PAYMENT_FIXED_FEE).to_numpy()
    fixed = np.where(method.isin(METHODS_WITHOUT_OPERATOR), 0.0, fixed)
    failed_fee = method.map(FAILED_PAYMENT_FEE).fillna(0.0).to_numpy()
    fee = np.where(status.eq("payment_failed"), failed_fee, np.where(amount > 0, amount * rate + fixed, 0.0))
    return pd.DataFrame({
        "payment_id": np.arange(1, len(first) + 1), "order_id": first.index.to_numpy(),
        "payment_amount": np.round(amount, 2), "fee_rate": np.where(status.eq("payment_failed"), 0.0, rate),
        "fixed_fee": np.where(status.eq("payment_failed"), failed_fee, fixed), "payment_fee": np.round(fee, 2),
    })


def _commission(orders, returns, products) -> pd.Series:
    category = orders["product_id"].map(products.set_index("product_id")["category"])
    rate = category.map(AFFILIATE_COMMISSION_RATE).fillna(DEFAULT_AFFILIATE_COMMISSION_RATE)
    refunded = returns[returns["return_status"].eq("refunded")].groupby("order_line_id")["returned_quantity"].sum()
    kept = orders["quantity"] - orders["order_line_id"].map(refunded).fillna(0)
    unit_net = _net(orders["unit_price_gross"] * (1 - orders["discount_rate"]))
    eligible = orders["channel"].eq("affiliate") & orders["order_status"].isin(REALISED)
    return pd.Series(np.round(np.where(eligible, rate * kept * unit_net, 0.0), 2), index=orders.index)


def add_costs(products, orders, shipments, returns) -> tuple[pd.DataFrame, ...]:
    """Return products, orders, shipments, returns and payments with the 1.7.0 cost columns added."""
    generator = np.random.default_rng(SEED)
    products = products.copy()
    products["parcel_size"] = parcel_size(products)
    shipments = _shipments(shipments, orders, products)
    returns = _returns(returns, products, generator)
    payments = _payments(orders, shipments)
    orders = orders.copy()
    orders["affiliate_commission"] = _commission(orders, returns, products)
    return products, orders, shipments, returns, payments
