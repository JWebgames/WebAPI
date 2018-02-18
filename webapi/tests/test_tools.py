"""Test runner for config module"""

from typing import Union, Optional
from unittest import TestCase
import logging
from sys import stdout
from ..tools import cast, real_type, DelayLogFor

class TestRealType(TestCase):
    """Test case for tools.real_type"""

    def test_real_type_optional(self):
        """real type of typing.Optional"""
        fake_type = Optional[int]
        self.assertEqual(real_type(fake_type), int)

    def test_real_type_union(self):
        """real type of typing.Union"""
        fake_type = Union[int, None]
        self.assertEqual(real_type(fake_type), int)

    def test_real_type_builtin(self):
        """real type of builtins"""
        self.assertEqual(int, int)


class TestCast(TestCase):
    """Test case for tools.cast"""
    def test_cast_str_to_int(self):
        """try casting str to int"""
        self.assertEqual(cast(int, "5"), 5)

class TestDelayLogFor(TestCase):
    """Test case for tools.DelayLogFor"""
    def setUp(self):
        """Create a base logger to work on"""
        self.logger = logging.getLogger("test_delay_log")
        self.logger.propagate = False
        self.logger.level = logging.INFO

        handler = logging.StreamHandler(stdout)
        handler.level = logging.WARNING
        self.logger.addHandler(handler)

    def test_delay_log_buffer(self):
        """Verify the internal buffer"""
        with self.assertLogs(self.logger, level=logging.NOTSET):
            with DelayLogFor(self.logger) as dlf:
                dlf.delayed_handlers[0].level = logging.WARNING  # the assertLogs is doing a mess
                self.logger.debug("debug")
                self.logger.info("info")
                self.logger.warning("warning")

                output = list(map(self.logger.handlers[0].format, dlf.buffer))
                self.assertEqual(output, ["info", "warning"])

    def test_delay_log_output(self):
        """Verify the output"""
        with self.assertLogs(self.logger, level=logging.NOTSET) as assert_logger:
            with DelayLogFor(self.logger) as dlf:
                dlf.delayed_handlers[0].level = logging.WARNING  # the assertLogs is doing a mess
                self.logger.debug("debug")
                self.logger.info("info")
                self.logger.warning("warning")
            self.assertEqual(assert_logger.output, ["WARNING:test_delay_log:warning"])
