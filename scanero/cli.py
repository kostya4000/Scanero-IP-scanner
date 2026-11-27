"""Command line interface: useful for cron jobs and quick checks."""
from __future__ import annotations

import argparse
import sys
import time

from .core.exporter import export
from .core.models import STATUS_ONLINE
from .core.netinfo import best_interface, list_interfaces, parse_targets, _plural
from .core.scanner import DEFAULT_PORTS, ScanOptions, scan_network
from . import __version__
from .core.storage import Settings
from .i18n import set_language, tr, translate_text


def main(argv: list[str] | None = None) -> int:
    settings = Settings()
    set_language(settings.get("language", "system"))
    parser = argparse.ArgumentParser(prog="scanero", description=tr("Scanero IP scanner — сканер локальной сети"))
    parser.add_argument("-r", "--range", dest="range_expr", help=tr("диапазон IP (например, 192.168.1.0/24)"))
    parser.add_argument("-i", "--interface", help=tr("сканировать подсеть интерфейса"))
    parser.add_argument("-p", "--ports", help=tr("порты через запятую"))
    parser.add_argument("--no-services", action="store_true", help=tr("не сканировать порты"))
    parser.add_argument("--no-names", action="store_true", help=tr("не определять имена"))
    parser.add_argument("--threads", type=int, default=settings.get("threads", 96))
    parser.add_argument("--timeout", type=float, default=settings.get("ping_timeout", 1.0))
    parser.add_argument("--json", metavar="FILE", help=tr("сохранить отчёт JSON"))
    parser.add_argument("--csv", metavar="FILE", help=tr("сохранить отчёт CSV"))
    parser.add_argument("--html", metavar="FILE", help=tr("сохранить отчёт HTML"))
    parser.add_argument("--all", action="store_true", help=tr("показать и выключенные адреса"))
    parser.add_argument("--version", action="version", version=f"Scanero IP scanner {__version__}")
    args = parser.parse_args(argv)

    ifaces = list_interfaces()
    if args.interface:
        iface = next((i for i in ifaces if i.name == args.interface), None)
        if not iface:
            print(tr("Интерфейс не найден: {name}", name=args.interface), file=sys.stderr)
            return 2
        expr = iface.subnet
    elif args.range_expr:
        expr = args.range_expr
    else:
        iface = best_interface(ifaces)
        if not iface:
            print(tr("Не удалось определить локальную сеть. Укажите --range."), file=sys.stderr)
            return 2
        expr = iface.default_range

    try:
        targets = parse_targets(expr, ifaces)
    except ValueError as exc:
        print(tr("Ошибка диапазона: {exc}", exc=exc), file=sys.stderr)
        return 2

    ports = DEFAULT_PORTS
    if args.ports:
        parsed = []
        for token in args.ports.split(","):
            try:
                parsed.append(int(token.strip()))
            except ValueError:
                pass
        if parsed:
            ports = parsed

    options = ScanOptions(
        threads=args.threads,
        ping_timeout=args.timeout,
        scan_services=not args.no_services,
        resolve_names=not args.no_names,
        ports=ports,
        interfaces=ifaces,
    )

    print(f"Scanero IP scanner · {expr} · {len(targets)} {_plural(len(targets), 'адрес', 'адреса', 'адресов')}", flush=True)
    started = time.time()

    def on_event(kind: str, payload: object) -> None:
        if kind == "progress" and isinstance(payload, dict):
            stage = tr("поиск") if payload.get("stage") == "discover" else tr("сервисы")
            pct = int(100 * payload.get("done", 0) / max(1, payload.get("total", 1)))
            print(f"\r  {stage}: {payload.get('done', 0)}/{payload.get('total', 1)} ({pct}%)   ", end="", flush=True)
        elif kind in ("found", "updated"):
            device = payload
            print(
                f"\r  + {device.ip:<15} {device.name[:24]:<25} {device.mac:<18} {device.vendor[:28]}"
                + " " * 12
            )

    result = scan_network(targets, options, expr, on_event)
    print("\r" + " " * 120 + "\r", end="")
    print(translate_text(
        f"Готово за {result.duration:.1f} с · в сети {result.online} · "
        f"не отвечают {result.offline} · "
        f"{result.services} {_plural(result.services, 'сервис', 'сервиса', 'сервисов')}"
    ))

    rows = [d for d in result.devices if d.status == STATUS_ONLINE or args.all]
    for device in rows:
        services = ", ".join(f"{s.display_name}:{s.port}" for s in device.services)
        print(
            f"  {device.ip:<15} {device.status_label:<10} {(device.name or '—')[:28]:<30} "
            f"{device.mac or '—':<18} {(device.vendor or '—')[:30]:<32} {services}"
        )

    meta = {
        "range": expr,
        "duration": result.duration,
        "online": result.online,
        "offline": result.offline,
        "services": result.services,
    }
    for fmt, path in (("json", args.json), ("csv", args.csv), ("html", args.html)):
        if path:
            export(path, result.devices, fmt, meta)
            print(tr("Сохранено: {path}", path=path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
