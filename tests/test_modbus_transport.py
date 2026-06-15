import pytest
from unittest.mock import AsyncMock, MagicMock
from pyatrea.modbus_transport import ModbusTransport
from pyatrea.exceptions import AtreaModbusError


class _RR:
    def __init__(self, registers=None, bits=None):
        self.registers = registers or []
        self.bits = bits or []
    def isError(self):
        return False


def _fake_client(values):
    c = MagicMock()
    c.connect = AsyncMock(return_value=True)
    c.close = MagicMock()
    async def rd(address, count=1, **kw):
        return _RR(registers=[int(values.get(address + i, 0)) for i in range(count)])
    async def rdbits(address, count=1, **kw):
        return _RR(bits=[bool(values.get(address + i, 0)) for i in range(count)])
    c.read_input_registers = AsyncMock(side_effect=rd)
    c.read_holding_registers = AsyncMock(side_effect=rd)
    c.read_coils = AsyncMock(side_effect=rdbits)
    c.read_discrete_inputs = AsyncMock(side_effect=rdbits)
    c.write_register = AsyncMock(return_value=_RR())
    c.write_coil = AsyncMock(return_value=_RR())
    return c


async def test_read_returns_raw_by_id(monkeypatch):
    vals = {10705: 2, 10706: 230, 10215: 200, 11183: 1}
    t = ModbusTransport("1.2.3.4", 502, 1, pace=0)
    t._client = _fake_client(vals)
    t._connected = True
    regs = await t.read()
    assert regs["H10705"] == "2"
    assert regs["H10706"] == "230"
    assert regs["I10215"] == "200"
    assert regs["D11183"] == "1"


async def test_write_holding_and_coil(monkeypatch):
    t = ModbusTransport("1.2.3.4", 502, 1, pace=0)
    client = _fake_client({})
    t._client = client
    t._connected = True
    await t.write({"H10714": "00040"})
    client.write_register.assert_awaited()
    # a coil write (if a coil id is given)
    await t.write({"C11409": "1"})
    client.write_coil.assert_awaited()


async def test_write_routes_coil_and_holding_by_prefix(monkeypatch):
    # The integration writes a coil (C10902) and a holding register (H11401)
    # via CommandBuilder.commands. The transport must route the C-prefix as a
    # coil (FC5/FC15) and the H-prefix as a holding register (FC6/FC16) — NOT
    # both as holding.
    t = ModbusTransport("1.2.3.4", 502, 1, pace=0)
    client = _fake_client({})
    t._client = client
    t._connected = True
    await t.write({"C10902": "00001", "H11401": "00000"})
    client.write_coil.assert_awaited_once()
    assert client.write_coil.await_args.args[0] == 10902
    client.write_register.assert_awaited_once()
    assert client.write_register.await_args.args[0] == 11401


async def test_read_descriptors_empty():
    t = ModbusTransport("1.2.3.4", 502, 1, pace=0)
    d = await t.read_descriptors()
    assert d.config_dir is None and d.user_labels == {} and d.ids_to_modes == {}


async def test_read_error_raises(monkeypatch):
    t = ModbusTransport("1.2.3.4", 502, 1, pace=0)
    client = _fake_client({})
    async def boom(address, count=1, **kw):
        class E:
            def isError(self): return True
        return E()
    client.read_input_registers = AsyncMock(side_effect=boom)
    t._client = client
    t._connected = True
    with pytest.raises(AtreaModbusError):
        await t.read()
