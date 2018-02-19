"""Test runner for config module"""

from collections import ChainMap
from unittest import TestCase

from ..config import WebAPIConfig,\
                     PostgresConfig,\
                     triples,\
                     get_default,\
                     validate,\
                     merge_sources
from ..exceptions import ConfigMissingOptionError,\
                         ConfigOptionTypeError,\
                         ConfigUnknownOptionError


class TestValidateConfig(TestCase):
    """Test case for config.validate_cofig"""

    default_config = get_default()

    def test_default_values(self):
        """Validate against default values"""
        for name, _, block in triples:
            self.assertIsNone(
                validate(name, block, self.default_config[name]))

    def test_missing_option(self):
        """Should fail for any missing field"""
        self.assertRaises(
            ConfigMissingOptionError, validate, "webapi", WebAPIConfig, {})

    def test_invalid_option_type(self):
        """Should fail for invalid type (without Union/Optionnal)"""
        config = ChainMap({"HOST": 5}, self.default_config["webapi"])
        self.assertRaises(
            ConfigOptionTypeError, validate, "webapi", WebAPIConfig, config)

    def test_invalid_option_type_involving_typing(self):
        """Should fail for invalid type (with Union/Optionnal)"""
        config = ChainMap({"DSN": 5}, self.default_config["postgres"])
        self.assertRaises(
            ConfigOptionTypeError, validate, "postgres", PostgresConfig, config)

    def test_unknown_option(self):
        """Should fail for unknow field"""
        config = ChainMap({"foo": None}, self.default_config["webapi"])
        self.assertRaises(
            ConfigUnknownOptionError, validate, "webapi", WebAPIConfig, config)

class TestMergeSources(TestCase):
    def test_merged_default_is_default(self):
        gen = merge_sources(get_default(), {})
        for name, _, block in triples:
            mname, mblock = next(gen)
            self.assertEqual(mblock, block())
