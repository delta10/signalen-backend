# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2020 - 2021 Vereniging van Nederlandse Gemeenten, Gemeente Amsterdam
from django.http import FileResponse
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.renderers import BaseRenderer
from rest_framework.viewsets import ViewSet

from signals.apps.api.generics.permissions import SIAPermissions, SIAReportPermissions
from signals.apps.reporting.csv.utils import DWH_ZIP_FILENAME
from signals.apps.reporting.utils import _get_storage_backend
from signals.auth.backend import JWTAuthBackend


class PassthroughRenderer(BaseRenderer):
    """
        Return data as-is. View should supply a Response.
    """
    media_type = ''
    format = ''

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class PrivateCsvViewSet(ViewSet):
    """
    Private ViewSet to retrieve generated csv files
    https://stackoverflow.com/a/51936269
    """

    authentication_classes = (JWTAuthBackend, )
    permission_classes = (SIAPermissions & SIAReportPermissions, )

    def list(self, detail=True, renderer_classes=(PassthroughRenderer,)):
        storage = _get_storage_backend(using='datawarehouse')

        if not storage.exists(DWH_ZIP_FILENAME):
            raise NotFound(detail='Latest CSV file not found', code=status.HTTP_404_NOT_FOUND)

        # Open file from storage backend
        file_obj = storage.open(DWH_ZIP_FILENAME, 'rb')

        return FileResponse(
            file_obj,
            as_attachment=True,
            filename=DWH_ZIP_FILENAME
        )
