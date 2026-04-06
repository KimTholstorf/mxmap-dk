#!/usr/bin/env python3
"""Layer 2: Fetch website metadata for flagged domains.

Fetches homepage title, meta description, and visible text snippet for each
flagged municipality domain. Outputs structured data for Claude Code to
analyze in-conversation.

Usage:
    python3 scripts/domain_llm_verify.py EE LV LT          # Specific countries
    python3 scripts/domain_llm_verify.py --all-flagged      # All flagged countries
    python3 scripts/domain_llm_verify.py --threshold 30 EE  # Custom risk threshold

Reads:  data/domain_validation/{cc}_flagged.json  (from domain_heuristics.py)
Writes: data/domain_validation/{cc}_metadata.json
"""

import asyncio
import json
import re
import ssl
import sys
from html.parser import HTMLParser
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
VALIDATION_DIR = ROOT / "data" / "domain_validation"

# Timeout for HTTP requests
TIMEOUT = 15.0
CONCURRENCY = 5

# Max text to extract from page body
MAX_TEXT_CHARS = 500


class MetadataExtractor(HTMLParser):
    """Extract title, meta description, and visible text from HTML."""

    def __init__(self):
        super().__init__()
        self._in_title = False
        self.title = ""
        self.description = ""
        self.og_title = ""
        self.og_description = ""
        self._text_parts: list[str] = []
        self._skip_tags = {"script", "style", "noscript", "svg", "head"}
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._skip_depth += 1
        if tag == "title" and self._skip_depth == 0:
            self._in_title = True
        if tag == "meta":
            attr_dict = dict(attrs)
            name = attr_dict.get("name", "").lower()
            prop = attr_dict.get("property", "").lower()
            content = attr_dict.get("content", "")
            if name == "description":
                self.description = content
            elif prop == "og:title":
                self.og_title = content
            elif prop == "og:description":
                self.og_description = content

    def handle_endtag(self, tag):
        if tag in self._skip_tags and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._skip_depth == 0:
            text = data.strip()
            if text:
                self._text_parts.append(text)

    @property
    def visible_text(self) -> str:
        combined = " ".join(self._text_parts)
        # Collapse whitespace
        combined = re.sub(r"\s+", " ", combined).strip()
        return combined[:MAX_TEXT_CHARS]


async def fetch_metadata(
    client: httpx.AsyncClient, domain: str, name: str, country: str
) -> dict:
    """Fetch homepage metadata for a domain."""
    result = {
        "domain": domain,
        "municipality": name,
        "country": country,
        "status": "error",
        "title": "",
        "description": "",
        "text_snippet": "",
        "final_url": "",
        "error": "",
    }

    urls_to_try = [
        f"https://www.{domain}",
        f"https://{domain}",
        f"http://www.{domain}",
        f"http://{domain}",
    ]

    for url in urls_to_try:
        try:
            resp = await client.get(url, follow_redirects=True, timeout=TIMEOUT)
            result["final_url"] = str(resp.url)
            result["http_status"] = resp.status_code

            if resp.status_code >= 400:
                result["error"] = f"HTTP {resp.status_code}"
                continue

            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                result["status"] = "not_html"
                result["error"] = f"Content-Type: {content_type}"
                return result

            html = resp.text[:50000]  # Limit parsing to first 50KB
            extractor = MetadataExtractor()
            try:
                extractor.feed(html)
            except Exception:
                pass  # Best effort

            result["title"] = extractor.title.strip()[:200]
            result["description"] = (
                extractor.description or extractor.og_description
            )[:300]
            result["og_title"] = extractor.og_title[:200]
            result["text_snippet"] = extractor.visible_text
            result["status"] = "ok"
            return result

        except httpx.ConnectError:
            result["error"] = "connection_refused"
        except httpx.ConnectTimeout:
            result["error"] = "timeout"
        except ssl.SSLError as e:
            result["error"] = f"ssl_error: {e}"
        except httpx.HTTPError as e:
            result["error"] = str(e)[:100]
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {str(e)[:80]}"

    result["status"] = "unreachable"
    return result


async def process_country(cc: str, threshold: int = 0) -> dict | None:
    """Process all flagged entries for a country."""
    flagged_file = VALIDATION_DIR / f"{cc.lower()}_flagged.json"
    if not flagged_file.exists():
        print(f"  {cc}: no flagged file found, run domain_heuristics.py first")
        return None

    with open(flagged_file) as f:
        data = json.load(f)

    flagged = data.get("flagged", [])
    if threshold > 0:
        flagged = [f for f in flagged if f["risk_score"] >= threshold]

    if not flagged:
        print(f"  {cc}: no entries above threshold")
        return None

    print(f"  {cc}: fetching metadata for {len(flagged)} flagged domains...")

    # Use permissive SSL context for municipal sites with bad certs
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    async with httpx.AsyncClient(
        verify=ssl_ctx,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; MXMap domain validator)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en,*;q=0.5",
        },
    ) as client:
        sem = asyncio.Semaphore(CONCURRENCY)

        async def fetch_with_sem(entry):
            async with sem:
                return await fetch_metadata(
                    client, entry["domain"], entry["name"], entry["country"]
                )

        results = await asyncio.gather(
            *[fetch_with_sem(e) for e in flagged]
        )

    # Merge heuristic flags with metadata
    entries = []
    for flag_entry, meta in zip(flagged, results):
        entry = {
            "id": flag_entry["id"],
            "name": flag_entry["name"],
            "domain": flag_entry["domain"],
            "country": flag_entry["country"],
            "provider": flag_entry.get("provider", ""),
            "risk_score": flag_entry["risk_score"],
            "flags": flag_entry["flags"],
            "similarity": flag_entry.get("similarity", 0),
            "website": meta,
        }
        entries.append(entry)

    output = {
        "country": cc,
        "count": len(entries),
        "entries": entries,
    }

    outfile = VALIDATION_DIR / f"{cc.lower()}_metadata.json"
    with open(outfile, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    ok = sum(1 for e in entries if e["website"]["status"] == "ok")
    err = sum(1 for e in entries if e["website"]["status"] != "ok")
    print(f"  {cc}: {ok} fetched, {err} errors → {outfile.name}")

    return output


async def main():
    args = sys.argv[1:]
    countries = []
    threshold = 0
    all_flagged = False

    i = 0
    while i < len(args):
        if args[i] == "--threshold" and i + 1 < len(args):
            threshold = int(args[i + 1])
            i += 2
        elif args[i] == "--all-flagged":
            all_flagged = True
            i += 1
        else:
            countries.append(args[i].upper())
            i += 1

    if all_flagged:
        # Find all *_flagged.json files
        countries = sorted(
            f.stem.replace("_flagged", "").upper()
            for f in VALIDATION_DIR.glob("*_flagged.json")
            if f.stem != "summary"
        )

    if not countries:
        print("Usage: python3 scripts/domain_llm_verify.py EE LV LT")
        print("       python3 scripts/domain_llm_verify.py --all-flagged")
        sys.exit(1)

    print(f"Fetching website metadata for: {', '.join(countries)}")

    for cc in countries:
        await process_country(cc, threshold)

    print("\nDone. Review *_metadata.json files or read them in Claude Code.")


if __name__ == "__main__":
    asyncio.run(main())
