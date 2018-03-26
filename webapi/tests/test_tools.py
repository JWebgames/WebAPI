"""Test runner for config module"""

import logging
from ipaddress import IPv4Address, IPv6Address
from sys import stdout
from typing import Union, List
from unittest import TestCase
from ..tools import cast, DelayLogFor

class TestCast(TestCase):
    """Test case for tools.cast"""
    def test_cast_str_to_int(self):
        """try casting str to int"""
        self.assertEqual(cast("5", int), 5)

    def test_cast_hard(self):
        """try smth very difficult"""
        the_type = List[Union[IPv4Address, IPv6Address]]

        self.assertEqual(cast(["127.0.0.1", "fe80::"], the_type),
                         [IPv4Address("127.0.0.1"), IPv6Address("fe80::")])

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
