from __future__ import annotations

import asyncio
import hashlib
import random
import string
from xml.etree import ElementTree as ET

import aiohttp

from . import parser
from .commands import CommandBuilder
from .const import REQUEST_TIMEOUT, AtreaMode, AtreaProgram
from .exceptions import AtreaAuthError, AtreaConnectionError, AtreaResponseError
from .models import AtreaParams, AtreaStatus


class AtreaClient:
    def __init__(
        self,
        ip: str,
        port: int = 80,
        password: str = "",
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._ip = ip
        self._port = port
        self._password = password
        self._session = session
        self._code = ""
        self._lock = asyncio.Lock()
        self._timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

    def _base_url(self) -> str:
        return f"http://{self._ip}:{self._port}/"

    def _url(self, param: str) -> str:
        sep = "&" if "?" in param else "?"
        nonce = random.choice(string.ascii_letters) + random.choice(string.ascii_letters)
        return f"{self._base_url()}{param}{sep}auth={self._code}&{nonce}"

    async def _request(self, url: str) -> str:
        assert self._session is not None, "AtreaClient needs an aiohttp session"
        try:
            async with self._session.get(url, timeout=self._timeout) as resp:
                if resp.status != 200:
                    raise AtreaConnectionError(f"HTTP {resp.status} for {url}")
                return await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
            raise AtreaConnectionError(str(err)) from err

    async def _get(self, param: str) -> str:
        return await self._request(self._url(param))

    async def _authenticate(self) -> None:
        magic = hashlib.md5(("\r\n" + self._password).encode()).hexdigest()
        text = await self._get(f"config/login.cgi?magic={magic}")
        try:
            token = ET.fromstring(text).text
        except ET.ParseError as err:
            raise AtreaResponseError("malformed login response") from err
        if token is None or token == "denied":
            raise AtreaAuthError("authentication denied")
        self._code = token

    async def _get_status_text(self) -> str:
        text = await self._get("config/xml.xml")
        if "HTTP: 403 Forbidden" in text:
            await self._authenticate()
            text = await self._get("config/xml.xml")
            if "HTTP: 403 Forbidden" in text:
                raise AtreaAuthError("403 after re-auth")
        return text

    async def fetch_params(self) -> AtreaParams:
        async with self._lock:
            text = await self._get("user/params.xml")
        return parser.parse_params(text.encode())

    async def fetch_status(self, with_params: bool = False) -> AtreaStatus:
        async with self._lock:
            text = await self._get_status_text()
        status = parser.parse_status(text.encode())
        if with_params:
            status.params = await self.fetch_params()
        return status

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

    async def fetch_config_dir(self) -> ET.Element | None:
        async with self._lock:
            text = await self._get("cfgdir.xml")
        return parser.parse_config_dir(text.encode())

    async def fetch_user_labels(self) -> dict[str, str]:
        async with self._lock:
            text = await self._get("config/texts.xml")
        return parser.parse_user_labels(text.encode())

    async def fetch_translations(self) -> dict[str, dict[str, object]]:
        async with self._lock:
            text = await self._get("lang/texts_2.xml")
        return parser.parse_translations(text.encode())

    async def fetch_supported(
        self, status: AtreaStatus
    ) -> tuple[
        dict[AtreaMode, bool],
        dict[int, AtreaMode],
        dict[AtreaMode, int],
        dict[int, AtreaMode],
    ]:
        """Return (writable_modes, ids_to_modes, modes_to_ids, forced_modes).
        Supported modes come from the I12004 bitmask when present (RD5), else
        from the userctrl ModeEC op (other firmware). ids_to_modes/modes_to_ids
        come from the ModeEC parse (empty for bitmask-only RD5 units, which is
        correct since those use enum-equal ids)."""
        async with self._lock:
            text = await self._get("lang/userCtrl.xml")
        raw = text.encode()
        ec_writable, ids_to_modes, modes_to_ids = parser.parse_supported_modes(raw)
        bitmask_writable = parser.supported_modes_from_status(status)
        writable = bitmask_writable if bitmask_writable is not None else ec_writable
        forced = parser.parse_supported_forced_modes(raw)
        return writable, ids_to_modes, modes_to_ids, forced

    async def fetch_userctrl(
        self,
    ) -> tuple[
        dict[AtreaMode, bool],
        dict[int, AtreaMode],
        dict[AtreaMode, int],
        dict[int, AtreaMode],
    ]:
        """Static userctrl.xml data (ModeEC writable map, id<->mode maps, forced
        modes). Firmware-static — fetch once and cache; combine with
        supported_modes_from_status(status) for the per-cycle bitmask overlay."""
        async with self._lock:
            text = await self._get("lang/userCtrl.xml")
        raw = text.encode()
        ec_writable, ids_to_modes, modes_to_ids = parser.parse_supported_modes(raw)
        forced = parser.parse_supported_forced_modes(raw)
        return ec_writable, ids_to_modes, modes_to_ids, forced

    def command_builder(self, params: AtreaParams, known_registers: set[str],
                        **kw: object) -> CommandBuilder:
        return CommandBuilder(params=params, known_registers=known_registers, **kw)  # type: ignore[arg-type]

    async def commit(self, builder: CommandBuilder) -> bool:
        if not builder.commands:
            return False
        suffix = "".join(f"&{r}{v}" for r, v in builder.commands.items())
        async with self._lock:
            text = await self._request(self._url("config/xml.cgi") + suffix)
            if "HTTP: 403 Forbidden" in text:
                await self._authenticate()
                text = await self._request(self._url("config/xml.cgi") + suffix)
                if "HTTP: 403 Forbidden" in text:
                    raise AtreaAuthError("403 after re-auth on commit")
        return True

    async def _frontend_version(self) -> str | None:
        try:
            text = await self._get("ver.txt")
        except AtreaConnectionError:
            return None
        try:
            int(text[0:2], 16)
        except (ValueError, IndexError):
            return None
        return text

    async def is_atrea_unit(self) -> bool:
        try:
            text = await self._get("config/login.cgi?magic=")
        except AtreaConnectionError:
            return False
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return False
        if root.text == "denied":
            return True
        if root.text is None and "HTTP: 404 Page (/config/login.cgi)" in text:
            return await self._frontend_version() is not None
        return False
