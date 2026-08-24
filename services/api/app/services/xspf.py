"""Safe parsing of user-supplied XSPF playlist documents."""
from lxml import etree


class XspfParseError(ValueError):
    """Raised when a document is not a playlist we are willing to parse."""


def _parser() -> etree.XMLParser:
    return etree.XMLParser(
        resolve_entities=False,
        load_dtd=False,
        no_network=True,
        huge_tree=False,
    )


def parse_titles(document: str) -> list[str]:
    """Return the `<title>` texts of an XSPF document.

    Entity resolution, DTD loading and network access are disabled, and documents carrying a
    doctype are rejected outright so that no entity definition can reach the parser.
    """
    try:
        root = etree.fromstring(document.encode("utf-8"), _parser())
    except etree.XMLSyntaxError as exc:
        raise XspfParseError("document is not well-formed XML") from exc

    if root.getroottree().docinfo.doctype:
        raise XspfParseError("doctype declarations are not allowed in playlist imports")

    titles = []
    for el in root.iter("{*}title"):
        if any(child.tag is etree.Entity for child in el):
            raise XspfParseError("entity references are not allowed in playlist imports")
        titles.append(el.text or "")
    return titles
