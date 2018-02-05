from collections import ChainMap, namedtuple
from typing import NamedTuple, Optional, Union
from argparse import ArgumentParser
from pathlib import Path
from os import environ
from sys import argv
from yaml import load as yaml_load
from exceptions import ConfigOptionTypeError,\
                       ConfigUnknownOptionError,\
                       ConfigMissingOptionError


class WebAPIConfig(NamedTuple):
    HOST: str
    PORT: int
    JWT_SECRET: str


class PostgresConfig(NamedTuple):
    DSN: Optional[str] = None
    HOST: Optional[str] = None
    PORT: Optional[int] = None
    USER: Optional[str] = None
    DATABASE: Optional[str] = None
    PASSWORD: Optional[str] = None
    SSL: Optional[bool] = None


def cast(typ, val):
    return real_type(typ)(val)


def real_type(typ):
    if typ.__class__ in [Union.__class__, Optional.__class__]:
        return typ.__args__[0]
    else:
        return typ


Triple = namedtuple("Triple", ["name", "prefix", "block"])
triples = [
    Triple("webapi", "WG_API_", WebAPIConfig),
    Triple("postgres", "PG", PostgresConfig)
]

webapi: WebAPIConfig
postgres: PostgresConfig
def load():
    cli = load_from_cli()
    env = load_from_environ()
    yml = load_from_file()
    
    for name, _, block in triples:
        config = ChainMap(cli.get(name, {}), env.get(name, {}), yml.get(name, {}))
        validate_config(name, block, config)
        globals()[name] = block(**config)


def load_from_file():
    with Path("config.yml").open() as yaml_file:
        yaml_config = yaml_load(yaml_file)

    for name, _, block in triples:
        for key in set(block._fields) & set(yaml_config[name]):
            if yaml_config[name][key] is not None:
                yaml_config[name][key] = cast(block._field_types[key], yaml_config[name][key])
    
    return yaml_config


def load_from_environ():
    environ_config = {}
    for name, prefix, block in triples:
        environ_config[name] = {}
        for key in block._fields:
            value = environ.get(prefix + key)
            if value:
                environ_config[name][key] = cast(block._field_types[key], value)
    
    return environ_config


def load_from_cli():
    parser = ArgumentParser(description="Webgames Web API for managing games")
    for name, prefix, block in triples:
        name_lower = name.lower()
        for key in block._fields:
            parser.add_argument("--%s_%s" % (name_lower, key.lower()),
                                type=real_type(block._field_types[key]),
                                action="store")
    return parser.parse_args().__dict__


def validate_config(name, block, config) -> None:
    """Raise ConfigError for invalids, missings or unknowns options"""

    for key, value in config.items():
        if key not in block._fields:
            raise ConfigUnknownOptionError(key, name)

        if "Union" in repr(block._field_types[key]):
            types = block._field_types[key].__args__ 
        else:
            types = block._field_types[key]
        if not isinstance(value, types):
            raise ConfigOptionTypeError(key, name, type(value))

    missings = set(block._fields) - config.keys()
    if missings:
        raise ConfigMissingOptionError(missings, name)


if __name__ == "__main__":
    load()
    for config in [webapi, postgres]:
        print(config)
