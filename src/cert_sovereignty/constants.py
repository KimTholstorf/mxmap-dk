"""Scan configuration constants for the cert_sovereignty pipeline."""

from __future__ import annotations

DEFAULT_PORT = 443
TLS_TIMEOUT = 15  # seconds
SEMAPHORE_LIMIT = 40  # concurrent TLS scans
HTTP_TIMEOUT = 30  # seconds for HTTP requests (CT log queries)
MAX_CT_ENTRIES = 50  # max crt.sh results per domain
