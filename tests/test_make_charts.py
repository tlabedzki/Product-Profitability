"""The text helpers of scripts/make_charts.py (the browser part runs only with the data and Chrome)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import make_charts  # noqa: E402

NBSP = chr(160)


def test_numbers_and_units_stay_on_one_line():
    text = "- **Trafione:** " + "słowo " * 20 + "jest 2 167 z 22 714 produktów, razem 73,0 tys. zł i 16,5 mln zł."
    wrapped = make_charts.wrap(text, width=60)
    assert all(len(line) <= 60 for line in wrapped.splitlines())
    assert f"2{NBSP}167" in wrapped and f"22{NBSP}714" in wrapped and f"73,0{NBSP}tys." in wrapped
    assert all(line.startswith("  ") for line in wrapped.splitlines()[1:])  # list item continues indented


def test_tables_and_images_are_not_wrapped():
    table = "| # | " + "x" * 200 + " |"
    image = "![" + "alt " * 60 + "](docs/img/a.png)"
    assert make_charts.wrap(table + chr(10) + image, width=60) == table + chr(10) + image


def test_no_one_letter_word_at_a_line_end():
    assert make_charts.keep_together("zostaje w kategorii i dalej") == f"zostaje w{NBSP}kategorii i{NBSP}dalej"
