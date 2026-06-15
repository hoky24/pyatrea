from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable
from xml.etree import ElementTree as ET

from .const import AtreaMode


@dataclass(slots=True)
class Descriptors:
    """Static, HTTP-only descriptive data. Modbus returns this empty (defaults)."""

    config_dir: ET.Element | None = None
    translations: dict[str, dict[str, object]] = field(
        default_factory=lambda: {"params": {}, "words": {}}
    )
    user_labels: dict[str, str] = field(default_factory=dict)
    ids_to_modes: dict[int, AtreaMode] = field(default_factory=dict)
    modes_to_ids: dict[AtreaMode, int] = field(default_factory=dict)
    forced_modes: dict[int, AtreaMode] = field(default_factory=dict)


@runtime_checkable
class AtreaTransport(Protocol):
    async def connect(self) -> None: ...
    async def read(self) -> dict[str, str]: ...
    async def write(self, commands: dict[str, str]) -> None: ...
    async def read_descriptors(self) -> Descriptors: ...
    async def is_atrea_unit(self) -> bool: ...
    async def close(self) -> None: ...
