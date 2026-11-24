import pandas as pd
from conftest import cost_tables, write_tables

import main


def test_cli_writes_both_files(tmp_path, capsys):
    write_tables(tmp_path, cost_tables())
    assert main.main(["--data", str(tmp_path), "--output", str(tmp_path / "out"), "--bestsellers", "2"]) == 0
    products = pd.read_csv(tmp_path / "out" / "product_margins.csv")
    losing = pd.read_csv(tmp_path / "out" / "loss_making_bestsellers.csv")
    assert set(products["product_id"]) == {1, 2}
    assert losing["product_id"].tolist() == [2]
    assert "to the grosz" in capsys.readouterr().out


def test_cli_without_data_says_what_to_run(tmp_path, capsys):
    assert main.main(["--data", str(tmp_path)]) == 1
    assert "get_data.py" in capsys.readouterr().err
