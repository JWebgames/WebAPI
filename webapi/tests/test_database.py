"""Test runner for database module"""

from asyncio import get_event_loop
from unittest import TestCase
from .. import server  # avoid diamond import
from ..tools import generate_token
from ..config import webapi
from ..database import InMemory

TOKEN = generate_token(key=webapi.JWT_SECRET)

class TestInMemoryTokenRevocationList(TestCase):
    """Test case the InMemory KVS Token Revocation List"""

    def setUp(self):
        self.kvs = InMemory()

    def test_token_not_revoked(self):
        """Test token not revoked"""
        coro = self.kvs.is_token_revoked(TOKEN)
        is_revoked = get_event_loop().run_until_complete(coro)
        self.assertFalse(is_revoked)

    def test_token_revoked(self):
        """Test token revoked"""
        coro = self.kvs.revoke_token(TOKEN)
        get_event_loop().run_until_complete(coro)
        coro = self.kvs.is_token_revoked(TOKEN)
        is_revoked = get_event_loop().run_until_complete(coro)
        self.assertTrue(is_revoked)
