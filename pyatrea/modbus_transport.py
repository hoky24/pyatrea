from __future__ import annotations

import asyncio
from typing import Any

from pymodbus.client import AsyncModbusTcpClient

from . import registers
from .exceptions import AtreaModbusError
from .transport import Descriptors

_READERS = {
    "input": "read_input_registers",
    "holding": "read_holding_registers",
    "coil": "read_coils",
    "discrete": "read_discrete_inputs",
}


def _is_kwarg_mismatch(err: TypeError) -> bool:
    """True if a TypeError is from the slave/device_id kwarg signature, not
    from inside the pymodbus call body (which must propagate, not be masked)."""
    msg = str(err)
    return "slave" in msg or "device_id" in msg or "unexpected keyword" in msg


class ModbusTransport:
    def __init__(
        self,
        ip: str,
        port: int = 502,
        slave_id: int = 1,
        pace: float = 0.3,
    ) -> None:
        self._ip = ip
        self._port = port
        self._slave = slave_id
        self._pace = pace
        self._client: AsyncModbusTcpClient | None = None
        self._connected = False

    async def connect(self) -> None:
        self._client = AsyncModbusTcpClient(self._ip, port=self._port, timeout=5)
        ok = await self._client.connect()
        if not ok:
            raise AtreaModbusError(
                f"cannot connect to {self._ip}:{self._port} "
                "(is Modbus TCP enabled?)"
            )
        self._connected = True

    async def close(self) -> None:
        if self._client is not None:
            self._client.close()
        self._connected = False

    async def _ensure(self) -> AsyncModbusTcpClient:
        if not self._connected or self._client is None:
            await self.connect()
        assert self._client is not None
        return self._client

    async def _call(self, fn_name: str, address: int, count: int) -> Any:
        client = await self._ensure()
        fn = getattr(client, fn_name)
        for kwargs in self._slave_kwargs():
            try:
                rr = await fn(address, count=count, **kwargs)
            except TypeError as err:
                if _is_kwarg_mismatch(err):
                    continue
                raise AtreaModbusError(str(err)) from err
            except Exception as err:  # noqa: BLE001
                raise AtreaModbusError(str(err)) from err
            if rr is None or rr.isError():
                raise AtreaModbusError(f"modbus read error @{address}: {rr}")
            return rr
        raise AtreaModbusError("no compatible pymodbus read signature")

    async def read(self) -> dict[str, str]:
        out: dict[str, str] = {}
        addr_to_id = {
            (d.kind, int(rid[1:])): rid for rid, d in registers.REGISTERS.items()
        }
        for kind, start, count in registers.modbus_ranges():
            rr = await self._call(_READERS[kind], start, count)
            vals = rr.bits if kind in ("coil", "discrete") else rr.registers
            for i, v in enumerate(vals):
                rid = addr_to_id.get((kind, start + i))
                if rid is not None:
                    out[rid] = str(int(v))
            if self._pace:
                await asyncio.sleep(self._pace)
        return out

    async def write(self, commands: dict[str, str]) -> None:
        client = await self._ensure()
        for rid, value in commands.items():
            reg = registers.REGISTERS.get(rid)
            if reg is not None:
                kind = reg.kind
            else:
                kind = "coil" if rid[:1] == "C" else "holding"
            addr = int(rid[1:])
            try:
                if kind == "coil":
                    await self._write_coil(client, addr, bool(int(value)))
                else:
                    await self._write_register(client, addr, int(value))
            except AtreaModbusError:
                raise
            except Exception as err:  # noqa: BLE001
                raise AtreaModbusError(str(err)) from err
            if self._pace:
                await asyncio.sleep(self._pace)

    def _slave_kwargs(self) -> tuple[dict[str, Any], ...]:
        # pymodbus renamed slave -> device_id across versions; try both, then
        # fall back to positional defaults. dict[str, Any] keeps mypy happy
        # about unpacking into the strictly typed keyword-only signatures.
        return ({"slave": self._slave}, {"device_id": self._slave}, {})

    async def _write_register(
        self, client: AsyncModbusTcpClient, addr: int, value: int
    ) -> None:
        for kwargs in self._slave_kwargs():
            try:
                await client.write_register(addr, value, **kwargs)
                return
            except TypeError as err:
                if _is_kwarg_mismatch(err):
                    continue
                raise AtreaModbusError(str(err)) from err
        raise AtreaModbusError("no compatible write_register signature")

    async def _write_coil(
        self, client: AsyncModbusTcpClient, addr: int, value: bool
    ) -> None:
        for kwargs in self._slave_kwargs():
            try:
                await client.write_coil(addr, value, **kwargs)
                return
            except TypeError as err:
                if _is_kwarg_mismatch(err):
                    continue
                raise AtreaModbusError(str(err)) from err
        raise AtreaModbusError("no compatible write_coil signature")

    async def read_descriptors(self) -> Descriptors:
        return Descriptors()

    async def is_atrea_unit(self) -> bool:
        try:
            await self._call("read_holding_registers", 10705, 1)
        except AtreaModbusError:
            return False
        return True
