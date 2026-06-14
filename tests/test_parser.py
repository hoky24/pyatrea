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


def test_user_labels_parity():
    content = load("texts.xml")
    xmldoc = ET.fromstring(content)
    legacy = {}
    node = xmldoc.find("texts")
    if node is not None:
        for t in node:
            legacy[t.attrib["id"]] = t.attrib["value"]
    from pyatrea.parser import parse_user_labels
    assert parse_user_labels(content) == legacy


def test_config_dir_returns_element():
    from pyatrea.parser import parse_config_dir
    el = parse_config_dir(load("cfgdir.xml"))
    assert el is not None


def test_find_child_returns_none_when_absent():
    from pyatrea.parser import parse_config_dir, find_child
    el = parse_config_dir(load("cfgdir.xml"))
    assert find_child(el, "this-id-does-not-exist-99999") is None


def test_translations_parser_smoke():
    from pyatrea.parser import parse_translations
    result = parse_translations(load("texts_2.xml"))
    assert set(result.keys()) == {"params", "words"}
    assert isinstance(result["params"], dict)


def test_forced_modes_parser_returns_dict():
    from pyatrea.parser import parse_supported_forced_modes
    from pyatrea.const import AtreaMode
    result = parse_supported_forced_modes(load("userctrl.xml"))
    assert isinstance(result, dict)
    assert all(isinstance(v, AtreaMode) for v in result.values())


def test_supported_modes_parser_returns_writable_map():
    from pyatrea.parser import parse_supported_modes
    modes, ids_to_modes, modes_to_ids = parse_supported_modes(load("userctrl.xml"))
    assert isinstance(modes, dict)
    assert isinstance(ids_to_modes, dict)
    assert isinstance(modes_to_ids, dict)


def test_parse_supported_modes_returns_modes_to_ids():
    from pyatrea.parser import parse_supported_modes
    writable, ids_to_modes, modes_to_ids = parse_supported_modes(load("userctrl.xml"))
    # modes_to_ids is the inverse of ids_to_modes
    assert all(modes_to_ids[m] == i for i, m in ids_to_modes.items())


def test_supported_modes_from_status_bitmask_parity():
    """RD5 unit derives supported modes from the I12004 bitmask, not userctrl."""
    from pyatrea.parser import parse_status, supported_modes_from_status
    from pyatrea.const import AtreaMode
    status = parse_status(load("status.xml"))
    result = supported_modes_from_status(status)
    assert result is not None  # this fixture HAS I12004 + H11700

    # legacy reference computation
    binary = "{0:08b}".format(int(status.registers["I12004"]))
    h11700 = int(status.registers["H11700"])
    expected = {}
    for i in range(8):
        if (i == 3 or i == 4) and h11700 == 0:
            expected[AtreaMode(i)] = False
        else:
            expected[AtreaMode(i)] = int(binary[7 - i]) != 0
    # result must agree with legacy for the first 8 modes
    for i in range(8):
        assert result[AtreaMode(i)] == expected[AtreaMode(i)]


def test_supported_modes_from_status_returns_none_without_registers():
    from pyatrea.parser import supported_modes_from_status
    from pyatrea.models import AtreaStatus
    assert supported_modes_from_status(AtreaStatus(registers={})) is None


def test_translate_resolves_and_unquotes():
    from pyatrea.parser import translate
    t = {"params": {"P1": {"t": "Hello%20World"}}, "words": {}}
    assert translate(t, "P1") == "Hello World"
    assert translate(t, "missing") == "missing"
