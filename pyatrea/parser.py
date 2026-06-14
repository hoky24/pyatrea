from __future__ import annotations
from xml.etree import ElementTree as ET
import demjson3  # type: ignore[import-untyped]
from .const import AtreaMode
from .exceptions import AtreaResponseError
from .models import AtreaParams, AtreaStatus


def parse_status(content: bytes) -> AtreaStatus:
    try:
        xmldoc = ET.fromstring(content)
        parent = xmldoc[0]  # /RD5WEB/RD5/ or /PCOWEB/PCO/
    except (ET.ParseError, IndexError) as err:
        raise AtreaResponseError("malformed status XML") from err
    registers: dict[str, str] = {}
    for data in list(parent):
        for child in list(data):
            if child.tag == "O" and "I" in child.attrib and "V" in child.attrib:
                registers[child.attrib["I"]] = child.attrib["V"]
    return AtreaStatus(registers=registers)


def parse_params(content: bytes) -> AtreaParams:
    params = AtreaParams()
    try:
        xmldoc = ET.fromstring(content)
    except ET.ParseError as err:
        raise AtreaResponseError("malformed params XML") from err
    for param in xmldoc.findall("params"):
        for child in list(param):
            if child.tag == "i" and "id" in child.attrib:
                cid = child.attrib["id"]
                params.ids.append(cid)
                flag = child.attrib.get("flag")
                if flag == "W":
                    params.warning.append(cid)
                elif flag == "A":
                    params.alert.append(cid)
                if "coef" in child.attrib:
                    params.coefs[cid] = float(child.attrib["coef"])
                if "offset" in child.attrib:
                    params.offsets[cid] = float(child.attrib["offset"])
    return params


def decompress(s: str) -> str:
    # Ported verbatim from the original pyatrea implementation.
    data = list(s)
    out = [data[0]]
    code = 512
    cache: dict[int, str] = {}
    old = curr = data[0]
    for char in data[1:]:
        cc = ord(char)
        if cc < 512:
            phrase = char
        elif cc in cache:
            phrase = cache[cc]
        else:
            phrase = old + curr
        out.append(phrase)
        curr = phrase[0]
        cache[code] = old + curr
        code += 1
        old = phrase
    return "".join(out)


def find_child(element: "ET.Element | None", id: str) -> "ET.Element | None":
    if element is None:
        return None
    for child in element:
        if "id" in child.attrib and child.attrib["id"].lstrip("0") == id:
            return child
    return None


def parse_config_dir(content: bytes) -> "ET.Element":
    try:
        return ET.fromstring(content)
    except ET.ParseError as err:
        raise AtreaResponseError("malformed cfgdir XML") from err


def parse_user_labels(content: bytes) -> dict[str, str]:
    labels: dict[str, str] = {}
    try:
        xmldoc = ET.fromstring(content)
    except ET.ParseError as err:
        raise AtreaResponseError("malformed texts XML") from err
    node = xmldoc.find("texts")
    if node is not None:
        for text in node:
            labels[text.attrib["id"]] = text.attrib["value"]
    return labels


def parse_translations(content: bytes) -> dict[str, dict]:
    result: dict[str, dict] = {"params": {}, "words": {}}
    try:
        xmldoc = ET.fromstring(content)
    except ET.ParseError as err:
        raise AtreaResponseError("malformed translations XML") from err
    nodes = [ET.fromstring(decompress(xmldoc.text or ""))] \
        if xmldoc.tag == "compress" else xmldoc.findall("texts")
    for node in nodes:
        for param in node.findall("params"):
            result["params"].update(demjson3.decode(param.text))
        for word in node.findall("words"):
            result["words"].update(demjson3.decode(word.text))
    return result


_FORCED_TITLE_TO_MODE = {
    "$off": AtreaMode.OFF, "$startUp": AtreaMode.STARTUP,
    "$runDown": AtreaMode.RUNDOWN, "D1": AtreaMode.D1, "D2": AtreaMode.D2,
    "D3": AtreaMode.D3, "D4": AtreaMode.D4, "IN1": AtreaMode.IN1,
    "IN2": AtreaMode.IN2, "$hpDefrosting": AtreaMode.HP_DEFROSTING,
    "$perVentCirc": AtreaMode.PERIODIC_VENTILATION,
}

_MODE_TITLE_TO_MODE = {
    "$perVentilation": AtreaMode.PERIODIC_VENTILATION,
    "$ventilation": AtreaMode.VENTILATION, "$circulation": AtreaMode.CIRCULATION,
    "$startUp": AtreaMode.STARTUP, "$runDown": AtreaMode.RUNDOWN,
    "$defrosting": AtreaMode.DEFROSTING, "$external": AtreaMode.EXTERNAL,
    "$hpDefrosting": AtreaMode.HP_DEFROSTING,
    "$nightBefCool": AtreaMode.NIGHT_PRECOOLING, "IN1": AtreaMode.IN1,
    "IN2": AtreaMode.IN2, "D1": AtreaMode.D1, "D2": AtreaMode.D2,
    "D3": AtreaMode.D3, "D4": AtreaMode.D4,
}


def parse_supported_forced_modes(content: bytes) -> dict[int, AtreaMode]:
    try:
        xmldoc = ET.fromstring(content)
    except ET.ParseError as err:
        raise AtreaResponseError("malformed userctrl XML") from err
    node = xmldoc.find("./layout/options/op[@id='ModeText']")
    result: dict[int, AtreaMode] = {}
    if node is None:
        return result
    for option in node:
        title = option.attrib.get("title")
        mode = _FORCED_TITLE_TO_MODE.get(title) if title else None
        if mode is not None:
            result[int(option.attrib["id"])] = mode
    return result


def parse_supported_modes(
    content: bytes,
) -> tuple[dict[AtreaMode, bool], dict[int, AtreaMode]]:
    writable: dict[AtreaMode, bool] = {m: False for m in AtreaMode}
    ids_to_modes: dict[int, AtreaMode] = {}
    try:
        xmldoc = ET.fromstring(content)
    except ET.ParseError as err:
        raise AtreaResponseError("malformed userctrl XML") from err
    node = xmldoc.find("./layout/options/op[@id='ModeEC']")
    if node is None:
        return writable, ids_to_modes
    for option in node:
        title = option.attrib.get("title")
        mode = _MODE_TITLE_TO_MODE.get(title) if title else None
        if mode is not None:
            oid = int(option.attrib["id"])
            ids_to_modes[oid] = mode
            if option.attrib.get("rw", "1") == "1":
                writable[mode] = True
    return writable, ids_to_modes
