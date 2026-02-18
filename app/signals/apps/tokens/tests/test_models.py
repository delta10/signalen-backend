# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2026 Delta10 B.V.
from datetime import timedelta

from django.test import TestCase
from django.utils.timezone import now
from freezegun import freeze_time

from signals.apps.tokens.models import APIKey


class TestAPIKeyModel(TestCase):
    """Tests for the APIKey model."""

    def test_hash_key_generates_sha256_hash(self):
        """Test that hash_key generates a SHA-256 hash."""
        key = 'test-api-key-12345'
        hashed = APIKey.hash_key(key)

        # SHA-256 produces 64 character hex string
        self.assertEqual(len(hashed), 64)
        self.assertTrue(all(c in '0123456789abcdef' for c in hashed))

    def test_hash_key_is_consistent(self):
        """Test that hashing the same key produces the same hash."""
        key = 'my-secret-key'
        hash1 = APIKey.hash_key(key)
        hash2 = APIKey.hash_key(key)

        self.assertEqual(hash1, hash2)

    def test_hash_key_is_unique_per_key(self):
        """Test that different keys produce different hashes."""
        key1 = 'key-one'
        key2 = 'key-two'

        hash1 = APIKey.hash_key(key1)
        hash2 = APIKey.hash_key(key2)

        self.assertNotEqual(hash1, hash2)

    def test_generate_key_returns_40_char_token(self):
        """Test that generate_key returns a 40 character token (DRF format)."""
        key = APIKey.generate_key()

        self.assertEqual(len(key), 40)
        self.assertTrue(key.isalnum())

    def test_generate_key_returns_unique_tokens(self):
        """Test that generate_key produces unique tokens."""
        key1 = APIKey.generate_key()
        key2 = APIKey.generate_key()

        self.assertNotEqual(key1, key2)

    def test_is_expired_returns_false_when_no_expiration(self):
        """Test that a key with no expiration is never expired."""
        api_key = APIKey(expires_at=None)

        self.assertFalse(api_key.is_expired())

    @freeze_time("2025-01-15 12:00:00")
    def test_is_expired_returns_true_for_past_date(self):
        """Test that a key is expired when expiration is in the past."""
        past_date = now() - timedelta(days=1)
        api_key = APIKey(expires_at=past_date)

        self.assertTrue(api_key.is_expired())

    @freeze_time("2025-01-15 12:00:00")
    def test_is_expired_returns_false_for_future_date(self):
        """Test that a key is not expired when expiration is in the future."""
        future_date = now() + timedelta(days=1)
        api_key = APIKey(expires_at=future_date)

        self.assertFalse(api_key.is_expired())

    @freeze_time("2025-01-15 12:00:00")
    def test_is_expired_returns_true_at_exact_expiration(self):
        """Test that a key is expired at the exact expiration time."""
        current_time = now()
        api_key = APIKey(expires_at=current_time)

        self.assertTrue(api_key.is_expired())

    def test_is_valid_returns_true_for_active_key_no_expiration(self):
        """Test that a key with no expiration is valid."""
        api_key = APIKey(expires_at=None)

        self.assertTrue(api_key.is_valid())

    @freeze_time("2025-01-15 12:00:00")
    def test_is_valid_returns_true_for_future_expiration(self):
        """Test that a key with future expiration is valid."""
        future_date = now() + timedelta(days=1)
        api_key = APIKey(expires_at=future_date)

        self.assertTrue(api_key.is_valid())

    @freeze_time("2025-01-15 12:00:00")
    def test_is_valid_returns_false_for_expired_key(self):
        """Test that an expired key is not valid."""
        past_date = now() - timedelta(days=1)
        api_key = APIKey(expires_at=past_date)

        self.assertFalse(api_key.is_valid())

    def test_str_representation(self):
        """Test the string representation of APIKey."""
        from signals.apps.users.factories import UserFactory

        user = UserFactory(username='testuser@example.com')
        api_key = APIKey(user=user)

        self.assertEqual(str(api_key), 'API Key for testuser@example.com')
