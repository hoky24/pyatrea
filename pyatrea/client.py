from __future__ import annotations

from xml.etree import ElementTree as ET

from . import parser
from .commands import CommandBuilder
from .const import AtreaMode, AtreaProgram
from .models import AtreaStatus
from .transport import AtreaTransport, Descriptors


class AtreaClient:
    """Transport-agnostic facade over an :class:`AtreaTransport`.

    All wire I/O (HTTP or Modbus) lives in the transport; this client adds the
    register-aware status/command semantics and the static status mappers.
    """

    def __init__(self, transport: AtreaTransport) -> None:
        self._transport = transport

    async def fetch_status(self) -> AtreaStatus:
        return AtreaStatus(registers=await self._transport.read())

    async def fetch_descriptors(self) -> Descriptors:
        return await self._transport.read_descriptors()

    @staticmethod
    def supported_from(
        status: AtreaStatus, descriptors: Descriptors
    ) -> tuple[
        dict[AtreaMode, bool],
        dict[int, AtreaMode],
        dict[AtreaMode, int],
        dict[int, AtreaMode],
    ]:
        """Return ``(writable, ids_to_modes, modes_to_ids, forced)``.

        ``writable`` comes from the per-cycle I12004 bitmask in ``status`` when
        present (RD5 firmware); otherwise every mode advertised by the
        descriptors' ModeEC map is treated as writable. id<->mode and forced
        maps come straight from ``descriptors``.
        """
        bitmask = parser.supported_modes_from_status(status)
        if bitmask is not None:
            writable = bitmask
        else:
            writable = {m: False for m in AtreaMode}
            for mode in descriptors.modes_to_ids:
                writable[mode] = True
        return (
            writable,
            descriptors.ids_to_modes,
            descriptors.modes_to_ids,
            descriptors.forced_modes,
        )

    def command_builder(self, **kw: object) -> CommandBuilder:
        return CommandBuilder(**kw)  # type: ignore[arg-type]

    async def commit(self, builder: CommandBuilder) -> bool:
        if not builder.commands:
            return False
        await self._transport.write(builder.commands)
        return True

    async def is_atrea_unit(self) -> bool:
        return await self._transport.is_atrea_unit()

    @staticmethod
    def program_of(status: AtreaStatus) -> AtreaProgram | None:
        for reg, mapping in (
            ("H10700", {0: AtreaProgram.MANUAL, 1: AtreaProgram.WEEKLY, 2: AtreaProgram.TEMPORARY}),
            ("H01015", {1: AtreaProgram.MANUAL, 0: AtreaProgram.WEEKLY, 2: AtreaProgram.TEMPORARY}),
        ):
            if reg in status.registers:
                value = status.value(reg)
                return mapping.get(int(value)) if value is not None else None
        return None

    @staticmethod
    def mode_of(status: AtreaStatus,
                ids_to_modes: dict[int, AtreaMode] | None = None) -> AtreaMode | None:
        if "H10705" in status.registers:
            value = status.value("H10705")
            try:
                return AtreaMode(int(value)) if value is not None else None
            except ValueError:
                return None
        if "H01000" in status.registers and ids_to_modes:
            value = status.value("H01000")
            return ids_to_modes.get(int(value)) if value is not None else None
        return None

    @staticmethod
    def version_of(status: AtreaStatus) -> str | None:
        r = status.registers
        if not {"I00020", "I00021", "I00022"} <= r.keys():
            return None
        if int(r["I00022"]) > 0:
            return f'{r["I00020"]}.{r["I00021"]}.{r["I00022"]}'
        return f'{r["I00020"]}.{r["I00021"]}'

    @staticmethod
    def latest_version_of(status: AtreaStatus) -> str:
        r = status.registers
        if not {"I10007", "I10008"} <= r.keys():
            return "0.0"
        if "I10009" in r and int(r["I10009"]) > 0:
            return f'{r["I10007"]}.{r["I10008"]}.{r["I10009"]}'
        return f'{r["I10007"]}.{r["I10008"]}'

    @staticmethod
    def id_of(status: AtreaStatus) -> str | None:
        chars = []
        for i in range(300, 310):
            key = f"H12{i}"
            if key not in status.registers:
                return None
            chars.append(chr(int(status.registers[key])))
        return "".join(chars)

    @staticmethod
    def forced_mode_of(status: AtreaStatus,
                       supported: dict[int, AtreaMode]) -> AtreaMode:
        if "H10712" in status.registers:
            value = status.value("H10712")
            if value is not None and int(value) in supported:
                return supported[int(value)]
        return AtreaMode.OFF

    def model_of(
        self, status: AtreaStatus, config_dir: ET.Element | None
    ) -> dict[str, str] | None:
        r = status.registers
        if config_dir is None or "H10520" not in r:
            return None
        data = {"main": "", "category": "", "model": ""}
        main = parser.find_child(config_dir, r["H10520"])
        if main is None:
            return None
        data["main"] = main.attrib.get("name", "")
        if "H10521" in r:
            cat = parser.find_child(main, r["H10521"])
            if cat is not None:
                data["category"] = cat.attrib.get("name", "")
                if "H10522" in r:
                    mdl = parser.find_child(cat, r["H10522"])
                    if mdl is not None:
                        data["model"] = mdl.attrib.get("name", "")
        return data
