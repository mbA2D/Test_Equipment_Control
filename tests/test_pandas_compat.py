from pathlib import Path

import pandas as pd

from GraphIV import dict_to_csv


def test_pandas_concat_replaces_append():
    first = pd.DataFrame({"value": [1.0]})
    second = pd.DataFrame({"value": [2.0]})
    combined = pd.concat([first, second], ignore_index=True)
    assert combined["value"].tolist() == [1.0, 2.0]


def test_dict_to_csv_uses_concat_without_duplicating_row(tmp_path: Path):
    filepath = tmp_path / "cycle_stats.csv"
    dict_to_csv(
        {
            "cell_name": "cell_1",
            "charge_start_time": 100.0,
        },
        filepath,
    )
    dict_to_csv(
        {
            "cell_name": "cell_1",
            "charge_start_time": 100.0,
        },
        filepath,
    )

    saved = pd.read_csv(filepath)
    assert saved["cell_name"].tolist() == ["cell_1"]
    assert saved["charge_start_time"].tolist() == [100.0]
