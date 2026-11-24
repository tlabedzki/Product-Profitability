"""
Loss-making bestsellers: which top sellers lose money after every selling cost, why, and what to do about it.

A bestseller is one of the `bestsellers` products with the highest net revenue. For each one with a negative true
margin the main driver is the margin step that took the most money (or the price list itself when the products were
sold at or below the purchase cost). The move is one of three:

    price           raise the price to break even, or cap the discount where it still breaks even
    free_shipping   take the product out of free delivery (most of its orders shipped free)
    delist          stop selling it: returns far above its category, or a break-even price rise above the limit
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from product_profitability.margin import STEPS, VAT_RATE

DRIVER_LABELS = {
    "price_list": "price below cost", "discount": "discounts", "returns": "returns", "shipping": "shipping",
    "payment": "payment fees", "commission": "affiliate commission",
}


@dataclass(frozen=True)
class Rules:
    bestsellers: int = 500           # top products by net revenue
    max_price_rise: float = 0.10     # a bigger break-even price rise means delist
    free_shipping_share: float = 0.5  # share of shipped lines with free delivery for the free_shipping move
    return_multiple: float = 2.0     # return rate this many times the category rate means delist
    min_discount_cap: float = 0.01   # a break-even discount below this is no discount: raise the price instead
    vat_rate: float = VAT_RATE


def bestsellers(products: pd.DataFrame, rules: Rules = Rules()) -> pd.DataFrame:
    """The top products by net revenue, with their rank (1 = highest)."""
    top = products.sort_values(["net_revenue", "product_id"], ascending=[False, True]).head(rules.bestsellers)
    return top.assign(revenue_rank=np.arange(1, len(top) + 1)).reset_index(drop=True)


def category_return_rates(products: pd.DataFrame) -> pd.Series:
    summed = products.groupby("category")[["units_refunded", "units"]].sum()
    return summed["units_refunded"] / summed["units"].where(summed["units"] > 0)


def add_diagnosis(products: pd.DataFrame, all_products: pd.DataFrame, rules: Rules = Rules()) -> pd.DataFrame:
    """Add driver, break-even price rise, move and a reason sentence to every row (meant for loss-makers)."""
    out = products.copy()
    steps = out[list(STEPS)]
    out["driver"] = np.where(out["list_margin"] <= 0, "price_list", steps.idxmax(axis=1))
    kept = out["units"] - out["units_refunded"]
    unit_gross = out["list_revenue"] * (1 + rules.vat_rate) / out["units"].where(out["units"] > 0)
    rise = -out["true_margin"] * (1 + rules.vat_rate) / kept.where(kept > 0)
    out["break_even_rise"] = rise.clip(lower=0)
    out["break_even_rise_rate"] = (out["break_even_rise"] / unit_gross).fillna(np.inf)
    out["free_delivery_share"] = (out["free_delivery_lines"] / out["shipped_lines"].where(out["shipped_lines"] > 0)
                                  ).fillna(0.0)
    out["category_return_rate"] = out["category"].map(category_return_rates(all_products)).fillna(0.0)
    revenue = out["list_revenue"].where(out["list_revenue"] > 0)
    out["discount_rate"] = (out["discount"] / revenue).fillna(0.0)
    # The biggest average discount that still breaks even (the other costs kept as they are).
    out["break_even_discount_rate"] = ((out["discount"] + out["true_margin"]) / revenue).fillna(0.0)
    out["move"] = [_move(row, rules) for row in out.itertuples(index=False)]
    out["reason"] = [_reason(row) + " " + _action(row, rules) for row in out.itertuples(index=False)]
    return out


def loss_making_bestsellers(products: pd.DataFrame, rules: Rules = Rules()) -> pd.DataFrame:
    """Bestsellers with a negative true margin, the biggest loss first, with driver, move and reason."""
    top = bestsellers(products, rules)
    losing = top[top["true_margin"] < 0]
    return add_diagnosis(losing, products, rules).sort_values("true_margin", ignore_index=True)


def _move(row, rules: Rules) -> str:
    if row.driver == "shipping" and row.free_delivery_share >= rules.free_shipping_share:
        return "free_shipping"
    if row.driver == "returns" and row.return_rate >= rules.return_multiple * max(row.category_return_rate, 1e-9):
        return "delist"
    if row.driver == "discount" and row.break_even_discount_rate >= rules.min_discount_cap:
        return "price"
    return "price" if row.break_even_rise_rate <= rules.max_price_rise else "delist"


def _pln(value: float) -> str:
    return f"{value:,.0f} zł".replace(",", " ")


def _pct(value: float) -> str:
    return f"{value:.0%}"


def _reason(row) -> str:
    against = f"against a price-list margin of {_pln(row.list_margin)}"
    if row.driver == "price_list":
        return f"Sold at or below the purchase cost: the price-list margin is {_pln(row.list_margin)}."
    if row.driver == "discount":
        return f"Discounts (on average {_pct(row.discount_rate)}) took {_pln(row.discount)} {against}."
    if row.driver == "returns":
        written = f", {row.units_written_off:.0f} written off" if row.units_written_off else ""
        return (f"{row.units_refunded:.0f} of {row.units:.0f} units came back (category: "
                f"{_pct(row.category_return_rate)}){written}; returns cost {_pln(row.returns)} {against}.")
    if row.driver == "shipping":
        return (f"Shipping cost {_pln(row.shipping)} more than customers paid for delivery, "
                f"{_pct(row.free_delivery_share)} of orders shipped free, {against}.")
    label = DRIVER_LABELS[row.driver]
    return f"{label.capitalize()} took {_pln(getattr(row, row.driver))} {against}."


def _action(row, rules: Rules) -> str:
    if row.move == "free_shipping":
        return "Take it out of free delivery or add a delivery fee for this product."
    if row.move == "delist":
        if row.driver == "returns":
            return "Delist it or change the supplier."
        return f"Delist it: breaking even needs a price rise of {_pct(row.break_even_rise_rate)}."
    if row.driver == "discount" and row.break_even_discount_rate >= rules.min_discount_cap:
        return f"Cap the discount at {_pct(row.break_even_discount_rate)} to break even."
    return (f"Raise the price by {_pln(row.break_even_rise)} ({_pct(row.break_even_rise_rate)}) per unit to break "
            f"even.")
