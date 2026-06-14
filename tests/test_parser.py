from xml.etree import ElementTree as ET
from pyatrea.parser import parse_status
from tests.conftest import load


def _legacy_parse_status(content: bytes) -> dict:
    out: dict[str, str] = {}
    xmldoc = ET.fromstring(content)
    parent = xmldoc[0]
    for data in list(parent):
        for child in list(data):
            if child.tag == "O" and "I" in child.attrib and "V" in child.attrib:
                out[child.attrib["I"]] = child.attrib["V"]
    return out


def test_status_parser_parity():
    content = load("status.xml")
    new = parse_status(content)
    assert new.registers == _legacy_parse_status(content)


def test_status_parser_returns_model():
    new = parse_status(load("status.xml"))
    assert isinstance(new.registers, dict)
    assert all(isinstance(k, str) and isinstance(v, str)
               for k, v in new.registers.items())


def test_status_parser_rejects_malformed():
    import pytest
    from pyatrea.exceptions import AtreaResponseError
    with pytest.raises(AtreaResponseError):
        parse_status(b"<broken>")
