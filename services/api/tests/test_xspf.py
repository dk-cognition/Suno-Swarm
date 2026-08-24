import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.xspf import XspfParseError, parse_titles  # noqa: E402


def test_parses_titles():
    document = """<?xml version="1.0"?>
    <playlist xmlns="http://xspf.org/ns/0/">
      <title>Late night drive</title>
      <trackList><track><title>Neon</title></track></trackList>
    </playlist>"""
    assert parse_titles(document) == ["Late night drive", "Neon"]


def test_rejects_doctype_with_external_entity(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("top-secret")
    document = f"""<?xml version="1.0"?>
    <!DOCTYPE playlist [<!ENTITY xxe SYSTEM "file://{secret}">]>
    <playlist xmlns="http://xspf.org/ns/0/"><title>&xxe;</title></playlist>"""
    with pytest.raises(XspfParseError):
        parse_titles(document)


def test_rejects_billion_laughs():
    document = """<?xml version="1.0"?>
    <!DOCTYPE playlist [
      <!ENTITY a "aaaaaaaaaa">
      <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
      <!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">
    ]>
    <playlist xmlns="http://xspf.org/ns/0/"><title>&c;</title></playlist>"""
    with pytest.raises(XspfParseError):
        parse_titles(document)


def test_rejects_malformed_document():
    with pytest.raises(XspfParseError):
        parse_titles("<playlist>")
