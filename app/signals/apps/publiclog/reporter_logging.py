# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2026 Delta10 B.V.
import ipaddress

from django.conf import settings
from rest_framework.request import Request

from signals.apps.publiclog.models import Blocklist, ReporterLog
from signals.apps.signals.models import Signal


def get_reporter_ip_address(request: Request) -> str | None:
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return _validate_ip_address(forwarded_for.split(',')[0])

    return _validate_ip_address(request.META.get('REMOTE_ADDR'))


def _validate_ip_address(value: str | None) -> str | None:
    if not value:
        return None

    value = _strip_port(value.strip())

    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def _strip_port(value: str) -> str:
    if value.startswith('['):
        address, separator, _port = value[1:].partition(']')
        if separator:
            return address

    if value.count(':') == 1:
        address, port = value.rsplit(':', 1)
        if port.isdigit():
            return address

    return value


def log_reporter_request(signal: Signal, request: Request) -> ReporterLog | None:
    if not settings.PUBLICLOG_REPORTER_REQUEST_LOGGING_ENABLED:
        return None

    return ReporterLog.objects.create(
        signal=signal,
        ip_address=get_reporter_ip_address(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )


def is_reporter_ip_address_blocked(request: Request) -> bool:
    ip_address = get_reporter_ip_address(request)
    if ip_address is None:
        return False

    address = ipaddress.ip_address(ip_address)
    for blocklist_item in Blocklist.objects.filter(is_active=True):
        try:
            if address in ipaddress.ip_network(blocklist_item.ip_network, strict=False):
                return True
        except ValueError:
            continue

    return False
