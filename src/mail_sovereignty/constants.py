import re

MICROSOFT_KEYWORDS = [
    "mail.protection.outlook.com",
    "outlook.com",
    "microsoft",
    "office365",
    "onmicrosoft",
    "spf.protection.outlook.com",
    "sharepointonline",
]
GOOGLE_KEYWORDS = [
    "google",
    "googlemail",
    "gmail",
    "_spf.google.com",
    "aspmx.l.google.com",
]
AWS_KEYWORDS = ["amazonaws", "amazonses", "awsdns"]

# Baltic-specific providers (replaces Infomaniak for Swiss)
ZONE_KEYWORDS = ["zone.eu", "zone.ee", "zoneit.eu"]
TELIA_KEYWORDS = ["telia.ee", "telia.lt", "telia.lv", "telia.com"]
TET_KEYWORDS = ["tet.lv"]

PROVIDER_KEYWORDS = {
    "microsoft": MICROSOFT_KEYWORDS,
    "google": GOOGLE_KEYWORDS,
    "aws": AWS_KEYWORDS,
    "zone": ZONE_KEYWORDS,
    "telia": TELIA_KEYWORDS,
    "tet": TET_KEYWORDS,
}

FOREIGN_SENDER_KEYWORDS = {
    "mailchimp": ["mandrillapp.com", "mandrill", "mcsv.net"],
    "sendgrid": ["sendgrid"],
    "mailjet": ["mailjet"],
    "mailgun": ["mailgun"],
    "brevo": ["sendinblue", "brevo"],
    "mailchannels": ["mailchannels"],
    "smtp2go": ["smtp2go"],
    "nl2go": ["nl2go"],
    "hubspot": ["hubspotemail"],
    "knowbe4": ["knowbe4"],
    "hornetsecurity": ["hornetsecurity", "hornetdmarc"],
}

SPARQL_URL = "https://query.wikidata.org/sparql"
# Not used — Baltic municipalities are loaded from seed JSON files
SPARQL_QUERY = ""

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
TYPO3_RE = re.compile(r"linkTo_UnCryptMailto\(['\"]([^'\"]+)['\"]")
SKIP_DOMAINS = {
    "example.com",
    "example.ee",
    "example.lv",
    "example.lt",
    "sentry.io",
    "w3.org",
    "gstatic.com",
    "googleapis.com",
    "schema.org",
}

SUBPAGES = [
    "/kontakt",
    "/contact",
    "/kontaktid",       # Estonian
    "/kontakti",        # Latvian
    "/kontaktai",       # Lithuanian
    "/kontakt/",
    "/contact/",
    "/meist",           # Estonian: "About us"
    "/par-mums",        # Latvian: "About us"
    "/apie-mus",        # Lithuanian: "About us"
    "/struktuur",       # Estonian: "Structure"
    "/struktura",       # Lithuanian: "Structure"
]

GATEWAY_KEYWORDS = {
    "seppmail": ["seppmail.cloud", "seppmail.com"],
    "barracuda": ["barracudanetworks.com", "barracuda.com"],
    "trendmicro": ["tmes.trendmicro.eu", "tmes.trendmicro.com"],
    "hornetsecurity": ["hornetsecurity.com"],
    "proofpoint": ["ppe-hosted.com"],
    "sophos": ["hydra.sophos.com"],
}

# Baltic ISP ASNs (replaces SWISS_ISP_ASNS)
BALTIC_ISP_ASNS: dict[int, str] = {
    # Estonia
    3249: "Telia (EE/LT)",
    2586: "Elisa Eesti",
    3327: "Telia Eesti",
    49604: "Telia Eesti",
    3212: "EENET",
    # Latvia
    5518: "TET (Lattelecom)",
    12578: "Lattelecom",
    12993: "LVRTC",
    2847: "LATNET",
    # Lithuania
    8764: "Telia Lietuva",
    13194: "Bite Lietuva",
    33922: "Cgates",
    15440: "Baltneta",
    61272: "Init (LT)",
    6769: "LITNET",
    # Multi-country
    2588: "Elisa",
}

CONCURRENCY = 20
CONCURRENCY_POSTPROCESS = 10
CONCURRENCY_SMTP = 5

SMTP_BANNER_KEYWORDS = {
    "microsoft": [
        "microsoft esmtp mail service",
        "outlook.com",
        "protection.outlook.com",
    ],
    "google": [
        "mx.google.com",
        "google esmtp",
    ],
    "zone": [
        "zone.eu",
        "zone.ee",
    ],
    "telia": [
        "telia.ee",
        "telia.lt",
    ],
    "aws": [
        "amazonaws",
        "amazonses",
    ],
}
