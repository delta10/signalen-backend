import json
import os
import subprocess
import sys
from unittest import TestCase
from urllib.parse import parse_qs, urlsplit


class ProtectedMediaSettingsTests(TestCase):
	def test_default_storage_backend_and_urls(self):
		for enabled in (False, True):
			with self.subTest(protected_media=enabled):
				environment = {
					**os.environ,
					'DJANGO_SETTINGS_MODULE': 'signals.settings',
					'SECRET_KEY': 'protected-media-regression',
					'PROTECTED_FILE_SYSTEM_STORAGE': str(enabled),
					'S3_STORAGE_ENABLED': 'False',
					'AZURE_STORAGE_ENABLED': 'False',
					'AZURE_APPLICATION_INSIGHTS_ENABLED': 'False',
				}
				output = subprocess.check_output(
					[sys.executable, '-c', (
						'import json; '
						'from django.core.files.storage import default_storage; '
						'print(json.dumps({'
						'"backend": default_storage.__class__.__name__, '
						'"url": default_storage.url("example.txt")}))'
					)],
					env=environment,
					text=True,
				)
				result = json.loads(output)
				self.assertEqual(
					result['backend'],
					'ProtectedFileSystemStorage' if enabled else 'FileSystemStorage',
				)
				query = parse_qs(urlsplit(result['url']).query)
				self.assertEqual(set(query), {'t', 's'} if enabled else set())
