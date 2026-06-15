from __future__ import annotations

from . import registers
from .const import AtreaMode, AtreaProgram


class CommandBuilder:
    def __init__(
        self,
        known_registers: set[str] | None = None,
        modes_to_ids: dict[AtreaMode, int] | None = None,
        supported_modes: dict[AtreaMode, bool] | None = None,
    ) -> None:
        # None means "no allow-list": every requested register is writable.
        # The explicit control writes below target proven-on-hardware write
        # registers (H10708/H10709/H10710 + their H010xx twins), so a None
        # allow-list is required. Pass an explicit set to restrict set_command
        # to a known subset.
        self.known_registers = known_registers
        self.modes_to_ids = modes_to_ids or {}
        self.supported_modes = supported_modes or {}
        self.commands: dict[str, str] = {}

    def set_command(self, register: str, value: int) -> None:
        if self.known_registers is not None and register not in self.known_registers:
            return
        d = registers.REGISTERS.get(register)
        if d is not None:
            if d.coef:
                value = int(value * d.coef)
            value = int(value + d.offset)
        self.commands[register] = f"{value:05}"

    def set_power(self, power: int) -> bool:
        if not isinstance(power, int) or power < 12 or power > 100:
            return False
        self.set_command("H10708", power)
        self.set_command("H01020", power)
        return True

    def set_temperature(self, temperature: int | float) -> bool:
        if not isinstance(temperature, (int, float)):
            return False
        if 10 <= temperature <= 40:
            self.set_command("H10710", int(temperature * 10))
            self.set_command("H01021", int(temperature))
            return True
        return False

    def set_program(self, program: AtreaProgram) -> bool:
        if program == AtreaProgram.MANUAL:
            triples = {"H10700": 0, "H10701": 0, "H10702": 0, "H10703": 0,
                       "H01015": 1, "H01016": 1, "H01017": 1}
        elif program == AtreaProgram.WEEKLY:
            triples = {"H10700": 1, "H10701": 1, "H10702": 1, "H10703": 1,
                       "H01015": 0, "H01016": 0, "H01017": 0}
        elif program == AtreaProgram.TEMPORARY:
            triples = {"H10700": 2, "H10701": 2, "H10702": 2,
                       "H01015": 2, "H01016": 2, "H01017": 2}
            self.commands.pop("H10703", None)
        else:
            return False
        for reg, val in triples.items():
            self.set_command(reg, val)
        return True

    def set_mode(self, mode: AtreaMode) -> bool:
        if mode != AtreaMode.OFF and not self.supported_modes.get(mode, False):
            return False
        mode_id = self.modes_to_ids.get(mode, int(mode))
        self.set_command("H10709", mode_id)
        self.set_command("H01019", mode_id)
        return True

    def prepare_update(self) -> None:
        self.commands["H10006"] = f"{1:05}"
        self.set_command("H10006", 1)
