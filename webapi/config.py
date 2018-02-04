from collections import ChainMap
from typing import NamedTuple, Optional
from argparse import ArgumentParser
from pathlib import Path
from yaml import load as yaml_load
from exceptions import ConfigOptionTypeError,
                       ConfigUnknownOptionError,
                       ConfigMissingOptionError


class WebAPIConfig(NamedTuple):
    HOST: str
    PORT: int
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
    config = ChainMap(load_from_file(), load_from_environ(), load_from_cli())

    validate_config(WebAPIConfig, config["webapi"])
    validate_config(PostgresConfig, config["postgres"])

    global webapi, postgres
    webapi = WebAPIConfig(**config["webapi"])
    postgres = PostgresConfig(**config["postgres"])


def load_from_file():
    with Path("config.yml").open() as yaml_file:
        return yaml_load(yaml_file)


def load_from_environ():
    pass


def load_from_cli():
    parser = ArgumentParser(description="Webgames Web API for managing games")


def validate_config(block, yaml_config) -> None:
    """Raise ConfigError for invalids, missings or unknowns options"""

    for key, value in yaml_config.items():
        if key not in block._fields:
            raise ConfigUnknownOptionError(key, block)

        if not isinstance(value, block._field_types[key]):
            raise ConfigOptionTypeError(key, block, type(value))

    missings = set(block._fields) - yaml_config.keys()
    if missings:
        raise ConfigMissingOptionError(missings, block)
