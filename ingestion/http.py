"""Shared HTTP machinery: session factory, timeouts, and a single retry policy.

Retry policy (deliberately narrow):
  - Retry: 429, any 5xx, connection errors, timeouts -> transient by nature.
  - Never retry other 4xx: a bad API key or malformed request will not fix
    itself; failing fast with a clear message beats burning retry budget.
"""

import logging

import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

logger = logging.getLogger("http")

DEFAULT_TIMEOUT_S = 30


class RetryableHTTPError(Exception):
    """HTTP response that is worth retrying (429 or 5xx)."""


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": "dakota-energy-pipeline/0.1"})
    return session


@retry(
    retry=retry_if_exception_type(
        (RetryableHTTPError, requests.ConnectionError, requests.Timeout)
    ),
    wait=wait_random_exponential(multiplier=1, max=30),
    stop=stop_after_attempt(4),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def get_json(session: requests.Session, url: str, params: dict | None = None) -> dict:
    response = session.get(url, params=params, timeout=DEFAULT_TIMEOUT_S)
    if response.status_code == 429 or response.status_code >= 500:
        raise RetryableHTTPError(f"{response.status_code} from {url}")
    response.raise_for_status()
    return response.json()
