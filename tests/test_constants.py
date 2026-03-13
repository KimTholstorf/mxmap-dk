from mail_sovereignty.constants import (
    MICROSOFT_KEYWORDS,
    GOOGLE_KEYWORDS,
    AWS_KEYWORDS,
    ZONE_KEYWORDS,
    TELIA_KEYWORDS,
    TET_KEYWORDS,
    PROVIDER_KEYWORDS,
    FOREIGN_SENDER_KEYWORDS,
    SKIP_DOMAINS,
    BALTIC_ISP_ASNS,
)


def test_keyword_lists_non_empty():
    assert MICROSOFT_KEYWORDS
    assert GOOGLE_KEYWORDS
    assert AWS_KEYWORDS
    assert ZONE_KEYWORDS
    assert TELIA_KEYWORDS
    assert TET_KEYWORDS


def test_provider_keywords_has_all_providers():
    assert set(PROVIDER_KEYWORDS.keys()) == {
        "microsoft", "google", "aws", "zone", "telia", "tet", "elkdata",
    }


def test_foreign_sender_keywords_non_empty():
    assert FOREIGN_SENDER_KEYWORDS
    assert "mailchimp" in FOREIGN_SENDER_KEYWORDS
    assert "sendgrid" in FOREIGN_SENDER_KEYWORDS
    assert "smtp2go" in FOREIGN_SENDER_KEYWORDS
    assert "nl2go" in FOREIGN_SENDER_KEYWORDS
    assert "hubspot" in FOREIGN_SENDER_KEYWORDS
    assert "knowbe4" in FOREIGN_SENDER_KEYWORDS
    assert "hornetsecurity" in FOREIGN_SENDER_KEYWORDS
    assert set(FOREIGN_SENDER_KEYWORDS.keys()).isdisjoint(set(PROVIDER_KEYWORDS.keys()))


def test_skip_domains_contains_expected():
    assert "example.com" in SKIP_DOMAINS
    assert "sentry.io" in SKIP_DOMAINS
    assert "schema.org" in SKIP_DOMAINS


def test_baltic_isp_asns_contains_key_providers():
    assert 3249 in BALTIC_ISP_ASNS  # Telia
    assert 5518 in BALTIC_ISP_ASNS  # TET
    assert 2586 in BALTIC_ISP_ASNS  # Elisa
    assert 13194 in BALTIC_ISP_ASNS  # Bite


def test_baltic_isp_asns_minimum_count():
    assert len(BALTIC_ISP_ASNS) >= 10
