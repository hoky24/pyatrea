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

# Compatibility shim: aioresponses 0.7.8 normalizes URLs with
# parse_qsl(keep_blank_values=False), which silently drops valueless query
# tokens (e.g. the Atrea write payload `?auth=CODE&H1070800040`). That makes
# the request callback observe a URL stripped of the register writes. Preserve
# blank values so tests can assert on the real, fully-formed request URL.
from urllib.parse import parse_qsl, urlencode  # noqa: E402

from aioresponses import core as _ar_core  # noqa: E402
from yarl import URL as _URL  # noqa: E402


def _normalize_url_keep_blank(url):  # type: ignore[no-untyped-def]
    # Unlike the upstream helper we do NOT sort the query params: tests assert
    # on write-path ordering (auth before register writes). All matchers in the
    # suite are regex-based, so ordering does not affect request matching.
    url = _URL(url)
    return url.with_query(
        urlencode(parse_qsl(url.query_string, keep_blank_values=True))
    )


_ar_core.normalize_url = _normalize_url_keep_blank  # type: ignore[attr-defined]

# Compatibility shim: aioresponses 0.7.8 builds the mocked response body via
# StreamReader(limit=2**16).feed_data(body). When body exceeds the 128 KiB
# high-water mark (cfgdir.xml is ~720 KiB, texts_2.xml ~165 KiB), the stream
# calls protocol.pause_reading(), which asserts on a real parser the synthetic
# response never has, and crashes. Replace the factory with one whose limit is
# large enough to hold any fixture, so pause_reading is never triggered.
from aiohttp import StreamReader as _StreamReader  # noqa: E402
from aiohttp.client_proto import ResponseHandler as _ResponseHandler  # noqa: E402


def _large_stream_reader_factory(loop=None):  # type: ignore[no-untyped-def]
    return _StreamReader(_ResponseHandler(loop=loop), limit=2 ** 24, loop=loop)


_ar_core.stream_reader_factory = _large_stream_reader_factory  # type: ignore[attr-defined]

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
