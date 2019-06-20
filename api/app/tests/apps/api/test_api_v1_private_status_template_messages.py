from django.contrib.auth.models import Permission
from rest_framework.reverse import reverse

from tests.apps.signals.factories import CategoryFactory, StatusMessageTemplateFactory
from tests.test import SIAReadWriteUserMixin, SignalsBaseApiTestCase


class TestPrivateCategoryStatusMessages(SIAReadWriteUserMixin, SignalsBaseApiTestCase):
    link_test_cat_sub = None
    link_cat_sub_templates = None

    def setUp(self):
        statusmessagetemplate_write_permission = Permission.objects.get(
            codename='sia_statusmessagetemplate_write'
        )
        self.sia_read_write_user.user_permissions.add(statusmessagetemplate_write_permission)
        self.sia_read_write_user.save()
        self.client.force_authenticate(user=self.sia_read_write_user)

        self.subcategory = CategoryFactory.create()
        self.link_test_cat_sub = reverse(
            'v1:category-detail', kwargs={
                'slug': self.subcategory.parent.slug,
                'sub_slug': self.subcategory.slug,
            }
        )
        self.link_cat_sub_templates = reverse(
            'v1:private-status-message-templates-child', kwargs={
                'slug': self.subcategory.parent.slug,
                'sub_slug': self.subcategory.slug,
            }
        )

    def test_get_no_status_message_templates(self):
        response = self.client.get(self.link_cat_sub_templates)

        self.assertEqual(200, response.status_code)
        self.assertEqual(0, len(response.json()))

    def test_get_status_message_templates(self):
        templates = StatusMessageTemplateFactory.create_batch(
            5,
            category=self.subcategory,
            state='m'
        )

        response = self.client.get(self.link_cat_sub_templates)
        self.assertEqual(200, response.status_code)

        response_json = response.json()
        self.assertEqual(1, len(response_json))
        self.assertEqual(len(templates), len(response_json[0]['templates']))

    def test_add_status_messages(self):
        response = self.client.get(self.link_cat_sub_templates)
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, len(response.json()))

        data = [
            {
                'state': 'm',
                'templates': [
                    {
                        'title': 'M Title #1',
                        'text': 'M Text #1',
                    },
                    {
                        'title': 'M Title #2',
                        'text': 'M Text #2',
                    },
                ],
            },
            {
                'state': 'o',
                'templates': [
                    {
                        'title': 'O Title #1',
                        'text': 'O Text #1',
                    },
                ],
            },
        ]
        response = self.client.post(self.link_cat_sub_templates, data, format='json')
        self.assertEqual(200, response.status_code)

        response_data = response.json()
        self.assertEqual(2, len(response_data))

        self.assertEqual('m', response_data[0]['state'])
        self.assertEqual(2, len(response_data[0]['templates']))
        self.assertEqual('M Title #1', response_data[0]['templates'][0]['title'])
        self.assertEqual('M Text #1', response_data[0]['templates'][0]['text'])
        self.assertEqual('M Title #2', response_data[0]['templates'][1]['title'])
        self.assertEqual('M Text #2', response_data[0]['templates'][1]['text'])

        self.assertEqual('o', response_data[1]['state'])
        self.assertEqual(1, len(response_data[1]['templates']))
        self.assertEqual('O Title #1', response_data[1]['templates'][0]['title'])
        self.assertEqual('O Text #1', response_data[1]['templates'][0]['text'])

    def test_delete_status_messages(self):
        StatusMessageTemplateFactory.create(order=0, category=self.subcategory, state='o')
        StatusMessageTemplateFactory.create(order=0, category=self.subcategory, state='m')
        StatusMessageTemplateFactory.create(order=1, category=self.subcategory, state='m')

        response = self.client.get(self.link_cat_sub_templates)
        self.assertEqual(200, response.status_code)

        response_data = response.json()
        self.assertEqual(2, len(response_data))
        self.assertEqual(2, len(response_data[0]['templates']))
        self.assertEqual(1, len(response_data[1]['templates']))

        data = [
            {
                'state': 'm',
                'templates': [],
            },
        ]

        response = self.client.post(self.link_cat_sub_templates, data, format='json')
        self.assertEqual(200, response.status_code)

        response_data = response.json()
        self.assertEqual(1, len(response_data))
        self.assertEqual('o', response_data[0]['state'])
        self.assertEqual(1, len(response_data[0]['templates']))
