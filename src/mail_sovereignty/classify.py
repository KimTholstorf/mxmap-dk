from mail_sovereignty.constants import (
    AWS_KEYWORDS,
    ELKDATA_KEYWORDS,
    FOREIGN_SENDER_KEYWORDS,
    GATEWAY_KEYWORDS,
    GOOGLE_KEYWORDS,
    TELIA_KEYWORDS,
    TET_KEYWORDS,
    ZONE_KEYWORDS,
    MICROSOFT_KEYWORDS,
    PROVIDER_KEYWORDS,
    SMTP_BANNER_KEYWORDS,
    BALTIC_ISP_ASNS,
)


def classify_from_smtp_banner(banner: str, ehlo: str = "") -> str | None:
    """Classify provider from SMTP banner/EHLO. Returns provider or None."""
    if not banner and not ehlo:
        return None
    blob = f"{banner} {ehlo}".lower()
    for provider, keywords in SMTP_BANNER_KEYWORDS.items():
        if any(k in blob for k in keywords):
            return provider
    return None


def classify_from_autodiscover(autodiscover: dict[str, str] | None) -> str | None:
    """Classify provider from autodiscover DNS records."""
    if not autodiscover:
        return None
    blob = " ".join(autodiscover.values()).lower()
    for provider, keywords in PROVIDER_KEYWORDS.items():
        if any(k in blob for k in keywords):
            return provider
    return None


def detect_gateway(mx_records: list[str]) -> str | None:
    """Return gateway provider name if MX matches a known gateway, else None."""
    mx_blob = " ".join(mx_records).lower()
    for gateway, keywords in GATEWAY_KEYWORDS.items():
        if any(k in mx_blob for k in keywords):
            return gateway
    return None


def classify_from_dkim(dkim: dict[str, str] | None) -> str | None:
    """Classify provider from DKIM CNAME targets."""
    if not dkim:
        return None
    blob = " ".join(dkim.values()).lower()
    # Microsoft: selector1/2 -> *.onmicrosoft.com
    if "onmicrosoft.com" in blob:
        return "microsoft"
    # Google: google._domainkey -> *.googlemail.com or *.google.com
    if "google" in blob or "googlemail" in blob:
        return "google"
    for provider, keywords in PROVIDER_KEYWORDS.items():
        if any(k in blob for k in keywords):
            return provider
    return None


def _check_spf_for_provider(spf_blob: str) -> str | None:
    """Check an SPF blob for hyperscaler keywords, return provider or None."""
    for provider, keywords in PROVIDER_KEYWORDS.items():
        if any(k in spf_blob for k in keywords):
            return provider
    return None


def _check_spf_all(
    spf_record: str | None, resolved_spf: str | None
) -> str | None:
    """Check raw and resolved SPF for a provider keyword."""
    spf_blob = (spf_record or "").lower()
    provider = _check_spf_for_provider(spf_blob)
    if not provider and resolved_spf:
        provider = _check_spf_for_provider(resolved_spf.lower())
    return provider


def classify(
    mx_records: list[str],
    spf_record: str | None,
    mx_cnames: dict[str, str] | None = None,
    mx_asns: set[int] | None = None,
    resolved_spf: str | None = None,
    autodiscover: dict[str, str] | None = None,
    dkim: dict[str, str] | None = None,
) -> tuple[str, str]:
    """Classify email provider based on MX, CNAME targets, SPF, autodiscover, and DKIM.

    Returns (provider, reason) where reason explains the classification decision.

    Classification order:
    1. MX hostname matches a known provider directly
    2. CNAME of MX host resolves to a known provider
    3. MX is a known gateway (spam filter) → check SPF/autodiscover/DKIM for backend
    4. MX exists but unrecognized → check DKIM, then independent or Baltic ISP (by ASN)
    5. No MX → unknown
    """
    mx_blob = " ".join(mx_records).lower()
    mx_display = ", ".join(mx_records[:2])

    # 1. Direct MX hostname match
    for provider, keywords, label in [
        ("microsoft", MICROSOFT_KEYWORDS, "Microsoft"),
        ("google", GOOGLE_KEYWORDS, "Google"),
        ("zone", ZONE_KEYWORDS, "Zone.eu"),
        ("telia", TELIA_KEYWORDS, "Telia"),
        ("tet", TET_KEYWORDS, "TET"),
        ("aws", AWS_KEYWORDS, "AWS"),
        ("elkdata", ELKDATA_KEYWORDS, "Elkdata"),
    ]:
        if any(k in mx_blob for k in keywords):
            return provider, f"MX record ({mx_display}) matches {label}"

    # 2. CNAME resolution of MX hosts
    if mx_records and mx_cnames:
        cname_blob = " ".join(mx_cnames.values()).lower()
        for provider, keywords, label in [
            ("microsoft", MICROSOFT_KEYWORDS, "Microsoft"),
            ("google", GOOGLE_KEYWORDS, "Google"),
            ("zone", ZONE_KEYWORDS, "Zone.eu"),
            ("telia", TELIA_KEYWORDS, "Telia"),
            ("tet", TET_KEYWORDS, "TET"),
            ("aws", AWS_KEYWORDS, "AWS"),
            ("elkdata", ELKDATA_KEYWORDS, "Elkdata"),
        ]:
            if any(k in cname_blob for k in keywords):
                cname_target = next(iter(mx_cnames.values()), "?")
                return provider, f"MX CNAME ({cname_target}) resolves to {label}"

    # 3. Known email gateway → look through to backend provider
    gateway = detect_gateway(mx_records) if mx_records else None
    if gateway:
        spf_provider = _check_spf_all(spf_record, resolved_spf)
        if spf_provider:
            return spf_provider, (
                f"MX is {gateway} gateway; SPF authorizes {spf_provider}"
            )
        ad_provider = classify_from_autodiscover(autodiscover)
        if ad_provider:
            return ad_provider, (
                f"MX is {gateway} gateway; autodiscover points to {ad_provider}"
            )
        dkim_provider = classify_from_dkim(dkim)
        if dkim_provider:
            return dkim_provider, (
                f"MX is {gateway} gateway; DKIM signs via {dkim_provider}"
            )
        # Gateway relays to unknown backend — fall through to independent

    # 4. MX exists but no direct provider match → check DKIM for hidden
    #    backend (self-hosted gateway pattern), then Baltic ISP, then independent
    #    Note: SPF is NOT used here — SPF only indicates send authorization,
    #    not where mailboxes are hosted. Many ISP-hosted municipalities have
    #    SPF includes for Outlook (shared calendars, etc.) without using it
    #    for mail hosting. DKIM CNAMEs are specific to the actual mail host.
    if mx_records:
        # Check if DKIM reveals a backend provider (self-hosted gateway)
        if not gateway:
            dkim_provider = classify_from_dkim(dkim)
            if dkim_provider:
                return dkim_provider, (
                    f"MX ({mx_display}) is local gateway; "
                    f"DKIM reveals {dkim_provider} backend"
                )

        is_baltic_isp = bool(mx_asns and mx_asns & BALTIC_ISP_ASNS.keys())

        if is_baltic_isp:
            asn_names = [
                BALTIC_ISP_ASNS[a]
                for a in sorted(mx_asns & BALTIC_ISP_ASNS.keys())
            ]
            return "baltic-isp", (
                f"MX ({mx_display}) hosted on Baltic ISP "
                f"({', '.join(asn_names)})"
            )

        return "independent", (
            f"MX ({mx_display}) is self-hosted"
        )

    # 5. No MX → unknown
    return "unknown", "No MX records found"


def classify_from_mx(mx_records: list[str]) -> str | None:
    """Classify provider from MX records alone."""
    if not mx_records:
        return None
    blob = " ".join(mx_records).lower()
    for provider, keywords in PROVIDER_KEYWORDS.items():
        if any(k in blob for k in keywords):
            return provider
    return "independent"


def classify_from_spf(spf_record: str | None) -> str | None:
    """Classify provider from SPF record alone."""
    if not spf_record:
        return None
    blob = spf_record.lower()
    for provider, keywords in PROVIDER_KEYWORDS.items():
        if any(k in blob for k in keywords):
            return provider
    return None


def spf_mentions_providers(spf_record: str | None) -> set[str]:
    """Return set of providers mentioned in SPF (main + foreign senders)."""
    if not spf_record:
        return set()
    blob = spf_record.lower()
    found = set()
    for provider, keywords in PROVIDER_KEYWORDS.items():
        if any(k in blob for k in keywords):
            found.add(provider)
    for provider, keywords in FOREIGN_SENDER_KEYWORDS.items():
        if any(k in blob for k in keywords):
            found.add(provider)
    return found
