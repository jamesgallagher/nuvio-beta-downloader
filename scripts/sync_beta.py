#!/usr/bin/env python3
"""Mirror NuvioTV's newest universal beta APK to one stable release URL."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


UPSTREAM = "NuvioMedia/NuvioTV"
ASSET_NAME = "app-full-universal-release.apk"
MIRROR_ASSET_NAME = "NuvioTV-beta-universal.apk"
RELEASE_TAG = "beta"
MARKER = "<!-- nuvio-beta-source: "
BETA_TAG = re.compile(r"(?:^|[.\-])beta(?:[.\-]|$)", re.IGNORECASE)


def api_json(url: str) -> object:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "nuvio-beta-downloader"}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
        return json.load(response)


def newest_beta(releases: list[dict]) -> tuple[dict, dict]:
    candidates = []
    for release in releases:
        tag = release.get("tag_name", "")
        if release.get("draft") or not BETA_TAG.search(tag) or not release.get("published_at"):
            continue
        asset = next((a for a in release.get("assets", []) if a.get("name") == ASSET_NAME), None)
        if asset:
            candidates.append((release, asset))
    if not candidates:
        raise RuntimeError("No published beta release with the universal APK was found")
    return max(candidates, key=lambda item: (item[0]["published_at"], item[0]["tag_name"]))


def gh(*args: str, capture: bool = True) -> str:
    proc = subprocess.run(["gh", *args], check=True, text=True, capture_output=capture)
    return proc.stdout.strip() if capture else ""


def current_release() -> dict | None:
    proc = subprocess.run(
        ["gh", "release", "view", RELEASE_TAG, "--json", "body,assets"],
        text=True,
        capture_output=True,
    )
    if proc.returncode == 0:
        return json.loads(proc.stdout)
    if "release not found" in proc.stderr.lower() or "http 404" in proc.stderr.lower():
        return None
    raise RuntimeError(f"Could not inspect mirror release: {proc.stderr.strip()}")


def source_metadata(body: str) -> dict | None:
    match = re.search(r"<!-- nuvio-beta-source: (\{[^\n]*\}) -->", body)
    return json.loads(match.group(1)) if match else None


def download_and_validate(url: str, expected_size: int, path: Path) -> str:
    if not url.startswith(f"https://github.com/{UPSTREAM}/releases/download/"):
        raise RuntimeError("Upstream APK URL did not come from the official NuvioTV releases")
    digest = hashlib.sha256()
    total = 0
    request = urllib.request.Request(url, headers={"User-Agent": "nuvio-beta-downloader"})
    with urllib.request.urlopen(request, timeout=120) as response, path.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
            digest.update(chunk)
            total += len(chunk)
    if total != expected_size or total < 10_000_000:
        raise RuntimeError(f"Downloaded APK size mismatch: got {total}, expected {expected_size}")
    if not zipfile.is_zipfile(path):
        raise RuntimeError("Downloaded file is not an APK/ZIP archive")
    with zipfile.ZipFile(path) as apk:
        if "AndroidManifest.xml" not in apk.namelist() or apk.testzip() is not None:
            raise RuntimeError("Downloaded APK failed archive validation")
    return digest.hexdigest()


def release_notes(release: dict, asset: dict, sha256: str) -> str:
    metadata = {
        "tag": release["tag_name"],
        "published_at": release["published_at"],
        "sha256": sha256,
    }
    return (
        "Unofficial mirror of the official NuvioTV universal beta APK. "
        "The APK is copied byte-for-byte; it is not rebuilt or re-signed.\n\n"
        f"Upstream release: https://github.com/{UPSTREAM}/releases/tag/{release['tag_name']}\n\n"
        f"Original APK: {asset['browser_download_url']}\n\n"
        f"Corresponding source: https://github.com/{UPSTREAM}/archive/refs/tags/{release['tag_name']}.zip\n\n"
        f"Upstream license: https://github.com/{UPSTREAM}/blob/{release['tag_name']}/LICENSE\n\n"
        f"SHA-256: `{sha256}`\n\n"
        f"{MARKER}{json.dumps(metadata, separators=(',', ':'))} -->\n"
    )


def main() -> None:
    releases = api_json(f"https://api.github.com/repos/{UPSTREAM}/releases?per_page=100")
    release, asset = newest_beta(releases)
    print(f"Newest beta: {release['tag_name']} ({release['published_at']}); universal APK {asset['size']} bytes")

    if "--check" in sys.argv:
        return

    if "--verify-upstream" in sys.argv:
        with tempfile.TemporaryDirectory() as temp:
            digest = download_and_validate(asset["browser_download_url"], asset["size"], Path(temp) / MIRROR_ASSET_NAME)
        print(f"Official APK verified; SHA-256 {digest}")
        return

    if not os.environ.get("GH_REPO") or not os.environ.get("GH_TOKEN"):
        raise RuntimeError("GH_REPO and GH_TOKEN are required when publishing")

    existing = current_release()
    old = source_metadata(existing.get("body", "")) if existing else None
    has_asset = bool(existing and any(a["name"] == MIRROR_ASSET_NAME for a in existing.get("assets", [])))
    if old and old.get("tag") == release["tag_name"] and has_asset:
        print("Mirror is already current")
        return
    if old and old.get("published_at", "") > release["published_at"]:
        raise RuntimeError("Upstream appears older than the current mirror; refusing to roll back")

    with tempfile.TemporaryDirectory() as temp:
        apk_path = Path(temp) / MIRROR_ASSET_NAME
        digest = download_and_validate(asset["browser_download_url"], asset["size"], apk_path)
        notes_path = Path(temp) / "notes.md"
        notes_path.write_text(release_notes(release, asset, digest), encoding="utf-8")

        if existing is None:
            gh("release", "create", RELEASE_TAG, "--title", "Latest NuvioTV beta", "--prerelease", "--latest=false", "--notes", "Initializing verified beta mirror")
        gh("release", "upload", RELEASE_TAG, str(apk_path), "--clobber", capture=False)
        gh("release", "edit", RELEASE_TAG, "--title", "Latest NuvioTV beta", "--prerelease", "--latest=false", "--notes-file", str(notes_path), capture=False)
        print(f"Published {release['tag_name']} with SHA-256 {digest}")


if __name__ == "__main__":
    main()

