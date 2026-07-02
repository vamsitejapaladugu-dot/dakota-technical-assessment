"""Dagster resources: thin, env-driven wrappers so assets stay testable.

Assets receive these resources via injection, which is what lets the test
suite swap in fakes without any Docker or database.
"""

from pathlib import Path

from dagster import ConfigurableResource
from dagster_dbt import DbtCliResource

from ingestion.config import Config, load_config


class PipelineConfigResource(ConfigurableResource):
    """Exposes the shared ingestion Config to assets."""

    def get(self) -> Config:
        return load_config()


DBT_PROJECT_DIR = Path(__file__).joinpath("..", "..", "dbt").resolve()

dbt_resource = DbtCliResource(project_dir=str(DBT_PROJECT_DIR))
