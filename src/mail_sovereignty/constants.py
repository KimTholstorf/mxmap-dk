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
ZONE_KEYWORDS = ["zone.eu", "zone.ee", "zoneit.eu", "zonemx.eu"]
TELIA_KEYWORDS = ["telia.ee", "telia.lt", "telia.lv", "telia.com"]
TET_KEYWORDS = ["tet.lv"]
ELKDATA_KEYWORDS = ["elkdata.ee"]

PROVIDER_KEYWORDS = {
    "microsoft": MICROSOFT_KEYWORDS,
    "google": GOOGLE_KEYWORDS,
    "aws": AWS_KEYWORDS,
    "zone": ZONE_KEYWORDS,
    "telia": TELIA_KEYWORDS,
    "tet": TET_KEYWORDS,
    "elkdata": ELKDATA_KEYWORDS,
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
    "example.no",
    "example.se",
    "example.de",
    "kommune.no",
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
    "/impressum",       # German
    "/service/kontakt", # German
]

GATEWAY_KEYWORDS = {
    "seppmail": ["seppmail.cloud", "seppmail.com"],
    "barracuda": ["barracudanetworks.com", "barracuda.com"],
    "trendmicro": ["tmes.trendmicro.eu", "tmes.trendmicro.com"],
    "hornetsecurity": ["hornetsecurity.com"],
    "proofpoint": ["ppe-hosted.com"],
    "sophos": ["hydra.sophos.com"],
    "fortimail": ["fortimail", "fortimailcloud.com"],
    "secmail": ["secmail.com"],
    "d-fence": ["d-fence.eu"],
    "edelkey": ["edelkey.net"],
    "ippnet": ["ippnet.fi"],
    "garmtech": ["garmtech.com", "garmtech.net"],
    "cisco-ironport": ["iphmx.com"],
    "staysecure": ["staysecuregroup.com"],
    "mailanyone": ["mailanyone.net", "electric.net"],
    "comendo": ["comendosystems.com"],
    "heimdal": ["heimdalsecurity.com"],
    "messagelabs": ["messagelabs.com"],
    "nospamproxy": ["nospamproxy.de", "as-scan.de"],
    "antispameurope": ["antispameurope.com"],
    "retarus": ["retarus.com"],
    "psmanaged": ["psmanaged.com"],
}

# Local ISP ASNs (replaces SWISS_ISP_ASNS)
LOCAL_ISP_ASNS: dict[int, str] = {
    # Estonia
    3249: "Telia (EE/LT)",
    2586: "Elisa Eesti",
    3327: "Telia Eesti",
    49604: "Telia Eesti",
    3212: "EENET",
    216263: "Radicenter (EE)",
    # Latvia
    5518: "TET (Lattelecom)",
    12578: "Lattelecom",
    12993: "LVRTC",
    2847: "LATNET",
    5538: "SigmaNet (LV)",
    43513: "Nano IT (LV)",
    29600: "Latvenergo/IVIKS (LV)",
    206111: "LINKIT (LV)",
    # Lithuania
    8764: "Telia Lietuva",
    43811: "Telia Lietuva",
    13194: "Bite Lietuva",
    33922: "Cgates",
    15440: "Baltneta",
    61272: "Init (LT)",
    6769: "LITNET",
    15419: "LRTC (LT)",
    212531: "Interneto Vizija (LT)",
    # Multi-country
    2588: "Elisa",
    # Finland
    719: "Elisa (FI)",
    1759: "Cinia/SecMail",
    39699: "Lounea",
    198024: "Istekki",
    16086: "Ratkaisutalo",
    215722: "Lapit Oy",
    199087: "Kase Oy",
    29240: "LanMail",
    3238: "Ålands Telekommunikation",
    # Norway
    29492: "Eidsiva/Hedmark IKT (NO)",
    199900: "BedSys (NO)",
    8542: "Eviny (NO)",
    210615: "Alta Kommune (NO)",
    207464: "Varanger Kraft (NO)",
    29695: "Altibox (NO)",
    # Sweden
    3301: "Telia Sweden",
    28954: "Fiberstaden (SE)",
    12552: "GlobalConnect (SE)",
    29672: "Stockholm stad (SE)",
    198568: "Atea (SE)",
    202780: "Advania (SE)",
    60053: "Habo kommun (SE)",
    206387: "BLL (SE)",
    205574: "Borås stad (SE)",
    206114: "Hofors kommun (SE)",
    25417: "Ljusnet (SE)",
    1257: "Tele2 (SE)",
    6782: "Bdnet (SE)",
    # Germany
    553: "BelWü (DE)",
    680: "DFN (DE)",
    3209: "Vodafone (DE)",
    3320: "Deutsche Telekom (DE)",
    6687: "communelink (DE)",
    8560: "IONOS/1&1 (DE)",
    8767: "M-net (DE)",
    8881: "Versatel/1&1 (DE)",
    9063: "Saarland IT (DE)",
    9145: "EWE TEL (DE)",
    9197: "ekom21 (DE)",
    12693: "DIKOM Brandenburg (DE)",
    13045: "KDO Niedersachsen (DE)",
    13101: "TNG Stadtnetz (DE)",
    16097: "TELEPORT (DE)",
    20810: "ekom21 (DE)",
    21473: "Pfalzkom (DE)",
    24940: "Hetzner (DE)",
    33846: "Dataport (DE)",
    34011: "AKDB Bayern (DE)",
    34928: "regio iT (DE)",
    42652: "eCube/Saarland IT (DE)",
    48049: "ITK Rheinland (DE)",
    50964: "Komm.ONE (DE)",
    61352: "KISA Sachsen (DE)",
    198435: "DVZ-MV (DE)",
    201318: "Südwestfalen IT (DE)",
    210849: "ITK Rheinland (DE)",
    24961: "nol-IS/myLoc (DE)",
    202577: "KDVZ Frechen (DE)",
    8351: "SIS Schwerin (DE)",
    60123: "WTnet Wuppertal (DE)",
    8422: "NetCologne (DE)",
    16024: "GELSEN-NET (DE)",
    12897: "ENTEGA (DE)",
    8319: "KGRZ Fulda (DE)",
    30238: "Trier-net (DE)",
    29014: "IN-Ulm (DE)",
    15598: "QSC/q.beyond (DE)",
    15817: "WOBCOM (DE)",
    34788: "NM-NET (DE)",
    8820: "TAL.de (DE)",
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
    "elkdata": [
        "elkdata.ee",
    ],
}
