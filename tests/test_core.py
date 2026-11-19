"""Basic unit tests for the scanner core (no network required)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from scanero.core.exporter import export
from scanero.core.models import Device, Favorite, Service, ip_to_int
from scanero.core.netinfo import describe_targets, parse_targets
from scanero.core.oui import lookup, normalize_mac
from scanero.core.storage import FavoritesStore, HistoryEntry, HistoryStore, Settings


class RangeTests(unittest.TestCase):
    def test_cidr(self):
        targets = parse_targets("192.168.10.0/30")
        self.assertEqual([str(t) for t in targets], ["192.168.10.1", "192.168.10.2"])

    def test_short_range(self):
        targets = parse_targets("192.168.1.10-13")
        self.assertEqual(len(targets), 4)
        self.assertEqual(str(targets[0]), "192.168.1.10")
        self.assertEqual(str(targets[-1]), "192.168.1.13")

    def test_full_range_and_list(self):
        targets = parse_targets("192.168.1.250-192.168.2.2, 192.168.1.10")
        self.assertEqual(len(targets), 10)
        self.assertEqual(str(targets[-1]), "192.168.2.2")

    def test_wildcard(self):
        targets = parse_targets("10.0.5.*")
        self.assertEqual(len(targets), 254)
        self.assertEqual(str(targets[0]), "10.0.5.1")

    def test_invalid(self):
        with self.assertRaises(ValueError):
            parse_targets("not-an-ip")
        with self.assertRaises(ValueError):
            parse_targets("10.0.0.20-10.0.0.10")

    def test_description(self):
        targets = parse_targets("10.0.0.10-12")
        self.assertIn("10.0.0.10", describe_targets(targets))
        self.assertIn("–", describe_targets(targets))
        self.assertIn("3 адреса", describe_targets(parse_targets("10.0.0.1,10.0.0.3,10.0.0.9")))


class ModelTests(unittest.TestCase):
    def test_mac(self):
        self.assertEqual(normalize_mac("00-17-c8-35-ee-f6"), "00:17:C8:35:EE:F6")
        self.assertEqual(normalize_mac("oops"), "")

    def test_oui(self):
        self.assertIn("KYOCERA", lookup("00:17:C8:35:EE:F6"))
        self.assertTrue(lookup("00:15:5D:02:4B:00"))

    def test_service_url(self):
        self.assertEqual(Service(80).url("10.0.0.1"), "http://10.0.0.1/")
        self.assertEqual(Service(445).url("10.0.0.1"), "smb://10.0.0.1/")
        self.assertEqual(Service(139).url("10.0.0.1"), "smb://10.0.0.1/")
        self.assertEqual(Service(3389).url("10.0.0.1"), "rdp://10.0.0.1")
        self.assertEqual(Service(8080).url("10.0.0.1"), "http://10.0.0.1:8080/")

    def test_device_roundtrip(self):
        device = Device(
            ip="10.0.0.2",
            name="nas",
            mac="00:11:32:78:9A:BC",
            vendor="Synology",
            status="online",
            services=[Service(22), Service(445)],
            kind="nas",
        )
        restored = Device.from_dict(device.to_dict())
        self.assertEqual(restored.ip, device.ip)
        self.assertEqual(restored.name, "nas")
        self.assertEqual(len(restored.services), 2)
        self.assertGreater(ip_to_int("10.0.0.10"), ip_to_int("10.0.0.9"))


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        self.device = Device(
            ip="10.0.0.5",
            name="printer",
            mac="00:17:C8:35:EE:F6",
            vendor="KYOCERA",
            status="online",
            services=[Service(80), Service(631)],
            kind="printer",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_csv(self):
        path = self.dir / "report.csv"
        export(path, [self.device], "csv")
        text = path.read_text(encoding="utf-8-sig")
        self.assertIn("printer", text)
        self.assertIn("HTTP (80)", text)

    def test_json(self):
        path = self.dir / "report.json"
        export(path, [self.device], "json", {"range": "10.0.0.0/24"})
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["devices"][0]["ip"], "10.0.0.5")
        self.assertEqual(data["meta"]["range"], "10.0.0.0/24")

    def test_html(self):
        path = self.dir / "report.html"
        export(path, [self.device], "html")
        text = path.read_text(encoding="utf-8")
        self.assertIn("<!doctype html>", text)
        self.assertIn("printer", text)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = self.temp.name

    def tearDown(self):
        if self.old is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = self.old
        self.temp.cleanup()

    def test_settings(self):
        settings = Settings()
        settings.set("threads", 128)
        settings.set("ports", "80, 443, 445")
        self.assertEqual(settings.ports, [80, 443, 445])
        reloaded = Settings()
        self.assertEqual(reloaded.get("threads"), 128)

    def test_favorites(self):
        store = FavoritesStore()
        device = Device(ip="10.0.0.9", mac="00:11:32:78:9A:BC", name="nas", kind="nas")
        store.add(device)
        self.assertTrue(store.contains(device))
        reloaded = FavoritesStore()
        self.assertTrue(reloaded.contains(ip="10.0.0.9"))
        self.assertEqual(reloaded.items[0].kind, "nas")
        reloaded.remove(ip="10.0.0.9")
        self.assertFalse(reloaded.contains(ip="10.0.0.9"))

    def test_history(self):
        store = HistoryStore(limit=3)
        for i in range(5):
            store.add(HistoryEntry(
                id=str(i), timestamp=float(i), range_expr="10.0.0.0/24",
                target_count=254, online=i, offline=254 - i, services=i * 2,
                duration=1.0, devices=[],
            ))
        self.assertEqual(len(store.items), 3)
        self.assertEqual(store.items[0].online, 4)
        reloaded = HistoryStore(limit=3)
        self.assertEqual(len(reloaded.items), 3)


if __name__ == "__main__":
    unittest.main()


class DiscoveryTests(unittest.TestCase):
    def test_avahi_escaping(self):
        from scanero.core.discovery import _clean_name, _split_avahi

        line = "=;eth0;IPv4;Living\\032Room\\032TV;_airplay._tcp;local;tv.local;192.168.1.5;7000;"
        fields = _split_avahi(line)
        self.assertEqual(_clean_name(fields[3]), "Living Room TV")

    def test_snmp_oid_encoding(self):
        from scanero.core.probe import _ber_oid

        self.assertEqual(_ber_oid("1.3.6.1.2.1.1.5.0").hex(), "2b06010201010500")
