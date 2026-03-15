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
    "example.dk",
    "example.ad",
    "example.lu",
    "example.be",
    "example.at",
    "example.cz",
    "example.is",
    "example.es",
    "example.fr",
    "example.pl",
    "example.pt",
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
    "/kontaktid",  # Estonian
    "/kontakti",  # Latvian
    "/kontaktai",  # Lithuanian
    "/kontakt/",
    "/contact/",
    "/meist",  # Estonian: "About us"
    "/par-mums",  # Latvian: "About us"
    "/apie-mus",  # Lithuanian: "About us"
    "/struktuur",  # Estonian: "Structure"
    "/struktura",  # Lithuanian: "Structure"
    "/impressum",  # German
    "/service/kontakt",  # German
    "/hafa-samband",  # Icelandic: "Contact"
    "/um-sveitarfelagid",  # Icelandic: "About the municipality"
    "/contacto",  # Spanish
    "/contacta",  # Spanish (Catalan)
    "/sede-electronica",  # Spanish: "Electronic office"
    "/nous-contacter",  # French: "Contact us"
    "/contactez-nous",  # French: "Contact us"
    "/mentions-legales",  # French: "Legal notice"
    "/kontakt",  # Polish: "Contact" (same as German)
    "/bip",  # Polish: "Public Information Bulletin"
    "/contactos",  # Portuguese: "Contacts"
    "/contacte-nos",  # Portuguese: "Contact us"
    "/municipio",  # Portuguese: "Municipality"
]

GATEWAY_KEYWORDS = {
    "seppmail": ["seppmail.cloud", "seppmail.com"],
    "barracuda": ["barracudanetworks.com", "barracuda.com"],
    "trendmicro": ["tmes.trendmicro.eu", "tmes.trendmicro.com"],
    "hornetsecurity": ["hornetsecurity.com"],
    "proofpoint": ["ppe-hosted.com", "pphosted.com"],
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
    "simnet": ["simnet.is"],
    "skyggnir": ["skyggnir.is"],
    "siminn": ["spamvorn.internet.is"],
    "telefonica": ["correolimpio.telefonica.es"],
    "cdmon": ["cdmon.net", "cdmon.com"],
    "vadesecure": ["vadesecure.com"],
    "mailinblack": ["mailinblack.com"],
    "mimecast": ["mimecast.com"],
    "mailcontrol": ["mailcontrol.com"],
    "security-mail": ["security-mail.net"],
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
    # Denmark
    3292: "TDC/Nuuday (DK)",
    3308: "TDC NET (DK)",
    # Andorra
    6752: "Andorra Telecom (AD)",
    # Luxembourg
    6661: "POST Luxembourg (LU)",
    2602: "Restena (LU)",
    9008: "Cegecom (LU)",
    8632: "Proximus Luxembourg (LU)",
    34683: "LuxNetwork (LU)",
    # Belgium
    9208: "Proximus (BE)",
    5432: "Proximus/Skynet (BE)",
    15383: "Computerland (BE)",
    29222: "Infradata (BE)",
    6848: "Telenet (BE)",
    # Austria
    8447: "A1 Telekom Austria (AT)",
    8412: "Magenta Telekom (AT)",
    45012: "A1 Telekom Austria (AT)",
    8339: "Medialog (AT)",
    1764: "Next Layer (AT)",
    12605: "Salzburg AG (AT)",
    6830: "Liberty Global/UPC (AT)",
    29081: "OpenBusiness (AT)",
    1853: "ACOnet/ACONET (AT)",
    12762: "SPARDAT (AT)",
    31543: "myNet (AT)",
    42572: "Nessus (AT)",
    47692: "Nessus (AT)",
    25575: "domainfactory (AT)",
    21013: "Stadtwerke Kufstein (AT)",
    199217: "Linz Strom GAS (AT)",
    6798: "SIL/Salzburg Internet (AT)",
    # Czechia
    16019: "Vodafone CZ",
    2852: "CESNET (CZ)",
    13036: "T-Mobile CZ",
    43542: "4ISP (CZ)",
    5610: "O2 CZ",
    21430: "Forpsi (CZ)",
    12570: "Czech On Line (CZ)",
    5577: "root.cz (CZ)",
    35592: "CZNIC/Coolhousing (CZ)",
    15685: "Casablanca INT (CZ)",
    # France
    16276: "OVH (FR)",
    12876: "Online/Scaleway (FR)",
    3215: "Orange (FR)",
    15557: "LDCom/SFR (FR)",
    5410: "Bouygues Telecom (FR)",
    16347: "Inherent (FR)",
    20756: "Nameshield (FR)",
    # Poland
    5617: "Orange Polska (PL)",
    12741: "Netia (PL)",
    8308: "NASK (PL)",
    197226: "NASK (PL)",
    21021: "Multimedia Polska (PL)",
    6714: "OPL/TP SA (PL)",
    15694: "Atman (PL)",
    29522: "Nazwa.pl (PL)",
    16138: "Interia.pl (PL)",
    50840: "home.pl (PL)",
    48850: "Zenbox (PL)",
    43939: "PERN (PL)",
    20804: "Exatel (PL)",
    61141: "AZ.pl (PL)",
    201053: "EPSI (PL)",
    12824: "home.pl (PL)",
    15967: "Netart Group (PL)",
    31229: "Beyond.pl (PL)",
    34360: "Ogicom (PL)",
    50599: "Dataspace (PL)",
    48896: "dhosting.pl (PL)",
    47544: "IQ.pl (PL)",
    60713: "TARRCI (PL)",
    203417: "LH.pl (PL)",
    8267: "Cyfronet (PL)",
    42503: "Oktawave (PL)",
    48707: "Aftermarket.pl (PL)",
    41079: "CF Gdańsk (PL)",
    13110: "INEA (PL)",
    # Portugal
    3243: "MEO/Altice (PT)",
    2860: "NOS (PT)",
    12353: "Vodafone PT",
    8657: "PT Comunicações (PT)",
    15525: "MEO (PT)",
    39729: "Claranet PT",
    47787: "Ar Telecom (PT)",
    60729: "Nowo Communications (PT)",
    25291: "Adclick (PT)",
    # Iceland
    6677: "Simnet/Vist (IS)",
    29689: "Skyggnir (IS)",
    44925: "1984 Hosting (IS)",
    12969: "Síminn (IS)",
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
