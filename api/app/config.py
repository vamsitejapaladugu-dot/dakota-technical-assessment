from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Service configuration, environment-driven with safe local defaults.

    SEED controls all synthetic generation. Keeping it fixed by default means
    two evaluators running the project independently see identical data and
    an identical report.
    """

    seed: int = 42
    forecast_noise_pct: float = 0.04   # stddev of forecast error, as a fraction of level
    max_forecast_days: int = 90

    model_config = {"env_prefix": "ENRICHMENT_"}


settings = Settings()
