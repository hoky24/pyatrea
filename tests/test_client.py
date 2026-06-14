import asyncio
import re

import aiohttp
import pytest
from aioresponses import aioresponses

from pyatrea.client import AtreaClient
from pyatrea.const import AtreaMode, AtreaProgram
from pyatrea.exceptions import AtreaAuthError, AtreaConnectionError
from pyatrea.models import AtreaParams, AtreaStatus
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


async def test_fetch_status_includes_params(client):
    with aioresponses() as m:
        m.get(re.compile(r".*config/xml\.xml.*"), status=200, body=load("status.xml"))
        m.get(re.compile(r".*user/params\.xml.*"), status=200, body=load("params.xml"))
        status = await client.fetch_status(with_params=True)
        assert isinstance(status.params.ids, list)


def test_program_of_maps_registers():
    assert AtreaClient.program_of(AtreaStatus(registers={"H10700": "0"})) == AtreaProgram.MANUAL
    assert AtreaClient.program_of(AtreaStatus(registers={"H10700": "1"})) == AtreaProgram.WEEKLY
    assert AtreaClient.program_of(AtreaStatus(registers={"H10700": "2"})) == AtreaProgram.TEMPORARY
    assert AtreaClient.program_of(AtreaStatus(registers={})) is None


def test_mode_of_guards_bad_value():
    assert AtreaClient.mode_of(AtreaStatus(registers={"H10705": "2"})) == AtreaMode.VENTILATION
    assert AtreaClient.mode_of(AtreaStatus(registers={"H10705": "999"})) is None
    assert AtreaClient.mode_of(AtreaStatus(registers={})) is None


def test_version_of_partial_status_returns_none():
    assert AtreaClient.version_of(AtreaStatus(registers={})) is None
    s = AtreaStatus(registers={"I00020": "2", "I00021": "01", "I00022": "32"})
    assert AtreaClient.version_of(s) == "2.01.32"


def test_forced_mode_of_defaults_off():
    assert AtreaClient.forced_mode_of(AtreaStatus(registers={}), {}) == AtreaMode.OFF


def test_id_of_returns_none_when_incomplete():
    assert AtreaClient.id_of(AtreaStatus(registers={})) is None


async def test_commit_sends_register_payload(client):
    sent = {}

    def cb(url, **kwargs):
        sent["url"] = str(url)

    with aioresponses() as m:
        m.get(re.compile(r".*config/xml\.cgi.*"), status=200, body=b"", callback=cb)
        builder = client.command_builder(
            params=AtreaParams(ids=["H10708", "H01020"]),
            known_registers={"H10708", "H01020"},
        )
        builder.set_power(40)
        ok = await client.commit(builder)
        assert ok is True
        assert "H1070800040" in sent["url"]


async def test_commit_empty_builder_is_noop(client):
    builder = client.command_builder(params=AtreaParams(), known_registers=set())
    assert await client.commit(builder) is False


def test_public_exports():
    import pyatrea
    for name in ("AtreaClient", "AtreaMode", "AtreaProgram", "AtreaParams",
                 "AtreaStatus", "AtreaError", "AtreaConnectionError",
                 "AtreaAuthError", "AtreaResponseError", "CommandBuilder"):
        assert hasattr(pyatrea, name)
