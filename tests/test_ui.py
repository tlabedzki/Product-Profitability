"""Tests of the Dash app (ui/): layout, callbacks and views, on the tiny hand-computed shop (CI has no data)."""
from functools import cache

import pytest

from product_profitability import margin
from ui import app as ui_app


@pytest.fixture
def shop_app(tiny_shop):
    lines = margin.line_costs(tiny_shop)
    prepared = (tiny_shop, lines, margin.product_margins(tiny_shop, lines))
    original = ui_app.prepare
    ui_app.prepare = cache(lambda: prepared)
    ui_app.losing_for.cache_clear()
    ui_app.product_choices.cache_clear()
    yield ui_app, prepared
    ui_app.prepare = original
    ui_app.losing_for.cache_clear()
    ui_app.product_choices.cache_clear()


def walk(component):
    stack = [component]
    while stack:
        node = stack.pop()
        if isinstance(node, list | tuple):
            stack.extend(node)
            continue
        if not hasattr(node, "to_plotly_json"):
            continue
        yield node
        stack.append(getattr(node, "children", None))


def ids(component) -> set:
    return {node.id if isinstance(node.id, str) else str(node.id) for node in walk(component)
            if getattr(node, "id", None)}


def text_of(component) -> str:
    if isinstance(component, str | int | float):
        return str(component)
    if isinstance(component, list | tuple):
        return " ".join(text_of(c) for c in component)
    return text_of(getattr(component, "children", "") or "")


def test_layout_has_the_three_screens(shop_app):
    app, _ = shop_app
    found = ids(app.page())
    assert {"category", "cascade-view", "bestsellers", "rise", "loss-stats", "loss-table", "product", "card",
            "cascade", "losses", "product-card"} <= found


def test_page_without_data_says_what_to_run(monkeypatch):
    def missing():
        raise FileNotFoundError("No shop data in data/raw. Run: python scripts/get_data.py")

    monkeypatch.setattr(ui_app, "prepare", missing)
    assert "get_data.py" in text_of(ui_app.page())


def test_cascade_of_a_category(shop_app):
    app, _ = shop_app
    view = text_of(app.update_cascade("Furniture"))
    assert "Furniture loses money after selling costs" in view
    assert "products lose money" in view and "of 1 sold" in view


def test_bestseller_slider_changes_the_table(shop_app):
    app, _ = shop_app
    stats, table, top, rise = app.update_losses(2, 10)
    assert (top, rise) == ("top 2", "10%")
    buttons = [n for n in walk(table) if isinstance(getattr(n, "id", None), dict)]
    assert [b.id["index"] for b in buttons] == [2]
    assert "End free delivery" in text_of(table)
    assert text_of(stats).startswith("1 bestsellers lose money of the top 2")
    _, smaller, _, _ = app.update_losses(1, 10)
    assert "Sofa Big" in text_of(smaller)
    product_two_out = app.losing_for(1, 10)
    assert product_two_out["product_id"].tolist() == [2]


def test_no_loss_makers_message(shop_app, monkeypatch):
    app, (shop, lines, products) = shop_app
    empty = products.iloc[0:0]
    assert "No bestseller loses money" in text_of(app.loss_view(empty))


def test_clicked_product_ignores_rows_nobody_clicked():
    assert ui_app.clicked_product({"type": "open-product", "index": 2}, 1) == "2"
    assert ui_app.clicked_product({"type": "open-product", "index": 2}, None) is None
    assert ui_app.clicked_product(None, 1) is None


def test_product_card_shows_the_loss_and_every_order(shop_app):
    app, _ = shop_app
    card = app.update_card("2")
    text = text_of(card)
    assert "Sofa Big (gray)" in text and "Loses money." in text
    assert "Every order line (2)" in text
    rows = [n for n in walk(card) if type(n).__name__ == "Tr"]
    assert len(rows) == 1 + 2  # header and two order lines
    assert "Makes money" in text_of(app.update_card("1"))


def test_start_product_from_the_address(shop_app):
    app, (_, _, products) = shop_app
    assert app.start_product("1") == "1"
    assert app.start_product("999") == "2"  # unknown: the biggest loss
    assert app.start_product(None) == "2"
    assert [option["value"] for option in app.product_choices()[0]] == ["2", "1"]


def test_card_follows_the_slider_rules(shop_app, monkeypatch):
    # The card's verdict is judged with the rules of the sliders, the same as the loss table.
    app, _ = shop_app
    seen = []
    original = app.diagnose.add_diagnosis

    def spy(products, all_products, rules=None, language="en"):
        seen.append(rules)
        return original(products, all_products, rules, language)

    monkeypatch.setattr(app.diagnose, "add_diagnosis", spy)
    card = text_of(app.update_card("2", 300, 25))
    assert seen[-1] == app.diagnose.Rules(bestsellers=300, max_price_rise=0.25)
    assert app.losing_for(2, 25).set_index("product_id").loc[2, "reason"] in card


def test_page_with_broken_cost_data_shows_the_reason(monkeypatch):
    def broken():
        raise ValueError("The data has only some of the shop cost columns; missing: return_data.handling_cost")

    monkeypatch.setattr(ui_app, "prepare", broken)
    assert "missing: return_data.handling_cost" in text_of(ui_app.page())
