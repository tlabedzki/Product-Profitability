"""
Data and titles of the margin cascade, the category chart and the loss-making bestseller table, computed once for the
app and the README charts, so the numbers cannot drift apart. Drawing is in figures.py. Every function that writes
words or numbers for people takes `language` ("en" for the app and the public README, "pl" for the private README).
"""
from __future__ import annotations

import pandas as pd

from product_profitability import i18n
from product_profitability.diagnose import Rules
from product_profitability.margin import STEPS

MOVE_LABELS = i18n.MOVE_LABELS["en"]
LOSS_COLUMNS = ["product_id", "rank", "product", "category", "units", "return_rate", "net_revenue", "true_margin",
                "driver", "move", "reason"]
LOSS_HEADERS = {
    "en": "| # | Product | Category | Units | True margin | Main cost | Move |",
    "pl": "| # | Produkt | Kategoria | Sztuki | Marża na czysto | Główny koszt | Ruch |",
}


def compact(value: float, language: str = "en", unit: str = "") -> str:
    """
    12345678 -> '12.3M' and -72937 -> '−72.9k' (a minus sign, not a hyphen); in Polish '12,3 mln' and '−72,9 tys.'.
    """
    sign = "−" if value < 0 else ""
    size = abs(value)
    suffixes = ((1e6, " mln"), (1e3, " tys.")) if language == "pl" else ((1e6, "M"), (1e3, "k"))
    for limit, suffix in suffixes:
        scaled = round(size / limit, 2)  # round first: 999,960 is 1.00M, not 1000.0k
        if scaled >= 1:
            number = f"{size / limit:.{2 if scaled < 10 else 1}f}"
            text = (number.replace(".", ",") if language == "pl" else number) + suffix
            break
    else:
        text = f"{size:.0f}"
    return f"{sign}{text}{' ' + unit if unit else ''}"


def percent(value: float, decimals: int = 0, language: str = "en") -> str:
    if pd.isna(value):
        return "–"
    text = f"{value:.{decimals}%}".replace("-", "−")
    return text.replace(".", ",") if language == "pl" else text


def money(value: float, language: str = "en") -> str:
    """Whole złoty: '5,708 PLN' or '5 708 zł'."""
    text = f"{value:,.0f}".replace("-", "−")
    return f"{text.replace(',', ' ')} zł" if language == "pl" else f"{text} PLN"


def categories(products: pd.DataFrame) -> list[str]:
    """Categories by net revenue, the biggest first."""
    return products.groupby("category")["net_revenue"].sum().sort_values(ascending=False).index.tolist()


def cascade_data(products: pd.DataFrame, category: str | None = None, language: str = "en") -> pd.DataFrame:
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
    data["label"] = data["step"].map(i18n.STEP_LABELS[i18n.check(language)])
    list_margin = total["list_margin"]
    data["share"] = data["amount"] / list_margin if list_margin else float("nan")
    costs = data[data["kind"] == "cost"]
    data["highlight"] = data["step"] == costs.loc[costs["amount"].idxmax(), "step"]
    return data


def _period(period, language: str) -> str:
    if not period:
        return ""
    start, end = (i18n.month(stamp, language) for stamp in period)
    return f", {start} – {end}" if language == "pl" else f", {start} to {end}"


def cascade_title(data: pd.DataFrame, scope: str = "Lumo", period: tuple | None = None,
                  language: str = "en") -> tuple[str, str]:
    """A title that states the finding and a subtitle that says how to read the chart."""
    by_step = data.set_index("step")
    list_margin, true_margin = by_step.loc["list_margin", "amount"], by_step.loc["true_margin", "amount"]
    biggest = data[data["highlight"]].iloc[0]["label"].lower()
    kept = true_margin / list_margin if list_margin > 0 else float("nan")
    lost = percent(1 - kept, language=language)
    if language == "pl":
        if list_margin <= 0:
            title = f"{scope}: sprzedaż poniżej kosztu zakupu jeszcze przed kosztami sprzedaży"
        elif true_margin < 0:
            title = f"{scope} traci na sprzedaży: koszty zabierają {lost} marży z cennika, najwięcej {biggest}"
        else:
            title = (f"{scope} zatrzymuje {percent(kept, language='pl')} marży z cennika: koszty sprzedaży zabierają "
                     f"{lost}, najwięcej {biggest}")
        subtitle = (f"Marża w zł bez VAT{_period(period, language)}. Od marży z cennika (cena minus koszt zakupu) do "
                    f"marży po wszystkich kosztach sprzedaży; największy koszt na miedziano.")
        return title, subtitle
    if list_margin <= 0:
        title = f"{scope} sells below the purchase cost before any selling cost"
    elif true_margin < 0:
        title = (f"{scope} loses money after selling costs: they take {lost} of the price-list margin, "
                 f"{biggest} the most")
    else:
        title = (f"{scope} keeps {percent(kept)} of its price-list margin: selling costs take {lost}, "
                 f"{biggest} the most")
    subtitle = (f"Margin in PLN without VAT{_period(period, language)}. From the price-list margin (price minus "
                f"purchase cost) down to the true margin after every selling cost; the biggest cost in copper.")
    return title, subtitle


def category_data(products: pd.DataFrame, language: str = "en") -> pd.DataFrame:
    """Share of the price-list margin each category keeps after selling costs, the lowest first (highlighted)."""
    language = i18n.check(language)
    summed = products.groupby("category")[["list_margin", *STEPS, "true_margin"]].sum()
    # A category sold at or below the purchase cost has no share to keep (NaN) and goes first, as the worst.
    kept = summed["true_margin"] / summed["list_margin"].where(summed["list_margin"] > 0)
    out = pd.DataFrame({
        "category": summed.index,
        "label": [i18n.category(name, language) for name in summed.index],
        "list_margin": summed["list_margin"].to_numpy(),
        "true_margin": summed["true_margin"].to_numpy(),
        "kept": kept.to_numpy(),
        "biggest": summed[list(STEPS)].idxmax(axis=1).map(i18n.STEP_LABELS[language]).str.lower().to_numpy(),
    }).sort_values(["kept", "category"], ignore_index=True, na_position="first")
    out["highlight"] = out.index == 0
    return out


def category_title(data: pd.DataFrame, language: str = "en") -> tuple[str, str]:
    lowest, highest = data.iloc[0], data.iloc[-1]
    low, high = percent(lowest["kept"], language=language), percent(highest["kept"], language=language)
    if language == "pl":
        title = f"{lowest['label']} zatrzymuje najmniej marży z cennika: {low}, najwięcej zabierają {lowest['biggest']}"
        subtitle = (f"Udział marży z cennika, który zostaje po kosztach sprzedaży, w każdej kategorii; najwięcej "
                    f"zostaje w kategorii {highest['label']} ({high}).")
        return title, subtitle
    title = f"{lowest['label']} keeps the least of its price-list margin: {low}, {lowest['biggest']} take the most"
    subtitle = (f"Share of the price-list margin left after selling costs, by category; {highest['label']} keeps the "
                f"most ({high}).")
    return title, subtitle


def loss_table(losing: pd.DataFrame, language: str = "en") -> pd.DataFrame:
    """The loss-making bestsellers as a display table (one row per product, the biggest loss first)."""
    language = i18n.check(language)
    colors = losing["color"].fillna("").map(lambda name: i18n.color(name, language))
    table = pd.DataFrame({
        "product_id": losing["product_id"].astype(int),
        "rank": losing["revenue_rank"].astype(int),
        "product": losing["product_name"] + " (" + colors + ")",
        "category": losing["category"].map(lambda name: i18n.category(name, language)),
        "units": losing["units"].astype(int),
        "return_rate": losing["return_rate"].fillna(0.0),
        "net_revenue": losing["net_revenue"],
        "true_margin": losing["true_margin"],
        "driver": losing["driver"].map(i18n.DRIVER_LABELS[language]),
        "move": losing["move"].map(i18n.MOVE_LABELS[language]),
        "reason": losing["reason"],
    })
    table["product"] = table["product"].str.replace(" ()", "", regex=False)
    return table.sort_values(["true_margin", "product_id"], ignore_index=True)[LOSS_COLUMNS]


def loss_title(losing: pd.DataFrame, rules: Rules | None = None, language: str = "en") -> tuple[str, str]:
    rules = rules or Rules()
    count, loss = len(losing), float(losing["true_margin"].sum())
    if language == "pl":
        if count == 0:
            return (f"Każdy z {rules.bestsellers} bestsellerów zarabia po wszystkich kosztach sprzedaży",
                    "Bestsellery to produkty z najwyższym przychodem netto.")
        lose = i18n.plural_pl(count, "traci", "tracą", "traci")
        noun = i18n.plural_pl(rules.bestsellers, "produkt", "produkty", "produktów")
        return (f"{count} z {rules.bestsellers} bestsellerów {lose} pieniądze, razem {compact(loss, 'pl', 'zł')}",
                f"Bestsellery to {rules.bestsellers} {noun} z najwyższym przychodem netto. Przy każdym koszt, który "
                f"go pogrążył, i jeden ruch: zmiana ceny, koniec darmowej dostawy albo wycofanie.")
    if count == 0:
        title = f"All top {rules.bestsellers} bestsellers make money after every selling cost"
    else:
        title = f"{count} of the top {rules.bestsellers} bestsellers lose money, {compact(loss, language)} PLN together"
    subtitle = (f"Bestsellers are the {rules.bestsellers} products with the highest net revenue. Each line names the "
                f"cost that sank it and one move: change the price, end free delivery or delist.")
    return title, subtitle


def loss_markdown(table: pd.DataFrame, rows: int = 10, language: str = "en") -> str:
    """The first rows of the loss table in Markdown for the README (pipes in names escaped)."""
    lines = [LOSS_HEADERS[i18n.check(language)], "|---:|---|---|---:|---:|---|---|"]
    for row in table.head(rows).itertuples(index=False):
        cells = [str(row.rank), row.product, row.category, str(row.units), money(row.true_margin, language),
                 row.driver, row.move]
        lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |")
    return "\n".join(lines)


ORDER_COLUMNS = ["order_date", "order_id", "status", "units", "unit_price_gross", "discount_rate", "delivery",
                 "payment", "channel", "returned", "true_margin"]


def product_label(row) -> str:
    color = f" ({row.color})" if isinstance(row.color, str) and row.color else ""
    return f"{row.product_name}{color}"


def product_options(products: pd.DataFrame, limit: int = 2000) -> list[dict[str, str]]:
    """The products to pick a card from: the `limit` biggest by net revenue, as Select options."""
    top = products.sort_values(["net_revenue", "product_id"], ascending=[False, True]).head(limit)
    return [{"value": str(row.product_id), "label": f"{product_label(row)} · #{rank}"}
            for rank, row in enumerate(top.itertuples(index=False), start=1)]


def product_orders(orders: pd.DataFrame, returns: pd.DataFrame, lines: pd.DataFrame, product_id: int) -> pd.DataFrame:
    """Every order line of one product with its true margin, the newest first (fraud orders are not in `lines`)."""
    from product_profitability.margin import add_steps

    own = add_steps(lines[lines["product_id"] == product_id])
    info = orders[["order_line_id", "order_date", "order_status", "unit_price_gross", "discount_rate",
                   "delivery_method", "payment_method", "channel", "quantity"]]
    back = returns.groupby("order_line_id").agg(reason=("return_reason", "first"), state=("return_status", "first"),
                                                back=("returned_quantity", "sum"))
    table = own.merge(info, on="order_line_id", how="left").join(back, on="order_line_id")
    returned = [f"{int(n)} × {reason.replace('_', ' ')} ({state})" if isinstance(reason, str) else ""
                for n, reason, state in zip(table["back"], table["reason"], table["state"], strict=True)]
    out = pd.DataFrame({
        "order_date": table["order_date"], "order_id": table["order_id"],
        "status": table["order_status"].str.replace("_", " "), "units": table["quantity"].astype(int),
        "unit_price_gross": table["unit_price_gross"], "discount_rate": table["discount_rate"],
        "delivery": table["delivery_method"], "payment": table["payment_method"], "channel": table["channel"],
        "returned": returned, "true_margin": table["true_margin"],
    })
    return out.sort_values(["order_date", "order_id"], ascending=False, ignore_index=True)[ORDER_COLUMNS]
