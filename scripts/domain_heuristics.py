#!/usr/bin/env python3
"""Layer 1: Heuristic domain-municipality ownership scoring.

Flags municipalities where the assigned domain may not actually belong to
the municipality. Produces a risk-scored JSON per country.

Usage:
    python3 scripts/domain_heuristics.py              # All countries
    python3 scripts/domain_heuristics.py EE LV LT     # Specific countries
    python3 scripts/domain_heuristics.py --threshold 40  # Custom risk threshold

Output: data/domain_validation/{cc}_flagged.json
"""

import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_JSON = ROOT / "data.json"
SEED_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "data" / "domain_validation"

# Country-code TLDs that are appropriate for government/municipal use
GOVERNMENT_TLDS = {
    "AD": {".ad"},
    "AT": {".at", ".gv.at"},
    "AU": {".au", ".gov.au"},
    "BE": {".be"},
    "BG": {".bg"},
    "BR": {".br", ".gov.br"},
    "CA": {".ca", ".gc.ca"},
    "CH": {".ch"},
    "CY": {".cy"},
    "CZ": {".cz"},
    "DE": {".de"},
    "DK": {".dk"},
    "EE": {".ee"},
    "ES": {".es", ".gob.es", ".cat", ".eus", ".gal"},
    "FI": {".fi"},
    "FR": {".fr", ".gouv.fr"},
    "GB": {".uk", ".gov.uk"},
    "GR": {".gr"},
    "HR": {".hr"},
    "HU": {".hu"},
    "IE": {".ie"},
    "IS": {".is"},
    "IT": {".it"},
    "LI": {".li"},
    "LT": {".lt"},
    "LU": {".lu"},
    "LV": {".lv"},
    "ME": {".me"},  # Also generic TLD — higher risk
    "MK": {".mk", ".gov.mk"},
    "MT": {".mt", ".gov.mt", ".org.mt"},
    "MX": {".mx", ".gob.mx"},
    "NL": {".nl"},
    "NO": {".no", ".kommune.no"},
    "NZ": {".nz", ".govt.nz"},
    "PL": {".pl", ".gov.pl"},
    "PT": {".pt"},
    "RO": {".ro"},
    "RS": {".rs", ".gov.rs"},
    "RU": {".ru", ".рф"},
    "SE": {".se"},
    "SI": {".si"},
    "SK": {".sk"},
    "XK": {".xk", ".rks-gov.net"},
    # Non-European countries with government TLDs
    "AR": {".ar", ".gob.ar"},
    "AU": {".au", ".gov.au"},
    "AZ": {".az", ".nakhchivan.az"},
    "BA": {".ba", ".rs.ba"},
    "BR": {".br", ".gov.br"},
    "BY": {".by", ".gov.by"},
    "CL": {".cl", ".gob.cl"},
    "CO": {".co", ".gov.co"},
    "CR": {".cr", ".go.cr"},
    "ID": {".id", ".go.id"},
    "IN": {".in", ".gov.in"},
    "JP": {".jp", ".lg.jp"},
    "KR": {".kr", ".go.kr"},
    "MY": {".my", ".gov.my"},
    "PE": {".pe", ".gob.pe"},
    "PH": {".ph", ".gov.ph"},
    "SG": {".sg", ".gov.sg"},
    "TH": {".th", ".go.th"},
    "UA": {".ua", ".gov.ua"},
    "UY": {".uy", ".gub.uy"},
    "VE": {".ve", ".gob.ve"},
}

# Generic/commercial TLDs — suspicious for a municipality
COMMERCIAL_TLDS = {".com", ".net", ".org", ".io", ".info", ".biz", ".co"}

# Known corporate namesake domains (from CLAUDE.md examples + MANUAL_OVERRIDES)
KNOWN_CORPORATE_DOMAINS = {
    "nokia.fi",
    "outokumpu.fi",
    "noo.ee",
    "peipsi.ee",
    "rouge.ee",
    "siauliu.lt",
}

# Blog/free-hosting/social platforms — domain definitely wrong if used as municipality domain
PLATFORM_PATTERNS = [
    "blogspot.", "wordpress.com", "weebly.com", "wixsite.com", "wix.com",
    "sites.google.com", "tumblr.com", "jimdo.com", "webnode.", "squarespace.com",
    "geocities.com", "orgfree.com", "webcindario.com", "galeon.com", "netne.net",
    "tripod.com", "angelfire.com", "freewebs.com", "webs.com",
    "facebook.com", "twitter.com", "instagram.com",
    "altanet.org", "localtic.net", "ese2.com", "es.tl", "es.mn",
    "opennemas.com", "blogia.com", "pueblos-espana.org",
]


def normalize_name(name: str) -> str:
    """Normalize municipality name for comparison: lowercase, strip suffixes,
    remove diacritics."""
    s = name.lower().strip()
    # Remove common administrative suffixes
    for suffix in [
        " vald", " linn", " kommun", " kommune", " kaupunki", " kunta",
        " novads", " savivaldybė", " rajono savivaldybė",
        " miesto savivaldybė", " rajono", " miesto",
        " stadt", " gemeinde", " markt",
        " municipality", " council", " borough",
        " concelho", " municipio", " provincia",
        " općina", " grad", " opština",
        " hrad", " okres",
    ]:
        if s.endswith(suffix):
            s = s[: -len(suffix)]
            break
    # Remove parenthetical notes
    s = re.sub(r"\s*\(.*?\)\s*", "", s)
    return s.strip()


def strip_diacritics(s: str) -> str:
    """Remove diacritics and normalize to ASCII-safe form."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def domain_slug(domain: str) -> str:
    """Extract the meaningful slug from a domain (strip TLD and subdomains).

    Handles government TLD patterns across many countries:
    - Two-part: .gov.uk, .gv.at, .gob.mx, .gouv.fr, .kommune.no, etc.
    - Three-part: .bgld.gv.at, .ktn.gde.at, .rs.ba, etc.
    - Asian/LatAm: .go.kr, .go.id, .go.th, .go.cr, .gub.uy, .lg.jp, etc.
    - E-gov platforms: name.atende.net, name.rks-gov.net, etc.
    - German VG/Amt: amt-name.de, vg-name.de
    """
    domain = domain.lower().strip()
    parts = domain.split(".")

    # E-government platforms where municipality name is a subdomain
    # e.g. "caxambu.atende.net", "gjilan.rks-gov.net"
    EGOV_HOSTS = {
        "atende.net", "rks-gov.net", "ls.gov.rs",
        "ds.gov.lk",  # Sri Lanka shared government portal
        "gov.kz",  # Kazakhstan shared portal
    }
    if len(parts) >= 3:
        host_2 = ".".join(parts[-2:])
        if host_2 in EGOV_HOSTS:
            return parts[-3]
        host_3 = ".".join(parts[-3:]) if len(parts) >= 4 else ""
        if host_3 in EGOV_HOSTS:
            return parts[-4] if len(parts) >= 5 else parts[0]

    # Three-part government TLDs: .bgld.gv.at, .ktn.gde.at, .brest-region.by, etc.
    GOV_MIDDLE = {
        "gv", "gde", "gov", "region", "oblast",
    }
    if len(parts) >= 4 and parts[-2] in GOV_MIDDLE:
        return parts[-4]
    # Also: .od.gov.ua, .cg.gov.ua, .if.gov.ua (4-part)
    if len(parts) >= 4 and parts[-3] in ("gov",):
        return parts[-4]

    # Two-part government TLDs
    GOV_SECOND = {
        "gv", "gov", "gouv", "gob", "govt", "go", "gub",
        "kommune", "suohkan", "herad",
        "lg",  # Japan: .lg.jp
        "co", "com", "or", "ac", "edu", "org",
        "rs",  # Republika Srpska: .rs.ba
        "nakhchivan",  # Azerbaijan
    }
    if len(parts) >= 3 and parts[-2] in GOV_SECOND:
        slug = parts[-3]
        # Skip generic subdomains
        if slug in ("www", "web", "pref", "metro", "city"):
            return parts[-4] if len(parts) >= 4 else slug
        return slug

    # German VG/Amt patterns: strip "amt-", "vg-" prefix from slug
    if len(parts) >= 2:
        slug = parts[-2]
        return slug

    return parts[0]


def name_domain_similarity(name: str, domain: str) -> float:
    """Score 0-1 how well the municipality name matches the domain slug."""
    norm = normalize_name(name)
    slug = domain_slug(domain)

    # Direct match
    norm_ascii = strip_diacritics(norm).replace(" ", "").replace("-", "")
    slug_clean = slug.replace("-", "")

    if norm_ascii == slug_clean:
        return 1.0

    # Check if slug is contained in name or vice versa
    if slug_clean in norm_ascii or norm_ascii in slug_clean:
        return 0.85

    # German umlaut expansion: ä→ae, ö→oe, ü→ue, ß→ss
    norm_de = norm_ascii.replace("a", "ae").replace("o", "oe").replace("u", "ue")
    # Better: expand from original
    norm_expanded = strip_diacritics(
        norm.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    ).replace(" ", "").replace("-", "")
    if norm_expanded == slug_clean:
        return 0.95

    # Sequence matcher for fuzzy similarity
    ratio = SequenceMatcher(None, norm_ascii, slug_clean).ratio()
    return ratio


def get_domain_tld(domain: str) -> str:
    """Extract the full TLD from a domain (handles .gv.at, .gov.uk, .go.kr, etc.)."""
    parts = domain.lower().split(".")
    # Three-part gov TLDs: .bgld.gv.at, .od.gov.ua
    if len(parts) >= 4 and parts[-2] in ("gv", "gde", "gov"):
        return "." + ".".join(parts[-3:])
    # Two-part gov TLDs
    if len(parts) >= 3 and parts[-2] in (
        "gv", "gov", "gouv", "gob", "govt", "go", "gub",
        "kommune", "suohkan", "herad", "lg",
        "co", "com", "or", "ac", "edu", "org",
    ):
        return "." + ".".join(parts[-2:])
    if len(parts) >= 2:
        return "." + parts[-1]
    return ""


def score_municipality(muni: dict, seed_domain: str | None) -> dict:
    """Score a single municipality for domain ownership risk.

    Returns a dict with risk_score (0-100, higher = more suspicious)
    and individual flag details.
    """
    flags = []
    risk = 0
    domain = muni.get("domain", "")
    name = muni.get("name", "")
    country = muni.get("country", "")
    provider = muni.get("provider", "unknown")

    if not domain:
        return {
            "risk_score": 0,
            "flags": ["no_domain"],
            "skip": True,
            "reason": "No domain to validate",
        }

    # --- Skip: Shared government portal (no individual domain, can't validate) ---
    SHARED_PORTALS = {
        "ds.gov.lk", "gov.kz", "kk.rks-gov.net",
    }
    if domain.lower() in SHARED_PORTALS:
        return {
            "risk_score": 0,
            "flags": ["shared_portal"],
            "skip": True,
            "reason": f"Shared government portal ({domain}), no individual domain to validate",
        }

    # --- Flag 0: Platform/blog domain (instant high risk) ---
    domain_lower = domain.lower()
    for pattern in PLATFORM_PATTERNS:
        if pattern in domain_lower:
            return {
                "risk_score": 90,
                "flags": [f"platform_domain:{pattern}"],
                "similarity": 0,
                "domain": domain,
                "name": name,
                "country": country,
                "provider": provider,
            }

    # --- Flag 1: Name-domain similarity ---
    similarity = name_domain_similarity(name, domain)
    if similarity < 0.3:
        risk += 35
        flags.append(f"low_name_match:{similarity:.2f}")
    elif similarity < 0.5:
        risk += 20
        flags.append(f"weak_name_match:{similarity:.2f}")
    elif similarity < 0.7:
        risk += 8
        flags.append(f"moderate_name_match:{similarity:.2f}")

    # --- Flag 2: Known corporate namesakes ---
    if domain.lower() in KNOWN_CORPORATE_DOMAINS:
        risk += 50
        flags.append("known_corporate_domain")

    # --- Flag 3: TLD appropriateness ---
    tld = get_domain_tld(domain)
    gov_tlds = GOVERNMENT_TLDS.get(country, set())
    if tld in COMMERCIAL_TLDS:
        risk += 20
        flags.append(f"commercial_tld:{tld}")
    elif gov_tlds and tld not in gov_tlds:
        # TLD exists but doesn't match expected country TLD
        risk += 10
        flags.append(f"foreign_tld:{tld}")

    # --- Flag 4: Seed domain vs actual domain mismatch ---
    if seed_domain and domain.lower() != seed_domain.lower():
        risk += 15
        flags.append(f"domain_changed_from_seed:{seed_domain}")

    # --- Flag 5: Provider status ---
    if provider == "unknown":
        risk += 15
        flags.append("unknown_provider")
    elif provider == "independent":
        risk += 5
        flags.append("independent_provider")

    # --- Flag 6: Domain looks like abbreviation (very short slug) ---
    slug = domain_slug(domain)
    if len(slug) <= 2 and similarity < 0.8:
        risk += 10
        flags.append(f"very_short_slug:{slug}")

    # --- Flag 7: Domain has numbers (unusual for municipalities) ---
    if re.search(r"\d", domain_slug(domain)):
        risk += 5
        flags.append("numeric_in_domain")

    # Cap at 100
    risk = min(risk, 100)

    return {
        "risk_score": risk,
        "flags": flags,
        "similarity": round(similarity, 3),
        "domain": domain,
        "name": name,
        "country": country,
        "provider": provider,
    }


def load_seed_domains(country: str) -> dict[str, str]:
    """Load seed file domains for a country. Returns {id: domain}."""
    seed_file = SEED_DIR / f"municipalities_{country.lower()}.json"
    if not seed_file.exists():
        return {}
    with open(seed_file) as f:
        seed = json.load(f)
    return {m["id"]: m.get("domain", "") for m in seed}


def run_heuristics(countries: list[str] | None = None, threshold: int = 20) -> dict:
    """Run heuristic scoring on all or specified countries.

    Returns summary stats and writes per-country flagged files.
    """
    with open(DATA_JSON) as f:
        data = json.load(f)

    munis = data["municipalities"]

    # Group by country
    by_country: dict[str, list[tuple[str, dict]]] = {}
    for mid, m in munis.items():
        cc = m.get("country", "??")
        if countries and cc not in countries:
            continue
        by_country.setdefault(cc, []).append((mid, m))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {}

    for cc in sorted(by_country):
        seed_domains = load_seed_domains(cc)
        results = []

        for mid, m in by_country[cc]:
            seed_dom = seed_domains.get(mid, "")
            result = score_municipality(m, seed_dom if seed_dom else None)
            result["id"] = mid
            results.append(result)

        # Sort by risk descending
        results.sort(key=lambda r: r["risk_score"], reverse=True)

        flagged = [r for r in results if r["risk_score"] >= threshold and not r.get("skip")]
        total = len(results)
        with_domain = sum(1 for r in results if not r.get("skip"))

        # Write per-country file
        output = {
            "country": cc,
            "total_municipalities": total,
            "with_domain": with_domain,
            "flagged_count": len(flagged),
            "threshold": threshold,
            "flagged": flagged,
            "clean": [r for r in results if r["risk_score"] < threshold and not r.get("skip")],
        }
        outfile = OUTPUT_DIR / f"{cc.lower()}_flagged.json"
        with open(outfile, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        summary[cc] = {
            "total": total,
            "with_domain": with_domain,
            "flagged": len(flagged),
            "top_risks": [
                {"id": r["id"], "name": r["name"], "domain": r["domain"],
                 "risk": r["risk_score"], "flags": r["flags"]}
                for r in flagged[:10]
            ],
        }

        # Print summary
        pct = (len(flagged) / with_domain * 100) if with_domain else 0
        print(f"{cc}: {len(flagged)}/{with_domain} flagged ({pct:.0f}%)")
        for r in flagged[:5]:
            print(f"  {r['risk_score']:3d} {r['id']:12s} {r['name'][:30]:30s} → {r['domain']}")

    return summary


def main():
    countries = []
    threshold = 20

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--threshold" and i + 1 < len(args):
            threshold = int(args[i + 1])
            i += 2
        else:
            countries.append(args[i].upper())
            i += 1

    summary = run_heuristics(countries or None, threshold)

    # Write overall summary
    summary_file = OUTPUT_DIR / "summary.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\nSummary written to {summary_file}")


if __name__ == "__main__":
    main()
