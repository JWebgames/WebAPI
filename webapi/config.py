from collections import ChainMap
from PyYAML import load as yaml_load
from typing import NamedTuple, Optional
from pathlib import Path
from exceptions import ConfigOptionTypeError, ConfigUnknownOption


class WebAPIConfig(NamedTuple):
    HOST: str = "localhost"
    PORT: int = 22645
    JWT_SECRET: str

    def __str__(self):
        return "webapi"


class PostgresConfig(NamedTuple):
    DNS: Optional[str] = None
    HOST: Optional[str] = None
    PORT: Optional[int] = None
    USER: Optional[str] = None
    DATABASE: Optional[str] = None
    PASSWORD: Optional[str] = None
    SSL: Optional[bool] = None

    def __str__(self):
        return "postgres"


webapi: WebAPIConfig
postgres: PostgresConfig
def load():
    global webapi, postgres

    with Path("config.yml").open() as yaml_file:
        yaml_config = yaml_load(yaml_file)

    webapi_yaml_config = yaml_config["webapi"]
    check(WebAPIConfig, webapi_yaml_config)
    webapi = WebAPIConfig(**webapi_yaml_config)
    
    postgres_yaml_config = yaml_config["postgres"]
    check(PostgresConfig, postgres_yaml_config)
    postgres = PostgresConfig(**postgres_yaml_config)


def check(block, yaml_config):
    """Verify the configuration file against the stored configuration template
    
    Raises:
        """
    for key, value in yaml_config.items():
        if key not in block._fields:
            raise ConfigUnknownOption(key, block)

        if not isinstance(value, block._field_types[key]):
            raise ConfigOptionTypeError(key, block, type(value))