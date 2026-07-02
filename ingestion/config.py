"""Environment-driven configuration. One place to read os.environ; everything
downstream receives a frozen Config object."""

import os
from dataclasses import dataclass, field


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Config:
    eia_api_key: str = field(default_factory=lambda: os.environ.get("EIA_API_KEY", ""))
    eia_base_url: str = field(
        default_factory=lambda: os.environ.get("EIA_BASE_URL", "https://api.eia.gov/v2")
    )
    database_url: str = field(
        default_factory=lambda: os.environ.get(
            "DATABASE_URL", "postgresql://dakota:dakota@localhost:5432/energy"
        )
    )
    enrichment_api_url: str = field(
        default_factory=lambda: os.environ.get("ENRICHMENT_API_URL", "http://localhost:8001")
    )
    eia_respondents: tuple[str, ...] = field(
        default_factory=lambda: _split_csv(os.environ.get("EIA_RESPONDENTS", "ERCO,CISO,MISO"))
    )
    backfill_days: int = field(default_factory=lambda: int(os.environ.get("BACKFILL_DAYS", "30")))
    incremental_lookback_hours: int = field(
        default_factory=lambda: int(os.environ.get("INCREMENTAL_LOOKBACK_HOURS", "72"))
    )

    @property
    def demo_mode(self) -> bool:
        """True when no EIA key is configured; the EIA client then synthesizes
        deterministic sample data so the pipeline remains fully evaluable."""
        return not self.eia_api_key


def load_config() -> Config:
    return Config()
