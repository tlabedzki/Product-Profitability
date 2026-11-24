"""
Get the shop data: clone a release of Data-Generator, run it (seed 42) and copy the tables the margin model reads to
data/raw/, together with the true cost rates from its settings (releases from 1.7.0 on).

    python scripts/get_data.py                      # the release in product_profitability.data.DATA_GENERATOR_TAG
    python scripts/get_data.py --tag v1.7.0         # another release
    python scripts/get_data.py --source ../Data-Generator --tag my-branch --refresh   # a local clone and branch
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from product_profitability.data import DATA_GENERATOR_TAG, RAW_DIR, TABLES  # noqa: E402

GITHUB_URL = "https://github.com/tlabedzki/Data-Generator.git"
CACHE_DIR = ROOT / ".cache"
RATE_NAMES = (
    "carrier_rates", "default_carrier_rates", "cod_collection_fee", "return_label_rates", "shop_paid_return_reasons",
    "return_handling_cost", "write_off_share", "default_write_off_share", "payment_fee_rate",
    "default_payment_fee_rate", "payment_fixed_fee", "default_payment_fixed_fee", "failed_payment_fee",
    "affiliate_commission_rate", "default_affiliate_commission_rate",
)

TRUTH_SCRIPT = f"""
import json
from settings import commerce_settings as cs, market_settings as ms
rates = {{name: getattr(cs, name) for name in {RATE_NAMES!r} if hasattr(cs, name)}}
print(json.dumps({{"vat_rate": ms.vat_rate, "cost_rates": rates}}))
"""


def run(command: list[str], cwd: Path | None = None) -> str:
    env = {**os.environ, "MPLBACKEND": "Agg", "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise SystemExit(f"Command failed: {' '.join(command)}\n{result.stderr[-2000:]}")
    return result.stdout


def clone(source: str, tag: str, refresh: bool) -> Path:
    target = CACHE_DIR / f"data-generator-{re.sub(r'[^A-Za-z0-9._-]', '-', tag)}"
    if refresh or not (target / "main.py").exists():
        shutil.rmtree(target, ignore_errors=True)
        CACHE_DIR.mkdir(exist_ok=True)
        print(f"Cloning Data-Generator {tag} from {source}")
        run(["git", "-c", "advice.detachedHead=false", "clone", "--quiet", "--depth", "1", "--branch", tag,
             source, str(target)])
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tag", default=DATA_GENERATOR_TAG, help="Data-Generator release tag or branch")
    parser.add_argument("--source", default=GITHUB_URL, help="git URL or local path of Data-Generator")
    parser.add_argument("--refresh", action="store_true", help="clone and generate again (for a moving branch)")
    args = parser.parse_args()

    generator_dir = clone(args.source, args.tag, args.refresh)
    export_dir = generator_dir / "export"
    if not (export_dir / "product_data.parquet").exists():
        print("Generating the data (seed 42), about 10 seconds")
        run([sys.executable, "main.py"], cwd=generator_dir)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    copied = []
    for table in TABLES:
        source_file, target_file = export_dir / f"{table}.parquet", RAW_DIR / f"{table}.parquet"
        if source_file.exists():
            shutil.copy2(source_file, target_file)
            copied.append(table)
        elif target_file.exists():
            target_file.unlink()

    truth = json.loads(run([sys.executable, "-c", TRUTH_SCRIPT], cwd=generator_dir))
    commit = run(["git", "rev-parse", "HEAD"], cwd=generator_dir).strip()
    truth["source"] = {"repository": args.source, "tag": args.tag, "commit": commit, "seed": 42}
    (RAW_DIR / "truth.json").write_text(json.dumps(truth, indent=2), encoding="utf-8")

    print(f"Saved {', '.join(copied)} and truth.json to {RAW_DIR.relative_to(ROOT)}")
    if "payment_data" not in copied:
        print("This release has no shop cost columns: the model uses the mock costs (see mock_costs.py).")


if __name__ == "__main__":
    main()
