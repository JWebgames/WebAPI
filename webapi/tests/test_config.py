from typing import Optional, Union
from collections import ChainMap
from unittest import TestCase

from ..config import WebAPIConfig,\
                     PostgresConfig,\
                     triples,\
                     get_default,\
                     validate_config

from ..exceptions import ConfigMissingOptionError,\
                         ConfigOptionTypeError,\
                         ConfigUnknownOptionError


class TestValidateConfig(TestCase):
    default_config = get_default()

    def test_default_values(self):
        for name, _, block in triples:
            self.assertIsNone(
                validate_config(name, block, self.default_config[name]))

    def test_missing_option(self):
        self.assertRaises(
            ConfigMissingOptionError, validate_config, "webapi", WebAPIConfig, {})

    def test_invalid_option_type_one_valid(self):
        config = ChainMap({"HOST": None}, self.default_config["webapi"])
        self.assertRaises(
            ConfigOptionTypeError, validate_config, "webapi", WebAPIConfig, config)

    def test_invalid_option_type_multiple_valids(self):
        config = ChainMap({"DSN": 5}, self.default_config["postgres"])
        self.assertRaises(
            ConfigOptionTypeError, validate_config, "postgres", PostgresConfig, config)

    def test_unknown_option(self):
        config = ChainMap({"DSN": None}, self.default_config["webapi"])
        self.assertRaises(
            ConfigUnknownOptionError, validate_config, "webapi", WebAPIConfig, config)
        