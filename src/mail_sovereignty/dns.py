import asyncio
import logging
import re

import dns.asyncresolver
import dns.exception
import dns.resolver
import httpx

logger = logging.getLogger(__name__)

_resolvers = None


def make_resolvers() -> list[dns.asyncresolver.Resolver]:
    """Create a list of async resolvers pointing to different DNS servers."""
    cache = dns.resolver.Cache()
    resolvers = []
    for nameservers in [None, ["8.8.8.8", "8.8.4.4"], ["1.1.1.1", "1.0.0.1"]]:
        r = dns.asyncresolver.Resolver()
        if nameservers:
            r.nameservers = nameservers
        r.timeout = 10
        r.lifetime = 15
        r.cache = cache
        resolvers.append(r)
    return resolvers


def get_resolvers() -> list[dns.asyncresolver.Resolver]:
    global _resolvers
    if _resolvers is None:
        _resolvers = make_resolvers()
    return _resolvers


async def resolve_robust(qname: str, rdtype: str) -> dns.resolver.Answer | None:
    """Universal DNS query with multi-resolver fallback.

    Iterates system → Google → Cloudflare resolvers.
    NXDOMAIN is terminal (returns None immediately).
    NoAnswer/NoNameservers/Timeout retry on next resolver.
    """
    resolvers = get_resolvers()
    for i, resolver in enumerate(resolvers):
        try:
            return await resolver.resolve(qname, rdtype)
        except dns.resolver.NXDOMAIN:
            return None
        except dns.exception.Timeout:
            logger.debug(
                "%s %s: Timeout on resolver %d, retrying", rdtype, qname, i
            )
            await asyncio.sleep(0.5)
            continue
        except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            logger.debug(
                "%s %s: NoAnswer/NoNameservers on resolver %d, retrying",
                rdtype, qname, i,
            )
            continue
        except Exception:
            continue
    logger.info("%s %s: all resolvers failed", rdtype, qname)
    return None


async def lookup_mx(domain: str) -> list[str]:
    """Return list of MX exchange hostnames."""
    answers = await resolve_robust(domain, "MX")
    if answers is None:
        return []
    return sorted(str(r.exchange).rstrip(".").lower() for r in answers)


_VERIFICATION_PREFIXES: dict[str, str] = {
    "ms=": "microsoft",
    "google-site-verification=": "google",
    "apple-domain-verification=": "apple",
    "atlassian-domain-verification=": "atlassian",
    "facebook-domain-verification=": "facebook",
    "docusign=": "docusign",
}


async def lookup_txt(domain: str) -> tuple[str, dict[str, str]]:
    """Return (SPF record, verification tokens) from TXT records.

    Parses all TXT records in a single query: extracts the SPF record and
    domain verification tokens (MS=, google-site-verification=, etc.).
    """
    answers = await resolve_robust(domain, "TXT")
    if answers is None:
        return "", {}
    spf_records = []
    verifications: dict[str, str] = {}
    for r in answers:
        txt = b"".join(r.strings).decode("utf-8", errors="ignore")
        txt_lower = txt.lower()
        if txt_lower.startswith("v=spf1"):
            spf_records.append(txt)
        else:
            for prefix, provider in _VERIFICATION_PREFIXES.items():
                if txt_lower.startswith(prefix):
                    verifications[provider] = txt[len(prefix):]
                    break
    spf = sorted(spf_records)[0] if spf_records else ""
    return spf, verifications


async def lookup_spf(domain: str) -> str:
    """Return the SPF TXT record if found.

    Convenience wrapper around lookup_txt() for callers that only need SPF.
    """
    spf, _ = await lookup_txt(domain)
    return spf


_SPF_INCLUDE_RE = re.compile(r"\binclude:(\S+)", re.IGNORECASE)
_SPF_REDIRECT_RE = re.compile(r"\bredirect=(\S+)", re.IGNORECASE)


async def resolve_spf_includes(spf_record: str, max_lookups: int = 10) -> str:
    """Recursively resolve include: and redirect= directives in an SPF record.

    Returns the original SPF text concatenated with all resolved SPF texts.
    Uses BFS to follow nested includes. Tracks visited domains for loop
    detection and enforces a lookup limit.
    """
    if not spf_record:
        return ""

    initial_domains = _SPF_INCLUDE_RE.findall(spf_record) + _SPF_REDIRECT_RE.findall(
        spf_record
    )
    if not initial_domains:
        return spf_record

    visited: set[str] = set()
    parts = [spf_record]
    queue = list(initial_domains)
    lookups = 0

    while queue and lookups < max_lookups:
        domain = queue.pop(0).lower().rstrip(".")
        if domain in visited:
            continue
        visited.add(domain)
        lookups += 1
        resolved = await lookup_spf(domain)
        if resolved:
            parts.append(resolved)
            nested = _SPF_INCLUDE_RE.findall(resolved) + _SPF_REDIRECT_RE.findall(
                resolved
            )
            queue.extend(nested)

    return " ".join(parts)


async def lookup_cname_chain(hostname: str, max_hops: int = 10) -> list[str]:
    """Follow CNAME chain for hostname. Return list of targets (empty if no CNAME)."""
    chain = []
    current = hostname

    for _ in range(max_hops):
        answers = await resolve_robust(current, "CNAME")
        if answers is None:
            break
        target = str(list(answers)[0].target).rstrip(".").lower()
        chain.append(target)
        current = target

    return chain


async def resolve_mx_cnames(mx_hosts: list[str]) -> dict[str, str]:
    """For each MX host, follow CNAME chain. Return mapping of host -> final target (only for hosts with CNAMEs)."""
    result = {}
    for host in mx_hosts:
        chain = await lookup_cname_chain(host)
        if chain:
            result[host] = chain[-1]
    return result


async def lookup_a(hostname: str) -> list[str]:
    """Resolve hostname to IPv4 addresses via A record query."""
    answers = await resolve_robust(hostname, "A")
    if answers is None:
        return []
    return [str(r) for r in answers]


async def lookup_asn_cymru(ip: str) -> int | None:
    """Query Team Cymru DNS for ASN number of an IP address."""
    result = await lookup_asn_country_cymru(ip)
    return result[0] if result else None


async def lookup_asn_country_cymru(ip: str) -> tuple[int, str] | None:
    """Query Team Cymru DNS for ASN and country code of an IP address.

    Returns (asn, country_code) or None if lookup fails.
    """
    reversed_ip = ".".join(reversed(ip.split(".")))
    query = f"{reversed_ip}.origin.asn.cymru.com"
    answers = await resolve_robust(query, "TXT")
    if answers is None:
        return None
    for r in answers:
        txt = b"".join(r.strings).decode("utf-8", errors="ignore")
        # Format: "3303 | 193.135.252.0/24 | CH | ripencc | ..."
        parts = txt.split("|")
        try:
            asn = int(parts[0].strip())
        except (ValueError, IndexError):
            continue
        cc = parts[2].strip().upper() if len(parts) > 2 else ""
        return asn, cc
    return None


async def lookup_srv(name: str) -> list[tuple[str, int]]:
    """Return list of (target, port) from SRV records."""
    answers = await resolve_robust(name, "SRV")
    if answers is None:
        return []
    return [(str(r.target).rstrip(".").lower(), r.port) for r in answers]


async def lookup_autodiscover(domain: str) -> dict[str, str]:
    """Check autodiscover DNS records. Returns dict of record_type -> target."""
    cname_coro = lookup_cname_chain(f"autodiscover.{domain}", max_hops=1)
    srv_coro = lookup_srv(f"_autodiscover._tcp.{domain}")

    cname_result, srv_result = await asyncio.gather(cname_coro, srv_coro)

    result: dict[str, str] = {}
    if cname_result:
        result["autodiscover_cname"] = cname_result[-1]
    if srv_result:
        result["autodiscover_srv"] = srv_result[0][0]
    return result


async def lookup_dkim(domain: str) -> dict[str, str]:
    """Check DKIM CNAME records for common selectors. Returns dict of selector -> target."""
    selectors = ["selector1", "selector2", "google"]
    result: dict[str, str] = {}

    async def _check(selector: str) -> tuple[str, str | None]:
        chain = await lookup_cname_chain(f"{selector}._domainkey.{domain}", max_hops=1)
        return selector, chain[-1] if chain else None

    results = await asyncio.gather(*[_check(s) for s in selectors])
    for selector, target in results:
        if target:
            result[selector] = target
    return result


async def resolve_mx_asns(mx_hosts: list[str]) -> set[int]:
    """Resolve all MX hosts to IPs, look up ASNs, return set of unique ASNs."""
    asns = set()
    for host in mx_hosts:
        ips = await lookup_a(host)
        for ip in ips:
            asn = await lookup_asn_cymru(ip)
            if asn is not None:
                asns.add(asn)
    return asns


async def resolve_mx_countries(mx_hosts: list[str]) -> set[str]:
    """Resolve all MX hosts to IPs, look up countries, return set of country codes."""
    countries = set()
    for host in mx_hosts:
        ips = await lookup_a(host)
        for ip in ips:
            result = await lookup_asn_country_cymru(ip)
            if result and result[1]:
                countries.add(result[1])
    return countries


async def lookup_tenant(domain: str) -> str | None:
    """Query Microsoft's getuserrealm.srf to detect MS365 tenant.

    Returns 'Managed' or 'Federated' if an MS365 tenant is detected,
    None otherwise.
    """
    url = "https://login.microsoftonline.com/getuserrealm.srf"
    params = {"login": f"user@{domain}", "json": "1"}
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            ns_type = data.get("NameSpaceType")
            if ns_type in ("Managed", "Federated"):
                return ns_type
    except Exception as e:
        logger.debug("Tenant check failed for %s: %s", domain, e)
    return None
