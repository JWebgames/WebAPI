from typing import Union, Optional
from unittest import TestCase
from ..tools import cast, real_type, DelayLogFor
import logging
from sys import stdout

class TestRealType(TestCase):
    def test_real_type_optional(self):
        fake_type = Optional[int]
        self.assertEqual(real_type(fake_type), int)

    def test_real_type_union(self):
        fake_type = Union[int, None]
        self.assertEqual(real_type(fake_type), int)

    def test_real_type_builtin(self):
        self.assertEqual(int, int)


class TestCast(TestCase):
    def test_cast_str_to_int(self):
        self.assertEqual(cast(int, "5"), 5)

class TestDelayLogFor(TestCase):
    def setUp(self):
        self.logger = logging.getLogger("test_delay_log")
        self.logger.propagate = False
        self.logger.level = logging.INFO

        handler = logging.StreamHandler(stdout)
        handler.level = logging.WARNING
        self.logger.addHandler(handler)

    def test_delay_log_buffer(self):
        with self.assertLogs(self.logger, level=logging.NOTSET) as cm:
            with DelayLogFor(self.logger) as dlf:
                dlf.delayed_handlers[0].level = logging.WARNING  # the assertLogs is doing a mess
                self.logger.debug("debug")
                self.logger.info("info")
                self.logger.warning("warning")

                output = list(map(self.logger.handlers[0].format, dlf.buffer))
                self.assertEqual(output, ["info", "warning"])

    def test_delay_log_output(self):
        with self.assertLogs(self.logger, level=logging.NOTSET) as cm:
            with DelayLogFor(self.logger) as dlf:
                dlf.delayed_handlers[0].level = logging.WARNING  # the assertLogs is doing a mess
                self.logger.debug("debug")
                self.logger.info("info")
                self.logger.warning("warning")

        self.assertEqual(cm.output, ["WARNING:test_delay_log:warning"])
