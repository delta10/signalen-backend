# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2026 Delta10 B.V.
from datetime import timedelta

from django.contrib.auth.hashers import check_password
from django.test import TestCase
from django.utils.timezone import now
from freezegun import freeze_time

from signals.apps.tokens.models import APIKey


class TestAPIKeyModel(TestCase):
    """Tests for the APIKey model."""

    def test_hash_key_generates_django_password_hash(self):
        """Test that hash_key generates a Django password hash."""
        key = 'test-api-key-12345'
        hashed = APIKey.hash_key(key)

        # Django password hashes start with algorithm identifier
        self.assertTrue(hashed.startswith('pbkdf2_sha256$'))
        # Should be able to verify the password
        self.assertTrue(check_password(key, hashed))

    def test_hash_key_is_unique_per_call(self):
        """Test that hashing the same key produces different hashes (due to salt)."""
        key = 'my-secret-key'
        hash1 = APIKey.hash_key(key)
        hash2 = APIKey.hash_key(key)

        # Hashes should be different due to salt
        self.assertNotEqual(hash1, hash2)
        # But both should verify correctly
        self.assertTrue(check_password(key, hash1))
        self.assertTrue(check_password(key, hash2))

    def test_hash_key_is_unique_per_key(self):
        """Test that different keys produce different hashes."""
        key1 = 'key-one'
        key2 = 'key-two'

        hash1 = APIKey.hash_key(key1)
        hash2 = APIKey.hash_key(key2)

        self.assertNotEqual(hash1, hash2)
        # Each hash should only verify its own key
        self.assertTrue(check_password(key1, hash1))
        self.assertTrue(check_password(key2, hash2))
        self.assertFalse(check_password(key1, hash2))
        self.assertFalse(check_password(key2, hash1))

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

    def test_str_representation(self):
        """Test the string representation of APIKey."""
        from signals.apps.users.factories import UserFactory

        user = UserFactory(username='testuser@example.com')
        api_key = APIKey(user=user)

        self.assertEqual(str(api_key), 'API Key for testuser@example.com')