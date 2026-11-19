#!/usr/bin/env python3
"""Pre-render the monochrome icon set to PNG masks.

QtSvg is not shipped with the base PyQt6 package on Ubuntu, so the app
uses white alpha masks and tints them at runtime with QPainter.
Run this script only when icons change:  python3 tools/build_icons.py
"""
from __future__ import annotations

import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "scanero" / "assets" / "icons"
OUT.mkdir(parents=True, exist_ok=True)

# 24x24 viewBox bodies. Everything is stroked in white unless `fill` is set.
ICONS: dict[str, str] = {
    "radar": '<circle cx="12" cy="12" r="9" opacity="0.35"/><circle cx="12" cy="12" r="5.4" opacity="0.6"/><path d="M12 12l6.4-6.4"/><circle cx="17.6" cy="6.4" r="1.2" fill="#fff" stroke="none"/>',
    "scan": '<path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3"/><path d="M4 12h16"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="2.6" fill="#fff" stroke="none"/>',
    "wifi": '<path d="M2.5 8.8a15 15 0 0 1 19 0"/><path d="M5.5 12.2a10.5 10.5 0 0 1 13 0"/><path d="M8.7 15.5a6 6 0 0 1 6.6 0"/><circle cx="12" cy="19" r="1.1" fill="#fff" stroke="none"/>',
    "settings": '<path d="M4 7h9M17.5 7H20M4 17h3.5M11 17h9"/><circle cx="15" cy="7" r="2.2"/><circle cx="9" cy="17" r="2.2"/>',
    "star": '<path d="M12 3.6l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/>',
    "star-fill": '<path d="M12 3.6l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z" fill="#fff"/>',
    "history": '<path d="M3 12a9 9 0 1 0 2.6-6.4"/><path d="M3 4v5h5"/><path d="M12 8v4.4l3 1.8"/>',
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.2 4.2"/>',
    "chevron-down": '<path d="M6 9.5l6 6 6-6"/>',
    "chevron-right": '<path d="M9.5 6l6 6-6 6"/>',
    "chevron-up": '<path d="M6 14.5l6-6 6 6"/>',
    "arrow-up-right": '<path d="M7 17L17 7M8 7h9v9"/>',
    "arrow-left": '<path d="M19 12H5M11 6l-6 6 6 6"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "minus": '<path d="M5 12h14"/>',
    "square": '<rect x="5.5" y="5.5" width="13" height="13" rx="2"/>',
    "restore": '<rect x="4.5" y="8.5" width="10.5" height="10.5" rx="1.6"/><path d="M8.5 5.5h9a1.5 1.5 0 0 1 1.5 1.5v9"/>',
    "monitor": '<rect x="3" y="4.5" width="18" height="12.5" rx="2"/><path d="M8.5 20h7M12 17v3"/>',
    "laptop": '<path d="M5 5.5h14v10H5z"/><path d="M2.5 19h19l-1.5-3.5H4z"/>',
    "server": '<rect x="3.5" y="4" width="17" height="6.5" rx="2"/><rect x="3.5" y="13.5" width="17" height="6.5" rx="2"/><path d="M7 7.2h.01M7 16.8h.01"/><path d="M11 7.2h6M11 16.8h6"/>',
    "printer": '<path d="M7 8V4.5h10V8"/><rect x="3.5" y="8" width="17" height="8" rx="2"/><path d="M7 13.5h10V20H7z"/><path d="M17.5 11h.01"/>',
    "router": '<rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 16.5h.01M11 16.5h.01"/><path d="M8 9.5a5.7 5.7 0 0 1 8 0M5.5 6.5a9.4 9.4 0 0 1 13 0"/>',
    "smartphone": '<rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M10.5 18.5h3"/>',
    "tablet": '<rect x="4" y="3" width="16" height="18" rx="2.5"/><path d="M11 18.2h2"/>',
    "tv": '<rect x="3" y="5.5" width="18" height="12" rx="2"/><path d="M8 21h8M9 2.5l3 3 3-3"/>',
    "camera": '<path d="M4 7.5h3l1.5-2h7L17 7.5h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1z"/><circle cx="12" cy="13" r="3.4"/>',
    "hard-drive": '<rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M3 12h18"/><path d="M7 16h.01M11 16h.01"/>',
    "cpu": '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9.5" y="9.5" width="5" height="5" rx="1"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
    "device": '<circle cx="12" cy="12" r="9"/><path d="M9.2 9.3a2.9 2.9 0 1 1 4.1 2.7c-.8.4-1.3 1-1.3 1.9v.4"/><path d="M12 17.6h.01"/>',
    "globe": '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.3 2.3 3.5 5.2 3.5 8.5S14.3 18.2 12 20.5C9.7 18.2 8.5 15.3 8.5 12S9.7 5.8 12 3.5z"/>',
    "folder": '<path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2v7.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',
    "terminal": '<rect x="3" y="4.5" width="18" height="15" rx="2.5"/><path d="M7.5 9l3 3-3 3M13 15h4"/>',
    "shield": '<path d="M12 3l7 2.8v5.4c0 4.4-2.9 7.7-7 9.8-4.1-2.1-7-5.4-7-9.8V5.8z"/><path d="M9 12l2.2 2.2L15.3 10"/>',
    "activity": '<path d="M3 12h4l2.5-6 4 12 2.5-6h5"/>',
    "download": '<path d="M12 4v11M7.5 10.5L12 15l4.5-4.5"/><path d="M4.5 19.5h15"/>',
    "upload": '<path d="M12 15V4M7.5 8.5L12 4l4.5 4.5"/><path d="M4.5 19.5h15"/>',
    "copy": '<rect x="8.5" y="8.5" width="11" height="11" rx="2"/><path d="M15.5 8.5v-3a2 2 0 0 0-2-2h-7a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h3"/>',
    "play": '<path d="M7 4.8l12 7.2-12 7.2z"/>',
    "pause": '<path d="M8.5 5v14M15.5 5v14"/>',
    "power": '<path d="M12 3v8"/><path d="M6.3 6.3a8 8 0 1 0 11.4 0"/>',
    "refresh": '<path d="M20 11a8 8 0 0 0-14.7-4L3.5 9.5"/><path d="M3.5 4.5v5h5"/><path d="M4 13a8 8 0 0 0 14.7 4l1.8-2.5"/><path d="M20.5 19.5v-5h-5"/>',
    "trash": '<path d="M4 7h16M9.5 7V4.5h5V7M6.5 7l.8 13h9.4l.8-13"/><path d="M10 11v5M14 11v5"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "check": '<path d="M4.5 12.5l5 5 10-11"/>',
    "alert": '<path d="M12 3.5L21 19H3z"/><path d="M12 9v4.5M12 16.8h.01"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 10.5V17M12 7.5h.01"/>',
    "external": '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 13.5v5a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 4 18.5v-11A1.5 1.5 0 0 1 5.5 6h5"/>',
    "target": '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1.2" fill="#fff" stroke="none"/>',
    "network": '<circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="12" cy="18" r="2.5"/><path d="M8.5 6h7M7.2 8.3l3.6 7.4M16.8 8.3l-3.6 7.4"/>',
    "ethernet": '<path d="M4 9.5h16v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z"/><path d="M8 9.5V5h8v4.5M8 14h.01M12 14h.01M16 14h.01"/>',
    "eye": '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
    "edit": '<path d="M14.5 5.5l4 4M4 20l4.5-1 10-10a2.8 2.8 0 0 0-4-4l-10 10z"/>',
    "map-pin": '<path d="M12 21s7-5.4 7-11a7 7 0 1 0-14 0c0 5.6 7 11 7 11z"/><circle cx="12" cy="10" r="2.6"/>',
    "database": '<ellipse cx="12" cy="5.5" rx="8" ry="3.2"/><path d="M4 5.5v6c0 1.8 3.6 3.2 8 3.2s8-1.4 8-3.2v-6"/><path d="M4 11.5v6c0 1.8 3.6 3.2 8 3.2s8-1.4 8-3.2v-6"/>',
    "lock": '<rect x="4.5" y="10.5" width="15" height="10" rx="2.5"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/><path d="M12 14.5v2"/>',
    "plug": '<path d="M9 3v5M15 3v5M6 8h12v3a6 6 0 0 1-12 0z"/><path d="M12 17v4"/>',
    "filter": '<path d="M4 5h16l-6.2 7.2v5.3L10.2 20v-7.8z"/>',
    "list": '<path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"/>',
    "radio": '<circle cx="12" cy="12" r="2" fill="#fff" stroke="none"/><path d="M7.8 7.8a6 6 0 0 0 0 8.4M16.2 7.8a6 6 0 0 1 0 8.4"/><path d="M5 5a10 10 0 0 0 0 14M19 5a10 10 0 0 1 0 14"/>',
    "signal": '<path d="M4 20v-3M9 20v-7M14 20V9M19 20V4"/>',
    "users": '<circle cx="9" cy="8" r="3.2"/><path d="M3.5 20a5.5 5.5 0 0 1 11 0"/><path d="M16 5.3a3.2 3.2 0 0 1 0 6.2M17.5 14.9A5.5 5.5 0 0 1 21 20"/>',
    "moon": '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5z"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M18.7 5.3l-1.4 1.4M6.7 17.3l-1.4 1.4"/>',
    "pin": '<path d="M9 4h6l-1 5 3 3v2H7v-2l3-3z"/><path d="M12 14v6"/>',
    "sparkles": '<path d="M12 3l1.7 4.3L18 9l-4.3 1.7L12 15l-1.7-4.3L6 9l4.3-1.7z"/><path d="M18.5 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z"/>',
}


def render(name: str, body: str) -> None:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="#ffffff" stroke-width="1.9" '
        'stroke-linecap="round" stroke-linejoin="round">'
        f"{body}</svg>"
    )
    target = OUT / f"{name}.png"
    proc = subprocess.run(
        ["convert", "-background", "none", "-resize", "96x96", "svg:-", "png32:-"],
        input=svg.encode(),
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"convert failed for {name}: {proc.stderr.decode()}")
    target.write_bytes(proc.stdout)
    print("  ", target.name)


def main() -> None:
    print(f"Rendering {len(ICONS)} icons to {OUT}")
    for name, body in ICONS.items():
        render(name, body)
    print("Done.")


if __name__ == "__main__":
    main()
