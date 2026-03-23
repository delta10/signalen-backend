# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2026 Delta10 B.V.
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from signals.apps.tokens.models import APIKey


class SignalsTokenAuthentication(TokenAuthentication):
    """
    Custom TokenAuthentication that uses APIKey model.
    Expects header: Authorization: Bearer <key>
    """
    keyword = 'Bearer'

    def authenticate(self, request: Request) -> tuple[User, APIKey] | None:
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != self.keyword.lower().encode():
            raise AuthenticationFailed('No token provided.')

        return super().authenticate(request)  # type: ignore[return-value]

    def authenticate_credentials(self, key: str) -> tuple[User, APIKey]:
        """Authenticate using the provided API key."""
        # Since Django password hashes are unique due to salt, we need to check all API keys
        # This could be optimized in the future by adding an index or other lookup mechanism
        api_keys = APIKey.objects.select_related('user').filter(
            expires_at__isnull=True
        ).union(
            APIKey.objects.select_related('user').filter(
                expires_at__gt=timezone.now()
            )
        )
        
        for api_key in api_keys:
            if check_password(key, api_key.key_hash):                
                if not api_key.user.is_active:
                    raise AuthenticationFailed('User inactive or deleted.')
                
                return api_key.user, api_key
        
        raise AuthenticationFailed('Invalid token.')
