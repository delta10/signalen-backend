# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2025 Delta10 B.V.

from django.dispatch import receiver

from signals.apps.signals.managers import create_initial

from . import tasks


@receiver(create_initial, dispatch_uid='get_llm_prediction')
def create_initial_handler(sender, signal_obj, *args, **kwargs):
    tasks.predict_signal.delay(signal_id=signal_obj.pk)
