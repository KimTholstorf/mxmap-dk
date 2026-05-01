"""Pipeline orchestration: scan → classify → serialize.

Adapted from koldex/ca-sovereignty-map for the mxmap-dk data format.
Reads municipalities from our data.json (keyed by BFS ID), scans TLS certs,
writes ca-data.json with the same key structure.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from .classifier import classify
from .models import ClassificationResult
from .probes import probe_caa, probe_ct_log
from .tls import scan_certificate_chain

SEMAPHORE_LIMIT = 40  # concurrent TLS scans
TLS_TIMEOUT = 15  # seconds

CATEGORY_MAP: dict[str, str] = {
    "us": "us-controlled",
    "eu": "eu-controlled",
    "nordic": "nordic",
    "allied": "allied",
    "other": "unknown",
}


# ── Single-domain scan ────────────────────────────────────────────────────────


async def scan_domain(
    domain: str,
    *,
    port: int = 443,
    semaphore: asyncio.Semaphore,
    skip_ct: bool = False,
    tls_timeout: int = TLS_TIMEOUT,
) -> ClassificationResult:
    """Scan a single domain and return classification result."""
    async with semaphore:
        logger.debug("Scanning {}", domain)

        tls_result = await scan_certificate_chain(
            domain, port=port, timeout=tls_timeout
        )
        tls_evidence = tls_result.get("evidence", [])
        chain = tls_result.get("chain", [])
        tls_version = tls_result.get("tls_version", "")
        verification = tls_result.get("verification", "")
        error = tls_result.get("error")

        caa_evidence = await probe_caa(domain)
        caa_records = [ev.raw for ev in caa_evidence]

        ct_evidence = []
        ct_issuers: list[str] = []
        if not skip_ct:
            ct_evidence = await probe_ct_log(domain)
            ct_issuers = list(dict.fromkeys(ev.raw for ev in ct_evidence))

        return classify(
            domain=domain,
            tls_evidence=tls_evidence,
            caa_evidence=caa_evidence,
            ct_evidence=ct_evidence,
            chain=chain,
            caa_records=caa_records,
            ct_issuers=ct_issuers,
            tls_version=tls_version,
            verification=verification,
            error=error,
            cert_mismatch=tls_result.get("cert_mismatch", False),
            http_accessible=tls_result.get("http_accessible"),
            scanned_domain=tls_result.get("scanned_domain", ""),
        )


# ── Batch scan with progress bar ─────────────────────────────────────────────


async def scan_many(
    domains: list[str],
    *,
    concurrency: int = SEMAPHORE_LIMIT,
    skip_ct: bool = False,
    tls_timeout: int = TLS_TIMEOUT,
) -> dict[str, ClassificationResult]:
    """Scan multiple domains concurrently with a live progress bar.

    Returns dict: domain → ClassificationResult.
    """
    total = len(domains)
    semaphore = asyncio.Semaphore(concurrency)

    async def _tracked(domain: str) -> tuple[str, ClassificationResult]:
        result = await scan_domain(
            domain, semaphore=semaphore, skip_ct=skip_ct, tls_timeout=tls_timeout
        )
        return domain, result

    tasks = [asyncio.create_task(_tracked(d)) for d in domains]

    output: dict[str, ClassificationResult] = {}
    done_count = 0
    classified = 0
    start_time = time.monotonic()
    PROGRESS_EVERY = max(1, total // 50)

    for coro in asyncio.as_completed(tasks):
        try:
            domain, result = await coro
        except Exception as exc:
            logger.error("Unexpected exception in scan task: {}", exc)
            continue

        if isinstance(result, Exception):
            logger.error("scan_domain raised: {}", result)
        else:
            output[domain] = result
            if result.jurisdiction.value != "other":
                classified += 1

        done_count += 1
        if done_count % PROGRESS_EVERY == 0 or done_count == total:
            elapsed = time.monotonic() - start_time
            pct = done_count / total * 100
            rate = done_count / elapsed if elapsed > 0 else 0
            eta = (total - done_count) / rate if rate > 0 else 0
            bar_len = 30
            filled = int(bar_len * done_count / total)
            bar = "█" * filled + "░" * (bar_len - filled)
            sys.stderr.write(
                f"\r  [{bar}] {done_count}/{total} ({pct:.0f}%)"
                f"  classified: {classified}"
                f"  {rate:.1f} dom/s"
                f"  ETA: {int(eta)}s  "
            )
            sys.stderr.flush()

    sys.stderr.write("\n")
    sys.stderr.flush()
    return output


# ── Shared hosting detection ──────────────────────────────────────────────────


def _detect_shared_hosting(
    results: dict[str, ClassificationResult],
    threshold: int = 5,
) -> dict[str, tuple[bool, str]]:
    """Return {domain: (is_shared, fingerprint)} for certs shared by ≥threshold domains."""
    fp_count: Counter[str] = Counter()
    domain_fp: dict[str, str] = {}
    for domain, result in results.items():
        if result.cert_chain:
            fp = result.cert_chain[0].sha256_fingerprint
            if fp:
                fp_count[fp] += 1
                domain_fp[domain] = fp

    shared_fps = {fp for fp, count in fp_count.items() if count >= threshold}
    return {domain: (fp in shared_fps, fp) for domain, fp in domain_fp.items()}


# ── Serialization ─────────────────────────────────────────────────────────────


def _error_category(result: ClassificationResult, shared_hosting: bool) -> str:
    error = result.error or ""
    error_lower = error.lower()
    if error == "http_only":
        return "http_only"
    if result.cert_mismatch or shared_hosting:
        return "shared_hosting"
    if "dns resolution failed" in error_lower:
        return "dns_failed"
    if "timeout" in error_lower:
        return "timeout"
    if "verification failed" in error_lower:
        return "ssl_mismatch"
    if "ssl" in error_lower:
        return "ssl_error"
    if error:
        return "connection_error"
    return ""


def serialize_result(
    result: ClassificationResult,
    meta: dict,
    shared_hosting: bool = False,
    shared_cert_fp: str = "",
) -> dict:
    """Serialize a ClassificationResult to our ca-data.json municipality format."""
    jurisdiction_str = result.jurisdiction.value
    category = CATEGORY_MAP.get(jurisdiction_str, "unknown")

    # Pull cert_expiry from leaf cert if available
    cert_expiry = ""
    if result.cert_chain:
        leaf = result.cert_chain[0]
        cert_expiry = leaf.not_after

    return {
        "id": meta.get("id", ""),
        "name": meta.get("name", ""),
        "country": meta.get("country", ""),
        "region": meta.get("region", ""),
        "domain": result.domain,
        "scanned_domain": result.scanned_domain or "",
        "primary_ca": result.primary_ca,
        "ca_owner": result.ca_owner,
        "ca_country": result.ca_country,
        "jurisdiction": jurisdiction_str,
        "risk_level": result.risk_level.value,
        "category": category,
        "confidence": round(result.confidence * 100, 1),
        "tls_version": result.tls_version,
        "cert_expiry": cert_expiry,
        "caa_records": result.caa_records,
        "ct_issuers": result.ct_issuers,
        "cert_chain": [
            entry.model_dump(exclude_none=True) for entry in result.cert_chain
        ],
        "cert_mismatch": result.cert_mismatch,
        "http_accessible": result.http_accessible,
        "shared_hosting": shared_hosting,
        "shared_cert_fingerprint": shared_cert_fp,
        "error_category": _error_category(result, shared_hosting),
        "error": result.error,
        "scan_timestamp": result.scan_timestamp,
    }


# ── Build ca-data.json ────────────────────────────────────────────────────────


def build_ca_data(
    entries: list[dict],
    results: dict[str, ClassificationResult],
) -> dict:
    """Build ca-data.json from municipality metadata + scan results.

    entries: list of {id, name, country, region, domain, ...}
    results: domain → ClassificationResult
    """
    generated = datetime.now(UTC).isoformat()
    shared_info = _detect_shared_hosting(results)

    counts: dict[str, int] = {
        "us-controlled": 0,
        "eu-controlled": 0,
        "nordic": 0,
        "allied": 0,
        "http_only": 0,
        "unknown": 0,
    }

    muni_data: dict[str, dict] = {}

    for entry in entries:
        entry_id = entry["id"]
        domain = entry.get("domain", "")
        result = results.get(domain) if domain else None

        if result:
            is_shared, fp = shared_info.get(domain, (False, ""))
            serialized = serialize_result(
                result, entry, shared_hosting=is_shared, shared_cert_fp=fp
            )
            if result.error == "http_only":
                counts["http_only"] += 1
            else:
                cat = serialized.get("category", "unknown")
                counts[cat] = counts.get(cat, 0) + 1
        else:
            serialized = {
                **entry,
                "primary_ca": "Unknown",
                "jurisdiction": "other",
                "risk_level": "unknown",
                "category": "unknown",
                "confidence": 0,
                "error": "no_domain" if not domain else "not_scanned",
                "error_category": "no_domain" if not domain else "not_scanned",
            }
            counts["unknown"] += 1

        muni_data[entry_id] = serialized

    return {
        "generated": generated,
        "total": len(entries),
        "counts": counts,
        "municipalities": muni_data,
    }


def write_ca_data(data: dict, output_path: Path) -> None:
    """Write ca-data.json."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    size_kb = output_path.stat().st_size // 1024
    logger.info("Wrote {} ({} KB)", output_path, size_kb)
