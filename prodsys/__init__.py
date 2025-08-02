import logging

import importlib_metadata
import toml
from prodsys.conf.logging_config import set_logging
from prodsys.models import (
    dependency_data,
    processes_data,
    product_data,
    queue_data,
    resource_data,
    scenario_data,
    sink_data,
    source_data,
    state_data,
    time_model_data,
    production_system_data
)
from prodsys.models.production_system_data import ProductionSystemData

from prodsys.util import post_processing  # , optimization_util
from prodsys.simulation import runner

logger = logging.getLogger(__name__)


def get_version() -> str:
    try:
        return importlib_metadata.version("prodsys")
    except:
        logger.info(
            "Could not find version in package metadata. Trying to read from pyproject.toml"
        )
    try:
        pyproject = toml.load("pyproject.toml")
        return pyproject["tool"]["poetry"]["version"]
    except:
        logger.error(
            "Could not find pyproject.toml file. Trying to read from poetry.lock"
        )
    raise ModuleNotFoundError(
        "Could not find version in package metadata or pyproject.toml"
    )


VERSION = get_version()
