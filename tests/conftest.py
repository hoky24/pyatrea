import pathlib
import pytest

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
