# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2026 Delta10 B.V.
from django.utils.timezone import now
from rest_framework.authentication import TokenAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from signals.apps.tokens.models import APIKey


class SignalsTokenAuthentication(TokenAuthentication):
    """
    Custom TokenAuthentication that uses APIKey model.
    Expects header: Authorization: Token <key>
    """
    model = APIKey
    keyword = 'Token'

    def authenticate(self, request):
        auth = get_authorization_header(request).split()
        
        if not auth or auth[0].lower() != self.keyword.lower().encode():
            raise AuthenticationFailed('No token provided.')

        return super().authenticate(request)

    def authenticate_credentials(self, key):
        """Authenticate using the provided API key."""
        model = self.get_model()
        key_hash = model.hash_key(key)

        try:
            api_key = model.objects.select_related('user').get(key_hash=key_hash)
        except model.DoesNotExist:
            raise AuthenticationFailed('Invalid token.')
            
        if api_key.is_expired():
            raise AuthenticationFailed('Token has expired.')

        if not api_key.user.is_active:
            raise AuthenticationFailed('User inactive or deleted.')

        return api_key.user, api_key