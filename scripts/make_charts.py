"""
README images and numbers in one run: the two charts (the same Plotly code as the app, drawn in headless Chrome with
Inter from the repository), the app screenshots and every <!-- generated:... --> block of README.md.

    python scripts/make_charts.py                # Polish README (private repository), new app screenshots
    python scripts/make_charts.py --lang en      # English README, before the repository goes public
    python scripts/make_charts.py --no-app       # charts and numbers only, keep the screenshots

Needs the data from scripts/get_data.py, Chrome or Edge, and requirements-dev.txt (websockets).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import socket
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from browser import Browser, stop_tree, wait_for  # noqa: E402

from product_profitability import data, diagnose, figures, i18n, margin, report  # noqa: E402
from product_profitability import theme as t  # noqa: E402

IMG = ROOT / "docs" / "img"
README = ROOT / "README.md"
CACHE = ROOT / ".cache" / "charts"
FONTS = ROOT / "ui" / "assets" / "fonts"
CHART_WIDTH, PAD, SCALE = 712, 24, 2  # CSS pixels; the PNG is (712 + 2 * 24) * 2 = 1520 px wide
APP_WIDTH, APP_SCALE, APP_PAD = 1280, 1.25, 32


# ---------------------------------------------------------------------------------------------------------------- #
# Numbers

def compute(language: str) -> dict:
    shop = data.load()
    lines = margin.line_costs(shop)
    report_rows = margin.reconcile(shop, lines)
    products = margin.product_margins(shop, lines)
    rules = diagnose.Rules()
    losing = diagnose.loss_making_bestsellers(products, rules, language)
    return {"shop": shop, "lines": lines, "reconcile": report_rows, "products": products, "rules": rules,
            "losing": losing, "language": language}


def blocks(numbers: dict) -> dict[str, str]:
    """Text of every generated block, in the README language."""
    language, products, losing = numbers["language"], numbers["products"], numbers["losing"]
    rules = numbers["rules"]
    cascade = report.cascade_data(products, language=language).set_index("step")
    categories = report.category_data(products, language)
    lm, tm = cascade.loc["list_margin", "amount"], cascade.loc["true_margin", "amount"]
    costs = cascade[cascade["kind"] == "cost"].sort_values("amount", ascending=False)
    first, second = costs.iloc[0], costs.iloc[1]
    moves = losing["move"].value_counts()
    top_category = losing["category"].value_counts()
    cat_name = i18n.category(top_category.index[0], language)
    worst = losing.iloc[0]
    sold = len(products)
    losing_all = int((products["true_margin"] < 0).sum())
    sources = len(numbers["reconcile"])
    worst_diff = float(numbers["reconcile"]["difference"].abs().max())
    if worst_diff >= 0.005:
        raise SystemExit(f"Costs do not add up ({worst_diff:.2f} PLN): the README would claim 'to the grosz'")
    free = int(moves.get("free_shipping", 0))
    if free:
        raise SystemExit(f"'End free delivery' now fires {free} times: rewrite chapter 7 and the summary first")
    median_units = int(losing.loc[losing["category"] == top_category.index[0], "units"].median())
    free_share = float(products["free_delivery_lines"].sum() / products["shipped_lines"].sum())
    shipping_net = float(products["shipping"].sum())
    c = lambda value: report.compact(value, language)  # noqa: E731
    n = lambda value: f"{value:,}".replace(",", " " if language == "pl" else ",")  # noqa: E731
    grosz = f"{worst_diff:.2f}".replace(".", "," if language == "pl" else ".")
    p = lambda value: report.percent(value, language=language)  # noqa: E731
    lowest, highest = categories.iloc[0], categories.iloc[-1]
    hero_alt_numbers = report.loss_title(losing, rules, language)[0]
    cascade_alt = report.cascade_title(report.cascade_data(products, language=language), "Lumo", None, language)[0]
    category_alt = report.category_title(categories, language)[0]
    discount_returns = p((cascade.loc["discount", "amount"] + cascade.loc["returns", "amount"]) / lm)
    low_kept, high_kept = p(lowest["kept"]), p(highest["kept"])

    if language == "pl":
        return {
            "result": (f"**Wynik.** Z {c(lm)} zł marży z cennika zostaje {c(tm)} zł, czyli {p(tm / lm)}. Najwięcej "
                       f"zabierają {first['label'].lower()} ({c(first['amount'])} zł) i "
                       f"{second['label'].lower()} ({c(second['amount'])} zł). {len(losing)} z {rules.bestsellers} "
                       f"bestsellerów traci pieniądze, razem {c(-losing['true_margin'].sum())} zł."),
            "hero": (f"![Aplikacja: suwaki reguł, liczby i tabela stratnych bestsellerów; {hero_alt_numbers}]"
                     f"(docs/img/app.png)"),
            "summary": (
                f"- **Trafione:** każdy z {sources} kosztów rozkłada się na produkty co do grosza (największa różnica "
                f"{grosz} zł). Na minusie jest {n(losing_all)} z {n(sold)} sprzedanych produktów, ale tylko "
                f"{len(losing)} z nich to bestsellery, więc lista do decyzji jest krótka.\n"
                f"- **Chybione:** ruch „bez darmowej dostawy” nie pada ani razu ({moves.get('free_shipping', 0)} "
                f"z {len(losing)}). {top_category.iloc[0]} z {len(losing)} stratnych bestsellerów to "
                f"{cat_name.lower()} sprzedawana w kilku sztukach (mediana {median_units}), więc jeden zwrot "
                f"zmienia wynik."),
            "cascade": (f"![{cascade_alt}](docs/img/margin-cascade.png)\n\n"
                        f"Rabaty i zwroty to razem {discount_returns} marży z cennika. Wysyłka netto, czyli koszt "
                        f"przewoźnika minus to, co zapłacili klienci, to tylko {c(shipping_net)} zł, choć "
                        f"{p(free_share)} wysłanych linii jechało z darmową dostawą."),
            "categories": (f"![{category_alt}](docs/img/category-margin.png)\n\n"
                           f"Rozpiętość między kategoriami jest duża: {lowest['label']} zatrzymuje {low_kept}, "
                           f"{highest['label']} {high_kept}."),
            "losses": (f"{report.loss_title(losing, rules, language)[0]}. Ruchy: zmiana ceny "
                       f"{moves.get('price', 0)}, koniec darmowej dostawy {moves.get('free_shipping', 0)}, wycofanie "
                       f"{moves.get('delist', 0)}. Dziesięć największych strat:\n\n"
                       + report.loss_markdown(report.loss_table(losing, language), 10, language)),
            "card": (f"![Karta produktu {worst['product_name']}: kaskada marży i lista zamówień]"
                     f"(docs/img/app-card.png)\n\n"
                     f"Największa strata wśród bestsellerów: {worst['product_name']} "
                     f"({i18n.color(worst['color'], language)}), {report.money(worst['true_margin'], language)}. "
                     f"{worst['reason']}"),
        }
    return {
        "result": (f"**Result.** Of {c(lm)} PLN of price-list margin, {c(tm)} PLN is left, or {p(tm / lm)}. "
                   f"{first['label']} ({c(first['amount'])} PLN) and {second['label'].lower()} "
                   f"({c(second['amount'])} PLN) take the most. {len(losing)} of the top {rules.bestsellers} "
                   f"bestsellers lose money, {c(-losing['true_margin'].sum())} PLN together."),
        "hero": (f"![The app: rule sliders, headline numbers and the table of loss-making bestsellers; "
                 f"{hero_alt_numbers}](docs/img/app.png)"),
        "summary": (
            f"- **What worked:** each of the {sources} costs is spread over products to the grosz (largest difference "
            f"{grosz} PLN). {n(losing_all)} of {n(sold)} products sold lose money, but only {len(losing)} of "
            f"them are bestsellers, so the list to act on is short.\n"
            f"- **What missed:** the move “end free delivery” never fires ({moves.get('free_shipping', 0)} of "
            f"{len(losing)}). {top_category.iloc[0]} of the {len(losing)} loss-making bestsellers are "
            f"{cat_name.lower()} sold in a few units (median {median_units}), so one return changes the result."),
        "cascade": (f"![{cascade_alt}](docs/img/margin-cascade.png)\n\n"
                    f"Discounts and returns together take {discount_returns} of the price-list margin. Net shipping, "
                    f"the carrier cost minus what customers paid, is only {c(shipping_net)} PLN, although "
                    f"{p(free_share)} of shipped lines went with free delivery."),
        "categories": (f"![{category_alt}](docs/img/category-margin.png)\n\n"
                       f"The spread between categories is wide: {lowest['label']} keeps {low_kept}, "
                       f"{highest['label']} {high_kept}."),
        "losses": (f"{report.loss_title(losing, rules)[0]}. Moves: change the price {moves.get('price', 0)}, end free "
                   f"delivery {moves.get('free_shipping', 0)}, delist {moves.get('delist', 0)}. The ten biggest "
                   f"losses:\n\n" + report.loss_markdown(report.loss_table(losing), 10)),
        "card": (f"![Product card of {worst['product_name']}: margin cascade and order list](docs/img/app-card.png)"
                 f"\n\nThe biggest loss among bestsellers: {worst['product_name']} ({worst['color']}), "
                 f"{report.money(worst['true_margin'])}. {worst['reason']}"),
    }


def wrap(text: str, width: int = 120) -> str:
    """Wrap prose lines and list items of a block at `width` characters; tables and images stay as they are."""
    out = []
    for line in text.splitlines():
        # Keep "2 167", "16,5 mln" and "435 PLN" on one line: a non-breaking space inside numbers and before units.
        line = re.sub(r"(?<=\d) (?=\d|mln|tys\.|zł|PLN)", " ", line)
        if line.startswith(("|", "![")) or len(line) <= width:
            out.append(line)
        elif line.startswith("- "):
            out.append(textwrap.fill(line, width, subsequent_indent="  ", break_long_words=False,
                                     break_on_hyphens=False))
        else:
            out.append(textwrap.fill(line, width, break_long_words=False, break_on_hyphens=False))
    return chr(10).join(out)


def write_readme(texts: dict[str, str]) -> None:
    readme = README.read_text(encoding="utf-8")
    for name, text in texts.items():
        text = wrap(text)
        pattern = re.compile(rf"(<!-- generated:{name} -->\n)(?:.*?\n)?(<!-- /generated:{name} -->)", re.S)
        if not pattern.search(readme):
            raise SystemExit(f"README.md has no block <!-- generated:{name} -->")
        readme = pattern.sub(lambda match, text=text: match.group(1) + text + "\n" + match.group(2), readme)
    README.write_text(readme, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------------------------------------------- #
# Charts

def font_faces() -> str:
    css = (ROOT / "ui" / "assets" / "fonts.css").read_text(encoding="utf-8")
    return css.replace("url('fonts/", f"url('{FONTS.as_uri()}/")


def keep_together(text: str) -> str:
    """No one-letter word at the end of a line (Polish typography): a non-breaking space after it."""
    return re.sub(r"(?<=\s)([aiouwzAIOUWZ]) ", lambda match: match.group(1) + " ", text)


def chart_page(title: str, subtitle: str, figure) -> str:
    title, subtitle = keep_together(title), keep_together(subtitle)
    figure.update_layout(width=CHART_WIDTH, autosize=False)
    body = figure.to_html(full_html=False, include_plotlyjs=True, config={"staticPlot": True})
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{font_faces()}
html, body {{ margin: 0; background: {t.PAGE}; }}
#chart {{ width: {CHART_WIDTH}px; padding: {PAD}px; background: {t.PAGE}; font-family: {t.SANS_STACK};
         -webkit-font-smoothing: antialiased; }}
.title {{ font-size: 21px; font-weight: 600; letter-spacing: -0.01em; color: {t.INK}; line-height: 1.3; }}
.sub {{ margin-top: 4px; font-size: 14px; color: {t.MUTED}; line-height: 1.45; }}
.graph {{ margin-top: 14px; }}
.graph text {{ font-feature-settings: {t.NUMBER_FEATURES}; }}
</style></head><body><div id="chart"><div class="title">{title}</div><div class="sub">{subtitle}</div>
<div class="graph">{body}</div></div></body></html>"""


def charts(numbers: dict) -> list[tuple[str, str]]:
    language, products, shop = numbers["language"], numbers["products"], numbers["shop"]
    cascade = report.cascade_data(products, language=language)
    categories = report.category_data(products, language)
    return [
        ("margin-cascade", chart_page(*report.cascade_title(cascade, "Lumo", shop.period, language),
                                      figures.cascade(cascade, language))),
        ("category-margin", chart_page(*report.category_title(categories, language),
                                       figures.category_kept(categories, language))),
    ]


async def draw(pages: list[tuple[str, str]]) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    async with Browser() as page:
        await page.viewport(CHART_WIDTH + 2 * PAD, 900, SCALE)
        for name, html in pages:
            path = CACHE / f"{name}.html"
            path.write_text(html, encoding="utf-8")
            await page.open(path.as_uri())
            await page.until("document.fonts.status === 'loaded' && !!document.querySelector('.main-svg')")
            await page.js("document.fonts.ready.then(() => true)")
            await asyncio.sleep(0.5)
            await page.shot("#chart", IMG / f"{name}.png")
            print(f"Saved docs/img/{name}.png")


# ---------------------------------------------------------------------------------------------------------------- #
# App screenshots

def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def app_shots(port: int) -> None:
    async with Browser() as page:
        await page.viewport(APP_WIDTH, 900, APP_SCALE)
        await page.open(f"http://127.0.0.1:{port}/")
        await page.until("document.querySelectorAll('#loss-table tbody tr').length > 0 && "
                         "document.querySelectorAll('#card tbody tr').length > 0 && "
                         "document.fonts.status === 'loaded'")
        await asyncio.sleep(1.5)
        await page.js("document.getElementById('losses').scrollIntoView()")
        await page.js("document.querySelector('#losses .dg-table-scroll').style.maxHeight = '360px'")
        await asyncio.sleep(0.5)
        await page.shot("#losses", IMG / "app.png", pad=APP_PAD)
        await page.shot("#product-card", IMG / "app-card.png", pad=APP_PAD)
        print("Saved docs/img/app.png and docs/img/app-card.png")


def run_app_shots() -> None:
    port = free_port()
    env = {**os.environ, "PP_PORT": str(port), "MPLBACKEND": "Agg"}
    hidden = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    app = subprocess.Popen([sys.executable, "-m", "ui.app"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, **hidden)
    try:
        wait_for(f"http://127.0.0.1:{port}/")
        asyncio.run(app_shots(port))
    finally:
        stop_tree(app)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lang", choices=i18n.LANGUAGES, default="pl", help="language of README.md")
    parser.add_argument("--no-app", action="store_true", help="keep the app screenshots as they are")
    args = parser.parse_args()
    IMG.mkdir(parents=True, exist_ok=True)
    numbers = compute(args.lang)
    asyncio.run(draw(charts(numbers)))
    if not args.no_app:
        run_app_shots()
    write_readme(blocks(numbers))
    print("Updated the generated blocks of README.md")


if __name__ == "__main__":
    main()
