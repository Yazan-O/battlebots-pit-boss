"""Thin Bright Data client: every external fetch in Pit Boss goes through here.

Products used (see notes/BRIGHTDATA.md for doc-cited endpoints):
- Web Unlocker  -> fetch(url)                    zone: pitboss_unlocker
- SERP API      -> serp(query)                   zone: pitboss_serp
- Web Scraper API -> collect(dataset_id, inputs) ready-made collectors (Reddit/YouTube)

Raw responses are cached under data/raw/<source>/<YYYY-MM-DD>/ so re-runs are free.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
load_dotenv(REPO_ROOT / ".env")

API = "https://api.brightdata.com"
MCP = "https://mcp.brightdata.com/mcp"
UNLOCKER_ZONE = os.environ.get("BRIGHTDATA_UNLOCKER_ZONE", "mcp_unlocker")
SERP_ZONE = os.environ.get("BRIGHTDATA_SERP_ZONE", "pitboss_serp")

# Ready-made collector dataset ids (verified against docs.brightdata.com 2026-07-06)
DATASET_REDDIT_POSTS = "gd_lvz8ah06191smkebj4"
DATASET_REDDIT_COMMENTS = "gd_lvzdpsdlw09j6t702"
DATASET_YOUTUBE_VIDEOS = "gd_lk56epmy2i5g7lzu0k"
DATASET_YOUTUBE_COMMENTS = "gd_lk9q0ew71spt1mxywf"


def _key() -> str:
    key = os.environ.get("BRIGHTDATA_API_KEY")
    if not key:
        raise RuntimeError("BRIGHTDATA_API_KEY missing: put it in repo/.env")
    return key


def _headers() -> dict:
    return {"Authorization": f"Bearer {_key()}", "Content-Type": "application/json"}


def _cache_path(source: str, url: str, ext: str) -> Path:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", url.split("://", 1)[-1])[:80].strip("-")
    h = hashlib.sha1(url.encode()).hexdigest()[:8]
    d = RAW_DIR / source / date.today().isoformat()
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{slug}.{h}.{ext}"


def fetch(url: str, source: str, *, use_cache: bool = True) -> str:
    """GET a page through Web Unlocker; returns raw HTML/text. Cached per day."""
    path = _cache_path(source, url, "html")
    if use_cache and path.exists():
        return path.read_text(encoding="utf-8")
    r = requests.post(
        f"{API}/request",
        headers=_headers(),
        json={"zone": UNLOCKER_ZONE, "url": url, "format": "raw"},
        timeout=120,
    )
    r.raise_for_status()
    if r.text.startswith("Request Failed ("):
        raise RuntimeError(f"Bright Data error for {url}: {r.text[:200]}")
    # scrub third-party API keys embedded in scraped pages before caching/committing
    text = re.sub(r"AIza[0-9A-Za-z_-]{35}", "AIza_REDACTED_THIRD_PARTY_KEY", r.text)
    path.write_text(text, encoding="utf-8")
    return text


def fetch_open(url: str, source: str, *, use_cache: bool = True) -> str:
    """Direct GET for open-API sources (Wikipedia action=raw).

    Bright Data declines Wikipedia per robots.txt (bad_endpoint) — verified
    2026-07-06 on both Unlocker and MCP. Everything non-open goes through fetch().
    """
    path = _cache_path(source, url, "html")
    if use_cache and path.exists():
        return path.read_text(encoding="utf-8")
    r = requests.get(url, headers={"User-Agent": "PitBoss/0.1 (battlebots analytics; github.com/Yazan-O/battlebots-pit-boss)"}, timeout=60)
    r.raise_for_status()
    text = re.sub(r"AIza[0-9A-Za-z_-]{35}", "AIza_REDACTED_THIRD_PARTY_KEY", r.text)
    path.write_text(text, encoding="utf-8")
    return text


def serp(query: str, *, use_cache: bool = True) -> dict:
    """Google search via Bright Data's SERP layer.

    Uses the dedicated SERP API zone when provisioned; otherwise the hosted MCP
    server's search_engine tool (same SERP product, MCP transport).
    """
    path = _cache_path("serp", "serp:" + query, "json")
    if use_cache and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    zones = requests.get(f"{API}/zone/get_active_zones", headers=_headers(), timeout=30).json()
    if any(z["name"] == SERP_ZONE for z in zones):
        target = f"https://www.google.com/search?q={requests.utils.quote(query)}&brd_json=1"
        r = requests.post(
            f"{API}/request",
            headers=_headers(),
            json={"zone": SERP_ZONE, "url": target, "format": "raw"},
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
    else:
        data = mcp_call("search_engine", {"query": query})
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return data


def mcp_call(tool: str, arguments: dict) -> dict:
    """One-shot tool call against the hosted Bright Data MCP server."""
    url = f"{MCP}?token={_key()}"
    headers = {"Content-Type": "application/json",
               "Accept": "application/json, text/event-stream"}
    init = requests.post(url, headers=headers, json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                   "clientInfo": {"name": "pitboss", "version": "0.1"}}}, timeout=60)
    init.raise_for_status()
    sid = init.headers["mcp-session-id"]
    headers["mcp-session-id"] = sid
    requests.post(url, headers=headers, json={
        "jsonrpc": "2.0", "method": "notifications/initialized"}, timeout=30)
    r = requests.post(url, headers=headers, json={
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": tool, "arguments": arguments}}, timeout=180)
    r.raise_for_status()
    payload = None
    for line in r.text.splitlines():
        if line.startswith("data: "):
            payload = json.loads(line[6:])
    if payload is None or "result" not in payload:
        raise RuntimeError(f"MCP {tool} returned no result: {r.text[:300]}")
    text = payload["result"]["content"][0]["text"]
    m = re.search(r"_BEGIN=====\n(.*)\n=====UNTRUSTED", text, re.S)
    body = m.group(1) if m else text
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"text": body}


def collect(dataset_id: str, inputs: list[dict], source: str, *,
            use_cache: bool = True, poll_s: int = 15, timeout_s: int = 900) -> list[dict]:
    """Web Scraper API ready-made collector: trigger -> poll -> download. Cached per day."""
    cache_key = dataset_id + json.dumps(inputs, sort_keys=True)
    path = _cache_path(source, cache_key, "json")
    if use_cache and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    r = requests.post(
        f"{API}/datasets/v3/trigger",
        headers=_headers(),
        params={"dataset_id": dataset_id, "format": "json"},
        json=inputs,
        timeout=60,
    )
    r.raise_for_status()
    snapshot_id = r.json()["snapshot_id"]
    deadline = time.time() + timeout_s
    while True:
        p = requests.get(f"{API}/datasets/v3/progress/{snapshot_id}",
                         headers=_headers(), timeout=60)
        p.raise_for_status()
        status = p.json()["status"]
        if status == "ready":
            break
        if status == "failed":
            raise RuntimeError(f"collector {dataset_id} snapshot {snapshot_id} failed: {p.json()}")
        if time.time() > deadline:
            raise TimeoutError(f"collector {dataset_id} snapshot {snapshot_id} still {status} after {timeout_s}s")
        time.sleep(poll_s)
    d = requests.get(f"{API}/datasets/v3/snapshot/{snapshot_id}",
                     headers=_headers(), params={"format": "json"}, timeout=300)
    d.raise_for_status()
    records = d.json()
    path.write_text(json.dumps(records, indent=1), encoding="utf-8")
    return records


if __name__ == "__main__":
    # Smoke test (P2.T2): one Unlocker fetch + one SERP query.
    html = fetch("https://battlebots.com/proleague/", "battlebots", use_cache=False)
    print(f"UNLOCKER ok: {len(html)} bytes; first 200: {html[:200]!r}")
    s = serp("BattleBots Pro League", use_cache=False)
    org = s.get("organic", [])[:3]
    print(f"SERP ok: {len(org)} organic sample:")
    for it in org:
        print(" -", it.get("title"))
