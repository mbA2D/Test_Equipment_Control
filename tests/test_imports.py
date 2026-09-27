def test_core_imports():
    import battery_test
    from charge_discharge import process_entrypoints
    import equipment
    import FileIO
    import GraphIV
    import jsonIO
    import Templates

    assert battery_test.MainTestWindow is not None
    assert process_entrypoints.run_charge_discharge_control is not None


def test_representative_driver_imports():
    from lab_equipment import DMM_A2D_4CH_Isolated_ADC
    from lab_equipment import Eload_DL3000
    from lab_equipment import PSU_SPD1000

    assert DMM_A2D_4CH_Isolated_ADC.A2D_4CH_Isolated_ADC is not None
    assert Eload_DL3000.DL3000 is not None
    assert PSU_SPD1000.SPD1000 is not None
