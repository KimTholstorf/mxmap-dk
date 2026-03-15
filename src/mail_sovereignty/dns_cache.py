"""Per-country file-based DNS cache.

Cache files are stored in data/dns_cache/{cc}.json and committed to the repo.
Each entry has a timestamp; entries older than TTL_DAYS are re-queried.

The cache is domain-scoped: all DNS queries for a domain are stored together.
This makes entries easy to inspect and update.

Usage:
    cache = DnsCache("PT")
    # In scan_municipality, wrap the domain's DNS results:
    cached = cache.get_domain(domain)
    if cached:
        mx, spf, ... = cached["mx"], cached["spf"], ...
    else:
        mx = await lookup_mx(domain)
        ...
        cache.set_domain(domain, {"mx": mx, "spf": spf, ...})
    cache.save()
"""

import json
import time
from pathlib import Path

TTL_DAYS = 7
TTL_SECONDS = TTL_DAYS * 86400

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "dns_cache"


class DnsCache:
    """Per-country DNS result cache backed by a JSON file.

    Stores all DNS results for a domain as a single entry:
    {
      "domain.example": {
        "mx": [...], "spf": "...", "mx_cnames": {...},
        "mx_asns": [...], "mx_countries": [...],
        "autodiscover": {...}, "dkim": {...},
        "spf_resolved": "...",
        "ts": 1710500000
      }
    }
    """

    def __init__(self, country_code: str):
        self.cc = country_code.upper()
        self.path = CACHE_DIR / f"{self.cc.lower()}.json"
        self.data: dict[str, dict] = {}
        self.hits = 0
        self.misses = 0
        self._load()

    def _load(self):
        if self.path.exists():
            with open(self.path, encoding="utf-8") as f:
                self.data = json.load(f)

    def get_domain(self, domain: str) -> dict | None:
        """Return cached DNS results for a domain, or None if miss/expired."""
        if not domain:
            return None
        entry = self.data.get(domain)
        if entry is None:
            self.misses += 1
            return None
        age = time.time() - entry.get("ts", 0)
        if age > TTL_SECONDS:
            self.misses += 1
            return None
        self.hits += 1
        return entry

    def set_domain(self, domain: str, results: dict):
        """Store all DNS results for a domain."""
        if not domain:
            return
        results["ts"] = int(time.time())
        self.data[domain] = results

    def save(self):
        """Write cache to disk."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        # Sort keys for stable diffs
        sorted_data = dict(sorted(self.data.items()))
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(sorted_data, f, separators=(",", ":"), ensure_ascii=False)
        total = self.hits + self.misses
        if total > 0:
            pct = self.hits * 100 // total
            print(
                f"  DNS cache ({self.cc}): {self.hits} hits, "
                f"{self.misses} misses ({pct}% hit rate), "
                f"{len(self.data)} entries"
            )

    def stats(self) -> tuple[int, int]:
        return self.hits, self.misses
