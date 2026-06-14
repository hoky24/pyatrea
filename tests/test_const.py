from pyatrea.const import AtreaMode, AtreaProgram


def test_enum_values_match_protocol():
    assert AtreaProgram.MANUAL == 0
    assert AtreaProgram.WEEKLY == 1
    assert AtreaProgram.TEMPORARY == 2
    assert AtreaMode.OFF == 0
    assert AtreaMode.VENTILATION == 2
    assert AtreaMode.D4 == 19
