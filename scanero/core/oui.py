"""MAC address vendor lookup using a bundled IEEE OUI database."""
from __future__ import annotations

import gzip
import json
import re
from functools import lru_cache
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"

_MAC_CLEAN = re.compile(r"[^0-9A-F]")

# Small fallback used if the bundled database is unavailable.
_FALLBACK = {
    "000C29": "VMware, Inc.",
    "005056": "VMware, Inc.",
    "080027": "Oracle VirtualBox",
    "525400": "QEMU virtual NIC",
    "00155D": "Microsoft Corporation",
    "3C5282": "Hewlett Packard",
    "B827EB": "Raspberry Pi Foundation",
    "DCA632": "Raspberry Pi Trading",
    "001A2B": "Cisco Systems",
    "001B63": "Apple, Inc.",
    "3C22FB": "Apple, Inc.",
    "F01898": "Apple, Inc.",
    "001DD8": "Microsoft Corporation",
    "002590": "Super Micro Computer",
    "AC1F6B": "Super Micro Computer",
    "001C42": "Parallels, Inc.",
    "00005E": "IANA",
}


@lru_cache(maxsize=1)
def _database() -> dict[str, str]:
    path = ASSETS / "oui.json.gz"
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            data = json.load(fh)
        entries = data.get("entries", {})
        if isinstance(entries, dict) and entries:
            return entries
    except Exception:
        pass
    return dict(_FALLBACK)


def normalize_mac(mac: str) -> str:
    raw = _MAC_CLEAN.sub("", (mac or "").upper())
    if len(raw) != 12:
        return ""
    return ":".join(raw[i:i + 2] for i in range(0, 12, 2))


def is_random_mac(mac: str) -> bool:
    raw = _MAC_CLEAN.sub("", (mac or "").upper())
    if len(raw) < 2:
        return False
    try:
        first = int(raw[:2], 16)
    except ValueError:
        return False
    return bool(first & 0x02)


def lookup(mac: str) -> str:
    """Return the organization for a MAC address, or an empty string."""
    raw = _MAC_CLEAN.sub("", (mac or "").upper())
    if len(raw) != 12:
        return ""
    if is_random_mac(mac):
        return "Локальный адрес"
    vendor = _database().get(raw[:6], "")
    return _clean_vendor(vendor)


def _clean_vendor(vendor: str) -> str:
    vendor = re.sub(r"\s+", " ", vendor or "").strip()
    if not vendor:
        return ""
    # A few extremely common, overly long legal names read better shortened.
    replacements = {
        "Hewlett Packard Enterprise": "Hewlett Packard Enterprise",
        "Hewlett Packard": "Hewlett Packard",
        "Shenzhen ...": "Shenzhen",
    }
    return replacements.get(vendor, vendor)


def short_vendor(vendor: str, limit: int = 34) -> str:
    if len(vendor) <= limit:
        return vendor
    return vendor[: limit - 1].rstrip() + "…"


def vendor_hint(vendor: str) -> str:
    return (vendor or "").lower()
