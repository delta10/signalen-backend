# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2026 Delta10 B.V.
from datetime import timedelta

from django.test import TestCase
from django.test.client import RequestFactory
from django.utils.timezone import now
from freezegun import freeze_time
from rest_framework.exceptions import AuthenticationFailed

from signals.apps.tokens.factories import APIKeyFactory
from signals.apps.tokens.models import APIKey
from signals.apps.tokens.rest_framework.authentication import SignalsTokenAuthentication
from signals.apps.users.factories import UserFactory


class TestSignalsTokenAuthentication(TestCase):
    """Tests for the SignalsTokenAuthentication class."""

    def setUp(self):
        self.auth = SignalsTokenAuthentication()
        self.factory = RequestFactory()

    def test_authenticate_with_valid_key_returns_user_and_key(self):
        """Test authenticating with a valid API key returns the user and key."""
        user = UserFactory()
        api_key = APIKeyFactory(user=user)
        plain_key = api_key._plain_key

        request = self.factory.get('/test/', HTTP_AUTHORIZATION=f'Token {plain_key}')

        result = self.auth.authenticate(request)

        self.assertIsNotNone(result)
        authenticated_user, authenticated_key = result
        self.assertEqual(authenticated_user, user)
        self.assertEqual(authenticated_key, api_key)

    def test_authenticate_with_invalid_key_raises_error(self):
        """Test authenticating with an invalid key raises AuthenticationFailed."""
        request = self.factory.get('/test/', HTTP_AUTHORIZATION='Token invalid-key-12345')

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    @freeze_time("2025-01-15 12:00:00")
    def test_authenticate_with_expired_key_raises_error(self):
        """Test authenticating with an expired key raises AuthenticationFailed."""
        user = UserFactory()
        past_date = now() - timedelta(days=1)
        api_key = APIKeyFactory(user=user, expires_at=past_date)
        plain_key = api_key._plain_key

        request = self.factory.get('/test/', HTTP_AUTHORIZATION=f'Token {plain_key}')

        with self.assertRaises(AuthenticationFailed) as cm:
            self.auth.authenticate(request)

        # Check for expiration-related error message
        error_msg = str(cm.exception).lower()
        self.assertTrue('expired' in error_msg or 'verlopen' in error_msg)

    def test_authenticate_with_inactive_user_raises_error(self):
        """Test authenticating with an inactive user raises AuthenticationFailed."""
        user = UserFactory(is_active=False)
        api_key = APIKeyFactory(user=user)
        plain_key = api_key._plain_key

        request = self.factory.get('/test/', HTTP_AUTHORIZATION=f'Token {plain_key}')

        with self.assertRaises(AuthenticationFailed) as cm:
            self.auth.authenticate(request)

        # Check for user inactive error message
        error_msg = str(cm.exception).lower()
        self.assertTrue(
            'inactive' in error_msg or
            'deleted' in error_msg or
            'inactief' in error_msg or
            'verwijderd' in error_msg
        )

    def test_authenticate_with_no_header_raises_error(self):
        """Test that no authentication header raises AuthenticationFailed."""
        request = self.factory.get('/test/')

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_authenticate_with_wrong_keyword_raises_error(self):
        """Test that wrong keyword (e.g., Bearer) raises AuthenticationFailed."""
        request = self.factory.get('/test/', HTTP_AUTHORIZATION='Bearer some-token')

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_authenticate_with_empty_token_raises_error(self):
        """Test that empty token raises AuthenticationFailed."""
        request = self.factory.get('/test/', HTTP_AUTHORIZATION='Token')

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_authenticate_with_token_containing_spaces_raises_error(self):
        """Test that token with spaces raises AuthenticationFailed."""
        request = self.factory.get('/test/', HTTP_AUTHORIZATION='Token key with spaces')

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_authenticate_with_lowercase_keyword(self):
        """Test that lowercase 'token' keyword works."""
        user = UserFactory()
        api_key = APIKeyFactory(user=user)
        plain_key = api_key._plain_key

        request = self.factory.get('/test/', HTTP_AUTHORIZATION=f'token {plain_key}')

        result = self.auth.authenticate(request)

        self.assertIsNotNone(result)
        authenticated_user, _ = result
        self.assertEqual(authenticated_user, user)

    def test_authenticate_credentials_with_valid_key(self):
        """Test authenticate_credentials directly with valid key."""
        user = UserFactory()
        api_key = APIKeyFactory(user=user)
        plain_key = api_key._plain_key

        result = self.auth.authenticate_credentials(plain_key)

        self.assertIsNotNone(result)
        authenticated_user, authenticated_key = result
        self.assertEqual(authenticated_user, user)
        self.assertEqual(authenticated_key, api_key)

    def test_authenticate_credentials_with_invalid_key(self):
        """Test authenticate_credentials with invalid key raises error."""
        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate_credentials('non-existent-key')

    @freeze_time("2025-01-15 12:00:00")
    def test_authenticate_credentials_with_expired_key(self):
        """Test authenticate_credentials with expired key raises error."""
        user = UserFactory()
        past_date = now() - timedelta(days=1)
        api_key = APIKeyFactory(user=user, expires_at=past_date)
        plain_key = api_key._plain_key

        with self.assertRaises(AuthenticationFailed) as cm:
            self.auth.authenticate_credentials(plain_key)

        # Check for expiration-related error message
        error_msg = str(cm.exception).lower()
        self.assertTrue('expired' in error_msg or 'verlopen' in error_msg)

    def test_key_hash_storage(self):
        """Test that keys are properly hashed and stored."""
        user = UserFactory()
        api_key = APIKeyFactory(user=user)
        plain_key = api_key._plain_key

        # Verify the stored hash is SHA-256 of the key
        expected_hash = APIKey.hash_key(plain_key)
        self.assertEqual(api_key.key_hash, expected_hash)

        # Verify we can authenticate with the stored hash
        request = self.factory.get('/test/', HTTP_AUTHORIZATION=f'Token {plain_key}')
        result = self.auth.authenticate(request)
        self.assertIsNotNone(result)

    def test_multiple_keys_for_same_user(self):
        """Test that a user can have multiple API keys."""
        user = UserFactory()
        api_key1 = APIKeyFactory(user=user)
        api_key2 = APIKeyFactory(user=user)

        # Authenticate with first key
        request1 = self.factory.get('/test/', HTTP_AUTHORIZATION=f'Token {api_key1._plain_key}')
        result1 = self.auth.authenticate(request1)
        self.assertEqual(result1[0], user)

        # Authenticate with second key
        request2 = self.factory.get('/test/', HTTP_AUTHORIZATION=f'Token {api_key2._plain_key}')
        result2 = self.auth.authenticate(request2)
        self.assertEqual(result2[0], user)
