from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(slots=True)
class AtreaParams:
    warning: list[str] = field(default_factory=list)
    alert: list[str] = field(default_factory=list)
    ids: list[str] = field(default_factory=list)
    coefs: dict[str, float] = field(default_factory=dict)
    offsets: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class AtreaStatus:
    registers: dict[str, str] = field(default_factory=dict)
    params: AtreaParams = field(default_factory=AtreaParams)

    def value(self, key: str) -> int | float | None:
        if key not in self.registers:
            return None
        value: int | float = int(self.registers[key])
        if key in self.params.offsets:
            value -= self.params.offsets[key]
        if key in self.params.coefs:
            value /= self.params.coefs[key]
        return value
