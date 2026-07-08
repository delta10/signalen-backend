# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2026 Delta10 B.V.
from django.test import RequestFactory, SimpleTestCase

from signals.apps.publiclog.reporter_logging import get_reporter_ip_address


class TestGetReporterIPAddress(SimpleTestCase):
    def setUp(self):
        self.request_factory = RequestFactory()

    def test_strips_port_from_remote_addr_ipv4(self):
        request = self.request_factory.post(
            '/',
            REMOTE_ADDR='203.0.113.10:443',
        )

        self.assertEqual('203.0.113.10', get_reporter_ip_address(request))

    def test_strips_port_from_forwarded_for_ipv4(self):
        request = self.request_factory.post(
            '/',
            HTTP_X_FORWARDED_FOR='203.0.113.10:443, 198.51.100.20',
        )

        self.assertEqual('203.0.113.10', get_reporter_ip_address(request))

    def test_strips_port_from_bracketed_ipv6(self):
        request = self.request_factory.post(
            '/',
            REMOTE_ADDR='[2001:db8::1]:443',
        )

        self.assertEqual('2001:db8::1', get_reporter_ip_address(request))

    def test_keeps_plain_ipv6(self):
        request = self.request_factory.post(
            '/',
            REMOTE_ADDR='2001:db8::1',
        )

        self.assertEqual('2001:db8::1', get_reporter_ip_address(request))

