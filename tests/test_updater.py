"""Unit tests for GitHub update checks and package verification."""
from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scanero.core import updater


class FakeResponse:
    def __init__(self, data: bytes, headers: dict[str, str] | None = None) -> None:
        self._buffer = io.BytesIO(data)
        self.headers = headers or {}

    def read(self, size: int = -1) -> bytes:
        return self._buffer.read(size)

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_exc) -> bool:
        return False


def release_payload(version: str = "1.4.0") -> dict:
    asset = f"scanero-ip-scanner_{version}_all.deb"
    prefix = f"https://github.com/kostya4000/Scanero-IP-scanner/releases/download/v{version}"
    return {
        "tag_name": f"v{version}",
        "name": f"Scanero IP scanner {version}",
        "body": "## Новое\n- Проверка обновлений\n",
        "html_url": f"https://github.com/kostya4000/Scanero-IP-scanner/releases/tag/v{version}",
        "assets": [
            {"name": asset, "browser_download_url": f"{prefix}/{asset}"},
            {"name": f"{asset}.sha256", "browser_download_url": f"{prefix}/{asset}.sha256"},
        ],
    }


class VersionTests(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(updater.parse_version("v1.4.0"), (1, 4, 0))
        self.assertEqual(updater.parse_version("1.10.2"), (1, 10, 2))
        self.assertEqual(updater.parse_version("release-2.0"), (2, 0))
        self.assertEqual(updater.parse_version(""), (0,))

    def test_is_newer(self):
        self.assertTrue(updater.is_newer("1.4.0", "1.3.0"))
        self.assertTrue(updater.is_newer("v1.10.0", "1.9.9"))
        self.assertFalse(updater.is_newer("1.4.0", "1.4.0"))
        self.assertFalse(updater.is_newer("1.3.9", "1.4.0"))


class ReleaseTests(unittest.TestCase):
    def test_fetch_latest_release(self):
        payload = release_payload()

        def fake_urlopen(request, timeout=0):
            self.assertEqual(request.full_url, updater.API_URL)
            return FakeResponse(json.dumps(payload).encode("utf-8"))

        with patch("urllib.request.urlopen", fake_urlopen):
            release = updater.fetch_latest_release()

        self.assertEqual(release.version, "1.4.0")
        self.assertEqual(release.tag, "v1.4.0")
        self.assertTrue(release.deb_url.endswith("_all.deb"))
        self.assertTrue(release.sha_url.endswith("_all.deb.sha256"))
        self.assertIn("Проверка обновлений", release.notes)

    def test_download_and_verify_checksum(self):
        version = "1.4.0"
        package = b"fake deb package"
        checksum = hashlib.sha256(package).hexdigest()
        release = updater.ReleaseInfo(
            version=version,
            tag=f"v{version}",
            name="Scanero",
            notes="",
            page_url="https://github.com/kostya4000/Scanero-IP-scanner/releases/tag/v1.4.0",
            deb_url=(
                "https://github.com/kostya4000/Scanero-IP-scanner/releases/download/"
                f"v{version}/scanero-ip-scanner_{version}_all.deb"
            ),
            sha_url=(
                "https://github.com/kostya4000/Scanero-IP-scanner/releases/download/"
                f"v{version}/scanero-ip-scanner_{version}_all.deb.sha256"
            ),
        )

        def fake_urlopen(request, timeout=0):
            if request.full_url.endswith(".sha256"):
                return FakeResponse(f"{checksum}  package.deb\n".encode("utf-8"))
            return FakeResponse(package, {"Content-Length": str(len(package))})

        progress: list[int] = []
        with tempfile.TemporaryDirectory() as directory:
            with patch("urllib.request.urlopen", fake_urlopen):
                path = updater.download_release(
                    release,
                    destination=directory,
                    progress=progress.append,
                )
            self.assertEqual(path.read_bytes(), package)
            self.assertEqual(progress[-1], 100)

    def test_download_rejects_bad_checksum(self):
        release = updater.ReleaseInfo(
            version="1.4.0",
            tag="v1.4.0",
            name="Scanero",
            notes="",
            page_url="https://github.com/kostya4000/Scanero-IP-scanner/releases/tag/v1.4.0",
            deb_url=(
                "https://github.com/kostya4000/Scanero-IP-scanner/releases/download/"
                "v1.4.0/scanero-ip-scanner_1.4.0_all.deb"
            ),
            sha_url=(
                "https://github.com/kostya4000/Scanero-IP-scanner/releases/download/"
                "v1.4.0/scanero-ip-scanner_1.4.0_all.deb.sha256"
            ),
        )

        def fake_urlopen(request, timeout=0):
            if request.full_url.endswith(".sha256"):
                return FakeResponse(("0" * 64).encode("utf-8"))
            return FakeResponse(b"package", {"Content-Length": "7"})

        with tempfile.TemporaryDirectory() as directory:
            with patch("urllib.request.urlopen", fake_urlopen):
                with self.assertRaises(updater.UpdateError):
                    updater.download_release(release, destination=directory)
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
