from __future__ import annotations

import asyncio
import hashlib
import random
import string
from xml.etree import ElementTree as ET

import aiohttp

from . import parser
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

    async def _get(self, param: str) -> str:
        assert self._session is not None, "AtreaClient needs an aiohttp session"
        try:
            async with self._session.get(self._url(param), timeout=self._timeout) as resp:
                if resp.status != 200:
                    raise AtreaConnectionError(f"HTTP {resp.status} for {param}")
                return await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
            raise AtreaConnectionError(str(err)) from err

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
