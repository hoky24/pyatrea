from pyatrea.commands import CommandBuilder
from pyatrea.const import AtreaMode, AtreaProgram


def builder() -> CommandBuilder:
    return CommandBuilder()


def test_set_power_writes_proven_registers():
    b = builder()
    assert b.set_power(40) is True
    # proven-on-hardware write targets, not the readback registers
    assert b.commands["H10708"] == "00040"
    assert b.commands["H01020"] == "00040"
    assert "H10704" not in b.commands
    assert "H10714" not in b.commands


def test_set_power_rejects_out_of_range():
    b = builder()
    assert b.set_power(5) is False
    assert b.set_power(101) is False
    assert b.commands == {}


def test_set_mode_writes_proven_registers():
    b = builder()
    assert b.set_mode(AtreaMode.OFF) is True
    mode_id = int(AtreaMode.OFF)
    assert b.commands["H10709"] == f"{mode_id:05}"
    assert b.commands["H01019"] == f"{mode_id:05}"
    assert "H10705" not in b.commands
    assert "H10715" not in b.commands


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
    # H10710 gets int(t*10); H01021 gets int(t) — proven write targets
    assert b.commands["H10710"] == "00220"
    assert b.commands["H01021"] == "00022"
    assert "H10706" not in b.commands
    assert "H10716" not in b.commands
    assert b.set_temperature(5) is False


def test_prepare_update_sets_h10006():
    b = builder()
    b.prepare_update()
    assert b.commands["H10006"] == "00001"
