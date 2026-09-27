
import pandas as pd
import pytest


def test_pandas_concat_replaces_append():
    first = pd.DataFrame({"value": [1.0]})
    second = pd.DataFrame({"value": [2.0]})
    combined = pd.concat([first, second], ignore_index=True)
    assert combined["value"].tolist() == [1.0, 2.0]


def test_graphiv_dict_to_csv_replaces_append(tmp_path):
    from GraphIV import dict_to_csv

    filepath = tmp_path / "stats.csv"
    dict_to_csv({"cell_name": "cell1", "charge_start_time": 100}, filepath)
    dict_to_csv({"cell_name": "cell2", "charge_start_time": 200}, filepath)

    import pandas as pd

    df = pd.read_csv(filepath)
    assert df["cell_name"].tolist() == ["cell1", "cell2"]


def test_fake_equipment_requires_a_shared_simulation_link():
    from battery_app.simulation import FakeInstrumentNotAttachedError
    from lab_equipment.DMM_Fake import Fake_DMM
    from lab_equipment.Eload_Fake import Fake_Eload
    from lab_equipment.PSU_Fake import Fake_PSU

    with pytest.raises(FakeInstrumentNotAttachedError):
        Fake_DMM().measure_voltage()
    with pytest.raises(FakeInstrumentNotAttachedError):
        Fake_Eload().set_current(2.5)
    with pytest.raises(FakeInstrumentNotAttachedError):
        Fake_PSU().measure_power()


def test_representative_imports():
    from lab_equipment import DMM_A2D_4CH_Isolated_ADC, Eload_DL3000, PSU_SPD1000

    assert hasattr(DMM_A2D_4CH_Isolated_ADC, "A2D_4CH_Isolated_ADC")
    assert hasattr(Eload_DL3000, "DL3000")
    assert hasattr(PSU_SPD1000, "SPD1000")


def test_gui_smoke(qtbot):
    from battery_test import MainTestWindow

    window = MainTestWindow()
    qtbot.addWidget(window)
    assert window.num_battery_channels == 1
