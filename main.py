"""
True margin of every product of Lumo, a fictional online shop, and the bestsellers that lose money.

    python scripts/get_data.py     # once: the shop data from Data-Generator
    python main.py                 # writes output/product_margins.csv and output/loss_making_bestsellers.csv
    python main.py --bestsellers 200
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from product_profitability import data, diagnose, margin  # noqa: E402

OUTPUT_DIR = ROOT / "output"


def pln(value: float) -> str:
    return f"{value:>14,.0f} zł".replace(",", " ")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=data.RAW_DIR, help="folder with the Data-Generator tables")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR, help="folder for the CSV files")
    parser.add_argument("--bestsellers", type=int, default=diagnose.Rules.bestsellers,
                        help="how many products by net revenue count as bestsellers")
    args = parser.parse_args(argv)

    try:
        shop = data.load(args.data)
    except FileNotFoundError as error:
        print(error, file=sys.stderr)
        return 1
    lines = margin.line_costs(shop)
    report = margin.reconcile(shop, lines)
    worst = report["difference"].abs().max()
    if worst >= 0.005:
        print(report.to_string(index=False), file=sys.stderr)
        print(f"Costs do not add up: {worst:.2f} zł lost or doubled", file=sys.stderr)
        return 2

    products = margin.product_margins(shop, lines)
    rules = diagnose.Rules(bestsellers=args.bestsellers)
    losing = diagnose.loss_making_bestsellers(products, rules)
    args.output.mkdir(parents=True, exist_ok=True)
    products.round(4).to_csv(args.output / "product_margins.csv", index=False)
    losing.round(4).to_csv(args.output / "loss_making_bestsellers.csv", index=False)

    start, end = shop.period
    source = "mock costs" if shop.costs_are_mock else "cost columns of the data"
    print(f"Lumo, {start:%Y-%m-%d} to {end:%Y-%m-%d}: {len(products):,} products sold ({source})")
    print("Every cost spread over products to the grosz.\n")
    for step, value in margin.shop_cascade(products).items():
        print(f"  {step:<22}{pln(value)}")
    print(f"\n{len(losing)} of the top {rules.bestsellers} products by net revenue lose money "
          f"({pln(losing['true_margin'].sum()).strip()} together):")
    for row in losing.head(10).itertuples():
        print(f"  #{row.revenue_rank:<4} {row.product_name} ({row.color}): {pln(row.true_margin).strip()}, {row.move}")
        print(f"        {row.reason}")
    print(f"\nSaved {args.output / 'product_margins.csv'} and loss_making_bestsellers.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
