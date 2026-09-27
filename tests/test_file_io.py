import re

import FileIO


def test_start_bdf_file_uses_convention_and_unique_sequence(tmp_path):
    first_path = FileIO.start_bdf_file(tmp_path, 'Local Lab', 'cell 1')
    assert re.search(r'Local_Lab__cell_1__\d{8}_001\.bdf\.csv$', first_path)

    tmp_path.joinpath(first_path.split('\\')[-1]).touch()
    second_path = FileIO.start_bdf_file(tmp_path, 'Local Lab', 'cell 1')
    assert second_path.endswith('_002.bdf.csv')


def test_bdf_sequence_continues_across_dates_and_step_count(tmp_path):
    prior_path = tmp_path / 'Local_Lab__cell_1__20260924_005.bdf.csv'
    prior_path.write_text(
        'Test Time / s,Step Count / 1\n0,12\n1,13\n',
        encoding='utf-8',
    )

    next_path = FileIO.start_bdf_file(tmp_path, 'Local Lab', 'cell 1')

    assert next_path.endswith('_006.bdf.csv')
    assert FileIO.bdf_cycle_number(next_path) == 6
    assert FileIO.latest_bdf_step_count(tmp_path, 'Local Lab', 'cell 1') == 13
