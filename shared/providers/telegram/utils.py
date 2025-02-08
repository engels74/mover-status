# shared/providers/telegram/utils.py

"""Telegram utility functions."""

from typing import List
from urllib.parse import urlparse

from .constants import ALLOWED_DOMAINS


def validate_url(url: str, allowed_domains: List[str] = ALLOWED_DOMAINS) -> bool:
    """Validate if URL belongs to allowed Telegram domains.

    Args:
        url: URL to validate
        allowed_domains: List of allowed domains

    Returns:
        bool: True if URL is valid
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        return any(domain.endswith(d) for d in allowed_domains)
    except Exception:
        return False
