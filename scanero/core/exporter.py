"""CSV / JSON / HTML report export."""
from __future__ import annotations

import csv
import html
import json
import time
from pathlib import Path
from typing import Iterable

from ..i18n import current_language, tr
from .models import Device, STATUS_ONLINE, kind_label


HEADERS = ["Статус", "Имя", "IP-адрес", "MAC-адрес", "Производитель", "Тип", "ОС", "Сервисы", "NetBIOS", "Рабочая группа"]


def _online(devices: Iterable[Device]) -> list[Device]:
    return [d for d in devices if d.status == STATUS_ONLINE]


def _service_text(device: Device) -> str:
    return ", ".join(f"{s.display_name} ({s.port})" for s in device.services)


def export_csv(path: str | Path, devices: Iterable[Device]) -> None:
    path = Path(path)
    rows = _online(devices)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=";", lineterminator="\r\n")
        writer.writerow([tr(header) for header in HEADERS])
        for d in rows:
            writer.writerow([
                d.status_label,
                d.name or d.hostname,
                d.ip,
                d.mac,
                d.vendor,
                kind_label(d.kind),
                d.os_label,
                _service_text(d),
                d.netbios,
                d.workgroup,
            ])


def export_json(path: str | Path, devices: Iterable[Device], meta: dict | None = None) -> None:
    path = Path(path)
    rows = _online(devices)
    payload = {
        "application": "Scanero IP scanner",
        "version": 1,
        "exported": time.time(),
        "exported_label": time.strftime("%d.%m.%Y %H:%M"),
        "meta": meta or {},
        "devices": [d.to_dict() for d in rows],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def export_html(path: str | Path, devices: Iterable[Device], meta: dict | None = None) -> None:
    path = Path(path)
    rows = _online(devices)
    meta = meta or {}
    services = sum(len(d.services) for d in rows)
    generated = time.strftime("%d.%m.%Y, %H:%M")
    range_expr = html.escape(str(meta.get("range", "")))
    duration = meta.get("duration", 0) or 0

    def esc(value: object) -> str:
        return html.escape("" if value is None else str(value))

    body_rows = []
    for d in rows:
        chips = "".join(
            f'<span class="chip">{esc(s.display_name)} <b>{s.port}</b></span>' for s in d.services
        ) or '<span class="dim">—</span>'
        body_rows.append(f"""
        <tr>
          <td><span class="dot"></span></td>
          <td><div class="name">{esc(d.name or d.hostname) or f'<span class="dim">{esc(tr("Без имени"))}</span>'}</div>
              <div class="sub">{esc(d.vendor) or esc(kind_label(d.kind))}</div></td>
          <td class="mono">{esc(d.ip)}</td>
          <td class="mono dim">{esc(d.mac) or '—'}</td>
          <td>{esc(d.vendor) or '—'}</td>
          <td>{esc(d.os_label) or '—'}</td>
          <td>{chips}</td>
        </tr>""")
    rows_html = "\n".join(body_rows) if body_rows else (
        f'<tr><td colspan="7" class="empty">{esc(tr("Устройства не найдены"))}</td></tr>'
    )

    doc = f"""<!doctype html>
<html lang="{current_language()}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Scanero IP scanner · {esc(tr("Отчёт о сканировании"))}</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 48px 28px; background: #070b14; color: #e8eef9;
         font-family: Inter, "Segoe UI", system-ui, sans-serif; }}
  .wrap {{ max-width: 1180px; margin: 0 auto; }}
  .brand {{ display:flex; align-items:center; gap:12px; margin-bottom: 34px; }}
  .logo {{ width: 42px; height: 42px; border-radius: 13px;
           background: linear-gradient(135deg,#22d3ee,#7c8cff); position:relative; }}
  .logo:after {{ content:""; position:absolute; inset:11px; border:2px solid rgba(7,14,24,.75);
                 border-radius:50%; }}
  h1 {{ font-size: 26px; margin: 0; letter-spacing: -0.02em; }}
  .muted {{ color: #8fa1b8; }}
  .meta {{ margin: 4px 0 0; font-size: 13px; }}
  .cards {{ display:grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 28px 0; }}
  .card {{ background: #0e1524; border: 1px solid #1c2940; border-radius: 16px; padding: 18px 20px; }}
  .value {{ font-size: 28px; font-weight: 700; letter-spacing: -0.03em; }}
  .label {{ font-size: 11px; text-transform: uppercase; letter-spacing: .12em; color:#8fa1b8; margin-top: 6px; }}
  .green {{ color:#3ddc97; }} .indigo {{ color:#8b9cff; }} .cyan {{ color:#22d3ee; }} .red {{ color:#ff6b7a; }}
  table {{ width:100%; border-collapse: separate; border-spacing: 0; background:#0e1524;
           border:1px solid #1c2940; border-radius: 16px; overflow:hidden; }}
  th {{ text-align:left; font-size:10.5px; letter-spacing:.1em; text-transform:uppercase; color:#7d90a8;
        padding: 14px 16px; border-bottom:1px solid #1c2940; background:#0b1220; }}
  td {{ padding: 13px 16px; border-bottom:1px solid #151f31; font-size: 13px; vertical-align: middle; }}
  tr:last-child td {{ border-bottom:none; }}
  tr:hover td {{ background:#101a2c; }}
  .name {{ font-weight:600; }}
  .sub {{ color:#7d90a8; font-size:11px; margin-top:3px; }}
  .mono {{ font-family:"JetBrains Mono", ui-monospace, monospace; font-size:12px; }}
  .dim {{ color:#75879e; }}
  .dot {{ display:inline-block; width:8px; height:8px; border-radius:50%; background:#3ddc97;
          box-shadow:0 0 10px rgba(61,220,151,.7); }}
  .chip {{ display:inline-block; padding:3px 7px; margin:2px 3px 2px 0; border-radius:7px;
           background:rgba(124,140,255,.1); border:1px solid rgba(124,140,255,.22); font-size:10.5px; }}
  .chip b {{ color:#8b9cff; font-weight:600; }}
  .empty {{ text-align:center; padding:40px; color:#7d90a8; }}
  footer {{ margin-top: 26px; color:#5c6c82; font-size:11.5px; text-align:center; }}
  @media print {{ body {{ background:#fff; color:#111; }} .card, table {{ background:#fff; }} }}
</style>
</head>
<body>
<div class="wrap">
  <div class="brand">
    <div class="logo"></div>
    <div>
      <h1>Scanero IP scanner</h1>
      <p class="meta muted">{esc(tr("Отчёт о сканировании"))} · {generated}</p>
    </div>
  </div>
  <div class="cards">
    <div class="card"><div class="value green">{len(rows)}</div><div class="label">{esc(tr("Устройств в сети"))}</div></div>
    <div class="card"><div class="value indigo">{services}</div><div class="label">{esc(tr("Открытых сервисов"))}</div></div>
    <div class="card"><div class="value cyan">{esc(range_expr) or '—'}</div><div class="label">{esc(tr("Диапазон сканирования"))}</div></div>
    <div class="card"><div class="value red">{duration:.1f} {"s" if current_language() == "en" else "с"}</div><div class="label">{esc(tr("Длительность"))}</div></div>
  </div>
  <table>
    <thead><tr><th></th><th>{esc(tr("Устройство"))}</th><th>{esc(tr("IP-адрес"))}</th><th>MAC</th><th>{esc(tr("Производитель"))}</th><th>{esc(tr("ОС"))}</th><th>{esc(tr("Сервисы"))}</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
  <footer>{esc(tr("Создано в Scanero IP scanner · сканер локальной сети для Ubuntu"))}</footer>
</div>
</body>
</html>"""
    path.write_text(doc, encoding="utf-8")


def export(path: str | Path, devices: Iterable[Device], fmt: str, meta: dict | None = None) -> None:
    fmt = fmt.lower()
    if fmt == "csv":
        export_csv(path, devices)
    elif fmt == "json":
        export_json(path, devices, meta)
    elif fmt in ("html", "htm"):
        export_html(path, devices, meta)
    else:
        raise ValueError(tr("Неизвестный формат: {fmt}", fmt=fmt))
