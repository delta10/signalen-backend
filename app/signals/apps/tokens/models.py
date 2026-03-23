from django.db import models

# Create your models here.
# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2026 Delta10 B.V.
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db import models
from django.utils.timezone import now
from rest_framework.authtoken.models import Token

User = get_user_model()


class APIKey(models.Model):
    """
    API Key for system users.
    The actual key is only shown once during creation (in admin).
    Only the hash is stored in the database.
    """
    key_hash = models.CharField(max_length=128, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_keys')
    description = models.TextField(
        blank=True,
        null=True,
        help_text='Optionele beschrijving van deze API key, om het doel ervan vast te leggen.'
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'API Key'
        verbose_name_plural = 'API Keys'
        ordering = ['-created_at']

    def __str__(self):
        return f'API Key for {self.user.username}'

    @classmethod
    def hash_key(cls, key: str) -> str:
        """Hash the API key using Django's password hasher."""
        return make_password(key)
    
    @classmethod
    def generate_key(cls) -> str:
        """Generate a new API key using DRF's Token generator."""
        return Token.generate_key()

    def is_expired(self) -> bool:
        """Check if the API key has expired."""
        if self.expires_at is None:
            return False
        return now() >= self.expires_at