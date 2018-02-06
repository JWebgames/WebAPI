from typing import Union, Optional
from unittest import TestCase
from tools import cast, real_type


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