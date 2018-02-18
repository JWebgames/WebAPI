"""
Configuration manager

Load and parse the configuration given by multiple sources and expose
them in one merged NamedTuple per configuration block
"""

from argparse import ArgumentParser
from collections import ChainMap, namedtuple
from logging import getLogger
from os import environ
from typing import NamedTuple, Optional
from yaml import safe_load as yaml_load, dump as yaml_dump

from .exceptions import ConfigOptionTypeError,\
                        ConfigUnknownOptionError,\
                        ConfigMissingOptionError
from .tools import cast, real_type, get_package_path

logger = getLogger(__name__)


class WebAPIConfig(NamedTuple):
    HOST: str = "loclhost"
    PORT: int = 22548
    JWT_SECRET: str = "super-secret-password"
    LOG_LEVEL: str = "WARNING"


class PostgresConfig(NamedTuple):
    DSN: Optional[str] = None
    HOST: Optional[str] = None
    PORT: Optional[int] = None
    USER: Optional[str] = None
    DATABASE: Optional[str] = None
    PASSWORD: Optional[str] = None


class RedisConfig(NamedTuple):
    DSN: Optional[str] = None
    HOST: Optional[str] = None
    PORT: Optional[int] = None
    DATABASE: Optional[str] = None
    PASSWORD: Optional[str] = None


webapi: WebAPIConfig
postgres: PostgresConfig
redis: RedisConfig
Triple = namedtuple("Triple", ["name", "prefix", "block"])
triples = [
    Triple("webapi", "WG_API_", WebAPIConfig),
    Triple("postgres", "PG", PostgresConfig),
    Triple("redis", "REDIS_", RedisConfig)
]


def get_default():
    """Get the configuration from the source code"""
    return {name: dict(block()._asdict()) for name, _, block in triples}


def get_from_cli():
    """Get the configuration from the command line"""
    parser = ArgumentParser(description="Webgames Web API for managing games")
    for name, _, block in triples:
        name_lower = name.lower()
        for key in block._fields:
            parser.add_argument("--%s_%s" % (name_lower, key.lower()),
                                type=real_type(block._field_types[key]),
                                action="store")
    return parser.parse_args().__dict__


def get_from_env():
    """Get the configuration from the environement variables"""
    environ_config = {}
    for name, prefix, block in triples:
        environ_config[name] = {}
        for key in block._fields:
            value = environ.get(prefix + key)
            if value:
                environ_config[name][key] = cast(block._field_types[key], value)

    return environ_config


def get_from_yml():
    """Get the configuration from the YAML configuration file"""
    with get_package_path().joinpath("config.yml").open() as yaml_file:
        yaml_config = yaml_load(yaml_file)

    for name, _, block in triples:
        for key in set(block._fields) & set(yaml_config[name]):
            if yaml_config[name][key] is not None:
                yaml_config[name][key] = cast(block._field_types[key], yaml_config[name][key])

    return yaml_config


def validate_config(name, block, config) -> None:
    """Look for invalid value type and missing/unknow fields"""

    for key, value in config.items():
        if key not in block._fields:
            raise ConfigUnknownOptionError(key, name)

        if "Union" in repr(block._field_types[key]):
            types = block._field_types[key].__args__
        else:
            types = block._field_types[key]
        if not isinstance(value, types):
            raise ConfigOptionTypeError(key, name, types, type(value))

    missings = set(block._fields) - config.keys()
    if missings:
        raise ConfigMissingOptionError(missings, name)


def load_merge_validate_expose():
    """Load from different sources, merge them into one unique source,
    validate the merged source, create one namedtuple per block and
    expose them to be accessible as module variable."""

    logger.info("Loading configuration...")
    logger.debug("Get configuration from command line interface.")
    cli = get_from_cli()
    logger.debug("Get configuration from environment variables.")
    env = get_from_env()
    logger.debug("Get configuration from YAML configuration file.")
    yml = get_from_yml()

    for name, _, block in triples:
        logger.debug("Merge block %s.", name)
        config = ChainMap(cli.get(name, {}), env.get(name, {}), yml.get(name, {}))
        logger.debug("Validate block %s.", name)
        validate_config(name, block, config)
        logger.debug("Expose block %s.", name)
        globals()[name] = block(**config)
    logger.info("Configuration loaded.")


def export_default_config():
    """Replace /config.yml by a new one generated from hardcoded values"""
    with get_package_path().joinpath("config.yml").open("w") as yaml_file:
        yaml_dump(get_default(), yaml_file, default_flow_style=False)
