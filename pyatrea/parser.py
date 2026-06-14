from __future__ import annotations
from xml.etree import ElementTree as ET
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
