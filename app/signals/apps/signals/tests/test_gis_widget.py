from django.test import TestCase
from django.urls import reverse

from signals.apps.users.factories import SuperUserFactory


class AreaAdminWidgetTest(TestCase):
    def setUp(self):
        self.user = SuperUserFactory.create()
        self.client.force_login(self.user)

    def test_widget_appears_in_admin(self):
        url = reverse("admin:signals_area_add")
        response = self.client.get(url)

        self.assertContains(response, '<div id="id_geometry_map" class="dj_map" data-width="600" data-height="400" style="width: 600px; height: 400px;">')
        self.assertContains(response, '<textarea id="id_geometry" class="vSerializedField required" cols="150" rows="10" name="geometry">')
        self.assertTemplateUsed(response, "gis/custom-openlayers-osm.html")
        self.assertTemplateUsed(response, "gis/custom-openlayers.html")