from pyatrea.commands import CommandBuilder
from pyatrea.const import AtreaProgram


def builder() -> CommandBuilder:
    return CommandBuilder()


def test_set_power_writes_idw():
    b = builder()
    assert b.set_power(50) is True
    # H10704 control -> write_id H10714; H01020 has no write_id -> itself
    assert b.commands["H10714"] == "00050"
    assert "H10704" not in b.commands
    assert b.commands["H01020"] == "00050"


def test_set_power_rejects_out_of_range():
    b = builder()
    assert b.set_power(5) is False
    assert b.set_power(101) is False
    assert b.commands == {}


def test_set_program_manual_payload():
    b = builder()
    assert b.set_program(AtreaProgram.MANUAL) is True
    assert b.commands["H10700"] == "00000"
    assert b.commands["H01015"] == "00001"


def test_set_program_temporary_pops_h10703():
    b = builder()
    b.set_program(AtreaProgram.WEEKLY)
    b.set_program(AtreaProgram.TEMPORARY)
    assert "H10703" not in b.commands
    assert b.commands["H10700"] == "00002"


def test_set_temperature_scales_and_validates():
    b = builder()
    assert b.set_temperature(22) is True
    # H10706 control coef=10 -> write_id H10716, value 22 -> 220
    assert b.commands["H10716"] == "00220"
    assert b.set_temperature(5) is False
