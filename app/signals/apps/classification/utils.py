# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2020 - 2023 Gemeente Amsterdam
from typing import Union

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage, Storage
from storages.backends.azure_storage import AzureStorage
from storages.backends.s3 import S3Storage


def _get_storage_backend() -> Storage:
    """
    Returns one of the following storages:
        - AzureStorage, the "using" must be present in the AZURE_CONTAINERS setting.
        - S3Storage, location is set to 'datawarehouse'.
        - FileSystemStorage, location is set to the settings.DWH_MEDIA_ROOT.

    :param using:
    :returns: AzureStorage, S3Storage, or FileSystemStorage
    """

    if settings.AZURE_STORAGE_ENABLED:
        if not hasattr(settings, 'AZURE_CONTAINERS'):
            raise ImproperlyConfigured('AZURE_CONTAINERS settings must be set!')
        if 'datawarehouse' not in settings.AZURE_CONTAINERS.keys():
            raise ImproperlyConfigured(f'{'datawarehouse'} not present in the AZURE_CONTAINERS settings')

        return AzureStorage(**settings.AZURE_CONTAINERS.get('datawarehouse', {}))

    if settings.S3_STORAGE_ENABLED:
        return S3Storage(location='datawarehouse')

    return FileSystemStorage(location=settings.DWH_MEDIA_ROOT)
