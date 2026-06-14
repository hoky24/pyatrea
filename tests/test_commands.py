from pyatrea.commands import CommandBuilder
from pyatrea.const import AtreaProgram
from pyatrea.models import AtreaParams


def builder(ids=("H10708", "H01020", "H10700", "H10709", "H10710")):
    return CommandBuilder(params=AtreaParams(ids=list(ids)), known_registers=set(ids))


def test_set_power_within_range():
    b = builder()
    assert b.set_power(50) is True
    assert b.commands["H10708"] == "00050"
    assert b.commands["H01020"] == "00050"


def test_set_power_rejects_out_of_range():
    b = builder()
    assert b.set_power(5) is False
    assert b.set_power(101) is False
    assert b.commands == {}


def test_set_program_manual_payload():
    b = builder(ids=("H10700", "H10701", "H10702", "H10703",
                     "H01015", "H01016", "H01017"))
    assert b.set_program(AtreaProgram.MANUAL) is True
    assert b.commands["H10700"] == "00000"
    assert b.commands["H01015"] == "00001"


def test_set_program_temporary_pops_h10703():
    b = builder(ids=("H10700", "H10701", "H10702", "H10703",
                     "H01015", "H01016", "H01017"))
    b.set_program(AtreaProgram.WEEKLY)
    b.set_program(AtreaProgram.TEMPORARY)
    assert "H10703" not in b.commands
    assert b.commands["H10700"] == "00002"


def test_set_temperature_scales_and_validates():
    b = builder(ids=("H10710", "H01021"))
    assert b.set_temperature(22) is True
    assert b.commands["H10710"] == "00220"
    assert b.set_temperature(5) is False
