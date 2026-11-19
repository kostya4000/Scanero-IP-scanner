# Changelog

## 1.1.1 — 2026-11-19

- Service rows in the main list now have a visible gradient **Открыть** button
  (same style as **Сканировать**) that works with one click.
- Double-clicking that button no longer opens the resource twice.
- Focus helper stops after the first successful activation, so closing a
  terminal no longer makes focus jump back to it.

## 1.1.0 — 2026-11-19

- Added light, dark and system themes with live switching in Settings → Appearance.
- GitHub links in the sidebar, Settings → About and the About dialog.
- Better device names: mDNS browse, SSDP/UPnP, TLS certificate names and SNMP sysName.
- Fixed inspector not switching when another device is selected.
- Made the inspector **Open** button primary and responsive to a single click.
- External windows (browser, file manager, RDP, terminal) are raised and focused.
- Window focus work runs asynchronously, so the application no longer freezes.
- Fixed the About dialog clipping its description.
- Improved router/printer classification; version is now centralized.

## 1.0.0 — 2026-11-19

- Initial release: Scanero IP scanner / Scanero IP Сканер.
- Multi-threaded network discovery, MAC/vendor lookup, NetBIOS/DNS/mDNS,
  service scanning, SSH/RDP/SMB/HTTP actions, Wake-on-LAN, remote shutdown,
  favorites, history and CSV/JSON/HTML export.
