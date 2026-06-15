"""Register metadata — single source of truth for HTTP and Modbus transports.

Modbus address == ``int(id[1:])`` (direct 6-digit addressing, confirmed
empirically). Function code is selected by the id prefix:
``I`` = input, ``H`` = holding, ``C`` = coil, ``D`` = discrete.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Kind = Literal["input", "holding", "coil", "discrete"]
Role = Literal["sensor", "control", "warning", "alert", "info"]


@dataclass(frozen=True, slots=True)
class RegisterDef:
    kind: Kind
    coef: float = 1.0
    offset: float = 0.0
    role: Role = "sensor"


def _r(
    kind: Kind,
    coef: float = 1.0,
    offset: float = 0.0,
    role: Role = "sensor",
) -> RegisterDef:
    return RegisterDef(kind, coef, offset, role)


REGISTERS: dict[str, RegisterDef] = {
    # controls — READ-side state only. Writes go to proven hardware write
    # registers (H10708/H10709/H10710 + H010xx twins) via CommandBuilder, NOT
    # to these ids; see pyatrea/commands.py.
    "H10704": _r("holding", role="control"),
    "H10705": _r("holding", role="control"),
    "H10706": _r("holding", coef=10, role="control"),
    "H10707": _r("holding", role="control"),
    "H10700": _r("holding", role="control"),
    "H10712": _r("holding", role="control"),
    # requested-value readback registers (info role; e.g. _requested_power
    # is read from H10714 by the climate entity).
    "H10714": _r("holding", role="info"),
    "H10715": _r("holding", role="info"),
    "H10716": _r("holding", coef=10, role="info"),
    "H10717": _r("holding", role="info"),
    # temperatures coef=10
    "I10211": _r("input", coef=10),
    "I10212": _r("input", coef=10),
    "I10213": _r("input", coef=10),
    "I10214": _r("input", coef=10),
    "I10215": _r("input", coef=10),
    "I11420": _r("input", coef=10),
    # version / latest / id / model / bitmask / hours
    "I00020": _r("input", role="info"),
    "I00021": _r("input", role="info"),
    "I00022": _r("input", role="info"),
    "I10007": _r("input", role="info"),
    "I10008": _r("input", role="info"),
    "I10009": _r("input", role="info"),
    "H10520": _r("holding", role="info"),
    "H10521": _r("holding", role="info"),
    "H10522": _r("holding", role="info"),
    **{f"H123{n:02d}": _r("holding", role="info") for n in range(10)},
    "H13500": _r("holding"),
    "H13501": _r("holding"),
    "H13502": _r("holding"),
    "H13503": _r("holding"),
    "I12004": _r("input", role="info"),
    "H11700": _r("holding", role="info"),
}

# Warning flags (flag="W" in params.xml) — all discrete.
_WARNINGS: tuple[str, ...] = (
    "D11117", "D11118", "D11119", "D11120", "D11121", "D11122", "D11123",
    "D11124", "D11125", "D11126", "D11127", "D11128", "D11129", "D11130",
    "D11131", "D11132", "D11142", "D11149", "D11165", "D11168", "D11171",
    "D11173", "D11174", "D11183", "D11184", "D11196", "D11197",
)

# Alert flags (flag="A" in params.xml) — all discrete.
_ALERTS: tuple[str, ...] = (
    "D11100", "D11101", "D11102", "D11103", "D11104", "D11105", "D11106",
    "D11107", "D11108", "D11109", "D11110", "D11111", "D11112", "D11113",
    "D11114", "D11115", "D11116", "D11136", "D11140", "D11141", "D11143",
    "D11144", "D11145", "D11146", "D11147", "D11148", "D11150", "D11151",
    "D11152", "D11153", "D11154", "D11155", "D11156", "D11157", "D11158",
    "D11159", "D11162", "D11166", "D11167", "D11169", "D11170", "D11172",
    "D11175", "D11185", "D11188", "D11189", "D11190", "D11191", "D11192",
    "D11193", "D11194", "D11195", "D11400",
)

for _wid in _WARNINGS:
    REGISTERS[_wid] = _r("discrete", role="warning")
for _aid in _ALERTS:
    REGISTERS[_aid] = _r("discrete", role="alert")


def by_role(role: Role) -> list[str]:
    return [rid for rid, d in REGISTERS.items() if d.role == role]


def modbus_ranges(max_gap: int = 8) -> list[tuple[Kind, int, int]]:
    out: list[tuple[Kind, int, int]] = []
    for kind in ("input", "holding", "coil", "discrete"):
        addrs = sorted(int(r[1:]) for r, d in REGISTERS.items() if d.kind == kind)
        if not addrs:
            continue
        start = prev = addrs[0]
        for a in addrs[1:]:
            if a - prev > max_gap:
                out.append((kind, start, prev - start + 1))
                start = a
            prev = a
        out.append((kind, start, prev - start + 1))
    return out
