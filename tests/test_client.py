from unittest.mock import AsyncMock

from pyatrea import AtreaMode, AtreaProgram
from pyatrea.client import AtreaClient
from pyatrea.models import AtreaStatus
from pyatrea.transport import Descriptors


def fake_transport(regs: dict[str, str]) -> AsyncMock:
    t = AsyncMock()
    t.read = AsyncMock(return_value=regs)
    t.read_descriptors = AsyncMock(return_value=Descriptors())
    t.write = AsyncMock()
    t.is_atrea_unit = AsyncMock(return_value=True)
    return t


async def test_fetch_status_and_scaling():
    c = AtreaClient(fake_transport({"H10705": "2", "I10215": "200"}))
    s = await c.fetch_status()
    assert s.registers["H10705"] == "2"
    assert s.value("I10215") == 20.0  # coef=10 from registers.py


async def test_fetch_descriptors_delegates_to_transport():
    t = fake_transport({})
    c = AtreaClient(t)
    desc = await c.fetch_descriptors()
    assert isinstance(desc, Descriptors)
    t.read_descriptors.assert_awaited_once()


async def test_commit_writes_proven_register():
    t = fake_transport({})
    c = AtreaClient(t)
    b = c.command_builder()
    b.set_power(40)
    assert await c.commit(b) is True
    assert "H10708" in t.write.await_args.args[0]
    assert "H10714" not in t.write.await_args.args[0]


async def test_commit_empty_builder_is_noop():
    t = fake_transport({})
    c = AtreaClient(t)
    assert await c.commit(c.command_builder()) is False
    t.write.assert_not_awaited()


async def test_is_atrea_unit_delegates():
    t = fake_transport({})
    c = AtreaClient(t)
    assert await c.is_atrea_unit() is True
    t.is_atrea_unit.assert_awaited_once()


def test_program_and_mode_mappers():
    assert AtreaClient.program_of(AtreaStatus(registers={"H10700": "0"})) == AtreaProgram.MANUAL
    assert AtreaClient.mode_of(AtreaStatus(registers={"H10705": "2"})) == AtreaMode.VENTILATION


def test_program_of_maps_registers():
    assert AtreaClient.program_of(AtreaStatus(registers={"H10700": "0"})) == AtreaProgram.MANUAL
    assert AtreaClient.program_of(AtreaStatus(registers={"H10700": "1"})) == AtreaProgram.WEEKLY
    assert AtreaClient.program_of(AtreaStatus(registers={"H10700": "2"})) == AtreaProgram.TEMPORARY
    assert AtreaClient.program_of(AtreaStatus(registers={})) is None


def test_mode_of_guards_bad_value():
    assert AtreaClient.mode_of(AtreaStatus(registers={"H10705": "2"})) == AtreaMode.VENTILATION
    assert AtreaClient.mode_of(AtreaStatus(registers={"H10705": "999"})) is None
    assert AtreaClient.mode_of(AtreaStatus(registers={})) is None


def test_version_of_partial_status_returns_none():
    assert AtreaClient.version_of(AtreaStatus(registers={})) is None
    s = AtreaStatus(registers={"I00020": "2", "I00021": "01", "I00022": "32"})
    assert AtreaClient.version_of(s) == "2.01.32"


def test_latest_version_of_partial_returns_default():
    s = AtreaStatus(registers={"I10009": "3"})
    assert AtreaClient.latest_version_of(s) == "0.0"


def test_forced_mode_of_defaults_off():
    assert AtreaClient.forced_mode_of(AtreaStatus(registers={}), {}) == AtreaMode.OFF


def test_id_of_returns_none_when_incomplete():
    assert AtreaClient.id_of(AtreaStatus(registers={})) is None


def test_supported_from_uses_bitmask_when_present():
    # I12004 bitmask + H11700 present -> writable derived from status
    status = AtreaStatus(registers={"I12004": "255", "H11700": "1"})
    desc = Descriptors(
        ids_to_modes={1: AtreaMode.VENTILATION},
        modes_to_ids={AtreaMode.VENTILATION: 1},
        forced_modes={2: AtreaMode.OFF},
    )
    writable, ids_to_modes, modes_to_ids, forced = AtreaClient.supported_from(status, desc)
    assert isinstance(writable, dict)
    assert writable[AtreaMode.VENTILATION] is True  # bit set in 0b11111111
    assert ids_to_modes == {1: AtreaMode.VENTILATION}
    assert modes_to_ids == {AtreaMode.VENTILATION: 1}
    assert forced == {2: AtreaMode.OFF}


def test_supported_from_falls_back_to_descriptors_when_no_bitmask():
    status = AtreaStatus(registers={})  # no bitmask registers
    desc = Descriptors(
        ids_to_modes={1: AtreaMode.VENTILATION, 2: AtreaMode.NIGHT_PRECOOLING},
        modes_to_ids={AtreaMode.VENTILATION: 1, AtreaMode.NIGHT_PRECOOLING: 2},
    )
    writable, ids_to_modes, modes_to_ids, forced = AtreaClient.supported_from(status, desc)
    # bitmask absent -> all descriptor modes treated as writable
    assert writable[AtreaMode.VENTILATION] is True
    assert writable[AtreaMode.NIGHT_PRECOOLING] is True
    assert ids_to_modes == desc.ids_to_modes
    assert modes_to_ids == desc.modes_to_ids


def test_public_exports():
    import pyatrea
    for name in ("AtreaClient", "AtreaMode", "AtreaProgram", "AtreaParams",
                 "AtreaStatus", "AtreaError", "AtreaConnectionError",
                 "AtreaAuthError", "AtreaResponseError", "CommandBuilder"):
        assert hasattr(pyatrea, name)
