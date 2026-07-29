# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2026 Delta10 B.V.
import ipaddress

from django.core.exceptions import ValidationError
from django.contrib.gis.db import models


def validate_ip_network(value):
    try:
        ipaddress.ip_network(value, strict=False)
    except ValueError as e:
        raise ValidationError('Enter a valid IP address or CIDR range.') from e


class ReporterLog(models.Model):
    created_at = models.DateTimeField(editable=False, auto_now_add=True)

    signal = models.OneToOneField(
        'signals.Signal',
        related_name='reporter_log',
        on_delete=models.CASCADE,
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ('created_at',)


class Blocklist(models.Model):
    created_at = models.DateTimeField(editable=False, auto_now_add=True)

    ip_network = models.CharField(
        max_length=64,
        unique=True,
        validators=[validate_ip_network],
        help_text='Use an IP address or CIDR range, for example 203.0.113.10 or 203.0.113.0/24.',
    )
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('ip_network',)

    def clean(self):
        super().clean()
        self.ip_network = str(ipaddress.ip_network(self.ip_network, strict=False))

    def __str__(self):
        return self.ip_network
