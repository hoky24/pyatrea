from __future__ import annotations

import asyncio
import hashlib
import random
import string
from xml.etree import ElementTree as ET

import aiohttp

from . import parser
from .const import REQUEST_TIMEOUT
from .exceptions import AtreaAuthError, AtreaConnectionError, AtreaResponseError
from .transport import Descriptors


class HttpTransport:
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

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    def _url(self, param: str) -> str:
        sep = "&" if "?" in param else "?"
        nonce = random.choice(string.ascii_letters) + random.choice(string.ascii_letters)
        return f"http://{self._ip}:{self._port}/{param}{sep}auth={self._code}&{nonce}"

    async def _request(self, url: str) -> str:
        assert self._session is not None, "HttpTransport needs an aiohttp session"
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

    async def _status_text(self) -> str:
        text = await self._get("config/xml.xml")
        if "HTTP: 403 Forbidden" in text:
            await self._authenticate()
            text = await self._get("config/xml.xml")
            if "HTTP: 403 Forbidden" in text:
                raise AtreaAuthError("403 after re-auth")
        return text

    async def read(self) -> dict[str, str]:
        async with self._lock:
            text = await self._status_text()
        return parser.parse_status(text.encode()).registers

    async def write(self, commands: dict[str, str]) -> None:
        if not commands:
            return
        suffix = "".join(f"&{r}{v}" for r, v in commands.items())
        async with self._lock:
            text = await self._request(self._url("config/xml.cgi") + suffix)
            if "HTTP: 403 Forbidden" in text:
                await self._authenticate()
                text = await self._request(self._url("config/xml.cgi") + suffix)
                if "HTTP: 403 Forbidden" in text:
                    raise AtreaAuthError("403 after re-auth on commit")

    async def read_descriptors(self) -> Descriptors:
        async with self._lock:
            cfg = await self._get("cfgdir.xml")
            tr = await self._get("lang/texts_2.xml")
            labels = await self._get("config/texts.xml")
            uc = await self._get("lang/userCtrl.xml")
        ucb = uc.encode()
        _ec_writable, ids_to_modes, modes_to_ids = parser.parse_supported_modes(ucb)
        return Descriptors(
            config_dir=parser.parse_config_dir(cfg.encode()),
            translations=parser.parse_translations(tr.encode()),
            user_labels=parser.parse_user_labels(labels.encode()),
            ids_to_modes=ids_to_modes,
            modes_to_ids=modes_to_ids,
            forced_modes=parser.parse_supported_forced_modes(ucb),
        )

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
