"""GitHub release checks and update downloads."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .. import REPO_URL, __version__

API_URL = "https://api.github.com/repos/kostya4000/Scanero-IP-scanner/releases/latest"
_DOWNLOAD_PREFIX = "/kostya4000/Scanero-IP-scanner/releases/download/"
_ALLOWED_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "github-releases.githubusercontent.com",
}
_USER_AGENT = f"Scanero-IP-scanner/{__version__}"


class UpdateError(RuntimeError):
    """Raised when the update information cannot be fetched or verified."""


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    tag: str
    name: str
    notes: str
    page_url: str
    deb_url: str = ""
    sha_url: str = ""


def parse_version(value: str) -> tuple[int, ...]:
    """Turn a tag such as ``v1.4.0`` into ``(1, 4, 0)``."""
    numbers = re.findall(r"\d+", str(value or ""))
    return tuple(int(part) for part in numbers[:4]) if numbers else (0,)


def is_newer(remote: str, current: str = __version__) -> bool:
    remote_parts = parse_version(remote)
    current_parts = parse_version(current)
    size = max(len(remote_parts), len(current_parts))
    return remote_parts + (0,) * (size - len(remote_parts)) > current_parts + (0,) * (size - len(current_parts))


def _request(url: str, *, timeout: float) -> urllib.request.Request:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise UpdateError("Only HTTPS update URLs are allowed")
    return urllib.request.Request(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )


def fetch_latest_release(timeout: float = 7.0) -> ReleaseInfo:
    """Fetch the latest stable release from GitHub."""
    try:
        with urllib.request.urlopen(_request(API_URL, timeout=timeout), timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise UpdateError("No releases found") from exc
        raise UpdateError(f"GitHub API error: HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UpdateError(str(exc)) from exc
    except (ValueError, UnicodeDecodeError) as exc:
        raise UpdateError("Invalid GitHub response") from exc

    tag = str(payload.get("tag_name") or "").strip()
    version = ".".join(str(part) for part in parse_version(tag))
    page_url = str(payload.get("html_url") or REPO_URL)
    if not tag or not version:
        raise UpdateError("GitHub response has no version")

    deb_url = ""
    sha_url = ""
    for asset in payload.get("assets") or []:
        name = str(asset.get("name") or "")
        url = str(asset.get("browser_download_url") or "")
        if not url:
            continue
        if name.startswith("scanero-ip-scanner_") and name.endswith("_all.deb"):
            deb_url = url
        elif name.endswith("_all.deb.sha256"):
            sha_url = url

    return ReleaseInfo(
        version=version,
        tag=tag,
        name=str(payload.get("name") or tag),
        notes=str(payload.get("body") or ""),
        page_url=page_url,
        deb_url=deb_url,
        sha_url=sha_url,
    )


def _validate_download_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
        raise UpdateError("Unexpected update download URL")
    if parsed.hostname == "github.com" and not parsed.path.startswith(_DOWNLOAD_PREFIX):
        raise UpdateError("Unexpected update download URL")


def _fetch_text(url: str, *, timeout: float) -> str:
    with urllib.request.urlopen(_request(url, timeout=timeout), timeout=timeout) as response:
        return response.read(4096).decode("utf-8", errors="replace")


def _expected_sha256(value: str) -> str:
    match = re.search(r"\b([a-fA-F0-9]{64})\b", value)
    return match.group(1).lower() if match else ""


def download_release(
    release: ReleaseInfo,
    *,
    timeout: float = 15.0,
    progress: Callable[[int], None] | None = None,
    destination: str | Path | None = None,
) -> Path:
    """Download the release .deb and verify its SHA-256 checksum."""
    if not release.deb_url:
        raise UpdateError("The release has no Debian package")

    _validate_download_url(release.deb_url)
    if release.sha_url:
        _validate_download_url(release.sha_url)

    filename = Path(urllib.parse.unquote(urllib.parse.urlparse(release.deb_url).path)).name
    if not filename.endswith(".deb"):
        raise UpdateError("The release asset is not a .deb package")

    target_dir = Path(destination) if destination else Path(tempfile.mkdtemp(prefix="scanero-update-"))
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename

    try:
        with urllib.request.urlopen(_request(release.deb_url, timeout=timeout), timeout=timeout) as response:
            total = int(response.headers.get("Content-Length") or 0)
            downloaded = 0
            last_percent = -1
            with open(target, "wb") as handle:
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if progress and total > 0:
                        percent = min(100, int(downloaded * 100 / total))
                        if percent != last_percent:
                            last_percent = percent
                            progress(percent)

        if release.sha_url:
            expected = _expected_sha256(_fetch_text(release.sha_url, timeout=timeout))
            if not expected:
                raise UpdateError("The checksum file is empty")
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            if not hmac.compare_digest(digest, expected):
                raise UpdateError("The downloaded package failed checksum verification")
        if progress:
            progress(100)
        return target
    except Exception:
        target.unlink(missing_ok=True)
        raise


def install_command(path: str | Path) -> list[str] | None:
    """Return a command that installs the package with a graphical sudo prompt."""
    pkexec = shutil.which("pkexec")
    apt_get = shutil.which("apt-get")
    if not pkexec or not apt_get:
        return None
    return [
        pkexec,
        "env",
        "DEBIAN_FRONTEND=noninteractive",
        apt_get,
        "install",
        "-y",
        str(Path(path).resolve()),
    ]


def can_install_updates() -> bool:
    """Self-update is intended for the system-wide Debian installation."""
    try:
        running = Path(__file__).resolve()
        running.relative_to(Path("/usr/lib/scanero"))
    except (OSError, ValueError):
        return False
    return bool(shutil.which("pkexec") and shutil.which("apt-get"))
