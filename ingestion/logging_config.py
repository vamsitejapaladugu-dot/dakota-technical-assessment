"""Single logging configuration shared by ingestion, orchestration glue, and reporting.

One consistent line format across components makes multi-service logs greppable:
    2026-07-02 14:03:11 INFO eia_client run_id=... message key=value
"""

import logging

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if root.handlers:  # idempotent: safe to call from multiple entry points
        return
    logging.basicConfig(level=level, format=_FORMAT)
    # Third-party chatter that drowns out pipeline signal at INFO.
    logging.getLogger("urllib3").setLevel(logging.WARNING)
