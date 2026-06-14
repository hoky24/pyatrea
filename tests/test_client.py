import asyncio
import re

import aiohttp
import pytest
from aioresponses import aioresponses

from pyatrea.client import AtreaClient
from pyatrea.exceptions import AtreaAuthError, AtreaConnectionError
from tests.conftest import load


@pytest.fixture
async def client():
    async with aiohttp.ClientSession() as session:
        yield AtreaClient("1.2.3.4", 80, "secret", session)


async def test_fetch_status_ok(client):
    with aioresponses() as m:
        m.get(re.compile(r"http://1\.2\.3\.4/config/xml\.xml.*"),
              status=200, body=load("status.xml"))
        status = await client.fetch_status()
        assert status.registers


async def test_fetch_status_timeout_raises_connection_error(client):
    with aioresponses() as m:
        m.get(re.compile(r".*config/xml\.xml.*"), exception=asyncio.TimeoutError())
        with pytest.raises(AtreaConnectionError):
            await client.fetch_status()


async def test_403_triggers_reauth_then_succeeds(client):
    with aioresponses() as m:
        m.get(re.compile(r".*config/xml\.xml.*"), status=200,
              body=b"HTTP: 403 Forbidden")
        m.get(re.compile(r".*login\.cgi.*"), status=200, body=b"<a>TOKEN</a>")
        m.get(re.compile(r".*config/xml\.xml.*"), status=200, body=load("status.xml"))
        status = await client.fetch_status()
        assert status.registers


async def test_persistent_403_raises_auth_error(client):
    with aioresponses() as m:
        m.get(re.compile(r".*config/xml\.xml.*"), status=200,
              body=b"HTTP: 403 Forbidden")
        m.get(re.compile(r".*login\.cgi.*"), status=200, body=b"<a>denied</a>")
        m.get(re.compile(r".*config/xml\.xml.*"), status=200,
              body=b"HTTP: 403 Forbidden")
        with pytest.raises(AtreaAuthError):
            await client.fetch_status()
