from __future__ import annotations

import asyncio
import csv
import hashlib
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import httpx
from selectolax.parser import HTMLParser

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "raw_content"
DISCOVERY_DIR = RAW_DIR / "_discovery"
MANIFEST_DIR = RAW_DIR / "_manifests"
MANIFEST_PATH = MANIFEST_DIR / "manifest.csv"

# SEC EDGAR rate-limit is 10 req/sec across an IP. We hold to 8 to leave
# headroom for retries and other traffic.
MAX_RPS = 8
TIMEOUT_S = 30.0
MAX_RETRIES = 4

UA = os.environ.get(
    "VANTAGE_UA",
    "VANTAGE Research thematthewturner@gmail.com",
)

MANIFEST_COLUMNS = (
    "url_sha1",
    "company_id",
    "source_type",
    "url",
    "title",
    "discovered_at",
    "status",
    "http_status",
    "fetched_at",
    "content_type",
    "body_bytes",
    "text_bytes",
    "html_path",
    "text_path",
    "error",
)


@dataclass(frozen=True, slots=True)
class DiscoveryRow:
    company_id: str
    source_type: str
    url: str
    title: str
    discovered_at: str


def url_sha1(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def read_discovery() -> list[DiscoveryRow]:
    rows: dict[str, DiscoveryRow] = {}
    for path in sorted(DISCOVERY_DIR.glob("*.tsv")):
        with path.open() as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for r in reader:
                url = (r.get("url") or "").strip()
                if not url or not url.startswith(("http://", "https://")):
                    continue
                key = url_sha1(url)
                # First write wins; agent ordering is alphabetic so this is stable.
                rows.setdefault(
                    key,
                    DiscoveryRow(
                        company_id=(r.get("company_id") or "").strip(),
                        source_type=(r.get("source_type") or "").strip() or "news",
                        url=url,
                        title=(r.get("title") or "").strip(),
                        discovered_at=(r.get("discovered_at") or "").strip(),
                    ),
                )
    return list(rows.values())


def load_manifest_keys() -> set[str]:
    if not MANIFEST_PATH.exists():
        return set()
    keys: set[str] = set()
    with MANIFEST_PATH.open() as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            if r.get("status") == "ok":
                keys.add(r["url_sha1"])
    return keys


def extract_text(html: bytes, content_type: str) -> str:
    if "html" not in content_type.lower():
        # SEC EDGAR sometimes serves XBRL/XML; fall back to raw decode.
        try:
            return html.decode("utf-8", errors="ignore")
        except Exception:
            return ""
    tree = HTMLParser(html)
    for tag in ("script", "style", "noscript", "svg"):
        for node in tree.css(tag):
            node.decompose()
    body = tree.body or tree.root
    if body is None:
        return ""
    return body.text(separator="\n", strip=True)


def body_dir(company_id: str, source_type: str) -> Path:
    return RAW_DIR / company_id / source_type


async def fetch_one(
    client: httpx.AsyncClient,
    row: DiscoveryRow,
    sem: asyncio.Semaphore,
) -> dict[str, str]:
    sha = url_sha1(row.url)
    out: dict[str, str] = {
        "url_sha1": sha,
        "company_id": row.company_id,
        "source_type": row.source_type,
        "url": row.url,
        "title": row.title,
        "discovered_at": row.discovered_at,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "error",
        "http_status": "",
        "content_type": "",
        "body_bytes": "0",
        "text_bytes": "0",
        "html_path": "",
        "text_path": "",
        "error": "",
    }
    async with sem:
        delay = 1.0
        for attempt in range(MAX_RETRIES):
            try:
                resp = await client.get(row.url, follow_redirects=True)
                out["http_status"] = str(resp.status_code)
                if resp.status_code == 429 or 500 <= resp.status_code < 600:
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                if resp.status_code >= 400:
                    out["error"] = f"http_{resp.status_code}"
                    return out
                content_type = resp.headers.get("content-type", "")
                out["content_type"] = content_type.split(";")[0].strip()
                body = resp.content
                text = extract_text(body, content_type)

                target = body_dir(row.company_id, row.source_type)
                target.mkdir(parents=True, exist_ok=True)
                html_path = target / f"{sha}.html"
                text_path = target / f"{sha}.txt"
                html_path.write_bytes(body)
                text_path.write_text(text, encoding="utf-8")

                out.update(
                    {
                        "status": "ok",
                        "body_bytes": str(len(body)),
                        "text_bytes": str(len(text.encode("utf-8"))),
                        "html_path": str(html_path.relative_to(REPO_ROOT)),
                        "text_path": str(text_path.relative_to(REPO_ROOT)),
                    }
                )
                return out
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                out["error"] = f"{type(exc).__name__}: {exc}"
                await asyncio.sleep(delay)
                delay *= 2
        return out


def append_manifest(rows: Iterable[dict[str, str]]) -> None:
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    write_header = not MANIFEST_PATH.exists()
    with MANIFEST_PATH.open("a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_COLUMNS)
        if write_header:
            writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in MANIFEST_COLUMNS})


async def _run(rows: list[DiscoveryRow]) -> list[dict[str, str]]:
    # Token-bucket: limit concurrency AND pace. We use a semaphore + per-task
    # sleep so we cap at MAX_RPS without bursting.
    sem = asyncio.Semaphore(MAX_RPS)
    headers = {"User-Agent": UA, "Accept": "*/*"}
    async with httpx.AsyncClient(headers=headers, timeout=TIMEOUT_S, http2=True) as client:
        results: list[dict[str, str]] = []
        start = time.monotonic()
        tasks = [fetch_one(client, r, sem) for r in rows]
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            res = await coro
            results.append(res)
            # Crude pacing: ensure we don't exceed MAX_RPS across the run.
            target = start + (i + 1) / MAX_RPS
            now = time.monotonic()
            if now < target:
                await asyncio.sleep(target - now)
        return results


def main() -> None:
    all_rows = read_discovery()
    already = load_manifest_keys()
    todo = [r for r in all_rows if url_sha1(r.url) not in already]
    print(
        f"discovery rows: {len(all_rows)} | already fetched: {len(already)} | "
        f"todo: {len(todo)}"
    )
    if not todo:
        return
    results = asyncio.run(_run(todo))
    append_manifest(results)
    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"fetched ok: {ok} / {len(results)}")


if __name__ == "__main__":
    main()
