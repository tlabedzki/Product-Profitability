"""
Data and titles of the margin cascade and of the loss-making bestseller table, computed once for the app, the README
charts and the animated demo, so the numbers cannot drift apart. Drawing is in figures.py.
"""
from __future__ import annotations

import pandas as pd

from product_profitability.diagnose import DRIVER_LABELS, Rules
from product_profitability.margin import STEP_LABELS, STEPS

MOVE_LABELS = {"price": "Change the price", "free_shipping": "End free delivery", "delist": "Delist"}
LOSS_COLUMNS = ["rank", "product", "category", "units", "return_rate", "net_revenue", "true_margin", "driver",
                "move", "reason"]


def compact(value: float, language: str = "en", unit: str = "") -> str:
    """12345678 -> '12.3M', -72937 -> '−72.9k' (the minus sign, not a hyphen); Polish uses a decimal comma."""
    sign = "−" if value < 0 else ""
    size = abs(value)
    for limit, suffix in ((1e6, "M"), (1e3, "k")):
        if size >= limit:
            text = f"{size / limit:.{2 if size < 10 * limit else 1}f}{suffix}"
            break
    else:
        text = f"{size:.0f}"
    if language == "pl":
        text = text.replace(".", ",")
    return f"{sign}{text}{' ' + unit if unit else ''}"


def percent(value: float, decimals: int = 0) -> str:
    return f"{value:.{decimals}%}"


def categories(products: pd.DataFrame) -> list[str]:
    """Categories by net revenue, the biggest first."""
    return products.groupby("category")["net_revenue"].sum().sort_values(ascending=False).index.tolist()


def cascade_data(products: pd.DataFrame, category: str | None = None) -> pd.DataFrame:
    """
    The bars of the margin cascade of the shop or of one category: the price-list margin, each selling cost as a
    floating bar from the running margin down, and the true margin. The biggest cost is the one to highlight.
    """
    scope = products if category is None else products[products["category"] == category]
    if scope.empty:
        raise ValueError(f"No products sold in {category}")
    total = scope[["list_margin", *STEPS, "true_margin"]].sum()
    rows = [{"step": "list_margin", "kind": "margin", "amount": total["list_margin"], "start": 0.0,
             "end": total["list_margin"]}]
    running = total["list_margin"]
    for step in STEPS:
        rows.append({"step": step, "kind": "cost", "amount": total[step], "start": running,
                     "end": running - total[step]})
        running -= total[step]
    rows.append({"step": "true_margin", "kind": "margin", "amount": total["true_margin"], "start": 0.0,
                 "end": total["true_margin"]})
    data = pd.DataFrame(rows)
    data["label"] = data["step"].map(STEP_LABELS)
    list_margin = total["list_margin"]
    data["share"] = data["amount"] / list_margin if list_margin else float("nan")
    costs = data[data["kind"] == "cost"]
    data["highlight"] = data["step"] == costs.loc[costs["amount"].idxmax(), "step"]
    return data


def cascade_title(data: pd.DataFrame, scope: str = "Lumo", period: tuple | None = None) -> tuple[str, str]:
    """A title that states the finding and a subtitle that says how to read the chart."""
    by_step = data.set_index("step")
    list_margin, true_margin = by_step.loc["list_margin", "amount"], by_step.loc["true_margin", "amount"]
    biggest = data[data["highlight"]].iloc[0]
    if list_margin <= 0:
        title = f"{scope} sells below the purchase cost before any selling cost"
    elif true_margin < 0:
        title = (f"{scope} loses money after selling costs: they take {percent(1 - true_margin / list_margin)} of "
                 f"the price-list margin, {biggest['label'].lower()} the most")
    else:
        lost = 1 - true_margin / list_margin
        title = (f"{scope} keeps {percent(true_margin / list_margin)} of its price-list margin: selling costs take "
                 f"{percent(lost)}, {biggest['label'].lower()} the most")
    when = f", {period[0]:%b %Y} to {period[1]:%b %Y}" if period else ""
    subtitle = (f"Margin in PLN without VAT{when}. From the price-list margin (price minus purchase cost) down to "
                f"the true margin after every selling cost; the biggest cost in copper.")
    return title, subtitle


def loss_table(losing: pd.DataFrame) -> pd.DataFrame:
    """The loss-making bestsellers as a display table (one row per product, the biggest loss first)."""
    table = pd.DataFrame({
        "rank": losing["revenue_rank"].astype(int),
        "product": losing["product_name"] + " (" + losing["color"].fillna("") + ")",
        "category": losing["category"],
        "units": losing["units"].astype(int),
        "return_rate": losing["return_rate"].fillna(0.0),
        "net_revenue": losing["net_revenue"],
        "true_margin": losing["true_margin"],
        "driver": losing["driver"].map(DRIVER_LABELS),
        "move": losing["move"].map(MOVE_LABELS),
        "reason": losing["reason"],
    })
    table["product"] = table["product"].str.replace(" ()", "", regex=False)
    return table.sort_values("true_margin", ignore_index=True)[LOSS_COLUMNS]


def loss_title(losing: pd.DataFrame, rules: Rules | None = None, language: str = "en") -> tuple[str, str]:
    rules = rules or Rules()
    count, loss = len(losing), float(losing["true_margin"].sum())
    if count == 0:
        title = f"All top {rules.bestsellers} bestsellers make money after every selling cost"
    else:
        title = f"{count} of the top {rules.bestsellers} bestsellers lose money, {compact(loss, language)} PLN together"
    subtitle = (f"Bestsellers are the {rules.bestsellers} products with the highest net revenue. Each line names the "
                f"cost that sank it and one move: change the price, end free delivery or delist.")
    return title, subtitle


def loss_markdown(table: pd.DataFrame, rows: int = 10, language: str = "en") -> str:
    """The first rows of the loss table in Markdown for the README (pipes in names escaped)."""
    lines = ["| # | Product | Category | Units | True margin | Move | Why |", "|---:|---|---|---:|---:|---|---|"]
    for row in table.head(rows).itertuples(index=False):
        cells = [str(row.rank), row.product, row.category, str(row.units),
                 compact(row.true_margin, language, "PLN"), row.move, row.reason]
        lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |")
    return "\n".join(lines)
