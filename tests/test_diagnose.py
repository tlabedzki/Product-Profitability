import pandas as pd
import pytest

from product_profitability import diagnose, margin


def product(product_id, category="Electronics", units=10, refunded=0, written_off=0, list_revenue=10_000.0,
            purchase=6_000.0, discount=0.0, refund=0.0, restocked=0.0, write_off=0.0, carrier=0.0, delivery_fee=0.0,
            payment=0.0, commission=0.0, shipped=10, free=0):
    return {"product_id": product_id, "product_name": f"Product {product_id}", "category": category, "units": units,
            "units_refunded": refunded, "units_written_off": written_off, "list_revenue": list_revenue,
            "purchase_cost": purchase, "discount": discount, "refund": refund, "restocked_cost": restocked,
            "write_off_cost": write_off, "return_shipping_cost": 0.0, "return_handling_cost": 0.0,
            "carrier_cost": carrier, "delivery_fee": delivery_fee, "payment_fee": payment, "commission": commission,
            "shipped_lines": shipped, "free_delivery_lines": free}


PLANTED = [
    product(1, discount=6_000.0, payment=100.0),                                    # discounts eat the margin
    product(2, category="Furniture", list_revenue=3_000.0, purchase=2_000.0, carrier=1_500.0, free=9),  # free bulky
    product(3, category="Clothing", refunded=6, written_off=2, purchase=6_000.0, refund=6_000.0,
            restocked=3_600.0, write_off=2_000.0),                                  # returns far above category
    product(4, list_revenue=1_000.0, purchase=1_050.0, payment=20.0),               # sold below cost, small rise
    product(5, list_revenue=20_000.0, purchase=10_000.0, payment=200.0),            # profitable bestseller
    product(6, purchase=9_950.0, discount=1_000.0),                                 # break-even discount below 1%
    product(7, list_revenue=1_000.0, purchase=1_300.0),                             # break-even rise of 30%
    product(8, category="Clothing", units=100, refunded=2, list_revenue=5_000.0, purchase=2_000.0),
    product(9, units=1, list_revenue=50.0, purchase=60.0),                          # loss, but not a bestseller
]


@pytest.fixture
def planted():
    return margin.add_steps(pd.DataFrame(PLANTED))


def diagnosed(planted, **rules):
    return diagnose.loss_making_bestsellers(planted, diagnose.Rules(**rules)).set_index("product_id")


def test_each_planted_case_gets_its_driver_and_move(planted):
    found = diagnosed(planted, bestsellers=8)
    expected = {1: ("discount", "price"), 2: ("shipping", "free_shipping"), 3: ("returns", "delist"),
                4: ("price_list", "price"), 6: ("discount", "price"), 7: ("price_list", "delist")}
    assert {pid: (row.driver, row.move) for pid, row in found.iterrows()} == expected


def test_profitable_and_small_products_stay_off_the_list(planted):
    found = diagnosed(planted, bestsellers=8)
    assert 5 not in found.index and 8 not in found.index
    assert 9 not in found.index  # loses money but ranks below the top 8
    assert 9 in diagnosed(planted, bestsellers=9).index


def test_reason_sentences_name_the_numbers(planted):
    found = diagnosed(planted, bestsellers=8)
    assert found.loc[1, "reason"] == ("Discounts (on average 60%) took 6 000 zł against a price-list margin of "
                                      "4 000 zł. Cap the discount at 39% to break even.")
    assert "90% of orders shipped free" in found.loc[2, "reason"]
    assert found.loc[3, "reason"].startswith("6 of 10 units came back (category: 7%), 2 written off")
    assert found.loc[4, "reason"].endswith("Raise the price by 9 zł (7%) per unit to break even.")
    assert found.loc[7, "reason"].endswith("Delist it: breaking even needs a price rise of 30%.")


def test_no_zero_discount_cap(planted):
    row = diagnosed(planted, bestsellers=8).loc[6]
    assert row.break_even_discount_rate < 0.01
    assert "Cap the discount" not in row.reason and "Raise the price" in row.reason


def test_break_even_rise_really_breaks_even(planted):
    row = diagnosed(planted, bestsellers=8).loc[4]
    kept = row.units - row.units_refunded
    assert row.true_margin + row.break_even_rise / 1.23 * kept == pytest.approx(0.0)


def test_biggest_loss_first(planted):
    found = diagnose.loss_making_bestsellers(planted, diagnose.Rules(bestsellers=8))
    assert found["true_margin"].is_monotonic_increasing
