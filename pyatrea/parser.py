from __future__ import annotations
from xml.etree import ElementTree as ET
from .exceptions import AtreaResponseError
from .models import AtreaStatus


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
