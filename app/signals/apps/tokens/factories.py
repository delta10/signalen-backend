# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2026 Delta10 B.V.
from factory import SubFactory, post_generation
from factory.django import DjangoModelFactory

from signals.apps.tokens.models import APIKey


class APIKeyFactory(DjangoModelFactory):
    """Factory for creating APIKey instances for testing."""

    class Meta:
        model = APIKey
        skip_postgeneration_save = True

    user: SubFactory = SubFactory('signals.apps.users.factories.UserFactory')
    expires_at = None

    @post_generation
    def set_key_and_hash(obj, create, extracted, **kwargs):
        """Generate and store a unique key hash when creating an APIKey."""
        if create:
            plain_key = APIKey.generate_key()
            obj.key_hash = APIKey.hash_key(plain_key)
            obj._plain_key = plain_key
            obj.save(update_fields=['key_hash'])
