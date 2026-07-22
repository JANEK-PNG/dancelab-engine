#!/usr/bin/env python3
"""Fetch and validate the official Warehouse Project Apple Music catalogue."""

from __future__ import annotations

import argparse
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from dancelab.validation.djmix.warehouse_catalog import (
    WAREHOUSE_RAW_SCHEMA_VERSION,
    WarehouseCatalogError,
    parse_warehouse_album_html,
    parse_warehouse_curator_html,
)


DEFAULT_CURATOR_URL = "https://music.apple.com/pl/curator/the-warehouse-project-dj-mixes/1735396087"
MAX_PAGE_BYTES = 16 * 1024 * 1024
USER_AGENT = "DanceLab-Validation/1.0 (+local source-backed research)"


def _validate_source_url(url: str) -> str:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "music.apple.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
    ):
        raise WarehouseCatalogError(f"source URL is outside music.apple.com: {url!r}")
    return url


class _AppleMusicRedirectHandler(HTTPRedirectHandler):
    def redirect_request(  # type: ignore[override]
        self,
        req: Request,
        fp: object,
        code: int,
        msg: str,
        headers: Mapping[str, str],
        newurl: str,
    ) -> Request | None:
        _validate_source_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _request_text(url: str, *, timeout: float, retries: int) -> str:
    _validate_source_url(url)
    opener = build_opener(_AppleMusicRedirectHandler())
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with opener.open(request, timeout=timeout) as response:
                final_url = response.geturl()
                _validate_source_url(final_url)
                content_type = response.headers.get_content_type()
                if content_type not in {"text/html", "application/xhtml+xml"}:
                    raise WarehouseCatalogError(
                        f"unexpected content type {content_type!r} for {url}"
                    )
                body = response.read(MAX_PAGE_BYTES + 1)
                if len(body) > MAX_PAGE_BYTES:
                    raise WarehouseCatalogError(f"source page exceeds size limit: {url}")
                charset = response.headers.get_content_charset() or "utf-8"
                return body.decode(charset)
        except (HTTPError, URLError, OSError, UnicodeError, WarehouseCatalogError) as exc:
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(min(2**attempt, 8))
    raise WarehouseCatalogError(f"failed to fetch {url}: {last_error}") from last_error


def _load_curator(
    *,
    url: str,
    cache_path: Path,
    refresh: bool,
    timeout: float,
    retries: int,
) -> tuple[str, dict[str, object]]:
    if cache_path.exists() and not refresh:
        cached = cache_path.read_text(encoding="utf-8")
        try:
            return cached, parse_warehouse_curator_html(cached)
        except WarehouseCatalogError:
            pass
    html = _request_text(url, timeout=timeout, retries=retries)
    parsed = parse_warehouse_curator_html(html)
    _atomic_write_text(cache_path, html)
    return html, parsed


def _load_album(
    item: Mapping[str, object],
    *,
    cache_directory: Path,
    refresh: bool,
    timeout: float,
    retries: int,
) -> dict[str, object]:
    album_id = str(item["apple_album_id"])
    title = str(item["catalog_title"])
    url = _validate_source_url(str(item["album_url"]))
    cache_path = cache_directory / f"{album_id}.html"
    if cache_path.exists() and not refresh:
        cached = cache_path.read_text(encoding="utf-8")
        try:
            return parse_warehouse_album_html(
                cached,
                expected_album_id=album_id,
                expected_title=title,
            )
        except WarehouseCatalogError:
            pass
    html = _request_text(url, timeout=timeout, retries=retries)
    album = parse_warehouse_album_html(
        html,
        expected_album_id=album_id,
        expected_title=title,
    )
    _atomic_write_text(cache_path, html)
    return album


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    _atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--curator-url", default=DEFAULT_CURATOR_URL)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error("--workers must be between 1 and 8")
    if not 1 <= args.timeout <= 120:
        parser.error("--timeout must be between 1 and 120 seconds")
    if not 0 <= args.retries <= 6:
        parser.error("--retries must be between 0 and 6")

    output = args.output_directory.resolve()
    cache = output / "cache"
    curator_html, curator_payload = _load_curator(
        url=_validate_source_url(args.curator_url),
        cache_path=cache / "curator.html",
        refresh=args.refresh,
        timeout=args.timeout,
        retries=args.retries,
    )
    accepted = [
        item
        for item in curator_payload["catalog_items"]
        if item["catalog_classification"] == "dj_mix"
    ]
    accepted.sort(key=lambda item: int(item["apple_album_id"]))

    albums_by_id: dict[str, dict[str, object]] = {}
    failures: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures: dict[Future[dict[str, object]], str] = {
            executor.submit(
                _load_album,
                item,
                cache_directory=cache / "albums",
                refresh=args.refresh,
                timeout=args.timeout,
                retries=args.retries,
            ): str(item["apple_album_id"])
            for item in accepted
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            album_id = futures[future]
            try:
                albums_by_id[album_id] = future.result()
            except Exception as exc:  # noqa: BLE001 - retain every failed source page
                failures.append((album_id, str(exc)))
            print(f"[{completed:03d}/{len(futures):03d}] album {album_id}")

    if failures:
        print("Warehouse snapshot was not written; failed albums:")
        for album_id, message in sorted(failures, key=lambda item: int(item[0])):
            print(f"- {album_id}: {message}")
        return 2

    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload: dict[str, object] = {
        "schema_version": WAREHOUSE_RAW_SCHEMA_VERSION,
        "storefront": "pl",
        "source_name": "Apple Music public catalog",
        "curator_url": args.curator_url,
        "fetched_at": fetched_at.replace("+00:00", "Z"),
        "curator_page_sha256": curator_payload["source_page_sha256"],
        "curator": curator_payload["curator"],
        "programs": curator_payload["programs"],
        "catalog_items": curator_payload["catalog_items"],
        "albums": [albums_by_id[album_id] for album_id in sorted(albums_by_id, key=int)],
        "fetch_analysis": {
            **curator_payload["analysis"],
            "fetched_album_count": len(albums_by_id),
            "failed_album_count": 0,
            "curator_html_bytes": len(curator_html.encode("utf-8")),
        },
    }
    _write_json_atomic(output / "apple_music_raw.json", payload)
    print(json.dumps(payload["fetch_analysis"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
