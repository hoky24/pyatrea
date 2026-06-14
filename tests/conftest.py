import pathlib
import pytest

# Compatibility shim: aioresponses 0.7.8 constructs aiohttp.ClientResponse
# without the `stream_writer` kwarg, which became required in aiohttp 3.14.
# Default it to None so the mocked responses can be built. aioresponses
# replaces `.content` afterwards, so the writer is never exercised.
from aiohttp import client_reqrep as _client_reqrep  # noqa: E402

_orig_client_response_init = _client_reqrep.ClientResponse.__init__


class _StubStreamWriter:
    output_size = 0


def _patched_client_response_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
    kwargs.setdefault("stream_writer", _StubStreamWriter())
    _orig_client_response_init(self, *args, **kwargs)


_client_reqrep.ClientResponse.__init__ = _patched_client_response_init  # type: ignore[method-assign]

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


@pytest.fixture
def status_xml() -> bytes:
    return load("status.xml")


@pytest.fixture
def params_xml() -> bytes:
    return load("params.xml")


@pytest.fixture
def userctrl_xml() -> bytes:
    return load("userctrl.xml")


@pytest.fixture
def cfgdir_xml() -> bytes:
    return load("cfgdir.xml")
