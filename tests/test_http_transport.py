import re
import aiohttp
import pytest
from aioresponses import aioresponses
from pyatrea.http_transport import HttpTransport
from tests.conftest import load


@pytest.fixture
async def http():
    async with aiohttp.ClientSession() as s:
        yield HttpTransport("1.2.3.4", 80, "secret", s)


async def test_read_returns_registers(http):
    with aioresponses() as m:
        m.get(re.compile(r".*config/xml\.xml.*"), status=200, body=load("status.xml"))
        regs = await http.read()
        assert regs and "H10705" in regs


async def test_read_403_reauths(http):
    with aioresponses() as m:
        m.get(re.compile(r".*config/xml\.xml.*"), status=200, body=b"HTTP: 403 Forbidden")
        m.get(re.compile(r".*login\.cgi.*"), status=200, body=b"<a>TOKEN</a>")
        m.get(re.compile(r".*config/xml\.xml.*"), status=200, body=load("status.xml"))
        assert await http.read()


async def test_write_auth_before_register_writes(http):
    sent = {}
    def cb(url, **kw):
        sent["url"] = str(url)
    with aioresponses() as m:
        m.get(re.compile(r".*config/xml\.cgi.*"), status=200, body=b"", callback=cb)
        await http.write({"H10714": "00040"})
        u = sent["url"]
        assert "auth=" in u and u.index("?") < u.index("H1071400040")


async def test_write_empty_noop(http):
    await http.write({})  # must not raise / not call anything


async def test_read_descriptors_populated(http):
    with aioresponses() as m:
        m.get(re.compile(r".*cfgdir\.xml.*"), status=200, body=load("cfgdir.xml"))
        m.get(re.compile(r".*texts_2\.xml.*"), status=200, body=load("texts_2.xml"))
        m.get(re.compile(r".*config/texts\.xml.*"), status=200, body=load("texts.xml"))
        m.get(re.compile(r".*userCtrl\.xml.*"), status=200, body=load("userctrl.xml"))
        d = await http.read_descriptors()
        assert d.config_dir is not None
        assert set(d.translations) == {"params", "words"}


async def test_is_atrea_unit_denied_true(http):
    with aioresponses() as m:
        m.get(re.compile(r".*login\.cgi.*"), status=200, body=b"<a>denied</a>")
        assert await http.is_atrea_unit() is True
