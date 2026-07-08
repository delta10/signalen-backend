# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2026 Delta10 B.V.
import json
import os
from unittest.mock import patch

from signals.apps.api.validation.address.base import AddressValidationUnavailableException
from signals.apps.publiclog.models import Blocklist, ReporterLog
from signals.apps.signals.factories import CategoryFactory, SignalFactory
from signals.apps.signals.models import Signal
from signals.test.utils import SignalsBaseApiTestCase


THIS_DIR = os.path.dirname(__file__)
API_TESTS_DIR = os.path.join(THIS_DIR, '..', '..', 'api', 'tests')


class TestPublicSignalReporterLogging(SignalsBaseApiTestCase):
    list_endpoint = '/signals/v1/public/signals/'
    detail_endpoint = list_endpoint + '{uuid}'
    fixture_file = os.path.join(API_TESTS_DIR, 'request_data', 'create_initial_public.json')

    def setUp(self):
        with open(self.fixture_file, 'r') as f:
            self.create_initial_data = json.load(f)

        self.subcategory = CategoryFactory.create()
        self.create_initial_data['category'] = {
            'sub_category': '/signals/v1/public/terms/categories/{}/sub_categories/{}'.format(
                self.subcategory.parent.slug,
                self.subcategory.slug,
            )
        }

    @patch('signals.apps.api.validation.address.base.BaseAddressValidation.validate_address',
           side_effect=AddressValidationUnavailableException)
    def test_create_logs_reporter_request_metadata(self, validate_address):
        response = self.client.post(
            self.list_endpoint,
            self.create_initial_data,
            format='json',
            HTTP_X_FORWARDED_FOR='203.0.113.10, 198.51.100.20',
            HTTP_USER_AGENT='Signals test browser',
        )

        self.assertEqual(201, response.status_code)
        signal = Signal.objects.get()
        reporter_log = ReporterLog.objects.get(signal=signal)
        self.assertEqual('203.0.113.10', reporter_log.ip_address)
        self.assertEqual('Signals test browser', reporter_log.user_agent)

    @patch('signals.apps.api.validation.address.base.BaseAddressValidation.validate_address',
           side_effect=AddressValidationUnavailableException)
    def test_create_logs_remote_addr_when_forwarded_for_missing(self, validate_address):
        response = self.client.post(
            self.list_endpoint,
            self.create_initial_data,
            format='json',
            REMOTE_ADDR='198.51.100.30',
            HTTP_USER_AGENT='Signals test browser',
        )

        self.assertEqual(201, response.status_code)
        reporter_log = ReporterLog.objects.get(signal=Signal.objects.get())
        self.assertEqual('198.51.100.30', reporter_log.ip_address)
        self.assertEqual('Signals test browser', reporter_log.user_agent)

    def test_get_by_uuid_does_not_log_reporter_request_metadata(self):
        signal = SignalFactory.create()

        response = self.client.get(self.detail_endpoint.format(uuid=signal.uuid), format='json')

        self.assertEqual(200, response.status_code)
        self.assertEqual(0, ReporterLog.objects.count())

    @patch('signals.apps.api.validation.address.base.BaseAddressValidation.validate_address',
           side_effect=AddressValidationUnavailableException)
    def test_create_is_blocked_for_blocklisted_ip_address(self, validate_address):
        Blocklist.objects.create(ip_network='203.0.113.10')

        response = self.client.post(
            self.list_endpoint,
            self.create_initial_data,
            format='json',
            REMOTE_ADDR='203.0.113.10',
        )

        self.assertEqual(403, response.status_code)
        self.assertEqual(0, Signal.objects.count())
        self.assertEqual(0, ReporterLog.objects.count())

    @patch('signals.apps.api.validation.address.base.BaseAddressValidation.validate_address',
           side_effect=AddressValidationUnavailableException)
    def test_create_is_blocked_for_blocklisted_ip_range(self, validate_address):
        Blocklist.objects.create(ip_network='203.0.113.0/24')

        response = self.client.post(
            self.list_endpoint,
            self.create_initial_data,
            format='json',
            REMOTE_ADDR='203.0.113.10',
        )

        self.assertEqual(403, response.status_code)
        self.assertEqual(0, Signal.objects.count())
        self.assertEqual(0, ReporterLog.objects.count())

    @patch('signals.apps.api.validation.address.base.BaseAddressValidation.validate_address',
           side_effect=AddressValidationUnavailableException)
    def test_create_is_not_blocked_for_inactive_blocklist_item(self, validate_address):
        Blocklist.objects.create(ip_network='203.0.113.10', is_active=False)

        response = self.client.post(
            self.list_endpoint,
            self.create_initial_data,
            format='json',
            REMOTE_ADDR='203.0.113.10',
        )

        self.assertEqual(201, response.status_code)
        self.assertEqual(1, Signal.objects.count())
        self.assertEqual(1, ReporterLog.objects.count())
