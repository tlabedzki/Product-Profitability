"""
Dash + Mantine app of Product Profitability, in the portfolio look of Data-Generator: the margin cascade of the shop
or a category, the bestsellers that lose money (live rules) and the card of one product with its orders.

Run locally (from the repository root):
    python -m ui.app            # http://127.0.0.1:8050

The address can set the sliders and the product card, so a view is a link: /?bestsellers=200&rise=15&product=209170.
The server listens on 127.0.0.1 only.
"""
from __future__ import annotations

import os
import sys
from functools import cache, lru_cache
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import dash._dash_renderer  # noqa: E402
import dash_mantine_components as dmc  # noqa: E402
import pandas as pd  # noqa: E402
from dash import ALL, Dash, Input, Output, ctx, dcc, html, no_update  # noqa: E402

from product_profitability import data, diagnose, figures, margin, report  # noqa: E402
from ui import theme as t  # noqa: E402

dash._dash_renderer._set_react_version("19.2.4")  # Mantine 3 needs React 19; Dash 4.5 still defaults to 18

REPO_URL = "https://github.com/tlabedzki/Product-Profitability"
ALL_CATEGORIES = "all"
PRODUCT_OPTIONS = 2000
# name: (label, help, minimum, maximum, step, default, (prefix, decimals, suffix) of the value)
RULES = {
    "bestsellers": ("Bestsellers", "How many products with the highest net revenue count as bestsellers.",
                    100, 2000, 100, diagnose.Rules.bestsellers, ("top ", 0, "")),
    "rise": ("Largest acceptable price rise", "A loss that needs a bigger price rise to break even means delist.",
             0, 30, 1, round(diagnose.Rules.max_price_rise * 100), ("", 0, "%")),
}
LOSS_COLUMNS = [  # column, header, css class
    ("rank", "#", "pp-num"), ("product", "Product", ""), ("category", "Category", ""), ("units", "Units", "pp-num"),
    ("return_rate", "Returned", "pp-num"), ("true_margin", "True margin", "pp-num"), ("move", "Move", ""),
]
ORDER_COLUMNS = [
    ("order_date", "Date", ""), ("order_id", "Order", "pp-num"), ("status", "Status", ""), ("units", "Units", "pp-num"),
    ("unit_price_gross", "Price", "pp-num"), ("discount_rate", "Discount", "pp-num"), ("delivery", "Delivery", ""),
    ("payment", "Payment", ""), ("channel", "Channel", ""), ("returned", "Returned", ""),
    ("true_margin", "True margin", "pp-num"),
]


pln = report.money  # "5,708 PLN"


def amount(value: float) -> str:
    return f"{value:,.0f}".replace("-", "−")


pct = report.percent  # "34%", "–" when there is no value


# ---------------------------------------------------------------------------------------------------------------- #
# Data

@cache
def prepare():
    """Shop data, costed order lines and product margins, computed once."""
    shop = data.load()
    lines = margin.line_costs(shop)
    return shop, lines, margin.product_margins(shop, lines)


def rules_for(bestsellers, rise) -> diagnose.Rules:
    """The rules of the two sliders (the price rise in percent)."""
    return diagnose.Rules(bestsellers=int(bestsellers), max_price_rise=float(rise) / 100)


@lru_cache(maxsize=64)
def losing_for(bestsellers: int, rise: int) -> pd.DataFrame:
    """Loss-making bestsellers for one setting of the two sliders (cached: callbacks share it)."""
    _, _, products = prepare()
    return diagnose.loss_making_bestsellers(products, rules_for(bestsellers, rise))


@cache
def product_choices() -> tuple[list[dict[str, str]], frozenset[str], str]:
    """Options of the product picker, their values and the default card (the biggest loss), computed once."""
    _, _, products = prepare()
    options = report.product_options(products, PRODUCT_OPTIONS)
    losing = losing_for(RULES["bestsellers"][5], RULES["rise"][5])
    first = losing["product_id"].iloc[0] if len(losing) else products.sort_values("net_revenue").iloc[-1].product_id
    return options, frozenset(option["value"] for option in options), str(int(first))


def rule_text(name: str, value: float) -> str:
    prefix, decimals, suffix = RULES[name][-1]
    return f"{prefix}{float(value):.{decimals}f}{suffix}"


def start_product(requested: str | None = None) -> str:
    """The product of the card when the page opens: ?product=… if it is on the list, else the biggest loss."""
    _, values, default = product_choices()
    return requested if requested in values else default


# ---------------------------------------------------------------------------------------------------------------- #
# Building blocks

def section(number, title, lead, body, section_id):
    return html.Section([
        html.Div([html.Span(f"{number:02d}", className="dg-step"), html.H2(title, className="dg-h2")],
                 className="dg-section-head"),
        dmc.Text(lead, className="dg-lead-small"),
        html.Div(body, id=f"{section_id}-body"),
    ], id=section_id, className="dg-section")


def stat(label, value, note="", extra_class=""):
    return html.Div([html.Div(value, className="dg-stat-value"), html.Div(label, className="dg-stat-label"),
                     html.Div(note, className="dg-stat-note")], className=f"dg-stat {extra_class}".strip())


def start_values(args) -> dict[str, float]:
    """Slider values from the address (/?bestsellers=200&rise=15), clipped to the slider range; defaults otherwise."""
    values = {}
    for name, (_, _, low, high, step, default, _) in RULES.items():
        try:
            value = float(args.get(name, default))
        except (TypeError, ValueError):
            value = default
        value = min(max(value, low), high)
        values[name] = int(round(value / step) * step)
    return values


def rule_slider(name, value=None):
    label, help_text, low, high, step, default, (prefix, decimals, suffix) = RULES[name]
    value = default if value is None else value
    return html.Div([
        html.Div([dmc.Text(label, className="dg-label"),
                  html.Span(rule_text(name, value), id=f"{name}-value", className="pp-rule-value",
                            **{"data-prefix": prefix, "data-decimals": str(decimals), "data-suffix": suffix})],
                 className="pp-rule-head"),
        dmc.Text(help_text, className="dg-caption pp-rule-help"),
        dmc.Slider(id=name, min=low, max=high, step=step, value=value, color="petrol", size="sm", label=None,
                   updatemode="mouseup", className="pp-slider"),
    ], className="pp-rule")


def chart_block(text, figure, extra_class=""):
    title, subtitle = text
    return html.Figure([
        html.Figcaption([html.Div(title, className="dg-chart-title"), html.Div(subtitle, className="dg-chart-sub")]),
        dcc.Graph(figure=figure, config=figures.CONFIG, className="dg-graph",
                  style={"height": f"{figure.layout.height}px"}),
    ], className=f"dg-chart {extra_class}")


def scroll_table(header, rows, label):
    table = html.Table([html.Thead(html.Tr(header)), html.Tbody(rows)], className="dg-table pp-table")
    return html.Div(table, className="dg-table-scroll", tabIndex="0", role="region", **{"aria-label": label})


# ---------------------------------------------------------------------------------------------------------------- #
# Views (pure functions of the data, tested without a browser)

def cascade_view(products: pd.DataFrame, category: str | None, period) -> list:
    chosen = None if category in (None, ALL_CATEGORIES) else category
    cascade = report.cascade_data(products, chosen)
    scope = products if chosen is None else products[products["category"] == chosen]
    by_step = cascade.set_index("step")["amount"]
    kept = by_step["true_margin"] / by_step["list_margin"] if by_step["list_margin"] else float("nan")
    losing = int((scope["true_margin"] < 0).sum())
    stats = html.Div([
        stat("price-list margin, PLN", report.compact(by_step["list_margin"]), "price minus purchase cost"),
        stat("true margin, PLN", report.compact(by_step["true_margin"]), "after every selling cost"),
        stat("of the margin kept", pct(kept), f"{pct(1 - kept)} goes to selling costs"),
        stat("products lose money", f"{losing:,}", f"of {len(scope):,} sold"),
    ], className="dg-stats pp-stats-4")
    chart = chart_block(report.cascade_title(cascade, chosen or "Lumo", period), figures.cascade(cascade),
                        "pp-block")
    return [stats, chart]


def loss_stats(losing: pd.DataFrame, bestsellers: int) -> html.Div:
    moves = losing["move"].value_counts()
    return html.Div([
        stat("bestsellers lose money", f"{len(losing):,}", f"of the top {int(bestsellers):,}"),
        stat("loss together, PLN", report.compact(float(losing["true_margin"].sum())), "true margin", "pp-negative"),
        stat("change the price", f"{moves.get('price', 0):,}", "raise it or cap the discount"),
        stat("end free delivery", f"{moves.get('free_shipping', 0):,}", "shipping sinks them"),
        stat("delist", f"{moves.get('delist', 0):,}", "no price fixes them"),
    ], className="dg-stats")


def loss_view(losing: pd.DataFrame) -> list:
    if losing.empty:
        return [html.P("No bestseller loses money with these rules.", className="dg-placeholder")]
    rows = []
    for row in report.loss_table(losing).to_dict("records"):
        product_id = row["product_id"]
        cells = []
        for column, _, css in LOSS_COLUMNS:
            value = row[column]
            if column == "product":
                content = [html.Button(value, id={"type": "open-product", "index": int(product_id)},
                                       className="pp-open", title=f"Open the card of {value}"),
                           html.Div(row["reason"], className="pp-why-line")]
                css = "pp-product"
            elif column == "true_margin":
                content, css = pln(value), css + " pp-loss"
            elif column == "return_rate":
                content = pct(value)
            else:
                content = f"{value:,}" if isinstance(value, int) else value
            cells.append(html.Td(content, className=css or None))
        rows.append(html.Tr(cells))
    header = [html.Th(name, className=css or None) for _, name, css in LOSS_COLUMNS]
    return [
        scroll_table(header, rows, "Loss-making bestsellers, scrolls in both directions"),
        dmc.Text("Open a product to see its own cascade and every order.", className="dg-caption", mt="sm"),
    ]


def card_view(shop, lines: pd.DataFrame, products: pd.DataFrame, product_id: int,
              rules: diagnose.Rules | None = None) -> list:
    """The card of one product; its verdict uses the same rules as the loss table (the two sliders)."""
    rules = rules or diagnose.Rules()
    row = products.set_index("product_id").loc[product_id]
    one = products[products["product_id"] == product_id]
    name = report.product_label(one.iloc[0])
    stats = html.Div([
        stat("true margin, PLN", amount(row["true_margin"]), f"{pct(row['true_margin_rate'])} of net revenue",
             "pp-negative" if row["true_margin"] < 0 else ""),
        stat("units sold", f"{int(row['units']):,}", f"{int(row['units_refunded']):,} came back"),
        stat("price-list margin, PLN", amount(row["list_margin"]), f"{pct(row['list_margin_rate'])} of the list price"),
        stat("price today, PLN", amount(row["sales_price_gross"]), f"{row['category']}, {row['parcel_size']} parcel"),
    ], className="dg-stats pp-stats-4")
    diagnosis = diagnose.add_diagnosis(one, products, rules)
    if row["true_margin"] < 0:
        verdict = html.P([html.B("Loses money. "), diagnosis["reason"].iloc[0]], className="pp-verdict")
    else:
        verdict = html.P([html.B("Makes money "), "after every selling cost."], className="pp-verdict pp-fine")
    cascade = report.cascade_data(one)
    orders = report.product_orders(shop.orders, shop.returns, lines, product_id)
    header = [html.Th(title, className=css or None) for _, title, css in ORDER_COLUMNS]
    rows = [html.Tr([_order_cell(column, css, record) for column, _, css in ORDER_COLUMNS])
            for record in orders.to_dict("records")]
    return [
        html.H3(name, className="dg-chart-title"),
        stats, verdict,
        chart_block(report.cascade_title(cascade, name, shop.period), figures.cascade(cascade), "pp-block"),
        html.Div([html.Div(f"Every order line ({len(orders):,})", className="dg-chart-title"),
                  html.Div("Newest first. The true margin of a line carries its share of the order's delivery and "
                           "payment costs.", className="dg-chart-sub"),
                  scroll_table(header, rows, "Orders of the product, scrolls in both directions")],
                 className="pp-chart-gap"),
    ]


def _order_cell(column, css, record):
    value = record[column]
    if column == "order_date":
        text = f"{value:%Y-%m-%d}"
    elif column == "unit_price_gross":
        text = f"{value:,.0f} PLN"
    elif column == "discount_rate":
        text = pct(value) if value else ""
    elif column == "true_margin":
        text = pln(value)
        css += " pp-loss" if value < 0 else " pp-gain"
    elif column == "order_id":
        text = str(value)
    else:
        text = f"{value:,}" if isinstance(value, int) else value
    return html.Td(text, className=css.strip() or None)


# ---------------------------------------------------------------------------------------------------------------- #
# Page

def page():
    try:
        shop, _, products = prepare()
    except (FileNotFoundError, ValueError) as error:  # no data, or data that breaks the cost contract
        shop, products, problem = None, None, str(error)
    header = html.Header(html.Div([
        html.Span(["Product Profitability", html.Span(".", className="dg-dot")], className="dg-wordmark"),
        html.A("Source on GitHub", href=REPO_URL, target="_blank", className="dg-link"),
    ], className="dg-wrap dg-topline"))
    hero = html.Div([
        html.P("True margin per product", className="dg-eyebrow"),
        html.H1(["What every product ", html.Em("really"), " earns,", html.Br(), " after every selling cost."],
                className="dg-h1"),
        html.P("The margin in the price list leaves out discounts, returns, shipping, payment fees and commissions. "
               "This app takes them out product by product and names the bestsellers that lose money.",
               className="dg-lead"),
    ], className="dg-hero")
    if shop is None:
        body = [hero, section(1, "Margin", "The shop data is missing or incomplete.",
                              html.P(problem, className="dg-placeholder"), "cascade")]
    else:
        # The address (?bestsellers=…&rise=…&product=…) is read by apply_address: Dash fetches this layout with a
        # request of its own, which does not carry the page's query string.
        categories = [{"value": ALL_CATEGORIES, "label": "All categories"}] + [
            {"value": c, "label": c} for c in report.categories(products)]
        source = shop.truth.get("source", {})
        body = [
            hero,
            section(1, "Margin, step by step", "From the price-list margin to the true margin of the whole shop or "
                    "one category.", [
                        dmc.Select(id="category", data=categories, value=ALL_CATEGORIES, label="Category",
                                   allowDeselect=False, className="pp-select", size="md"),
                        html.Div(cascade_view(products, None, shop.period), id="cascade-view", className="pp-block"),
                    ], "cascade"),
            section(2, "Bestsellers that lose money", "Move a rule; the list and the moves update at once.", [
                html.Div([rule_slider(name) for name in RULES], className="pp-controls"),
                html.Div(id="loss-stats", className="pp-block"),
                html.Div(id="loss-table", className="pp-block"),
            ], "losses"),
            section(3, "Product card", "One product: its own cascade and every order line behind it.", [
                dmc.Select(id="product", data=product_choices()[0],
                           value=start_product(None), label="Product (top 2,000 by net revenue)",
                           searchable=True, allowDeselect=False, className="pp-product-select", size="md",
                           maxDropdownHeight=320),
                html.Div(id="card", className="pp-block"),
            ], "product-card"),
            dmc.Text(f"Data: Lumo, a fictional shop from Data-Generator {source.get('tag', '')} (seed "
                     f"{source.get('seed', '')}). {len(products):,} products sold, "
                     f"{shop.period[0]:%b %Y} to {shop.period[1]:%b %Y}.", className="dg-caption pp-chart-gap"),
        ]
    footer = html.Footer([
        html.P("All products, orders and costs are generated by Data-Generator: a fictional shop, seed 42. "
               "Amounts in PLN without VAT."),
        html.A(REPO_URL.removeprefix("https://"), href=REPO_URL, target="_blank", className="dg-link"),
    ], className="dg-footer")
    return dmc.MantineProvider(theme=t.MANTINE_THEME, children=html.Div([
        dcc.Location(id="url", refresh=False), dcc.Store(id="scroll-to-card"), dcc.Store(id="scroll-done"),
        header,
        html.Main(html.Div([*body, footer], className="dg-wrap")),
    ], className="dg-page"))


# ---------------------------------------------------------------------------------------------------------------- #
# App and callbacks

app = Dash(__name__, title="Product Profitability", assets_folder=str(Path(__file__).parent / "assets"),
           suppress_callback_exceptions=True)
app.layout = page


@app.callback(
    *[Output(name, "value") for name in RULES], Output("product", "value", allow_duplicate=True),
    Input("url", "search"), prevent_initial_call="initial_duplicate",
)
def apply_address(search):
    """Sliders and product card from the address when the page opens (/?bestsellers=200&rise=15&product=…)."""
    query = {key: values[0] for key, values in parse_qs((search or "").lstrip("?")).items()}
    values = start_values(query)
    return *[values[name] for name in RULES], start_product(query.get("product"))


@app.callback(Output("cascade-view", "children"), Input("category", "value"), prevent_initial_call=True)
def update_cascade(category):
    shop, _, products = prepare()
    return cascade_view(products, category, shop.period)


@app.callback(
    Output("loss-stats", "children"), Output("loss-table", "children"),
    *[Output(f"{name}-value", "children") for name in RULES],
    *[Input(name, "value") for name in RULES],
)
def update_losses(bestsellers, rise):
    if None in (bestsellers, rise):
        return (no_update,) * (2 + len(RULES))
    losing = losing_for(int(bestsellers), int(rise))
    values = [rule_text(name, value) for name, value in zip(RULES, (bestsellers, rise), strict=True)]
    return loss_stats(losing, bestsellers), loss_view(losing), *values


@app.callback(
    Output("product", "value"), Output("scroll-to-card", "data"),
    Input({"type": "open-product", "index": ALL}, "n_clicks"), prevent_initial_call=True,
)
def open_product(clicks):
    """A product name in the loss table opens its card."""
    product_id = clicked_product(ctx.triggered_id, ctx.triggered[0]["value"] if ctx.triggered else None)
    return (product_id, product_id) if product_id else (no_update, no_update)


def clicked_product(triggered_id, clicks) -> str | None:
    """The product of a clicked name; None when the callback fires for new table rows that nobody clicked."""
    if not isinstance(triggered_id, dict) or not clicks:
        return None
    return str(triggered_id["index"])


@app.callback(Output("card", "children"), Input("product", "value"), *[Input(name, "value") for name in RULES])
def update_card(product_id, bestsellers=None, rise=None):
    """The product card, judged by the same slider rules as the loss table."""
    if not product_id:
        return no_update
    shop, lines, products = prepare()
    rules = rules_for(bestsellers, rise) if None not in (bestsellers, rise) else diagnose.Rules()
    return card_view(shop, lines, products, int(product_id), rules)


app.clientside_callback(
    """function (productId) {
        if (productId) {
            setTimeout(function () {
                var card = document.getElementById('product-card');
                if (card) { card.scrollIntoView({behavior: 'smooth', block: 'start'}); }
            }, 150);
        }
        return window.dash_clientside.no_update;
    }""",
    Output("scroll-done", "data"), Input("scroll-to-card", "data"), prevent_initial_call=True,
)


def main():
    app.run(host="127.0.0.1", port=int(os.environ.get("PP_PORT", 8050)), debug=False)


if __name__ == "__main__":
    main()
