import pandas as pd
import pytest

import FileIO
from battery_app.bdf_output import build_cycle_metadata, build_bdf_row, write_metadata
from GraphIV import calc_capacity, load_bdf_file, parse_filename


def test_calc_capacity_reports_missing_columns():
    data = pd.DataFrame({'Voltage': [4.0], 'Current': [1.0]})

    with pytest.raises(ValueError, match='Test Time / s'):
        calc_capacity(data, type('Stats', (), {'stats': {}})())


def test_parse_filename_reports_unexpected_format():
    with pytest.raises(ValueError, match='Unexpected log filename format'):
        parse_filename('invalid-log-name-with-too-many-parts.csv')


def test_parse_filename_accepts_bdf_filename():
    assert parse_filename('LOCAL__cell_1__20260924_001.bdf.csv') == (
        'cell_1',
        'Standard_Charge-Discharge_Cycle',
        '20260924',
        '001',
        'Step',
    )


def test_load_bdf_file_uses_metadata_for_graphiv(tmp_path):
    filepath = tmp_path / 'LOCAL__cell_1__20260924_001.bdf.csv'
    row = build_bdf_row(
        {'Voltage': 3.7, 'Current': 1.0, 'Unix_Timestamp': 1_700_000_000.0},
        test_time_s=0.0,
        cycle_count=1,
        step_count=1,
        step_id=1,
        step_time_s=0.0,
        step_type='CC_CHG',
        temperature_sources={},
    )
    FileIO.write_bdf_data(filepath, row)
    metadata = build_cycle_metadata(
        data_path=filepath,
        institution_code='LOCAL',
        cell_name='cell_1',
        cycle_count=1,
        cycle_settings=[{
            'cycle_display': 'Charge',
            'bdf_step_type': 'CC_CHG',
            'cycle_type': 'step',
        }],
        equipment={},
        temperature_sources={},
        start_time_utc='2026-09-24T00:00:00+00:00',
    )
    write_metadata(filepath, metadata)

    dataframe, loaded_metadata = load_bdf_file(filepath)

    assert tuple(dataframe.columns) == tuple(row)
    assert loaded_metadata['test']['type'] == 'Charge'
