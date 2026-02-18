# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2026 Delta10 B.V.
from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html

from signals.apps.tokens.models import APIKey


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at', 'expires_at', 'is_active_display']
    list_filter = ['created_at', 'expires_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at']
    fields = ['user', 'expires_at', 'created_at']

    def is_active_display(self, obj):
        """Display whether the key is active or expired."""
        if obj.is_expired():
            return format_html('<span style="color: red;">Verlopen</span>')
        return format_html('<span style="color: green;">Actief</span>')
    is_active_display.short_description = 'Status'

    def get_readonly_fields(self, request, obj=None):
        """Make all fields readonly when editing an existing key."""
        if obj:
            return ['user', 'expires_at', 'created_at']
        return ['created_at']

    def save_model(self, request, obj, form, change):
        """Generate a new API key and store only the hash."""
        if not change:
            # Generate the actual key (shown once to user)
            plain_key = APIKey.generate_key()
            obj.key_hash = APIKey.hash_key(plain_key)

            # Store the plain key temporarily to show in success message
            self._plain_key = plain_key

        super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        """Show the plain API key once after creation."""
        if hasattr(self, '_plain_key'):
            plain_key = self._plain_key
            del self._plain_key

            messages.success(
                request,
                format_html(
                    'API Key created successfully! IMPORTANT: Copy this key now. It will not be shown again.<br><br>'
                    '<code style="background: #fff; color: black; padding: 10px; display: inline-block; font-size: 14px; '
                    'border: 1px solid #ddd; border-radius: 4px; user-select: all;">{}</code><br><br>'
                    'Store this key securely. It provides access as user: <strong>{}</strong>',
                    plain_key,
                    obj.user.username
                )
            )

        return super().response_add(request, obj, post_url_continue)
