"""
Configuration manager

Load and parse the configuration given by multiple sources and expose
them in one merged NamedTuple per configuration block
"""

import ipaddress
from argparse import ArgumentParser
from collections import ChainMap, namedtuple, defaultdict, Iterable
from logging import getLogger
from operator import attrgetter, methodcaller
from os import environ
from sys import argv
from typing import NamedTuple, Optional, Union, Dict, List, Tuple, Any, NewType

from yaml import safe_load as yaml_load, dump as yaml_dump

from .exceptions import ConfigOptionTypeError,\
                        ConfigUnknownOptionError,\
                        ConfigMissingOptionError
from .tools import cast, get_package_path, find

logger = getLogger(__name__)

Source = NewType("Source", Dict[str, Dict[str, Any]])
Triple = namedtuple("Triple", ["name", "prefix", "block"])
triples = []
def register(name, prefix=None):
    """Set name and prefix for a config block"""
    if prefix is None:
        prefix = name.upper() + "_"
    def wrapped(block):
        """Register a config block withe its name and prefix"""
        triples.append(Triple(name, prefix, block))
        return block
    return wrapped


webapi: "WebAPIConfig"
@register("webapi")
class WebAPIConfig(NamedTuple):
    """WebAPI configuration block"""
    HOST: str = "localhost"
    PORT: int = 22548
    JWT_SECRET: str = "super-secret-password"
    JWT_EXPIRATION_TIME: str = "12h"
    LOG_LEVEL: str = "WARNING"
    PRODUCTION: bool = False
    REVERSE_PROXY_IPS: Optional[List[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]]] = None


postgres: "PostgresConfig"
@register("postgres", "PG")
class PostgresConfig(NamedTuple):
    """Postgres configuration block"""
    DSN: Optional[str] = None
    HOST: Optional[str] = None
    PORT: Optional[int] = None
    USER: Optional[str] = None
    DATABASE: Optional[str] = None
    PASSWORD: Optional[str] = None


redis: "RedisConfig"
@register("redis")
class RedisConfig(NamedTuple):
    """Redis configuration block"""
    DSN: Optional[str] = None
    HOST: Optional[str] = None
    PORT: Optional[int] = None
    DATABASE: Optional[str] = None
    PASSWORD: Optional[str] = None


def safe_assign(source: Source, block: NamedTuple,
                blockname: str, field: str, value: Any) -> None:
    """Cast the value and store the result in the source"""
    source[blockname][field] = cast(value, block._field_types[field])


def get_default():
    """Get the configuration from the source code"""
    return {name: dict(block()._asdict()) for name, _, block in triples}


def get_from_cli():
    """Get the configuration from the command line"""
    sentinel = object()
    parser = ArgumentParser(prog="{} {}".format(argv[0], argv[1]),
                            description="Webgames Web API for managing games",
                            argument_default=sentinel)
    for name, _, block in triples:
        name_lower = name.lower()
        for key in block._fields:
            parser.add_argument("--%s_%s" % (name_lower, key.lower()),
                                action="store")
    cli = parser.parse_args(argv[2:])

    prefixes = list(map(attrgetter("name"), triples))
    cli_config = defaultdict(dict)
    for key, value in cli.__dict__.items():
        if value is sentinel:
            continue
        pos = key.find("_")
        if pos < 0 or key[:pos] not in prefixes:
            continue
        name = key[:pos]
        field = key[pos+1:].upper()
        block = find(lambda fs: fs[0] == name, triples).block
        safe_assign(cli_config, block, name, field, value)

    return cli_config


def get_from_env():
    """Get the configuration from the environement variables"""
    environ_config = defaultdict(dict)
    for name, prefix, block in triples:
        for field in block._fields:
            value = environ.get(prefix.upper() + field)
            if value:
                safe_assign(environ_config, block, name, field, value)

    return environ_config


def get_from_yml():
    """Get the configuration from the YAML configuration file"""
    with get_package_path().joinpath("config.yml").open() as yaml_file:
        yaml_config = yaml_load(yaml_file)

    for name, _, block in triples:
        for key in set(block._fields) & set(yaml_config[name]):
            value = yaml_config[name][key]
            if value is not None:
                safe_assign(yaml_config, block, name, key, value)

    return yaml_config


def load_all_sources() -> List[dict]:
    """Load from different sources"""
    cli = get_from_cli()
    env = get_from_env()
    yml = get_from_yml()
    return [cli, env, yml]


def validate(name: str, block: NamedTuple, config: dict) -> None:
    """Look for invalid value type and missing/unknow fields"""

    composite_classes = [Union.__class__, List.__class__, Tuple.__class__]
    for key, value in config.items():
        if key not in block._fields:
            raise ConfigUnknownOptionError(key, name)

        # Extract types from composite types (deep)
        types = [block._field_types[key]]
        while True:
            if types[-1].__class__ in composite_classes:
                types.extend(reversed(types[-1].__args__))
            else:
                break
        types = [typ for typ in types
                 if typ.__class__ not in composite_classes]

        if isinstance(value, list):
            value = value[0]

        if not isinstance(value, tuple(types)):
            raise ConfigOptionTypeError(key, name, types, type(value))

    missings = set(block._fields) - config.keys()
    if missings:
        raise ConfigMissingOptionError(missings, name)


def merge_sources(*sources) -> List[Tuple[str, NamedTuple]]:
    """Merge and validate all sources against every config block"""
    for name, _, block in triples:
        merged_config = ChainMap(*map(methodcaller("get", name, {}), sources))
        validate(name, block, merged_config)
        yield name, block(**merged_config)


def expose_block(name: str, block: NamedTuple) -> None:
    """Expose a given block at module level"""
    globals()[name] = block


def expose_default() -> None:
    """Expose the default configuration"""
    default_config = get_default()
    for name, _, block in triples:
        expose_block(name, block(**default_config[name]))


def load_merge_validate_expose() -> None:
    """All at once !!! :D"""
    sources = load_all_sources()
    for name, block in merge_sources(*sources):
        expose_block(name, block)


def export_default_config() -> None:
    """Print the default yaml configuration"""
    print(yaml_dump(get_default(), default_flow_style=False))


def show() -> None:
    """Nice output of the current configuration"""

    # Show configuration from each source
    cli, env, yml = load_all_sources()
    for sourcename, source in [("cli", cli), ("env", env), ("yml", yml)]:
        for blockname, block in source.items():
            print("+{!s:-^63}+".format("{}:{}".format(sourcename, blockname)))
            for key, value in block.items():
                if not isinstance(value, str) and isinstance(value, Iterable):
                    print("| {!s:<30}|{!s:>30} |".format(key, value[0]))
                    for element in value[1:]:
                        print("|{}|{!s:>30} |".format(" " * 31, element))
                else:
                    print("| {!s:<30}|{!s:>30} |".format(key, value))

    # Show merge and validated configuration
    for name, block in merge_sources(cli, env, yml):
        print("+{:-^63}+".format("Merged:" + name))
        for key, value in block._asdict().items():
            if not isinstance(value, str) and isinstance(value, Iterable):
                print("| {!s:<30}|{!s:>30} |".format(key, value[0]))
                for element in value[1:]:
                    print("|{}|{!s:>30} |".format(" " * 31, element))
            else:
                print("| {!s:<30}|{!s:>30} |".format(key, value))
    print("+{}+".format("-" * 63))
