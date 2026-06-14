from xml.etree import ElementTree as ET
from pyatrea.parser import parse_status, parse_params
from pyatrea.models import AtreaStatus, AtreaParams
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


def _legacy_parse_params(content: bytes) -> dict:
    p = {"warning": [], "alert": [], "ids": [], "coefs": {}, "offsets": {}}
    xmldoc = ET.fromstring(content)
    for param in xmldoc.findall("params"):
        for child in list(param):
            if child.tag == "i" and "id" in child.attrib:
                cid = child.attrib["id"]
                p["ids"].append(cid)
                if child.attrib.get("flag") == "W":
                    p["warning"].append(cid)
                elif child.attrib.get("flag") == "A":
                    p["alert"].append(cid)
                if "coef" in child.attrib:
                    p["coefs"][cid] = float(child.attrib["coef"])
                if "offset" in child.attrib:
                    p["offsets"][cid] = float(child.attrib["offset"])
    return p


def test_params_parser_parity():
    content = load("params.xml")
    new = parse_params(content)
    legacy = _legacy_parse_params(content)
    assert new.ids == legacy["ids"]
    assert new.warning == legacy["warning"]
    assert new.alert == legacy["alert"]
    assert new.coefs == legacy["coefs"]
    assert new.offsets == legacy["offsets"]


def test_value_applies_offset_then_coef():
    status = AtreaStatus(
        registers={"X": "100"},
        params=AtreaParams(offsets={"X": 10.0}, coefs={"X": 2.0}),
    )
    assert status.value("X") == 45.0


def test_value_missing_key_returns_none():
    assert AtreaStatus().value("nope") is None
