import pandas as pd
import pytest

from product_profitability import diagnose, figures, margin, report
from product_profitability import theme as t


@pytest.fixture
def products(tiny_shop):
    return margin.product_margins(tiny_shop)


def test_compact_numbers():
    assert report.compact(16_467_245) == "16.5M"
    assert report.compact(2_468_783) == "2.47M"
    assert report.compact(-72_937) == "−72.9k"
    assert report.compact(-5_708, unit="PLN") == "−5.71k PLN"
    assert report.compact(435) == "435"
    assert report.compact(2_468_783, "pl") == "2,47M"


def test_cascade_runs_from_list_margin_to_true_margin(products):
    data = report.cascade_data(products)
    assert data["step"].tolist() == ["list_margin", *margin.STEPS, "true_margin"]
    costs = data[data["kind"] == "cost"]
    # Each cost starts where the previous bar ended, and the last one ends at the true margin.
    assert costs["start"].tolist() == pytest.approx(data["end"].iloc[:-2].tolist())
    assert data["end"].iloc[-2] == pytest.approx(data["end"].iloc[-1])
    assert data["end"].iloc[-1] == pytest.approx(products["true_margin"].sum())


def test_only_the_biggest_cost_is_highlighted(products):
    data = report.cascade_data(products)
    assert data["highlight"].sum() == 1
    assert data.loc[data["highlight"], "step"].item() == "shipping"  # 80 + 70 carrier against 10 delivery fee


def test_cascade_of_one_category(products):
    furniture = report.cascade_data(products, "Furniture").set_index("step")
    assert furniture.loc["list_margin", "amount"] == pytest.approx(200.0)
    assert furniture.loc["returns", "amount"] == pytest.approx(0.0)
    with pytest.raises(ValueError, match="No products sold in Toys"):
        report.cascade_data(products, "Toys")


def test_cascade_title_states_the_finding(products):
    title, subtitle = report.cascade_title(report.cascade_data(products), "Lumo",
                                           (pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-06")))
    # List margin 350, true margin −37.30: the costs take more than the whole margin.
    assert title == "Lumo loses money after selling costs: they take 111% of the price-list margin, shipping the most"
    assert "Jan 2024 to Jan 2024" in subtitle


def test_cascade_title_below_cost():
    data = pd.DataFrame({"step": ["list_margin", "discount", "true_margin"], "kind": ["margin", "cost", "margin"],
                         "amount": [-10.0, 5.0, -15.0], "label": ["Price-list margin", "Discounts", "True margin"],
                         "highlight": [False, True, False]})
    assert "below the purchase cost" in report.cascade_title(data)[0]


def test_loss_table_and_markdown(products):
    losing = diagnose.loss_making_bestsellers(products, diagnose.Rules(bestsellers=2))
    table = report.loss_table(losing)
    assert table.columns.tolist() == report.LOSS_COLUMNS
    assert table["product"].tolist() == ["Sofa Big (gray)"]
    assert table["move"].iloc[0] in report.MOVE_LABELS.values()
    title, _ = report.loss_title(losing, diagnose.Rules(bestsellers=2))
    assert title.startswith("1 of the top 2 bestsellers lose money, −")
    table.loc[0, "product"] = "Sofa | Big"
    markdown = report.loss_markdown(table)
    assert r"Sofa \| Big" in markdown and markdown.count("\n") == 2


def test_no_loss_makers_title():
    empty = pd.DataFrame({"true_margin": [], "move": []})
    assert report.loss_title(empty, diagnose.Rules(bestsellers=3))[0].startswith("All top 3 bestsellers make money")


def test_cascade_figure_colors_and_labels(products):
    data = report.cascade_data(products)
    fig = figures.cascade(data)
    bar = fig.data[0]
    assert list(bar.marker.color).count(t.ACCENT) == 1
    assert bar.marker.color[0] == t.PRIMARY and bar.marker.color[-1] == t.PRIMARY
    assert bar.text[0] == report.compact(data["amount"].iloc[0])
    assert all(label.startswith(("−", "+", "0")) for label in bar.text[1:-1])
    assert len(fig.layout.shapes) == len(data) - 2
    assert fig.layout.xaxis.fixedrange and fig.layout.dragmode is False


def test_delivery_income_gets_a_plus_sign():
    data = pd.DataFrame({"kind": ["margin", "cost", "margin"], "amount": [100.0, -20.0, 120.0]})
    assert figures.value_labels(data) == ["100", "+20", "120"]
